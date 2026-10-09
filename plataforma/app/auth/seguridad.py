"""Primitivas de autenticación: contraseñas, códigos de alta y sesiones.

- Contraseñas con salting y hash BCrypt (Provos y Mazières, 1999).
- Política de NIST SP 800-63B-4: longitud mínima (12 en este proyecto), sin reglas
  de composición, bloqueo de contraseñas comunes y limitación de intentos.
- Sesiones del lado del servidor: el navegador recibe un token aleatorio en una
  cookie HttpOnly, Secure y SameSite=Strict; en la base solo se guarda su SHA-256.
"""

import hashlib
import secrets
from datetime import timedelta

import bcrypt

from .. import config, db
from ..util import ahora, iso, parse_iso

COMUNES = {
    "123456789012", "contraseña123", "contrasena123", "password1234", "qwertyuiop12", "administrador",
    "passwordpassword", "123456123456", "abc123abc123", "guatemala123", "guatemala2026", "umg123456789",
    "iloveyou1234", "1q2w3e4r5t6y", "000000000000", "111111111111", "correos12345", "seguridad123",
    "plataforma123", "operador1234", "admin1234567", "qwerty123456", "welcome12345", "letmein12345",
}
_HASH_FALSO = bcrypt.hashpw(b"valor-de-relleno-para-igualar-tiempos", bcrypt.gensalt(rounds=12))
ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


# ------------------------------------------------------------------ contraseñas
def _b(password: str) -> bytes:
    """BCrypt solo procesa 72 bytes; se trunca de forma explícita y consistente."""
    return password.encode("utf-8")[:72]


def politica(password: str, usuario: str) -> str | None:
    if len(password) < 12:
        return "La contraseña debe tener al menos 12 caracteres"
    if len(password) > 128:
        return "La contraseña no puede superar 128 caracteres"
    baja = password.lower()
    if baja in COMUNES or usuario.lower() in baja or len(set(baja)) < 4:
        return "La contraseña es demasiado común o contiene el nombre de usuario"
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_b(password), bcrypt.gensalt(rounds=12)).decode()


def verificar_password(password: str, h: str | None) -> bool:
    if not h:
        bcrypt.checkpw(_b(password), _HASH_FALSO)  # tiempo constante ante usuarios inexistentes
        return False
    return bcrypt.checkpw(_b(password), h.encode())


# ------------------------------------------------------------------ códigos de alta
def generar_codigo_alta() -> str:
    c = "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(12))
    return f"{c[:4]}-{c[4:8]}-{c[8:]}"


def hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.strip().upper().encode()).hexdigest()


def expiracion_codigo(dias: int = 0) -> str:
    return iso(ahora() + (timedelta(days=dias) if dias else timedelta(hours=config.CODIGO_ALTA_HORAS)))


def codigo_valido(u: dict, codigo: str) -> bool:
    if not u.get("codigo_alta_hash") or not u.get("codigo_alta_expira"):
        return False
    if parse_iso(u["codigo_alta_expira"]) < ahora():
        return False
    return secrets.compare_digest(u["codigo_alta_hash"], hash_codigo(codigo))


# ------------------------------------------------------------------ sesiones
def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def crear_sesion(usuario_id: int, etapa: str, ip: str | None) -> str:
    token = secrets.token_urlsafe(32)
    ts = iso()
    with db.transaccion() as con:
        con.execute("""INSERT INTO sesiones (token_hash, usuario_id, creada, ultimo_uso, etapa, mfa_en, reauth_en, ip)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (_h(token), usuario_id, ts, ts, etapa,
                     ts if etapa == "completa" else None, ts if etapa == "completa" else None, ip))
    return token


def obtener_sesion(token: str | None, tocar: bool = True) -> dict | None:
    """tocar=False: consultas de fondo (WebSocket, sondeos) que no cuentan como actividad del usuario."""
    if not token or len(token) > 100:
        return None
    s = db.uno("""SELECT s.*, u.usuario, u.nombre, u.rol, u.activo FROM sesiones s
                  JOIN usuarios u ON u.id = s.usuario_id WHERE s.token_hash = ?""", (_h(token),))
    if not s or not s["activo"]:
        return None
    limite = config.SESION_INACTIVIDAD_MIN if s["etapa"] == "completa" else 5
    if parse_iso(s["ultimo_uso"]) < ahora() - timedelta(minutes=limite):
        cerrar_sesion(token)
        return None
    if tocar:
        with db.transaccion() as con:
            con.execute("UPDATE sesiones SET ultimo_uso = ? WHERE token_hash = ?", (iso(), _h(token)))
    s["token_hash"] = _h(token)
    return s


def actualizar_sesion(token_hash: str, **campos):
    if not campos:
        return
    columnas = ", ".join(f"{k} = ?" for k in campos)
    with db.transaccion() as con:
        con.execute(f"UPDATE sesiones SET {columnas} WHERE token_hash = ?", (*campos.values(), token_hash))


def cerrar_sesion(token: str):
    with db.transaccion() as con:
        con.execute("DELETE FROM sesiones WHERE token_hash = ?", (_h(token),))


def cerrar_sesiones_de(usuario_id: int):
    with db.transaccion() as con:
        con.execute("DELETE FROM sesiones WHERE usuario_id = ?", (usuario_id,))


def reauth_vigente(s: dict) -> bool:
    return bool(s.get("reauth_en")) and parse_iso(s["reauth_en"]) >= ahora() - timedelta(minutes=config.REAUTH_MIN)
