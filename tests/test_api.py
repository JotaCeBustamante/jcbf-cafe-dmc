"""Pruebas de la API. Usan una base temporal para no tocar data/cafe.db.

Hay dos servicios (ADR-0003): la API de pedidos y clientes (app.main, puerto 8000) y el
catálogo (app.catalogo_main, puerto 8001). En las pruebas, pedidos llama al catálogo por
HTTP en memoria con un TestClient, sobre la misma base temporal.
"""
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.catalogo_cliente import Catalogo, get_catalogo
from app.catalogo_main import app as app_catalogo
from app.main import app
from scripts.crear_db import crear


@pytest.fixture()
def catalogo(tmp_path, monkeypatch):
    """Servicio de catálogo (puerto 8001 en producción)."""
    db = tmp_path / "test.db"
    monkeypatch.setenv("CAFE_DB", str(db))
    crear(db)
    return TestClient(app_catalogo)


@pytest.fixture()
def cliente(catalogo):
    """API de pedidos y clientes, conectada al catálogo por HTTP."""
    app.dependency_overrides[get_catalogo] = lambda: Catalogo(catalogo)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _stock(catalogo, producto_id):
    return catalogo.get(f"/productos/{producto_id}").json()["stock"]


def test_salud(cliente, catalogo):
    assert cliente.get("/salud").json() == {"estado": "ok"}
    assert catalogo.get("/salud").json() == {"estado": "ok"}


def test_listar_productos(catalogo):
    r = catalogo.get("/productos")
    assert r.status_code == 200
    assert len(r.json()) == 8


def test_filtrar_por_categoria(catalogo):
    r = catalogo.get("/productos", params={"categoria": "Pastelería"})
    assert {p["nombre"] for p in r.json()} == {"Croissant", "Torta de chocolate"}


def test_producto_inexistente(catalogo):
    assert catalogo.get("/productos/999").status_code == 404


def test_api_de_pedidos_ya_no_sirve_productos(cliente):
    assert cliente.get("/productos").status_code == 404


def test_crear_pedido_calcula_total(cliente):
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [
        {"producto_id": 1, "cantidad": 2}, {"producto_id": 7, "cantidad": 1}]})
    assert r.status_code == 201
    assert r.json()["total"] == 20.5  # 2 x 7.0 + 1 x 6.5


def test_stock_insuficiente(cliente):
    # La torta (id 8) tiene 20 unidades en stock: 2 líneas de 15 superan el stock
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [
        {"producto_id": 8, "cantidad": 15}]})
    assert r.status_code == 201
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [
        {"producto_id": 8, "cantidad": 15}]})
    assert r.status_code == 409


def test_cantidad_maxima(cliente):
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 21}]})
    assert r.status_code == 422

def test_obtener_cliente(cliente):
    r = cliente.get("/clientes/1")
    assert r.status_code == 200
    assert r.json() == {"id": 1, "nombre": "Ana Torres", "email": "ana@ejemplo.com"}


def test_cliente_inexistente(cliente):
    r = cliente.get("/clientes/999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Cliente no encontrado"


# --- PATCH /pedidos/{id}/estado ---------------------------------------------

def _nuevo_pedido(cliente) -> int:
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 1}]})
    assert r.status_code == 201
    return r.json()["id"]


def _cambiar_estado(cliente, pedido_id, estado):
    return cliente.patch(f"/pedidos/{pedido_id}/estado", json={"estado": estado})


@pytest.mark.parametrize("camino", [
    ["pagado"],
    ["pagado", "entregado"],
    ["anulado"],
    ["pagado", "anulado"],
])
def test_transiciones_permitidas(cliente, camino):
    pedido_id = _nuevo_pedido(cliente)
    for estado in camino:
        r = _cambiar_estado(cliente, pedido_id, estado)
        assert r.status_code == 200
        assert r.json()["estado"] == estado
        assert r.json()["id"] == pedido_id
    # el cambio queda guardado
    assert cliente.get(f"/pedidos/{pedido_id}").json()["estado"] == camino[-1]


@pytest.mark.parametrize("previos, destino", [
    ([], "entregado"),                       # pendiente → entregado (salta el pago)
    ([], "pendiente"),                       # pendiente → pendiente
    (["pagado"], "pendiente"),               # no se vuelve atrás
    (["pagado"], "pagado"),                  # pagado → pagado
    (["pagado", "entregado"], "anulado"),    # entregado es final
    (["pagado", "entregado"], "pagado"),
    (["anulado"], "pagado"),                 # anulado es final
    (["anulado"], "pendiente"),
])
def test_transiciones_prohibidas(cliente, previos, destino):
    pedido_id = _nuevo_pedido(cliente)
    for estado in previos:
        assert _cambiar_estado(cliente, pedido_id, estado).status_code == 200
    estado_antes = cliente.get(f"/pedidos/{pedido_id}").json()["estado"]
    r = _cambiar_estado(cliente, pedido_id, destino)
    assert r.status_code == 409
    # el estado no cambia
    assert cliente.get(f"/pedidos/{pedido_id}").json()["estado"] == estado_antes


def test_cambiar_estado_pedido_inexistente(cliente):
    assert _cambiar_estado(cliente, 999, "pagado").status_code == 404


def test_cambiar_estado_valor_desconocido(cliente):
    pedido_id = _nuevo_pedido(cliente)
    assert _cambiar_estado(cliente, pedido_id, "cocinando").status_code == 422


# --- GET /clientes/{id}/pedidos ---------------------------------------------

def test_pedidos_de_cliente(cliente):
    r = cliente.get("/clientes/1/pedidos")
    assert r.status_code == 200
    pedidos = r.json()
    # Ana tiene los pedidos 1 y 4 de los datos de prueba; el más reciente primero
    assert [p["id"] for p in pedidos] == [4, 1]
    assert all(p["cliente_id"] == 1 for p in pedidos)
    assert set(pedidos[0]) == {"id", "cliente_id", "estado", "total", "fecha"}


def test_pedidos_de_cliente_incluye_nuevo_y_su_estado(cliente):
    pedido_id = _nuevo_pedido(cliente)
    _cambiar_estado(cliente, pedido_id, "pagado")
    primero = cliente.get("/clientes/1/pedidos").json()[0]
    assert primero["id"] == pedido_id
    assert primero["estado"] == "pagado"


def test_pedidos_de_cliente_no_mezcla_clientes(cliente):
    assert [p["id"] for p in cliente.get("/clientes/2/pedidos").json()] == [2]


def test_pedidos_de_cliente_sin_pedidos(cliente, tmp_path):
    import sqlite3
    with sqlite3.connect(tmp_path / "test.db") as con:
        nuevo = con.execute("INSERT INTO clientes(nombre, email) VALUES (?, ?)",
                            ("Sin Pedidos", "sin@ejemplo.com")).lastrowid
    r = cliente.get(f"/clientes/{nuevo}/pedidos")
    assert r.status_code == 200
    assert r.json() == []


def test_pedidos_de_cliente_inexistente(cliente):
    r = cliente.get("/clientes/999/pedidos")
    assert r.status_code == 404
    assert r.json()["detail"] == "Cliente no encontrado"


# --- Índices del esquema ----------------------------------------------------

def _plan(db, sql, params):
    import sqlite3
    with sqlite3.connect(db) as con:
        return " | ".join(f[3] for f in con.execute("EXPLAIN QUERY PLAN " + sql, params))


def test_productos_por_categoria_usa_indice(tmp_path):
    db = crear(tmp_path / "plan.db")
    plan = _plan(db, "SELECT p.id FROM productos p JOIN categorias c ON c.id = p.categoria_id"
                     " WHERE p.activo = 1 AND c.nombre = ?", ("Café",))
    assert "idx_productos_categoria" in plan
    assert "SCAN" not in plan


def test_pedidos_por_estado_usa_indice(tmp_path):
    db = crear(tmp_path / "plan.db")
    plan = _plan(db, "SELECT id, cliente_id, estado, total FROM pedidos WHERE estado = ?",
                 ("pendiente",))
    assert "idx_pedidos_estado" in plan
    assert "SCAN" not in plan


# --- Catálogo: descontar y devolver stock (lo usa pedidos por HTTP) --------

def test_descontar_stock(catalogo):
    r = catalogo.post("/productos/1/descontar", json={"cantidad": 3})
    assert r.status_code == 200
    assert r.json()["stock"] == 97
    assert _stock(catalogo, 1) == 97


def test_descontar_mas_que_el_stock(catalogo):
    r = catalogo.post("/productos/8/descontar", json={"cantidad": 21})  # la torta tiene 20
    assert r.status_code == 409
    assert _stock(catalogo, 8) == 20


def test_descontar_producto_inexistente(catalogo):
    assert catalogo.post("/productos/999/descontar", json={"cantidad": 1}).status_code == 404


def test_descontar_cantidad_invalida(catalogo):
    assert catalogo.post("/productos/1/descontar", json={"cantidad": 0}).status_code == 422


def test_devolver_stock(catalogo):
    r = catalogo.post("/productos/1/devolver", json={"cantidad": 5})
    assert r.status_code == 200
    assert _stock(catalogo, 1) == 105


def test_devolver_producto_inexistente(catalogo):
    assert catalogo.post("/productos/999/devolver", json={"cantidad": 1}).status_code == 404


# --- Pedidos usa el catálogo por HTTP ---------------------------------------

def test_crear_pedido_descuenta_stock_en_catalogo(cliente, catalogo):
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 2}]})
    assert r.status_code == 201
    assert _stock(catalogo, 1) == 98


def test_producto_inexistente_en_pedido(cliente):
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 99, "cantidad": 1}]})
    assert r.status_code == 404
    assert r.json()["detail"] == "Producto 99 no existe"


def test_producto_repetido_compensa_stock(cliente, catalogo):
    # Torta (id 8) con stock 20: cada línea de 15 pasa la revisión, pero las dos juntas no.
    # La primera se descuenta, la segunda falla: se devuelve la primera y no se crea el pedido.
    antes = len(cliente.get("/clientes/1/pedidos").json())
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [
        {"producto_id": 8, "cantidad": 15}, {"producto_id": 8, "cantidad": 15}]})
    assert r.status_code == 409
    assert _stock(catalogo, 8) == 20
    assert len(cliente.get("/clientes/1/pedidos").json()) == antes


def _catalogo_caido():
    def responder(request):
        raise httpx.ConnectError("catálogo caído", request=request)
    return Catalogo(httpx.Client(transport=httpx.MockTransport(responder), base_url="http://catalogo"))


def test_catalogo_caido_responde_503(cliente):
    antes = len(cliente.get("/clientes/1/pedidos").json())
    app.dependency_overrides[get_catalogo] = _catalogo_caido
    r = cliente.post("/pedidos", json={"cliente_id": 1, "items": [{"producto_id": 1, "cantidad": 1}]})
    assert r.status_code == 503
    assert len(cliente.get("/clientes/1/pedidos").json()) == antes


def test_pedidos_no_hace_sql_sobre_tablas_del_catalogo():
    # AGENTS.md §4: cada tabla tiene un solo dueño. productos y categorias son del catálogo.
    fuente = (Path(__file__).parent.parent / "app" / "pedidos.py").read_text(encoding="utf-8")
    for tabla in ("productos", "categorias"):
        for sql in (f"FROM {tabla}", f"UPDATE {tabla}", f"JOIN {tabla}", f"INTO {tabla}"):
            assert sql not in fuente
