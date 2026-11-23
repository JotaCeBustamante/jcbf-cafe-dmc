"""Contexto PEDIDOS: crea pedidos validando stock y calculando el total."""
from fastapi import APIRouter, HTTPException

from app.db import Conexion
from app.modelos import CambioEstado, Pedido, PedidoNuevo

router = APIRouter(prefix="/pedidos", tags=["pedidos"])

# Flujo del estado del pedido (AGENTS.md, glosario). entregado y anulado son finales.
TRANSICIONES = {
    "pendiente": {"pagado", "anulado"},
    "pagado": {"entregado", "anulado"},
    "entregado": set(),
    "anulado": set(),
}


def listar_por_cliente(con, cliente_id: int) -> list[dict]:
    """Pedidos de un cliente, el más reciente primero. La usa el módulo de clientes."""
    filas = con.execute(
        "SELECT id, cliente_id, estado, total, fecha FROM pedidos"
        " WHERE cliente_id = ? ORDER BY id DESC", (cliente_id,)).fetchall()
    return [dict(f) for f in filas]


@router.post("", response_model=Pedido, status_code=201)
def crear_pedido(datos: PedidoNuevo, con: Conexion):
    if con.execute("SELECT 1 FROM clientes WHERE id = ?", (datos.cliente_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    total = 0.0
    lineas = []
    for item in datos.items:
        prod = con.execute(
            "SELECT id, precio, stock FROM productos WHERE id = ? AND activo = 1",
            (item.producto_id,),
        ).fetchone()
        if prod is None:
            raise HTTPException(status_code=404, detail=f"Producto {item.producto_id} no existe")
        if prod["stock"] < item.cantidad:
            raise HTTPException(status_code=409, detail=f"Stock insuficiente para producto {item.producto_id}")
        total += prod["precio"] * item.cantidad
        lineas.append((item.producto_id, item.cantidad, prod["precio"]))
    with con:  # transacción: todo o nada
        cur = con.execute("INSERT INTO pedidos(cliente_id, total) VALUES (?, ?)",
                          (datos.cliente_id, round(total, 2)))
        pedido_id = cur.lastrowid
        for producto_id, cantidad, precio in lineas:
            con.execute(
                "INSERT INTO detalle_pedido(pedido_id, producto_id, cantidad, precio_unitario)"
                " VALUES (?,?,?,?)", (pedido_id, producto_id, cantidad, precio))
            con.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, producto_id))
    return {"id": pedido_id, "cliente_id": datos.cliente_id, "estado": "pendiente",
            "total": round(total, 2)}


@router.get("/{pedido_id}", response_model=Pedido)
def obtener_pedido(pedido_id: int, con: Conexion):
    fila = con.execute("SELECT id, cliente_id, estado, total FROM pedidos WHERE id = ?",
                       (pedido_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return dict(fila)


@router.patch("/{pedido_id}/estado", response_model=Pedido)
def cambiar_estado(pedido_id: int, cambio: CambioEstado, con: Conexion):
    fila = con.execute("SELECT estado FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    actual = fila["estado"]
    if cambio.estado not in TRANSICIONES[actual]:
        raise HTTPException(status_code=409,
                            detail=f"No se puede pasar de '{actual}' a '{cambio.estado}'")
    with con:
        # El WHERE con el estado leído evita pisar un cambio hecho en paralelo
        cur = con.execute("UPDATE pedidos SET estado = ? WHERE id = ? AND estado = ?",
                          (cambio.estado, pedido_id, actual))
    if cur.rowcount == 0:
        raise HTTPException(status_code=409, detail="El pedido cambió de estado; vuelve a intentarlo")
    return obtener_pedido(pedido_id, con)
