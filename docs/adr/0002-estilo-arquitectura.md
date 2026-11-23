# ADR-0002: Empezar CaféDMC como monolito modular

- **Estado:** Aceptado
- **Fecha:** 2026-11-16
- **Relacionado:** [ADR-0001](0001-stack.md) (stack), [arquitectura.md](../arquitectura.md) (C4 nivel 2)

## Contexto
- El sistema tiene dos contextos: **Catálogo** (productos, precios y stock) y **Pedidos**
  (pedido, ítem, cliente y estado del pedido; ver el glosario de `AGENTS.md`).
- Pedidos depende de Catálogo: para crear un pedido hay que validar productos, precios y stock.
  Al pagar o anular un pedido, el stock debe quedar consistente con el pedido.
- ADR-0001 fija SQLite, que admite una sola escritura a la vez, y una ejecución local
  sin Docker en la laptop de cada alumno.
- El equipo es de **una persona** y la infraestructura es básica: una laptop, sin Docker ni
  orquestador. El dominio es chico. No hay requisitos de escalar ni desplegar cada contexto
  por separado.
- Los agentes de IA deben poder entender el sistema, probarlo con `poetry run pytest -q`
  y cambiarlo sin romper otro contexto.

## Decisión
CaféDMC empieza como un **monolito modular**: un solo proceso FastAPI (la API) y, aparte,
la pantalla Streamlit como cliente HTTP. Dentro de la API hay un módulo por contexto.

- Estructura: `app/catalogo/` y `app/pedidos/`. Cada módulo tiene su router, su lógica de
  negocio y su acceso a datos.
- Cada tabla de SQLite tiene un solo módulo dueño. Solo ese módulo hace SQL sobre ella.
- Un módulo usa otro solo a través de las funciones públicas de ese módulo (su "API interna").
  No importa su acceso a datos ni lee sus tablas. Ejemplo: Pedidos pide a Catálogo que
  reserve o descuente stock.
- Hay una sola base SQLite. Un pedido y su efecto en el stock se guardan en la misma transacción.
- La pantalla Streamlit no importa código de `app/` de la API; solo la llama por HTTP.

## Alternativas consideradas
| Alternativa | A favor | En contra | Resultado |
|---|---|---|---|
| Monolito modular (un proceso, módulos por contexto) | Un solo `poetry run` para levantar la API; transacciones locales entre pedido y stock; pruebas simples; los límites entre contextos quedan explícitos | Los límites se respetan por disciplina y revisión, no los impone el proceso; todo se despliega junto | ✅ Elegida |
| Microservicios (un proceso por contexto) | Despliegue y escalado independientes; aislamiento fuerte | Varios procesos y puertos en cada laptop; llamadas HTTP entre servicios; consistencia pedido–stock sin transacción común (sagas o compensaciones); con una sola SQLite compartida se pierde el aislamiento y la base es el cuello de botella; más difícil de probar para personas y agentes | Descartada por ahora |
| Monolito por capas sin módulos (`routers/`, `services/`, `repos/` globales) | Lo más rápido para empezar | Los contextos se mezclan; cualquier código toca cualquier tabla; más caro de separar después | Descartada |

## Consecuencias
**(+)**
- Para ejecutar la API basta un proceso y una base, en línea con ADR-0001.
- Las reglas entre contextos (stock al crear, pagar o anular un pedido) se resuelven con una
  transacción local.
- Un agente puede trabajar dentro de un módulo sabiendo qué puede tocar y qué no.
- Si un contexto necesita separarse más adelante, su límite y su API interna ya existen.

**(−)**
- Nada impide técnicamente que un módulo importe el acceso a datos de otro.
  Mitigación: dejar la regla en `AGENTS.md` y revisarla en code review. Más adelante se puede
  agregar una prueba o un linter de imports.
- Un fallo o una carga alta en un contexto afecta a todo el proceso.

**Seguimiento**
- ~~Agregar a `AGENTS.md` la regla de dependencias entre módulos.~~ Hecho (2026-11-22).
- Reflejar los módulos en el diagrama C4 de componentes (nivel 3) cuando exista código.
- Revisar esta decisión si aparece alguna de estas necesidades: desplegar o escalar un contexto
  por separado, equipos distintos por contexto, o pasar a PostgreSQL en producción (ver ADR-0001).

**Camino de evolución**
La separación en servicios está prevista para cuando el proyecto crezca, y se hará de a un
módulo a la vez, solo cuando una de las condiciones anteriores lo justifique:
1. El módulo ya respeta sus límites: es dueño de sus tablas y otros lo usan solo por su API interna.
2. Su API interna se expone por HTTP, y los demás módulos pasan a llamarlo por ahí.
3. Sus tablas se mueven a una base propia. La consistencia con los demás módulos se maneja
   con eventos o compensaciones.
4. El módulo se despliega como proceso propio. Cada separación se registra en un ADR nuevo
   que reemplaza a este en lo que corresponda.
