import hashlib
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, model_validator

from app import db

VERSION = "1.1.0"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("farmacia")


def registrar_evento(evento, **datos):
    # una linea JSON por evento; nunca se escribe el telefono ni la receta
    log.info(json.dumps({"fecha": datetime.now(timezone.utc).isoformat(), "evento": evento, **datos}, ensure_ascii=False))


@asynccontextmanager
async def ciclo_vida(app):
    db.inicializar()
    registrar_evento("inicio", version=VERSION)
    yield


PASARELA_API_KEY = "a8f5f167f44f4964e6c998dee827110c"

# sin /docs ni /openapi.json: la API no se describe sola a quien no tiene llave
app = FastAPI(
    title="Farmacia - registro de pedidos",
    version=VERSION,
    lifespan=ciclo_vida,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def bitacora(request: Request, call_next):
    inicio = time.perf_counter()
    try:
        respuesta = await call_next(request)
    except Exception as e:
        # un error no controlado igual se registra y sale con los encabezados de seguridad
        registrar_evento("error_interno", ruta=request.url.path, tipo=type(e).__name__)
        respuesta = JSONResponse({"detail": "Error interno"}, status_code=500)
    ms = round((time.perf_counter() - inicio) * 1000, 1)
    registrar_evento("peticion", metodo=request.method, ruta=request.url.path, estado=respuesta.status_code, ms=ms)
    return respuesta


# la pantalla trae Tabler de jsdelivr y usa onclick, por eso el unsafe-inline
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def encabezados_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers["Content-Security-Policy"] = CSP
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    respuesta.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    respuesta.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    return respuesta


def validar_llave(x_api_key: str = Header(default="")):
    esperada = os.environ.get("API_KEY", "")
    # sin llave configurada no se atiende nada
    # se comparan bytes: con texto, compare_digest truena si la llave trae una ñ o un acento
    if not esperada or not hmac.compare_digest(x_api_key.encode(), esperada.encode()):
        raise HTTPException(status_code=401, detail="Llave de acceso inválida")


class Item(BaseModel):
    codigo: str = Field(min_length=2, max_length=10, pattern=r"^[A-Z0-9]+$")
    cantidad: int = Field(gt=0, le=20)


class Pedido(BaseModel):
    telefono: str = Field(pattern=r"^[2-9]\d{7}$")
    items: list[Item] = Field(min_length=1, max_length=15)
    metodo_pago: Literal["efectivo", "tarjeta", "transferencia"]
    token_tarjeta: Optional[str] = Field(default=None, pattern=r"^tok_[A-Za-z0-9]{8,40}$")
    numero_receta: Optional[str] = Field(default=None, pattern=r"^[A-Z]{2}-\d{4,8}$")

    @model_validator(mode="after")
    def tarjeta_con_token(self):
        if self.metodo_pago == "tarjeta" and not self.token_tarjeta:
            raise ValueError("El pago con tarjeta necesita token_tarjeta")
        return self


def enmascarar(telefono):
    return telefono[:2] + "****" + telefono[-2:]


def enmascarar_receta(venta):
    # la receta completa queda en la base para auditoria, pero la API no la devuelve
    receta = venta["numero_receta"]
    return venta | {"numero_receta": receta[:3] + "****" + receta[-2:] if receta else None}


@app.get("/", include_in_schema=False)
def pantalla():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/salud")
def salud():
    return {"estado": "ok", "version": VERSION}


@app.get("/api/v1/productos", dependencies=[Depends(validar_llave)])
def listar_productos():
    with db.abrir() as con:
        filas = con.execute("SELECT * FROM productos ORDER BY nombre").fetchall()
    return [dict(f) | {"requiere_receta": bool(f["requiere_receta"])} for f in filas]


@app.post("/api/v1/ventas", status_code=201, dependencies=[Depends(validar_llave)])
def registrar_venta(
    pedido: Pedido,
    idempotency_key: Optional[str] = Header(default=None, pattern=r"^[A-Za-z0-9-]{8,64}$"),
):
    # si el mismo producto viene en varias lineas se suma antes de revisar existencias
    cantidades: dict[str, int] = {}
    for item in pedido.items:
        cantidades[item.codigo] = cantidades.get(item.codigo, 0) + item.cantidad

    # si la red se cae y la pantalla reintenta con la misma clave, se devuelve el pedido ya guardado
    huella = hashlib.sha256(pedido.model_dump_json().encode()).hexdigest()

    con = db.conectar()
    con.isolation_level = None
    try:
        # bloquea la base mientras se revisa y se descuenta, asi dos ventas a la vez no leen la misma existencia
        con.execute("BEGIN IMMEDIATE")
        if idempotency_key:
            previa = con.execute(
                "SELECT id, total, fecha, huella FROM ventas WHERE clave = ?", (idempotency_key,)
            ).fetchone()
            if previa is not None:
                if previa["huella"] != huella:
                    raise HTTPException(409, "Esa clave ya se usó con otro pedido")
                con.execute("ROLLBACK")
                registrar_evento("venta_repetida", id=previa["id"])
                return {"id": previa["id"], "total": previa["total"], "estado": "APROBADA", "fecha": previa["fecha"]}
        total = Decimal("0")
        lineas = []
        for codigo, cantidad in cantidades.items():
            prod = con.execute("SELECT * FROM productos WHERE codigo = ?", (codigo,)).fetchone()
            if prod is None:
                raise HTTPException(404, f"Producto {codigo} no existe")
            if prod["requiere_receta"] and not pedido.numero_receta:
                raise HTTPException(400, f"{prod['nombre']} solo se vende con receta médica")
            if prod["existencias"] < cantidad:
                raise HTTPException(409, f"No hay suficiente {prod['nombre']}")
            # el precio sale de la base, nunca del cliente
            precio = Decimal(prod["precio"])
            total += precio * cantidad
            lineas.append((codigo, cantidad, str(precio)))

        fecha = datetime.now(timezone.utc).isoformat()
        cur = con.execute(
            "INSERT INTO ventas (telefono, metodo_pago, numero_receta, total, fecha, clave, huella)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                enmascarar(pedido.telefono), pedido.metodo_pago, pedido.numero_receta,
                str(total), fecha, idempotency_key, huella,
            ),
        )
        venta_id = cur.lastrowid
        for codigo, cantidad, precio_unitario in lineas:
            con.execute("INSERT INTO detalle_venta VALUES (?, ?, ?, ?)", (venta_id, codigo, cantidad, precio_unitario))
            con.execute(
                "UPDATE productos SET existencias = existencias - ? WHERE codigo = ? AND existencias >= ?",
                (cantidad, codigo, cantidad),
            )
        con.execute("COMMIT")
    except Exception as e:
        if con.in_transaction:
            con.execute("ROLLBACK")
        if isinstance(e, HTTPException):
            registrar_evento("venta_rechazada", estado=e.status_code, motivo=e.detail)
        raise
    finally:
        con.close()

    registrar_evento("venta_aprobada", id=venta_id, total=str(total), metodo_pago=pedido.metodo_pago)

    return {"id": venta_id, "total": str(total), "estado": "APROBADA", "fecha": fecha}


@app.get("/api/v1/ventas", dependencies=[Depends(validar_llave)])
def ultimas_ventas():
    with db.abrir() as con:
        filas = con.execute(
            "SELECT id, telefono, metodo_pago, numero_receta, total, fecha FROM ventas ORDER BY id DESC LIMIT 10"
        ).fetchall()
    return [enmascarar_receta(dict(f)) for f in filas]


@app.get("/api/v1/ventas/{venta_id}", dependencies=[Depends(validar_llave)])
def obtener_venta(venta_id: int):
    with db.abrir() as con:
        venta = con.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,)).fetchone()
        if venta is None:
            raise HTTPException(404, "Venta no encontrada")
        detalle = con.execute(
            "SELECT codigo, cantidad, precio_unitario FROM detalle_venta WHERE venta_id = ?", (venta_id,)
        ).fetchall()
    return enmascarar_receta(dict(venta)) | {"detalle": [dict(d) for d in detalle]}
