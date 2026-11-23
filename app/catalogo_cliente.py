"""Cliente HTTP del servicio de catálogo. Pedidos lo usa en lugar de leer las tablas del catálogo.

La URL se toma de CAFE_CATALOGO_URL (por defecto http://127.0.0.1:8001).
"""
import os
from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import Depends


class CatalogoNoDisponible(Exception):
    """El catálogo no respondió, o respondió algo inesperado."""


class ProductoNoEncontrado(Exception):
    def __init__(self, producto_id: int):
        super().__init__(producto_id)
        self.producto_id = producto_id


class StockInsuficiente(Exception):
    def __init__(self, producto_id: int):
        super().__init__(producto_id)
        self.producto_id = producto_id


class Catalogo:
    def __init__(self, http: httpx.Client):
        self.http = http

    def _pedir(self, metodo: str, ruta: str, **kwargs) -> httpx.Response:
        try:
            r = self.http.request(metodo, ruta, **kwargs)
        except httpx.HTTPError as e:
            raise CatalogoNoDisponible(str(e)) from e
        if r.status_code >= 500:
            raise CatalogoNoDisponible(f"{metodo} {ruta} respondió {r.status_code}")
        return r

    def _esperar(self, r: httpx.Response, producto_id: int) -> dict:
        if r.status_code == 404:
            raise ProductoNoEncontrado(producto_id)
        if r.status_code == 409:
            raise StockInsuficiente(producto_id)
        if r.status_code != 200:
            raise CatalogoNoDisponible(f"respuesta inesperada {r.status_code}")
        return r.json()

    def obtener_producto(self, producto_id: int) -> dict:
        """Producto activo con su precio y stock actuales."""
        return self._esperar(self._pedir("GET", f"/productos/{producto_id}"), producto_id)

    def descontar(self, producto_id: int, cantidad: int) -> dict:
        r = self._pedir("POST", f"/productos/{producto_id}/descontar", json={"cantidad": cantidad})
        return self._esperar(r, producto_id)

    def devolver(self, producto_id: int, cantidad: int) -> dict:
        r = self._pedir("POST", f"/productos/{producto_id}/devolver", json={"cantidad": cantidad})
        return self._esperar(r, producto_id)


def get_catalogo() -> Iterator[Catalogo]:
    """Dependencia de FastAPI: un cliente HTTP por petición. Las pruebas la reemplazan."""
    url = os.environ.get("CAFE_CATALOGO_URL", "http://127.0.0.1:8001")
    with httpx.Client(base_url=url, timeout=5) as http:
        yield Catalogo(http)


CatalogoDep = Annotated[Catalogo, Depends(get_catalogo)]
