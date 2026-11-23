"""Contexto CLIENTES: consulta de clientes."""
from fastapi import APIRouter, HTTPException

from app import pedidos
from app.db import Conexion
from app.modelos import Cliente, PedidoDeCliente

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("/{cliente_id}", response_model=Cliente)
def obtener_cliente(cliente_id: int, con: Conexion):
    fila = con.execute("SELECT id, nombre, email FROM clientes WHERE id = ?",
                       (cliente_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return dict(fila)


@router.get("/{cliente_id}/pedidos", response_model=list[PedidoDeCliente])
def pedidos_del_cliente(cliente_id: int, con: Conexion):
    obtener_cliente(cliente_id, con)  # 404 si el cliente no existe
    return pedidos.listar_por_cliente(con, cliente_id)
