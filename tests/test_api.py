"""Pruebas de la API. Usan una base temporal para no tocar data/cafe.db."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts.crear_db import crear


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("CAFE_DB", str(db))
    crear(db)
    return TestClient(app)


def test_salud(cliente):
    assert cliente.get("/salud").json() == {"estado": "ok"}


def test_listar_productos(cliente):
    r = cliente.get("/productos")
    assert r.status_code == 200
    assert len(r.json()) == 8


def test_filtrar_por_categoria(cliente):
    r = cliente.get("/productos", params={"categoria": "Pastelería"})
    assert {p["nombre"] for p in r.json()} == {"Croissant", "Torta de chocolate"}


def test_producto_inexistente(cliente):
    assert cliente.get("/productos/999").status_code == 404


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
