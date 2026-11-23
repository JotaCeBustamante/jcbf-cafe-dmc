"""Servicio de CATÁLOGO: proceso propio, puerto 8001 (ADR-0003).

    poetry run uvicorn app.catalogo_main:app --port 8001
"""
from fastapi import FastAPI

from app import catalogo

app = FastAPI(title="CaféDMC Catálogo", version="0.1.0")
app.include_router(catalogo.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"estado": "ok"}
