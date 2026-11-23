# AGENTS.md — CaféDMC

## 1. Qué es el sistema
CaféDMC es el sistema de pedidos de una cafetería: API en FastAPI, pantalla en Streamlit y base SQLite.
El proyecto se gestiona con Poetry en modo sin paquete (`package-mode = false`).

## 2. Comandos (siempre con Poetry)
- Instalar dependencias: `poetry install`
- Pruebas: `poetry run pytest -q`
- Estilo: `poetry run ruff check .`
- Activar los hooks de pre-commit (una vez por clon): `poetry run pre-commit install`
- Correr los hooks a mano sobre todo el repo: `poetry run pre-commit run --all-files`

## 3. Arquitectura
- `app/` — código de la aplicación (API FastAPI y pantalla Streamlit).
- `tests/` — pruebas con pytest.
- `scripts/` — scripts de apoyo (por ejemplo, inicializar la base).
- `db/` — esquema y migraciones SQL de SQLite.
- `docs/adr/` — decisiones de arquitectura (ADR).

Monolito modular ([ADR-0002](docs/adr/0002-estilo-arquitectura.md)): un módulo por contexto,
`app/catalogo/` y `app/pedidos/`, cada uno con `router.py`, `schemas.py`, `servicio.py` y
`repositorio.py`. Ver el diagrama de componentes en `docs/arquitectura.md`.
- Las reglas de negocio van en `servicio.py` del módulo dueño, nunca en el router ni en la pantalla.
- Un router solo llama al servicio de su módulo; nunca a un repositorio.
- Cada tabla tiene un solo módulo dueño, y solo su `repositorio.py` hace SQL sobre ella.
- Un módulo usa a otro solo por su `servicio.py`. Ejemplo: Pedidos descuenta stock llamando a
  `catalogo/servicio.py`; nunca importa `catalogo/repositorio.py` ni lee sus tablas.
- La pantalla Streamlit solo llama a la API por HTTP; no importa código de la API.

## 4. Reglas
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

## 5. Glosario
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

## Pendiente
Cuando existan, agregar aquí los comandos para levantar la API y la pantalla Streamlit.
