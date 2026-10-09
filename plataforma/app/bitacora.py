"""Bitácora auditable de solo inserción con cadena de hash SHA-256.

hash_n = SHA-256( hash_{n-1} || JSON canónico de los campos del evento n )

Si alguien modifica o borra una fila, la verificación falla desde ese punto.
Controles: ISO/IEC 27001:2022 8.15 (registro) y 8.17 (sincronización de relojes);
NIST SP 800-53 AU-9 (protección de la información de auditoría).
"""

import hashlib
import json
import logging

from . import db
from .realtime import hub
from .util import iso

log = logging.getLogger("bitacora")
GENESIS = "0" * 64
SEVERIDADES = ("informativo", "advertencia", "critico")
CAMPOS = ("ts", "modulo", "tipo", "severidad", "descripcion", "control_iso", "norma", "actor", "ref_id", "datos")


def _canonico(evento: dict) -> str:
    return json.dumps([evento[c] for c in CAMPOS], ensure_ascii=False, separators=(",", ":"))


def _calcular_hash(hash_anterior: str, evento: dict) -> str:
    return hashlib.sha256((hash_anterior + _canonico(evento)).encode("utf-8")).hexdigest()


def registrar(modulo: str, tipo: str, severidad: str, descripcion: str, control_iso: str = "",
              norma: str = "", actor: str = "sistema", ref_id: int | None = None,
              datos: dict | None = None) -> dict:
    if severidad not in SEVERIDADES:
        raise ValueError(f"severidad inválida: {severidad}")
    evento = {
        "ts": iso(), "modulo": modulo, "tipo": tipo, "severidad": severidad,
        "descripcion": descripcion, "control_iso": control_iso, "norma": norma,
        "actor": actor, "ref_id": ref_id,
        "datos": json.dumps(datos or {}, ensure_ascii=False, sort_keys=True, default=str),
    }
    with db.transaccion() as con:
        fila = con.execute("SELECT hash FROM eventos ORDER BY id DESC LIMIT 1").fetchone()
        anterior = fila["hash"] if fila else GENESIS
        evento["hash_anterior"] = anterior
        evento["hash"] = _calcular_hash(anterior, evento)
        cur = con.execute(
            """INSERT INTO eventos (ts, modulo, tipo, severidad, descripcion, control_iso, norma,
                                   actor, ref_id, datos, hash_anterior, hash)
               VALUES (:ts,:modulo,:tipo,:severidad,:descripcion,:control_iso,:norma,
                       :actor,:ref_id,:datos,:hash_anterior,:hash)""", evento)
        evento["id"] = cur.lastrowid
    salida = publico(evento)
    log.info("[%s] %s/%s: %s", severidad, modulo, tipo, descripcion)
    hub.publicar("evento", salida)
    return salida


def publico(fila: dict) -> dict:
    d = dict(fila)
    try:
        d["datos"] = json.loads(d.get("datos") or "{}")
    except (TypeError, ValueError):
        d["datos"] = {}
    return d


def verificar() -> dict:
    anterior = GENESIS
    total = 0
    con = db.conectar()
    try:
        for fila in con.execute("SELECT * FROM eventos ORDER BY id"):
            total += 1
            f = dict(fila)
            if f["hash_anterior"] != anterior or _calcular_hash(anterior, f) != f["hash"]:
                return {"integra": False, "total": total, "primer_error_id": f["id"],
                        "detalle": "La cadena se rompe en este evento: fue modificado, insertado o se borró el anterior."}
            anterior = f["hash"]
    finally:
        con.close()
    return {"integra": True, "total": total, "primer_error_id": None, "ultimo_hash": anterior}


def listar(limite: int = 200, modulo: str | None = None, severidad: str | None = None,
           desde_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM eventos WHERE 1=1"
    params: list = []
    if modulo:
        sql += " AND modulo = ?"
        params.append(modulo)
    if severidad:
        sql += " AND severidad = ?"
        params.append(severidad)
    if desde_id:
        sql += " AND id > ?"
        params.append(desde_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(limite, 5000)))
    return [publico(f) for f in db.consultar(sql, params)]


def pendientes_de_acuse() -> list[dict]:
    """Eventos críticos sin un evento de acuse que los referencie."""
    filas = db.consultar(
        """SELECT e.* FROM eventos e
           WHERE e.severidad = 'critico' AND e.tipo <> 'acuse'
             AND NOT EXISTS (SELECT 1 FROM eventos a WHERE a.tipo = 'acuse' AND a.ref_id = e.id)
           ORDER BY e.id DESC LIMIT 100""")
    return [publico(f) for f in filas]
