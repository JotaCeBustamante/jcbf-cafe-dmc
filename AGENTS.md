# AGENTS.md — CaféDMC

## 1. Qué es el sistema
CaféDMC es el sistema de pedidos de una cafetería: dos servicios FastAPI (pedidos y clientes, y
catálogo), pantalla en Streamlit y base SQLite.
El proyecto se gestiona con Poetry en modo sin paquete (`package-mode = false`).

## 2. Comandos (siempre con Poetry)
- Instalar dependencias: `poetry install`
- Pruebas: `poetry run pytest -q`
- Estilo: `poetry run ruff check .`
- Activar los hooks de pre-commit (una vez por clon): `poetry run pre-commit install`
- Correr los hooks a mano sobre todo el repo: `poetry run pre-commit run --all-files`

## 3. Levantar el sistema
Desde la raíz del repo, en este orden. Los pasos 2, 3 y 4 quedan corriendo: cada uno en su
propia terminal.

1. **Crear la base** `data/cafe.db` con datos de prueba (una vez; si ya existe, no la vuelve a
   llenar y solo aplica lo nuevo del esquema):
   `poetry run python scripts/crear_db.py`
   Para borrarla y empezar de cero: `poetry run python scripts/crear_db.py --reset`
2. **Catálogo**, puerto 8001:
   `poetry run uvicorn app.catalogo_main:app --port 8001 --reload`
3. **API de pedidos y clientes**, puerto 8000 (necesita el catálogo para crear pedidos):
   `poetry run uvicorn app.main:app --port 8000 --reload`
4. **Pantalla Streamlit** (necesita los dos servicios):
   `poetry run streamlit run ui/streamlit_app.py`

Comprobar:
- `http://localhost:8001/salud` y `http://localhost:8000/salud` responden `{"estado": "ok"}`.
- Swagger: `http://localhost:8001/docs` (catálogo) y `http://localhost:8000/docs` (pedidos y clientes).
- Pantalla: `http://localhost:8501`.

Variables opcionales: `CAFE_DB` (ruta de la base), `CAFE_CATALOGO_URL` (catálogo que usa la API
de pedidos), `CAFE_API` y `CAFE_CATALOGO_API` (servicios que usa la pantalla).

## 4. Arquitectura
- `app/` — código de los dos servicios FastAPI.
- `ui/` — pantalla Streamlit.
- `tests/` — pruebas con pytest.
- `scripts/` — scripts de apoyo (por ejemplo, inicializar la base).
- `db/` — esquema y migraciones SQL de SQLite.
- `docs/adr/` — decisiones de arquitectura (ADR).

Monolito modular ([ADR-0002](docs/adr/0002-estilo-arquitectura.md)): un módulo por contexto,
`app/catalogo/` y `app/pedidos/`, cada uno con `router.py`, `schemas.py`, `servicio.py` y
`repositorio.py`. Ver el diagrama de componentes en `docs/arquitectura.md`.

El catálogo corre como servicio propio ([ADR-0003](docs/adr/0003-separar-catalogo-como-servicio.md)):
- Catálogo, puerto 8001 (`app/catalogo_main.py`): dueño de `productos` y `categorias`.
- Pedidos y clientes, puerto 8000 (`app/main.py`): no sirve `/productos`.
- Pedidos usa el catálogo **solo por HTTP**, con `app/catalogo_cliente.py` (URL en
  `CAFE_CATALOGO_URL`). Nunca importa `app/catalogo.py` ni hace SQL sobre sus tablas.
- Si pedidos descuenta stock y algo falla después, debe devolverlo (compensación); no hay
  transacción común entre los dos servicios.
- Las reglas de negocio van en `servicio.py` del módulo dueño, nunca en el router ni en la pantalla.
- Un router solo llama al servicio de su módulo; nunca a un repositorio.
- Cada tabla tiene un solo módulo dueño, y solo su `repositorio.py` hace SQL sobre ella.
- Un módulo usa a otro solo por su `servicio.py` (dentro del mismo servicio) o por HTTP (entre
  servicios). Ejemplo: Pedidos descuenta stock con `POST /productos/{id}/descontar` del catálogo.
- La pantalla Streamlit solo llama a los servicios por HTTP (`CAFE_API` y `CAFE_CATALOGO_API`);
  no importa código de `app/`.

## 5. Reglas
- Las dependencias se agregan solo con `poetry add` (desarrollo: `poetry add --group dev`).
  No edites a mano `pyproject.toml` ni `poetry.lock` para agregar paquetes, y no uses `pip install`.
- Todo SQL va parametrizado (`?` o parámetros con nombre). Nunca armes SQL con f-strings,
  `%` ni concatenación de valores.
- Cada endpoint nuevo o modificado lleva al menos una prueba en `tests/`.
- No leas, abras ni muestres `.env` ni nada dentro de `data/`.
- Antes de terminar un cambio, `poetry run pytest -q` y `poetry run ruff check .` deben pasar.
- Los commits pasan por pre-commit (ruff, ver `.pre-commit-config.yaml`). Si un hook falla,
  corrige el código y vuelve a hacer commit; nunca uses `git commit --no-verify` ni desactives hooks.
  Al actualizar ruff en `poetry.lock`, actualiza también su `rev` en `.pre-commit-config.yaml`.

## 6. Glosario
- **Pedido** — solicitud de un cliente a la cafetería; agrupa uno o más ítems y tiene un estado.
- **Ítem** — línea de un pedido: un producto del menú con su cantidad y precio unitario.
- **Stock** — cantidad disponible de un producto; limita qué ítems se pueden pedir.
- **Cliente** — persona que hace el pedido.
- **Estado del pedido** — etapa en la que está el pedido. Valores posibles:
  - `pendiente` — creado, aún sin pagar.
  - `pagado` — pago registrado; listo para preparar y entregar.
  - `entregado` — entregado al cliente. Estado final.
  - `anulado` — cancelado antes de la entrega. Estado final.

  Flujo: `pendiente` → `pagado` → `entregado`; `pendiente` o `pagado` → `anulado`.
