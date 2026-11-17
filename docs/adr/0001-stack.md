# ADR-0001: Stack tecnológico de CaféDMC

- **Estado:** Propuesto
- **Fecha:** 2026-11-16

## Contexto
- El equipo sabe Python.
- Cada alumno ejecuta el sistema en su laptop, sin Docker.
- Los agentes de IA deben poder leer, probar y modificar el sistema.

## Decisión
Python 3.11+, Poetry (`package-mode = false`), FastAPI + Pydantic, SQLite, Streamlit, pytest y ruff.

## Consecuencias
**(+)**
- Se instala con `poetry install`, sin Docker ni servidor de base de datos.
- Se verifica con `poetry run pytest -q` y `poetry run ruff check .`.
- Tipos y modelos explícitos; FastAPI genera OpenAPI.

**(−)**
- SQLite admite una sola escritura a la vez.
- SQL y migraciones de `db/` se escriben a mano.
- Streamlit limita el control de la interfaz.

## Alternativas consideradas
| Alternativa | A favor | En contra | Resultado |
|---|---|---|---|
| FastAPI + SQLite + Streamlit | Liviano, local, tipado | Concurrencia limitada | ✅ Elegida |
| Django | ORM, migraciones, panel de administración | Más estructura de la necesaria | Descartada |
| PostgreSQL | Concurrencia real | Requiere servidor o Docker | Descartada; revisar si pasa a producción |
