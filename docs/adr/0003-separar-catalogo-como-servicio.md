# ADR-0003: Separar el catálogo como servicio independiente

- **Estado:** Aceptado
- **Fecha:** 2026-11-22
- **Reemplaza en parte a:** [ADR-0002](0002-estilo-arquitectura.md): el catálogo deja de ser un
  módulo dentro del proceso de la API. Pedidos y clientes siguen siendo un monolito modular.
- **Relacionado:** [ADR-0001](0001-stack.md) (stack), [arquitectura.md](../arquitectura.md)

## Contexto
- ADR-0002 eligió un monolito modular y dejó un **camino de evolución**: separar un módulo a la
  vez, exponiendo primero su API interna por HTTP (paso 2) y moviendo después sus tablas a una
  base propia (paso 3).
- El 2026-11-22 se decidió separar el **catálogo** (productos, categorías, precio y stock) para
  ejercitar ese camino. No responde a una de las condiciones de revisión de ADR-0002 (escalar o
  desplegar por separado, otro equipo, PostgreSQL): es una decisión de aprendizaje del curso.
- Antes del cambio, `POST /pedidos` leía `productos` y descontaba stock con
  `UPDATE productos …` en la misma transacción que creaba el pedido.
- SQLite sigue siendo la única base (ADR-0001), y se ejecuta en la laptop, sin Docker.

## Decisión
El catálogo corre como **servicio propio**, y pedidos lo usa **solo por HTTP**.

- **Catálogo**, puerto 8001: `poetry run uvicorn app.catalogo_main:app --port 8001`. Expone
  `GET /productos`, `GET /productos/{id}`, `POST /productos/{id}/descontar` y
  `POST /productos/{id}/devolver`. Es el único que hace SQL sobre `productos` y `categorias`.
  - `descontar` es atómico: `UPDATE … SET stock = stock - ? WHERE id = ? AND activo = 1 AND stock >= ?`.
    Responde 409 si no alcanza, y el stock nunca queda negativo.
- **API de pedidos y clientes**, puerto 8000: `poetry run uvicorn app.main:app --port 8000`. Ya
  no sirve `/productos`. Llama al catálogo con `app/catalogo_cliente.py`, que toma la URL de
  `CAFE_CATALOGO_URL` (por defecto `http://127.0.0.1:8001`).
- **Crear un pedido:**
  1. Lee precio y stock de cada producto con `GET /productos/{id}`. Esta revisión es un aviso
     temprano; la que vale es la de `descontar`.
  2. Descuenta línea por línea con `POST /productos/{id}/descontar`.
  3. Guarda el pedido y sus líneas en una transacción local.
  4. **Compensación:** si falla un descuento o el guardado, devuelve lo ya descontado con
     `POST /productos/{id}/devolver` y no crea el pedido.
- **Errores del catálogo:** si no responde o responde 5xx, `POST /pedidos` responde **503**
  `"El catálogo no está disponible"`. Los 404 y 409 del catálogo se traducen a los mismos
  códigos y mensajes de antes.
- **Pantalla Streamlit:** lee los productos de `CAFE_CATALOGO_API` (8001) y los pedidos y
  clientes de `CAFE_API` (8000).
- **Fuera de alcance:** la base sigue siendo **una sola SQLite** compartida por los dos
  procesos (no se hizo el paso 3), y `detalle_pedido.producto_id` sigue con clave foránea a
  `productos`. Anular un pedido sigue sin devolver stock.

## Alternativas consideradas
| Alternativa | A favor | En contra | Resultado |
|---|---|---|---|
| Catálogo como servicio, lectura y descuento por HTTP con compensación | Pedidos deja de tocar las tablas del catálogo; el descuento atómico corrige el riesgo de stock negativo y el 500 por producto repetido | Dos procesos y dos puertos; sin transacción común entre pedido y stock; nuevo modo de falla (catálogo caído); más latencia | ✅ Elegida |
| Seguir con el monolito modular (ADR-0002) | Una transacción local entre pedido y stock; un solo proceso | No ejercita la separación pedida | Descartada |
| Solo lectura por HTTP, y `UPDATE productos` directo desde pedidos | Más simple: mantiene la transacción del pedido con el stock | Pedidos sigue escribiendo una tabla que no es suya; la separación es aparente | Descartada |
| Base propia para el catálogo, con eventos (paso 3 de ADR-0002) | Aislamiento real de datos | Requiere quitar la clave foránea de `detalle_pedido`, sincronizar datos y manejar eventos; demasiado para el alcance actual | Pospuesta |
| Mantener `/productos` también en el puerto 8000 | No rompe la pantalla ni a los clientes actuales | El mismo código corre en dos procesos; no queda claro quién es dueño del catálogo | Descartada |

## Consecuencias
**(+)**
- El límite del catálogo lo impone el proceso, no solo la disciplina. Una prueba
  (`test_pedidos_no_hace_sql_sobre_tablas_del_catalogo`) verifica que `app/pedidos.py` no
  haga SQL sobre `productos` ni `categorias`.
- El stock ya no puede quedar negativo, y un producto repetido en un pedido da 409 en vez de 500.
- El catálogo se puede reiniciar o cambiar sin tocar la API de pedidos.

**(−)**
- **Sin transacción común.** Si la API de pedidos se cae entre el descuento y el guardado, o si
  la compensación falla, el stock queda descontado sin pedido. La falla de compensación queda
  registrada en el log, y se corrige a mano.
- **Ventana de inconsistencia.** Mientras se crea un pedido, otro puede ver el stock ya
  descontado de un pedido que al final no se guarda.
- **Catálogo caído → no se pueden crear pedidos** (503). La pantalla tampoco muestra productos.
- **`descontar` y `devolver` no tienen autenticación:** cualquiera que llegue al puerto 8001
  puede cambiar el stock.
- Hay que levantar dos procesos para usar el sistema, y las pruebas necesitan reemplazar el
  cliente HTTP (`app.dependency_overrides[get_catalogo]`).
- Una sola SQLite para dos procesos: el aislamiento de datos es solo por convención, y la base
  sigue siendo un punto común de falla.

**Seguimiento**
- Actualizar los diagramas C4 de `docs/arquitectura.md` (niveles 2 y 3) con el catálogo como
  contenedor propio.
- Hacer idempotentes `descontar` y `devolver` (por ejemplo, con una clave por pedido), para que
  un reintento no descuente dos veces.
- Decidir si anular un pedido devuelve stock, ahora por `POST /productos/{id}/devolver`.
- Revisar el paso 3, base propia para el catálogo, si se pasa a PostgreSQL (ADR-0001).
