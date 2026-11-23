"""Contexto PEDIDOS: crea pedidos y cambia su estado. Precio y stock los pide al catálogo
por HTTP (ADR-0003); no hace SQL sobre las tablas del catálogo."""
import logging

from fastapi import APIRouter, HTTPException

from app.catalogo_cliente import (
    Catalogo,
    CatalogoDep,
    CatalogoNoDisponible,
    ProductoNoEncontrado,
    StockInsuficiente,
)
from app.db import Conexion
from app.modelos import CambioEstado, Pedido, PedidoNuevo

router = APIRouter(prefix="/pedidos", tags=["pedidos"])
log = logging.getLogger(__name__)

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
def crear_pedido(datos: PedidoNuevo, con: Conexion, catalogo: CatalogoDep):
    if con.execute("SELECT 1 FROM clientes WHERE id = ?", (datos.cliente_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    try:
        # 1. Precio y stock actuales, por HTTP al catálogo. La revisión de stock es solo un
        #    aviso temprano: la que vale es la del descuento, que es atómica en el catálogo.
        total = 0.0
        lineas = []
        for item in datos.items:
            prod = catalogo.obtener_producto(item.producto_id)
            if prod["stock"] < item.cantidad:
                raise StockInsuficiente(item.producto_id)
            total += prod["precio"] * item.cantidad
            lineas.append((item.producto_id, item.cantidad, prod["precio"]))

        # 2. Descontar línea por línea y guardar el pedido. Ya no hay una transacción común
        #    con el stock: si algo falla, se devuelve lo descontado (compensación).
        descontados: list[tuple[int, int]] = []
        try:
            for producto_id, cantidad, _ in lineas:
                catalogo.descontar(producto_id, cantidad)
                descontados.append((producto_id, cantidad))
            with con:  # transacción local: el pedido y sus líneas, todo o nada
                cur = con.execute("INSERT INTO pedidos(cliente_id, total) VALUES (?, ?)",
                                  (datos.cliente_id, round(total, 2)))
                pedido_id = cur.lastrowid
                con.executemany(
                    "INSERT INTO detalle_pedido(pedido_id, producto_id, cantidad, precio_unitario)"
                    " VALUES (?,?,?,?)", [(pedido_id, *linea) for linea in lineas])
        except Exception:
            _devolver(catalogo, descontados)
            raise
    except ProductoNoEncontrado as e:
        raise HTTPException(status_code=404, detail=f"Producto {e.producto_id} no existe") from e
    except StockInsuficiente as e:
        raise HTTPException(status_code=409,
                            detail=f"Stock insuficiente para producto {e.producto_id}") from e
    except CatalogoNoDisponible as e:
        raise HTTPException(status_code=503, detail="El catálogo no está disponible") from e
    return {"id": pedido_id, "cliente_id": datos.cliente_id, "estado": "pendiente",
            "total": round(total, 2)}


def _devolver(catalogo: Catalogo, descontados: list[tuple[int, int]]) -> None:
    """Compensación: devuelve al catálogo el stock ya descontado de un pedido que falló."""
    for producto_id, cantidad in descontados:
        try:
            catalogo.devolver(producto_id, cantidad)
        except Exception:
            # Si tampoco se puede devolver, el stock queda descontado de más: se registra
            # para corregirlo a mano.
            log.exception("No se pudo devolver %s unidades del producto %s", cantidad, producto_id)


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
