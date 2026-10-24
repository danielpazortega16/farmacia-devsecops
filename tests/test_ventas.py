from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app

LLAVE = {"X-API-Key": "llave-local"}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("API_KEY", "llave-local")
    with TestClient(app) as c:
        yield c


def pedido(**cambios):
    base = {"telefono": "55123456", "items": [{"codigo": "PAR500", "cantidad": 2}], "metodo_pago": "efectivo"}
    base.update(cambios)
    return base


def test_salud(cliente):
    assert cliente.get("/salud").json() == {"estado": "ok"}


def test_sin_llave_no_entra(cliente):
    assert cliente.post("/api/v1/ventas", json=pedido()).status_code == 401
    assert cliente.get("/api/v1/productos", headers={"X-API-Key": "otra"}).status_code == 401


def test_venta_valida(cliente):
    r = cliente.post("/api/v1/ventas", json=pedido(), headers=LLAVE)
    assert r.status_code == 201
    assert r.json()["total"] == "17.00"
    assert r.json()["estado"] == "APROBADA"


def test_total_lo_calcula_el_servidor(cliente):
    # aunque manden un total, se ignora
    r = cliente.post("/api/v1/ventas", json=pedido(total="0.01"), headers=LLAVE)
    assert r.json()["total"] == "17.00"


def test_controlado_sin_receta(cliente):
    r = cliente.post("/api/v1/ventas", json=pedido(items=[{"codigo": "CLZ2", "cantidad": 1}]), headers=LLAVE)
    assert r.status_code == 400


def test_controlado_con_receta(cliente):
    datos = pedido(items=[{"codigo": "CLZ2", "cantidad": 1}], numero_receta="MS-123456")
    r = cliente.post("/api/v1/ventas", json=datos, headers=LLAVE)
    assert r.status_code == 201


def test_cantidad_invalida(cliente):
    r = cliente.post("/api/v1/ventas", json=pedido(items=[{"codigo": "PAR500", "cantidad": 0}]), headers=LLAVE)
    assert r.status_code == 422


def test_tarjeta_sin_token(cliente):
    r = cliente.post("/api/v1/ventas", json=pedido(metodo_pago="tarjeta"), headers=LLAVE)
    assert r.status_code == 422


def test_sin_existencias(cliente):
    datos = pedido(items=[{"codigo": "TRM50", "cantidad": 11}], numero_receta="MS-5555")
    assert cliente.post("/api/v1/ventas", json=datos, headers=LLAVE).status_code == 409


def test_telefono_se_guarda_enmascarado(cliente):
    venta = cliente.post("/api/v1/ventas", json=pedido(), headers=LLAVE).json()
    guardada = cliente.get(f"/api/v1/ventas/{venta['id']}", headers=LLAVE).json()
    assert guardada["telefono"] == "55****56"
    assert guardada["detalle"][0]["codigo"] == "PAR500"


def test_lista_ultimas_ventas(cliente):
    cliente.post("/api/v1/ventas", json=pedido(), headers=LLAVE)
    cliente.post("/api/v1/ventas", json=pedido(telefono="44556677"), headers=LLAVE)
    ventas = cliente.get("/api/v1/ventas", headers=LLAVE).json()
    assert len(ventas) == 2
    assert ventas[0]["telefono"] == "44****77"


def existencias(cliente, codigo):
    productos = cliente.get("/api/v1/productos", headers=LLAVE).json()
    return next(p for p in productos if p["codigo"] == codigo)["existencias"]


def test_producto_repetido_se_suma(cliente):
    # 7 + 7 de clonazepam con 12 en existencia
    datos = pedido(items=[{"codigo": "CLZ2", "cantidad": 7}, {"codigo": "CLZ2", "cantidad": 7}], numero_receta="MS-1234")
    assert cliente.post("/api/v1/ventas", json=datos, headers=LLAVE).status_code == 409
    assert existencias(cliente, "CLZ2") == 12


def test_ventas_al_mismo_tiempo(cliente):
    # 15 pedidos de 1 tramadol a la vez, solo hay 10
    datos = pedido(items=[{"codigo": "TRM50", "cantidad": 1}], numero_receta="MS-1234")
    with ThreadPoolExecutor(max_workers=15) as hilos:
        codigos = list(hilos.map(lambda _: registrar(datos), range(15)))
    assert codigos.count(201) == 10
    assert codigos.count(409) == 5
    assert existencias(cliente, "TRM50") == 0


def registrar(datos):
    from app.main import Pedido, registrar_venta
    from fastapi import HTTPException
    try:
        registrar_venta(Pedido(**datos))
        return 201
    except HTTPException as e:
        return e.status_code


def test_descuenta_existencias(cliente):
    cliente.post("/api/v1/ventas", json=pedido(), headers=LLAVE)
    productos = cliente.get("/api/v1/productos", headers=LLAVE).json()
    par = next(p for p in productos if p["codigo"] == "PAR500")
    assert par["existencias"] == 118
