"""Datos iniciales: administrador con código de alta y tarjetas de la demostración."""

import logging
import secrets

import bcrypt

from . import bitacora, config, db
from .auth import seguridad
from .util import iso

log = logging.getLogger("seed")

# PIN de demostración. El PIN de coacción es el mismo con el último dígito + 1.
TARJETAS_DEMO = [
    ("C-1001", "Técnico de turno A", "1357", "activa"),
    ("C-1002", "Custodio de la sala", "2468", "activa"),
    ("C-1003", "Exempleado de mantenimiento", "1111", "revocada"),
]


def sembrar():
    if not db.uno("SELECT id FROM usuarios WHERE usuario = ?", (config.ADMIN_USUARIO,)):
        codigo = config.ADMIN_CODIGO_ALTA or seguridad.generar_codigo_alta()
        with db.transaccion() as con:
            con.execute("""INSERT INTO usuarios (usuario, nombre, rol, creado, codigo_alta_hash, codigo_alta_expira)
                           VALUES (?,?,?,?,?,?)""",
                        (config.ADMIN_USUARIO, "Administrador de la plataforma", "administrador", iso(),
                         seguridad.hash_codigo(codigo), seguridad.expiracion_codigo(dias=7)))
        bitacora.registrar("auth", "usuario_alta", "informativo",
                           f"Se creó la cuenta inicial {config.ADMIN_USUARIO} con código de alta de un solo uso",
                           "5.16", "NIST SP 800-63B-4")
        log.warning("=" * 64)
        log.warning(" CÓDIGO DE ALTA DEL ADMINISTRADOR  usuario=%s  código=%s", config.ADMIN_USUARIO, codigo)
        log.warning(" Úselo una sola vez en https://%s/alta (vence en 7 días)", config.RP_ID)
        log.warning("=" * 64)
        try:
            (config.DATOS_DIR / "CODIGO_ALTA_ADMIN.txt").write_text(
                f"usuario={config.ADMIN_USUARIO}\ncodigo={codigo}\n", encoding="utf-8")
        except OSError:
            pass

    if db.uno("SELECT COUNT(*) AS n FROM tarjetas")["n"] == 0:
        with db.transaccion() as con:
            for tarjeta, titular, pin, estado in TARJETAS_DEMO:
                h = bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=10)).decode()
                con.execute("INSERT INTO tarjetas VALUES (?,?,?,?,?)", (tarjeta, titular, h, estado, "SALA-SERVIDORES"))


def token() -> str:
    return secrets.token_urlsafe(32)
