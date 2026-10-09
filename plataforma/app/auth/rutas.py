"""Rutas de autenticación multifactor: contraseña + passkey WebAuthn.

Flujos
  Alta:   código de un solo uso -> contraseña -> registro de passkey -> sesión completa
  Login:  contraseña -> desafío WebAuthn firmado por la passkey -> sesión completa
  Reauth: nuevo desafío firmado antes de una acción administrativa

La passkey puede estar en el teléfono (biometría verificada en el dispositivo,
flujo con QR y Bluetooth), en una llave FIDO2, en Windows Hello o en el
autenticador virtual de Chrome para la demostración. El servidor solo recibe
la firma: la plantilla biométrica nunca sale del dispositivo.
"""

import json
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, AuthenticatorTransport, PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement, UserVerificationRequirement)

from .. import bitacora, config, db
from ..util import ahora, iso, parse_iso
from . import seguridad
from .dependencias import COOKIE, actor, sesion_completa, sesion_opcional

log = logging.getLogger("auth")
router = APIRouter(prefix="/api/auth", tags=["autenticación"])
MODULO = "auth"


class Login(BaseModel):
    usuario: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class Alta(BaseModel):
    usuario: str = Field(min_length=1, max_length=40)
    codigo: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=1, max_length=128)


class Credencial(BaseModel):
    credencial: dict
    nombre: str | None = Field(default=None, max_length=40)


def _poner_cookie(resp: Response, token: str):
    resp.set_cookie(COOKIE, token, httponly=True, secure=config.COOKIE_SECURE, samesite="strict", path="/")


def _ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()


def _transportes(texto: str | None) -> list[AuthenticatorTransport] | None:
    validos = {t.value for t in AuthenticatorTransport}
    lista = [AuthenticatorTransport(t) for t in json.loads(texto or "[]") if t in validos]
    return lista or None


def _credenciales_activas(usuario_id: int) -> list[dict]:
    return db.consultar("SELECT * FROM credenciales WHERE usuario_id = ? AND revocada = 0", (usuario_id,))


# ------------------------------------------------------------------ primer factor
@router.post("/login")
def login(datos: Login, request: Request, response: Response):
    usuario = datos.usuario.strip().lower()
    u = db.uno("SELECT * FROM usuarios WHERE usuario = ?", (usuario,))
    generico = HTTPException(401, "Usuario o contraseña incorrectos")
    if u and u["bloqueado_hasta"] and parse_iso(u["bloqueado_hasta"]) > ahora():
        seguridad.verificar_password(datos.password, None)
        raise HTTPException(429, "Cuenta bloqueada temporalmente por intentos fallidos")
    if not u or not u["activo"] or not seguridad.verificar_password(datos.password, u["password_hash"] if u else None):
        if u:
            _fallo(u, request)
        else:
            bitacora.registrar(MODULO, "auth_fallida", "advertencia", "Intento de inicio de sesión con un usuario inexistente",
                               "8.5", "NIST SP 800-63B-4", actor="anonimo", datos={"ip": _ip(request)})
        raise generico
    if not _credenciales_activas(u["id"]):
        raise HTTPException(403, "La cuenta no tiene passkey registrada: use su código de alta")
    with db.transaccion() as con:
        con.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = ?", (u["id"],))
    token = seguridad.crear_sesion(u["id"], "mfa_pendiente", _ip(request))
    _poner_cookie(response, token)
    return {"siguiente": "passkey"}


def _fallo(u: dict, request: Request):
    n = u["intentos_fallidos"] + 1
    bloqueo = None
    if n >= config.MAX_INTENTOS:
        bloqueo = iso(ahora() + timedelta(minutes=config.BLOQUEO_MIN))
        n = 0
    with db.transaccion() as con:
        con.execute("UPDATE usuarios SET intentos_fallidos = ?, bloqueado_hasta = ? WHERE id = ?", (n, bloqueo, u["id"]))
    if bloqueo:
        bitacora.registrar(MODULO, "auth_bloqueo", "critico",
                           f"Cuenta {u['usuario']} bloqueada {config.BLOQUEO_MIN} min tras {config.MAX_INTENTOS} intentos fallidos",
                           "8.5", "NIST SP 800-63B-4", actor="anonimo", datos={"ip": _ip(request)})
    else:
        bitacora.registrar(MODULO, "auth_fallida", "advertencia", f"Contraseña incorrecta para {u['usuario']}",
                           "8.5", "NIST SP 800-63B-4", actor="anonimo", datos={"ip": _ip(request)})


@router.post("/alta")
def alta(datos: Alta, request: Request, response: Response):
    usuario = datos.usuario.strip().lower()
    u = db.uno("SELECT * FROM usuarios WHERE usuario = ?", (usuario,))
    if not u or not u["activo"] or not seguridad.codigo_valido(u, datos.codigo):
        bitacora.registrar(MODULO, "alta_fallida", "advertencia", f"Código de alta inválido o vencido para {usuario}",
                           "5.16", "NIST SP 800-63B-4", actor="anonimo", datos={"ip": _ip(request)})
        raise HTTPException(401, "Código de alta inválido o vencido")
    error = seguridad.politica(datos.password, usuario)
    if error:
        raise HTTPException(422, error)
    with db.transaccion() as con:
        con.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (seguridad.hash_password(datos.password), u["id"]))
    token = seguridad.crear_sesion(u["id"], "enrolamiento", _ip(request))
    _poner_cookie(response, token)
    return {"siguiente": "registrar_passkey"}


# ------------------------------------------------------------------ registro de passkey
@router.post("/passkey/registro/opciones")
def registro_opciones(request: Request):
    s = sesion_opcional(request)
    if not s or not (s["etapa"] == "enrolamiento" or (s["etapa"] == "completa" and seguridad.reauth_vigente(s))):
        raise HTTPException(401, detail={"reauth": bool(s and s["etapa"] == "completa"),
                                         "mensaje": "Se requiere alta vigente o reautenticación"})
    existentes = _credenciales_activas(s["usuario_id"])
    opciones = generate_registration_options(
        rp_id=config.RP_ID, rp_name=config.RP_NAME, user_name=s["usuario"], user_display_name=s["nombre"],
        user_id=f"u{s['usuario_id']}".encode(),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"])) for c in existentes],
    )
    seguridad.actualizar_sesion(s["token_hash"], desafio=bytes_to_base64url(opciones.challenge), desafio_tipo="registro")
    return json.loads(options_to_json(opciones))


@router.post("/passkey/registro/verificar")
def registro_verificar(datos: Credencial, request: Request):
    s = sesion_opcional(request)
    if not s or s.get("desafio_tipo") != "registro" or not s.get("desafio"):
        raise HTTPException(401, "No hay un registro en curso")
    try:
        v = verify_registration_response(
            credential=datos.credencial, expected_challenge=base64url_to_bytes(s["desafio"]),
            expected_rp_id=config.RP_ID, expected_origin=config.ORIGENES, require_user_verification=True)
    except Exception as e:
        bitacora.registrar(MODULO, "passkey_rechazada", "advertencia", f"Registro de passkey rechazado para {s['usuario']}: {e}",
                           "8.5", "WebAuthn", actor=f"usuario:{s['usuario']}")
        raise HTTPException(400, "La passkey no pudo verificarse")
    finally:
        seguridad.actualizar_sesion(s["token_hash"], desafio=None, desafio_tipo=None)
    transportes = (datos.credencial.get("response") or {}).get("transports") or []
    nombre = (datos.nombre or "").strip() or ("Passkey sincronizada" if v.credential_device_type == "multi_device" else "Llave o dispositivo")
    with db.transaccion() as con:
        con.execute("""INSERT INTO credenciales (usuario_id, credential_id, public_key, sign_count, transports, tipo_disp, nombre, creada)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (s["usuario_id"], bytes_to_base64url(v.credential_id), v.credential_public_key, v.sign_count,
                     json.dumps(transportes), v.credential_device_type.value, nombre[:40], iso()))
        if s["etapa"] == "enrolamiento":
            con.execute("UPDATE usuarios SET codigo_alta_hash = NULL, codigo_alta_expira = NULL WHERE id = ?", (s["usuario_id"],))
    if s["etapa"] == "enrolamiento":
        seguridad.actualizar_sesion(s["token_hash"], etapa="completa", mfa_en=iso(), reauth_en=iso())
    bitacora.registrar(MODULO, "passkey_registrada", "informativo",
                       f"{s['usuario']} registró la passkey '{nombre[:40]}' ({', '.join(transportes) or 'sin transporte declarado'})",
                       "5.16; 8.5", "NIST SP 800-63B-4; WebAuthn", actor=f"{s['rol']}:{s['usuario']}",
                       datos={"tipo": v.credential_device_type.value,"respaldo": v.credential_backed_up, "transportes": transportes})
    return {"ok": True}


# ------------------------------------------------------------------ segundo factor y reautenticación
@router.post("/passkey/login/opciones")
def login_opciones(request: Request):
    s = sesion_opcional(request)
    if not s or s["etapa"] not in ("mfa_pendiente", "completa"):
        raise HTTPException(401, "Inicie sesión con su contraseña")
    creds = _credenciales_activas(s["usuario_id"])
    opciones = generate_authentication_options(
        rp_id=config.RP_ID, user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"]),
                                                         transports=_transportes(c["transports"]))
                           for c in creds])
    tipo = "login" if s["etapa"] == "mfa_pendiente" else "reauth"
    seguridad.actualizar_sesion(s["token_hash"], desafio=bytes_to_base64url(opciones.challenge), desafio_tipo=tipo)
    return json.loads(options_to_json(opciones))


@router.post("/passkey/login/verificar")
def login_verificar(datos: Credencial, request: Request):
    s = sesion_opcional(request)
    if not s or s.get("desafio_tipo") not in ("login", "reauth") or not s.get("desafio"):
        raise HTTPException(401, "No hay un desafío en curso")
    cred_id = str(datos.credencial.get("id", ""))
    c = db.uno("SELECT * FROM credenciales WHERE credential_id = ? AND usuario_id = ? AND revocada = 0",
               (cred_id, s["usuario_id"]))
    try:
        if not c:
            raise ValueError("credencial desconocida o revocada")
        v = verify_authentication_response(
            credential=datos.credencial, expected_challenge=base64url_to_bytes(s["desafio"]),
            expected_rp_id=config.RP_ID, expected_origin=config.ORIGENES,
            credential_public_key=c["public_key"], credential_current_sign_count=c["sign_count"],
            require_user_verification=True)
    except Exception as e:
        seguridad.actualizar_sesion(s["token_hash"], desafio=None, desafio_tipo=None)
        bitacora.registrar(MODULO, "auth_fallida", "advertencia", f"Firma de passkey rechazada para {s['usuario']}: {e}",
                           "8.5", "WebAuthn", actor=f"usuario:{s['usuario']}")
        raise HTTPException(401, "La passkey no pudo verificarse")
    with db.transaccion() as con:
        con.execute("UPDATE credenciales SET sign_count = ?, ultimo_uso = ? WHERE id = ?", (v.new_sign_count, iso(), c["id"]))
    tipo = s["desafio_tipo"]
    if tipo == "login":
        seguridad.actualizar_sesion(s["token_hash"], etapa="completa", mfa_en=iso(), reauth_en=iso(), desafio=None, desafio_tipo=None)
        bitacora.registrar(MODULO, "auth_exitosa", "informativo",
                           f"{s['usuario']} inició sesión con contraseña y passkey '{c['nombre']}'",
                           "8.5", "NIST SP 800-63B-4", actor=f"{s['rol']}:{s['usuario']}", datos={"ip": _ip(request)})
    else:
        seguridad.actualizar_sesion(s["token_hash"], reauth_en=iso(), desafio=None, desafio_tipo=None)
        bitacora.registrar(MODULO, "reautenticacion", "informativo", f"{s['usuario']} confirmó su identidad con la passkey",
                           "8.5", "NIST SP 800-63B-4", actor=f"{s['rol']}:{s['usuario']}")
    return {"ok": True, "etapa": "completa"}


# ------------------------------------------------------------------ sesión
@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        seguridad.cerrar_sesion(token)
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/yo")
def yo(request: Request):
    s = sesion_opcional(request)
    if not s:
        raise HTTPException(401, "Sin sesión")
    creds = db.consultar("""SELECT id, nombre, tipo_disp, transports, creada, ultimo_uso FROM credenciales
                            WHERE usuario_id = ? AND revocada = 0 ORDER BY id""", (s["usuario_id"],))
    return {"usuario": s["usuario"], "nombre": s["nombre"], "rol": s["rol"], "etapa": s["etapa"],
            "reauth_vigente": seguridad.reauth_vigente(s), "passkeys": creds,
            "inactividad_min": config.SESION_INACTIVIDAD_MIN}


@router.delete("/passkeys/{cred_id}")
def borrar_passkey(cred_id: int, s: dict = Depends(sesion_completa)):
    if not seguridad.reauth_vigente(s):
        raise HTTPException(401, detail={"reauth": True, "mensaje": "Confirme su identidad con la passkey"})
    activas = _credenciales_activas(s["usuario_id"])
    if len(activas) <= 1:
        raise HTTPException(409, "No puede eliminar su única passkey")
    if not any(c["id"] == cred_id for c in activas):
        raise HTTPException(404, "Passkey no encontrada")
    with db.transaccion() as con:
        con.execute("UPDATE credenciales SET revocada = 1 WHERE id = ?", (cred_id,))
    bitacora.registrar(MODULO, "passkey_revocada", "advertencia", f"{s['usuario']} revocó una de sus passkeys",
                       "5.18", "NIST SP 800-63B-4", actor=actor(s))
    return {"ok": True}

