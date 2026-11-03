import json
import sqlite3
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
    assert cliente.get("/salud").json() == {"estado": "ok", "version": "1.1.0"}


def test_encabezados_de_seguridad(cliente):
    h = cliente.get("/").headers
    assert h["X-Frame-Options"] == "DENY"
    assert h["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]


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
    # 15 pedidos de 1 tramadol a la vez por HTTP y con llave, solo hay 10
    datos = pedido(items=[{"codigo": "TRM50", "cantidad": 1}], numero_receta="MS-1234")
    with ThreadPoolExecutor(max_workers=15) as hilos:
        respuestas = list(hilos.map(lambda _: cliente.post("/api/v1/ventas", json=datos, headers=LLAVE), range(15)))
    codigos = [r.status_code for r in respuestas]
    assert codigos.count(201) == 10
    assert codigos.count(409) == 5
    assert existencias(cliente, "TRM50") == 0


def test_descuenta_existencias(cliente):
    cliente.post("/api/v1/ventas", json=pedido(), headers=LLAVE)
    productos = cliente.get("/api/v1/productos", headers=LLAVE).json()
    par = next(p for p in productos if p["codigo"] == "PAR500")
    assert par["existencias"] == 118


def test_bitacora_sin_datos_del_cliente(cliente, caplog):
    caplog.set_level("INFO", logger="farmacia")
    cliente.post("/api/v1/ventas", json=pedido(), headers=LLAVE)
    datos = pedido(items=[{"codigo": "CLZ2", "cantidad": 1}], telefono="44556677")
    cliente.post("/api/v1/ventas", json=datos, headers=LLAVE)
    datos = pedido(items=[{"codigo": "CLZ2", "cantidad": 1}], numero_receta="MS-998877")
    cliente.post("/api/v1/ventas", json=datos, headers=LLAVE)

    eventos = [json.loads(r.getMessage()) for r in caplog.records]
    assert [e["evento"] for e in eventos if e["evento"].startswith("venta")] == [
        "venta_aprobada", "venta_rechazada", "venta_aprobada"
    ]
    texto = caplog.text
    assert "55123456" not in texto and "44556677" not in texto
    assert "MS-998877" not in texto


def test_llave_con_caracter_especial(cliente):
    # antes tiraba un 500 sin encabezados de seguridad
    r = cliente.get("/api/v1/productos", headers={"X-API-Key": "llave-ñ".encode()})
    assert r.status_code == 401
    assert r.headers["X-Frame-Options"] == "DENY"


def test_error_interno_con_encabezados_y_bitacora(cliente, caplog, monkeypatch):
    def falla():
        raise sqlite3.OperationalError("disco lleno")

    monkeypatch.setattr("app.db.conectar", falla)
    caplog.set_level("INFO", logger="farmacia")
    r = cliente.get("/api/v1/productos", headers=LLAVE)
    assert r.status_code == 500
    assert r.json() == {"detail": "Error interno"}
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    eventos = [json.loads(x.getMessage()) for x in caplog.records]
    assert {"evento": "error_interno", "tipo": "OperationalError"}.items() <= next(
        e for e in eventos if e["evento"] == "error_interno"
    ).items()


def test_mismo_pedido_con_misma_clave_no_se_duplica(cliente):
    clave = LLAVE | {"Idempotency-Key": "pedido-0001"}
    primera = cliente.post("/api/v1/ventas", json=pedido(), headers=clave)
    segunda = cliente.post("/api/v1/ventas", json=pedido(), headers=clave)
    assert primera.status_code == segunda.status_code == 201
    assert primera.json() == segunda.json()
    assert existencias(cliente, "PAR500") == 118
    assert len(cliente.get("/api/v1/ventas", headers=LLAVE).json()) == 1


def test_misma_clave_con_otro_pedido(cliente):
    clave = LLAVE | {"Idempotency-Key": "pedido-0002"}
    cliente.post("/api/v1/ventas", json=pedido(), headers=clave)
    r = cliente.post("/api/v1/ventas", json=pedido(telefono="44556677"), headers=clave)
    assert r.status_code == 409


def test_claves_foraneas_activas(cliente):
    from app import db
    with pytest.raises(sqlite3.IntegrityError):
        with db.abrir() as con:
            con.execute("INSERT INTO detalle_venta VALUES (999, 'PAR500', 1, '8.50')")


def test_telefonos_de_guatemala(cliente):
    for telefono in ("81234567", "91234567", "22345678"):
        assert cliente.post("/api/v1/ventas", json=pedido(telefono=telefono), headers=LLAVE).status_code == 201
    for telefono in ("12345678", "5512345", "551234567"):
        assert cliente.post("/api/v1/ventas", json=pedido(telefono=telefono), headers=LLAVE).status_code == 422


def test_documentacion_cerrada(cliente):
    for ruta in ("/docs", "/redoc", "/openapi.json"):
        assert cliente.get(ruta).status_code == 404


def test_receta_enmascarada_en_la_api(cliente):
    datos = pedido(items=[{"codigo": "CLZ2", "cantidad": 1}], numero_receta="MS-123456")
    venta = cliente.post("/api/v1/ventas", json=datos, headers=LLAVE).json()
    assert cliente.get("/api/v1/ventas", headers=LLAVE).json()[0]["numero_receta"] == "MS-****56"
    assert cliente.get(f"/api/v1/ventas/{venta['id']}", headers=LLAVE).json()["numero_receta"] == "MS-****56"


def test_producto_inexistente(cliente):
    r = cliente.post("/api/v1/ventas", json=pedido(items=[{"codigo": "NOEXISTE", "cantidad": 1}]), headers=LLAVE)
    assert r.status_code == 404
    assert r.json()["detail"] == "Producto NOEXISTE no existe"


def test_venta_inexistente(cliente):
    r = cliente.get("/api/v1/ventas/999", headers=LLAVE)
    assert r.status_code == 404
    assert r.json()["detail"] == "Venta no encontrada"


def test_pedido_rechazado_a_medias_no_descuenta(cliente):
    # el paracetamol si alcanza, el clonazepam no: no debe salir nada
    datos = pedido(
        items=[{"codigo": "PAR500", "cantidad": 2}, {"codigo": "CLZ2", "cantidad": 13}], numero_receta="MS-1234"
    )
    assert cliente.post("/api/v1/ventas", json=datos, headers=LLAVE).status_code == 409
    assert existencias(cliente, "PAR500") == 120
    assert existencias(cliente, "CLZ2") == 12
    assert cliente.get("/api/v1/ventas", headers=LLAVE).json() == []


def test_base_vieja_recibe_columnas_nuevas(tmp_path, monkeypatch):
    # una base creada con la 1.0.0 no tenia clave ni huella
    monkeypatch.setenv("DB_PATH", str(tmp_path / "vieja.db"))
    con = sqlite3.connect(tmp_path / "vieja.db")
    con.execute("CREATE TABLE ventas (id INTEGER PRIMARY KEY, telefono TEXT, metodo_pago TEXT,"
                " numero_receta TEXT, total TEXT, fecha TEXT)")
    con.close()
    from app import db
    db.inicializar()
    with db.abrir() as con:
        columnas = {c["name"] for c in con.execute("PRAGMA table_info(ventas)")}
    assert {"clave", "huella"} <= columnas
