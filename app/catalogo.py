"""Contexto CATÁLOGO: productos, categorías y stock. Corre como servicio propio (ADR-0003)."""
from fastapi import APIRouter, HTTPException

from app.db import Conexion
from app.modelos import CambioStock, Producto

router = APIRouter(prefix="/productos", tags=["catálogo"])

SQL_BASE = """
SELECT p.id, p.nombre, c.nombre AS categoria, p.precio, p.stock
FROM productos p JOIN categorias c ON c.id = p.categoria_id
WHERE p.activo = 1
"""


@router.get("", response_model=list[Producto])
def listar_productos(con: Conexion, categoria: str | None = None):
    if categoria:
        filas = con.execute(SQL_BASE + " AND c.nombre = ? ORDER BY p.id", (categoria,)).fetchall()
    else:
        filas = con.execute(SQL_BASE + " ORDER BY p.id").fetchall()
    return [dict(f) for f in filas]


@router.get("/{producto_id}", response_model=Producto)
def obtener_producto(producto_id: int, con: Conexion):
    fila = con.execute(SQL_BASE + " AND p.id = ?", (producto_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return dict(fila)


@router.post("/{producto_id}/descontar", response_model=Producto)
def descontar_stock(producto_id: int, cambio: CambioStock, con: Conexion):
    """Descuenta stock de forma atómica: 409 si no alcanza, sin dejar el stock negativo."""
    with con:
        cur = con.execute(
            "UPDATE productos SET stock = stock - ? WHERE id = ? AND activo = 1 AND stock >= ?",
            (cambio.cantidad, producto_id, cambio.cantidad))
    if cur.rowcount == 0:
        if con.execute("SELECT 1 FROM productos WHERE id = ? AND activo = 1",
                       (producto_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        raise HTTPException(status_code=409, detail=f"Stock insuficiente para producto {producto_id}")
    return obtener_producto(producto_id, con)


@router.post("/{producto_id}/devolver", response_model=Producto)
def devolver_stock(producto_id: int, cambio: CambioStock, con: Conexion):
    """Devuelve stock. Pedidos lo usa para compensar un pedido que no se pudo crear."""
    with con:
        cur = con.execute("UPDATE productos SET stock = stock + ? WHERE id = ? AND activo = 1",
                          (cambio.cantidad, producto_id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return obtener_producto(producto_id, con)
