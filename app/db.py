import os
import sqlite3

from app.catalogo import PRODUCTOS


def ruta_db():
    return os.environ.get("DB_PATH", "farmacia.db")


def conectar():
    con = sqlite3.connect(ruta_db())
    con.row_factory = sqlite3.Row
    return con


def inicializar():
    with conectar() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS productos (
                codigo TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                precio TEXT NOT NULL,
                existencias INTEGER NOT NULL,
                requiere_receta INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telefono TEXT NOT NULL,
                metodo_pago TEXT NOT NULL,
                numero_receta TEXT,
                total TEXT NOT NULL,
                fecha TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS detalle_venta (
                venta_id INTEGER NOT NULL REFERENCES ventas(id),
                codigo TEXT NOT NULL REFERENCES productos(codigo),
                cantidad INTEGER NOT NULL,
                precio_unitario TEXT NOT NULL
            );
            """
        )
        for p in PRODUCTOS:
            con.execute(
                "INSERT OR IGNORE INTO productos VALUES (?, ?, ?, ?, ?)",
                (p["codigo"], p["nombre"], p["precio"], p["existencias"], int(p["requiere_receta"])),
            )
