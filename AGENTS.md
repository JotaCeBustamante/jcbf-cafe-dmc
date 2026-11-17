# AGENTS.md — CaféDMC

## 1. Qué es el sistema
CaféDMC es el sistema de pedidos de una cafetería: API en FastAPI, pantalla en Streamlit y base SQLite.
El proyecto se gestiona con Poetry en modo sin paquete (`package-mode = false`).

## 2. Comandos (siempre con Poetry)
- Instalar dependencias: `poetry install`
- Pruebas: `poetry run pytest -q`
- Estilo: `poetry run ruff check .`

## 3. Arquitectura
- `app/` — código de la aplicación (API FastAPI y pantalla Streamlit).
- `tests/` — pruebas con pytest.
- `scripts/` — scripts de apoyo (por ejemplo, inicializar la base).
- `db/` — esquema y migraciones SQL de SQLite.
- `docs/adr/` — decisiones de arquitectura (ADR).

## 4. Reglas
- Las dependencias se agregan solo con `poetry add` (desarrollo: `poetry add --group dev`).
  No edites a mano `pyproject.toml` ni `poetry.lock` para agregar paquetes, y no uses `pip install`.
- Todo SQL va parametrizado (`?` o parámetros con nombre). Nunca armes SQL con f-strings,
  `%` ni concatenación de valores.
- Cada endpoint nuevo o modificado lleva al menos una prueba en `tests/`.
- No leas, abras ni muestres `.env` ni nada dentro de `data/`.
- Antes de terminar un cambio, `poetry run pytest -q` y `poetry run ruff check .` deben pasar.

## Pendiente
Cuando existan, agregar aquí los comandos para levantar la API y la pantalla Streamlit.
