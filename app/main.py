import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from app import db

@asynccontextmanager
async def ciclo_vida(app):
    db.inicializar()
    yield


app = FastAPI(title="Farmacia - registro de pedidos", version="0.2.0", lifespan=ciclo_vida)


def validar_llave(x_api_key: str = Header(default="")):
    esperada = os.environ.get("API_KEY", "")
    # sin llave configurada no se atiende nada
    if not esperada or not hmac.compare_digest(x_api_key, esperada):
        raise HTTPException(status_code=401, detail="Llave de acceso inválida")


class Item(BaseModel):
    codigo: str = Field(min_length=2, max_length=10, pattern=r"^[A-Z0-9]+$")
    cantidad: int = Field(gt=0, le=20)


class Pedido(BaseModel):
    telefono: str = Field(pattern=r"^[2-7]\d{7}$")
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


@app.get("/", include_in_schema=False)
def pantalla():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.get("/api/v1/productos", dependencies=[Depends(validar_llave)])
def listar_productos():
    with db.conectar() as con:
        filas = con.execute("SELECT * FROM productos ORDER BY nombre").fetchall()
    return [dict(f) | {"requiere_receta": bool(f["requiere_receta"])} for f in filas]


@app.post("/api/v1/ventas", status_code=201, dependencies=[Depends(validar_llave)])
def registrar_venta(pedido: Pedido):
    with db.conectar() as con:
        total = Decimal("0")
        lineas = []
        for item in pedido.items:
            prod = con.execute("SELECT * FROM productos WHERE codigo = ?", (item.codigo,)).fetchone()
            if prod is None:
                raise HTTPException(404, f"Producto {item.codigo} no existe")
            if prod["requiere_receta"] and not pedido.numero_receta:
                raise HTTPException(400, f"{prod['nombre']} solo se vende con receta médica")
            if prod["existencias"] < item.cantidad:
                raise HTTPException(409, f"No hay suficiente {prod['nombre']}")
            # el precio sale de la base, nunca del cliente
            precio = Decimal(prod["precio"])
            total += precio * item.cantidad
            lineas.append((item.codigo, item.cantidad, str(precio)))

        fecha = datetime.now(timezone.utc).isoformat()
        cur = con.execute(
            "INSERT INTO ventas (telefono, metodo_pago, numero_receta, total, fecha) VALUES (?, ?, ?, ?, ?)",
            (enmascarar(pedido.telefono), pedido.metodo_pago, pedido.numero_receta, str(total), fecha),
        )
        venta_id = cur.lastrowid
        for codigo, cantidad, precio in lineas:
            con.execute("INSERT INTO detalle_venta VALUES (?, ?, ?, ?)", (venta_id, codigo, cantidad, precio))
            con.execute("UPDATE productos SET existencias = existencias - ? WHERE codigo = ?", (cantidad, codigo))

    return {"id": venta_id, "total": str(total), "estado": "APROBADA", "fecha": fecha}


@app.get("/api/v1/ventas", dependencies=[Depends(validar_llave)])
def ultimas_ventas():
    with db.conectar() as con:
        filas = con.execute(
            "SELECT id, telefono, metodo_pago, numero_receta, total, fecha FROM ventas ORDER BY id DESC LIMIT 10"
        ).fetchall()
    return [dict(f) for f in filas]


@app.get("/api/v1/ventas/{venta_id}", dependencies=[Depends(validar_llave)])
def obtener_venta(venta_id: int):
    with db.conectar() as con:
        venta = con.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,)).fetchone()
        if venta is None:
            raise HTTPException(404, "Venta no encontrada")
        detalle = con.execute(
            "SELECT codigo, cantidad, precio_unitario FROM detalle_venta WHERE venta_id = ?", (venta_id,)
        ).fetchall()
    return dict(venta) | {"detalle": [dict(d) for d in detalle]}
