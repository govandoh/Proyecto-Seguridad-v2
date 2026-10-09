"""Base de datos SQLite: esquema, conexión y datos iniciales.

La tabla `eventos` es de solo inserción. Un acuse o una corrección se registran
como un evento nuevo que referencia al original (campo ref_id), de modo que la
cadena de hash nunca necesita reescribirse.
"""

import sqlite3
import threading
from contextlib import contextmanager

from . import config

_lock = threading.RLock()

ESQUEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS eventos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    modulo        TEXT NOT NULL,
    tipo          TEXT NOT NULL,
    severidad     TEXT NOT NULL CHECK (severidad IN ('informativo','advertencia','critico')),
    descripcion   TEXT NOT NULL,
    control_iso   TEXT NOT NULL DEFAULT '',
    norma         TEXT NOT NULL DEFAULT '',
    actor         TEXT NOT NULL,
    ref_id        INTEGER,
    datos         TEXT NOT NULL DEFAULT '{}',
    hash_anterior TEXT NOT NULL,
    hash          TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_eventos_modulo ON eventos(modulo);
CREATE INDEX IF NOT EXISTS ix_eventos_ref ON eventos(ref_id);

CREATE TABLE IF NOT EXISTS inventario (
    ip         TEXT PRIMARY KEY,
    nombre     TEXT NOT NULL UNIQUE,
    tipo       TEXT NOT NULL,
    switch     TEXT NOT NULL,
    mac        TEXT,
    poe        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cargas (
    equipo     TEXT PRIMARY KEY,
    potencia_w REAL NOT NULL,
    critica    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS usuarios (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario             TEXT NOT NULL UNIQUE,
    nombre              TEXT NOT NULL,
    rol                 TEXT NOT NULL CHECK (rol IN ('operador','auditor','administrador')),
    password_hash       TEXT,
    activo              INTEGER NOT NULL DEFAULT 1,
    creado              TEXT NOT NULL,
    codigo_alta_hash    TEXT,
    codigo_alta_expira  TEXT,
    intentos_fallidos   INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta     TEXT
);

CREATE TABLE IF NOT EXISTS credenciales (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id     INTEGER NOT NULL REFERENCES usuarios(id),
    credential_id  TEXT NOT NULL UNIQUE,
    public_key     BLOB NOT NULL,
    sign_count     INTEGER NOT NULL DEFAULT 0,
    transports     TEXT NOT NULL DEFAULT '[]',
    tipo_disp      TEXT NOT NULL DEFAULT '',
    nombre         TEXT NOT NULL,
    creada         TEXT NOT NULL,
    ultimo_uso     TEXT,
    revocada       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sesiones (
    token_hash     TEXT PRIMARY KEY,
    usuario_id     INTEGER NOT NULL REFERENCES usuarios(id),
    creada         TEXT NOT NULL,
    ultimo_uso     TEXT NOT NULL,
    etapa          TEXT NOT NULL CHECK (etapa IN ('mfa_pendiente','enrolamiento','completa')),
    mfa_en         TEXT,
    reauth_en      TEXT,
    desafio        TEXT,
    desafio_tipo   TEXT,
    ip             TEXT
);

CREATE TABLE IF NOT EXISTS tarjetas (
    tarjeta    TEXT PRIMARY KEY,
    titular    TEXT NOT NULL,
    pin_hash   TEXT NOT NULL,
    estado     TEXT NOT NULL CHECK (estado IN ('activa','revocada')),
    zonas      TEXT NOT NULL DEFAULT 'SALA-SERVIDORES'
);

CREATE TABLE IF NOT EXISTS lecturas (
    ts      TEXT NOT NULL,
    sensor  TEXT NOT NULL,
    valor   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_lecturas ON lecturas(sensor, ts);

CREATE TABLE IF NOT EXISTS energia_muestras (
    ts          TEXT NOT NULL,
    estado      TEXT NOT NULL,
    carga_pct   REAL,
    runtime_min REAL
);
"""

INVENTARIO_INICIAL = [
    # ip, nombre, tipo, switch, mac, poe
    ("10.10.10.51", "SRV-TRAZA", "servidor", "SW-CIRC-A", None, 0),
    ("10.10.10.52", "CAM-01", "camara", "SW-CIRC-A", None, 1),
    ("10.10.10.53", "CAM-02", "camara", "SW-CIRC-A", None, 1),
    ("10.10.10.54", "LECT-01", "lectora", "SW-CIRC-B", None, 1),
    ("10.10.10.55", "CAM-03", "camara", "SW-CIRC-B", None, 1),
]

# Inventario de cargas del documento (Tabla 13): 566.2 W en total.
CARGAS_INICIALES = [
    ("SRV-TRAZA", 400.0, 1),
    ("SW-CIRC-A", 60.0, 1),
    ("SW-CIRC-B", 60.0, 1),
    ("CAM-01", 15.4, 0),
    ("CAM-02", 15.4, 0),
    ("LECT-01", 15.4, 1),
]


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH, timeout=10, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def transaccion():
    """Conexión con bloqueo global: SQLite admite un solo escritor a la vez."""
    with _lock:
        con = conectar()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def consultar(sql: str, params=()) -> list[dict]:
    con = conectar()
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def uno(sql: str, params=()) -> dict | None:
    filas = consultar(sql, params)
    return filas[0] if filas else None


def init_db():
    with transaccion() as con:
        con.executescript(ESQUEMA)
        if con.execute("SELECT COUNT(*) FROM inventario").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO inventario (ip, nombre, tipo, switch, mac, poe) VALUES (?,?,?,?,?,?)",
                INVENTARIO_INICIAL,
            )
        if con.execute("SELECT COUNT(*) FROM cargas").fetchone()[0] == 0:
            con.executemany("INSERT INTO cargas VALUES (?,?,?)", CARGAS_INICIALES)
        # Passkeys guardadas con str(enum) en Python 3.12 ("CredentialDeviceType.MULTI_DEVICE").
        con.execute("""UPDATE credenciales SET tipo_disp = lower(substr(tipo_disp, 22))
                       WHERE tipo_disp LIKE 'CredentialDeviceType.%'""")
