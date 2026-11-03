import os
import sqlite3
from contextlib import contextmanager

from app.catalogo import PRODUCTOS


def ruta_db():
    return os.environ.get("DB_PATH", "farmacia.db")


def conectar():
    con = sqlite3.connect(ruta_db(), timeout=15)
    con.row_factory = sqlite3.Row
    # SQLite trae las claves foraneas apagadas por defecto
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def abrir():
    # el with de sqlite3 solo confirma o deshace, no cierra la conexion
    con = conectar()
    try:
        with con:
            yield con
    finally:
        con.close()


def inicializar():
    with abrir() as con:
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
                fecha TEXT NOT NULL,
                clave TEXT,
                huella TEXT
            );
            CREATE TABLE IF NOT EXISTS detalle_venta (
                venta_id INTEGER NOT NULL REFERENCES ventas(id),
                codigo TEXT NOT NULL REFERENCES productos(codigo),
                cantidad INTEGER NOT NULL,
                precio_unitario TEXT NOT NULL
            );
            """
        )
        # bases creadas antes de la 1.1.0 no tienen las columnas de idempotencia
        columnas = {c["name"] for c in con.execute("PRAGMA table_info(ventas)")}
        if "clave" not in columnas:
            con.execute("ALTER TABLE ventas ADD COLUMN clave TEXT")
            con.execute("ALTER TABLE ventas ADD COLUMN huella TEXT")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ventas_clave ON ventas(clave)")
        for p in PRODUCTOS:
            con.execute(
                "INSERT OR IGNORE INTO productos VALUES (?, ?, ?, ?, ?)",
                (p["codigo"], p["nombre"], p["precio"], p["existencias"], int(p["requiere_receta"])),
            )
