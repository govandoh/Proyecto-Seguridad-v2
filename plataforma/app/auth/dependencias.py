"""Dependencias de FastAPI para exigir sesión, rol y reautenticación reciente."""

from fastapi import Depends, HTTPException, Request

from . import seguridad

COOKIE = "sid"

# Matriz de permisos (ISO/IEC 27001 5.15 y 5.18; NIST SP 800-53 AC-6 mínimo privilegio).
PERMISOS = {
    "ver":        {"operador", "auditor", "administrador"},
    "acusar":     {"operador", "administrador"},
    "simular":    {"operador", "administrador"},
    "auditar":    {"auditor", "administrador"},
    "administrar": {"administrador"},
}


def sesion_opcional(request: Request) -> dict | None:
    # Las consultas automáticas del tablero envían X-Fondo: 1 y no renuevan la inactividad.
    fondo = request.headers.get("x-fondo") == "1"
    return seguridad.obtener_sesion(request.cookies.get(COOKIE), tocar=not fondo)


def sesion_completa(request: Request) -> dict:
    s = sesion_opcional(request)
    if not s:
        raise HTTPException(401, "Sesión requerida")
    if s["etapa"] != "completa":
        raise HTTPException(401, "Falta el segundo factor")
    return s


def permiso(accion: str):
    def _dep(s: dict = Depends(sesion_completa)) -> dict:
        if s["rol"] not in PERMISOS[accion]:
            raise HTTPException(403, "Su rol no permite esta acción")
        return s
    return _dep


def permiso_con_reauth(accion: str):
    """Acciones sensibles: el administrador debe haber firmado un desafío en los últimos minutos."""
    base = permiso(accion)

    def _dep(s: dict = Depends(base)) -> dict:
        if not seguridad.reauth_vigente(s):
            raise HTTPException(401, detail={"reauth": True, "mensaje": "Confirme su identidad con la passkey"})
        return s
    return _dep


def actor(s: dict) -> str:
    return f"{s['rol']}:{s['usuario']}"
