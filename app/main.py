"""API de pedidos y clientes de CaféDMC, puerto 8000. El catálogo es otro servicio (ADR-0003)."""
from fastapi import FastAPI

from app import clientes, pedidos

app = FastAPI(title="CaféDMC API", version="0.1.0")
app.include_router(pedidos.router)
app.include_router(clientes.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"estado": "ok"}