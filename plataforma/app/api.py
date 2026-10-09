"""API del tablero: estado, bitácora, acuses, indicadores, consola de simulación y administración."""

import csv
import io
import ipaddress

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import bitacora, config, db, indicadores, procedimientos
from .auth import seguridad
from .auth.dependencias import actor, permiso, permiso_con_reauth
from .bus import bus
from .modulos import acceso, ambiente, energia, red
from .util import iso

router = APIRouter(prefix="/api", tags=["tablero"])


# ------------------------------------------------------------------ estado y bitácora
@router.get("/estado")
def estado(s: dict = Depends(permiso("ver"))):
    pend = bitacora.pendientes_de_acuse()
    return {"red": red.estado(), "energia": energia.estado(), "ambiente": ambiente.estado(),
            "acceso": acceso.estado(), "pendientes": pend, "usuario": {"usuario": s["usuario"], "rol": s["rol"]}}


@router.get("/eventos")
def eventos(limite: int = Query(200, ge=1, le=2000), modulo: str | None = Query(None, max_length=20),
            severidad: str | None = Query(None, max_length=12), desde_id: int | None = None,
            _s: dict = Depends(permiso("ver"))):
    return bitacora.listar(limite, modulo, severidad, desde_id)


class Acuse(BaseModel):
    nota: str = Field(default="", max_length=300)


@router.post("/eventos/{evento_id}/acuse")
def acusar(evento_id: int, datos: Acuse, s: dict = Depends(permiso("acusar"))):
    e = db.uno("SELECT * FROM eventos WHERE id = ?", (evento_id,))
    if not e or e["severidad"] != "critico":
        raise HTTPException(404, "Alerta crítica no encontrada")
    if db.uno("SELECT id FROM eventos WHERE tipo = 'acuse' AND ref_id = ?", (evento_id,)):
        raise HTTPException(409, "La alerta ya tiene acuse")
    nota = datos.nota.strip()
    return bitacora.registrar(e["modulo"], "acuse", "informativo",
                              f"Acuse de la alerta #{evento_id} ({e['tipo']}){': ' + nota if nota else ''}",
                              "5.26", "ISO/IEC 27001 7.4", actor=actor(s), ref_id=evento_id,
                              datos={"nota": nota, "procedimiento": procedimientos.para(e["tipo"])["titulo"]})


@router.get("/procedimientos/{tipo}")
def procedimiento(tipo: str, _s: dict = Depends(permiso("ver"))):
    return procedimientos.para(tipo[:40])


@router.get("/bitacora/verificar")
def verificar(s: dict = Depends(permiso("ver"))):
    r = bitacora.verificar()
    bitacora.registrar("bitacora", "verificacion_cadena", "informativo" if r["integra"] else "critico",
                       f"Verificación de la cadena de hash: {'íntegra' if r['integra'] else 'ROTA en el evento #' + str(r['primer_error_id'])} ({r['total']} eventos)",
                       "8.15", "NIST SP 800-53 AU-9", actor=actor(s), datos=r)
    return r


@router.get("/bitacora/exportar.csv")
def exportar(s: dict = Depends(permiso("auditar"))):
    filas = db.consultar("SELECT * FROM eventos ORDER BY id")
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["id", "ts", "modulo", "tipo", "severidad", "descripcion", "control_iso", "norma", "actor", "ref_id",
            "datos", "hash_anterior", "hash"]
    w.writerow(cols)
    for f in filas:
        w.writerow([f[c] for c in cols])
    bitacora.registrar("bitacora", "exportacion", "informativo", f"Exportación de la bitácora completa ({len(filas)} eventos)",
                       "8.15", "", actor=actor(s))
    nombre = f"bitacora_{iso()[:19].replace(':', '')}.csv"
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/historial/{modulo}")
def historial(modulo: str, minutos: int = Query(30, ge=1, le=1440), _s: dict = Depends(permiso("ver"))):
    if modulo == "ambiente":
        return ambiente.historial(minutos)
    if modulo == "energia":
        return energia.historial(minutos)
    raise HTTPException(404, "Historial no disponible")


@router.get("/indicadores")
def kpis(_s: dict = Depends(permiso("ver"))):
    return indicadores.calcular()


# ------------------------------------------------------------------ consola de simulación
COMANDOS = {
    "ups": {"corte_acometida", "retorno_acometida", "falla_planta", "reparar_planta", "prueba_mensual", "fijar_arranque"},
    "ambiente": {"falla_clima", "restaurar_clima", "fijar", "liberar", "humo", "abortar_supresion", "restablecer_humo",
                 "silenciar", "reactivar"},
    "puerta": {"leer", "forzar", "mantener"},
    "red": {"apagar_switch", "encender_switch", "conectar_intruso", "desconectar_intruso", "sustituir", "restaurar"},
}


class Comando(BaseModel):
    accion: str = Field(max_length=30)
    sensor: str | None = Field(default=None, max_length=24)
    valor: float | None = Field(default=None, ge=-10, le=60)
    segundos: float | None = Field(default=None, ge=0.5, le=60)
    tarjeta: str | None = Field(default=None, max_length=16, pattern=r"^[A-Z0-9-]*$")
    pin: str | None = Field(default=None, max_length=8, pattern=r"^[0-9]*$")
    switch: str | None = Field(default=None, max_length=12)
    nombre: str | None = Field(default=None, max_length=24)


@router.post("/sim/{dispositivo}")
def simular(dispositivo: str, c: Comando, s: dict = Depends(permiso("simular"))):
    if dispositivo not in COMANDOS or c.accion not in COMANDOS[dispositivo]:
        raise HTTPException(400, "Comando no permitido")
    carga = {k: v for k, v in c.model_dump().items() if v is not None}
    carga["actor"] = actor(s)
    bus.publicar(f"dc/cmd/{dispositivo}", carga)
    visible = {k: v for k, v in carga.items() if k != "pin"}
    bitacora.registrar("simulacion", "comando_simulado", "informativo",
                       f"Evento inyectado en {dispositivo}: {c.accion}", "", "", actor=actor(s), datos=visible)
    return {"ok": True}


# ------------------------------------------------------------------ administración
admin = APIRouter(prefix="/api/admin", tags=["administración"])


class NuevoUsuario(BaseModel):
    usuario: str = Field(min_length=3, max_length=30, pattern=r"^[a-z][a-z0-9._-]+$")
    nombre: str = Field(min_length=3, max_length=60)
    rol: str = Field(pattern=r"^(operador|auditor|administrador)$")


@admin.get("/usuarios")
def usuarios(_s: dict = Depends(permiso("administrar"))):
    return db.consultar("""SELECT u.id, u.usuario, u.nombre, u.rol, u.activo, u.creado,
                                  (u.codigo_alta_hash IS NOT NULL) AS alta_pendiente, u.bloqueado_hasta,
                                  (SELECT COUNT(*) FROM credenciales c WHERE c.usuario_id = u.id AND c.revocada = 0) AS passkeys
                           FROM usuarios u ORDER BY u.id""")


@admin.post("/usuarios")
def crear_usuario(d: NuevoUsuario, s: dict = Depends(permiso_con_reauth("administrar"))):
    if db.uno("SELECT id FROM usuarios WHERE usuario = ?", (d.usuario,)):
        raise HTTPException(409, "El usuario ya existe")
    codigo = seguridad.generar_codigo_alta()
    with db.transaccion() as con:
        con.execute("""INSERT INTO usuarios (usuario, nombre, rol, creado, codigo_alta_hash, codigo_alta_expira)
                       VALUES (?,?,?,?,?,?)""", (d.usuario, d.nombre.strip(), d.rol, iso(),
                                                  seguridad.hash_codigo(codigo), seguridad.expiracion_codigo()))
    bitacora.registrar("auth", "usuario_alta", "informativo", f"Alta de {d.usuario} con rol {d.rol}; código de un solo uso emitido",
                       "5.16", "NIST SP 800-63B-4", actor=actor(s), datos={"usuario": d.usuario, "rol": d.rol})
    return {"usuario": d.usuario, "codigo_alta": codigo, "vence_horas": config.CODIGO_ALTA_HORAS}


@admin.post("/usuarios/{uid}/restablecer")
def restablecer(uid: int, s: dict = Depends(permiso_con_reauth("administrar"))):
    u = db.uno("SELECT * FROM usuarios WHERE id = ? AND activo = 1", (uid,))
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    codigo = seguridad.generar_codigo_alta()
    with db.transaccion() as con:
        n = con.execute("UPDATE credenciales SET revocada = 1 WHERE usuario_id = ? AND revocada = 0", (uid,)).rowcount
        con.execute("""UPDATE usuarios SET password_hash = NULL, codigo_alta_hash = ?, codigo_alta_expira = ?,
                       intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = ?""",
                    (seguridad.hash_codigo(codigo), seguridad.expiracion_codigo(), uid))
    seguridad.cerrar_sesiones_de(uid)
    bitacora.registrar("auth", "usuario_restablecido", "advertencia",
                       f"Se restableció el alta de {u['usuario']}: {n} passkeys revocadas y nuevo código emitido",
                       "5.18", "NIST SP 800-63B-4", actor=actor(s), datos={"usuario": u["usuario"], "credenciales_revocadas": n})
    return {"usuario": u["usuario"], "codigo_alta": codigo}


@admin.post("/usuarios/{uid}/baja")
def baja(uid: int, s: dict = Depends(permiso_con_reauth("administrar"))):
    if uid == s["usuario_id"]:
        raise HTTPException(409, "No puede darse de baja a sí mismo")
    u = db.uno("SELECT * FROM usuarios WHERE id = ? AND activo = 1", (uid,))
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    with db.transaccion() as con:
        n = con.execute("UPDATE credenciales SET revocada = 1 WHERE usuario_id = ? AND revocada = 0", (uid,)).rowcount
        con.execute("UPDATE usuarios SET activo = 0, codigo_alta_hash = NULL WHERE id = ?", (uid,))
    seguridad.cerrar_sesiones_de(uid)
    bitacora.registrar("auth", "usuario_baja", "advertencia",
                       f"Baja de {u['usuario']}: {n} passkeys revocadas y sesiones cerradas en el mismo acto",
                       "5.18", "NIST SP 800-63B-4", actor=actor(s), datos={"usuario": u["usuario"], "credenciales_revocadas": n})
    return {"ok": True, "credenciales_revocadas": n}


@admin.post("/tarjetas/{tarjeta}/revocar")
def revocar_tarjeta(tarjeta: str, s: dict = Depends(permiso_con_reauth("administrar"))):
    t = db.uno("SELECT * FROM tarjetas WHERE tarjeta = ?", (tarjeta[:16],))
    if not t:
        raise HTTPException(404, "Tarjeta no encontrada")
    with db.transaccion() as con:
        con.execute("UPDATE tarjetas SET estado = 'revocada' WHERE tarjeta = ?", (t["tarjeta"],))
    bitacora.registrar("acceso", "tarjeta_revocada", "advertencia", f"Tarjeta {t['tarjeta']} de {t['titular']} revocada",
                       "5.18", "NFPA 731", actor=actor(s), datos={"tarjeta": t["tarjeta"]})
    return {"ok": True}


class Equipo(BaseModel):
    ip: str = Field(max_length=15)
    nombre: str = Field(max_length=24)
    tipo: str = Field(max_length=12)
    switch: str = Field(max_length=12)
    mac: str | None = Field(default=None, max_length=17)


@admin.get("/inventario")
def inventario(_s: dict = Depends(permiso("ver"))):
    return red.inventario_listar()


@admin.post("/inventario")
def agregar_equipo(e: Equipo, s: dict = Depends(permiso_con_reauth("administrar"))):
    try:
        equipo = red.validar_equipo(e.ip, e.nombre, e.tipo, e.switch, e.mac)
        red.inventario_agregar(equipo, actor(s))
    except ValueError as err:
        raise HTTPException(422, str(err))
    return {"ok": True}


@admin.delete("/inventario/{ip}")
def eliminar_equipo(ip: str, s: dict = Depends(permiso_con_reauth("administrar"))):
    try:
        ipaddress.IPv4Address(ip)
        red.inventario_eliminar(ip, actor(s))
    except ValueError as err:
        raise HTTPException(422, str(err))
    return {"ok": True}
