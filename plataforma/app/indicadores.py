"""Indicadores de verificación (Tabla 22 del Entregable 2) calculados sobre la bitácora."""

import json

from . import bitacora, config, db
from .modulos import ambiente, energia
from .util import parse_iso


def _datos(fila):
    try:
        return json.loads(fila.get("datos") or "{}")
    except ValueError:
        return {}


def calcular() -> list[dict]:
    ind = []

    # 1. Tiempo de detección de desconexión
    filas = db.consultar("SELECT datos FROM eventos WHERE tipo IN ('dispositivo_desconectado','cascada_poe')")
    lat = [d.get("latencia_deteccion_s") for d in map(_datos, filas) if d.get("latencia_deteccion_s") is not None]
    meta_det = config.UMBRAL_DESCONEXION_S + config.INTERVALO_REVISION_S
    prom = round(sum(lat) / len(lat), 1) if lat else None
    ind.append({"id": "deteccion_desconexion", "nombre": "Tiempo medio de detección de desconexión",
                "valor": prom, "unidad": "s", "meta": f"≤ {meta_det:.0f} s",
                "cumple": None if prom is None else prom <= meta_det, "muestras": len(lat)})

    # 2. Tiempo de acuse de alertas críticas
    pares = db.consultar("""SELECT e.ts AS t_alerta, a.ts AS t_acuse FROM eventos a
                            JOIN eventos e ON e.id = a.ref_id WHERE a.tipo = 'acuse'""")
    dif = [(parse_iso(p["t_acuse"]) - parse_iso(p["t_alerta"])).total_seconds() / 60 for p in pares]
    prom = round(sum(dif) / len(dif), 1) if dif else None
    pendientes = len(bitacora.pendientes_de_acuse())
    ind.append({"id": "acuse", "nombre": "Tiempo medio de acuse de alertas críticas", "valor": prom,
                "unidad": "min", "meta": "≤ 5 min", "cumple": None if prom is None else prom <= 5,
                "muestras": len(dif), "extra": f"{pendientes} pendientes"})

    # 3. Transferencias dentro del tipo 10
    filas = db.consultar("SELECT datos FROM eventos WHERE tipo IN ('transferencia_planta','transferencia_fuera_de_tipo')")
    trans = [_datos(f) for f in filas]
    ok = sum(1 for t in trans if t.get("cumple"))
    pct = round(100 * ok / len(trans), 1) if trans else None
    ind.append({"id": "transferencia", "nombre": "Transferencias dentro del tipo 10 de NFPA 110", "valor": pct,
                "unidad": "%", "meta": "100 %", "cumple": None if pct is None else pct == 100, "muestras": len(trans)})

    # 4. Autonomía reportada frente a diseño
    e = energia.estado()
    rt = (e.get("telemetria") or {}).get("battery.runtime")
    diseno = e["diseno"]["autonomia_min"]
    pct = None
    if rt is not None and e["estado"] == "NORMAL" and diseno:
        pct = round(100 * (float(rt) / 60) / diseno, 1)
    ind.append({"id": "autonomia", "nombre": "Autonomía reportada frente a la de diseño", "valor": pct,
                "unidad": "%", "meta": "≥ 90 %", "cumple": None if pct is None else pct >= 90, "muestras": 1 if pct else 0})

    # 5. Pruebas de la planta en los últimos 12 meses
    n = db.uno("""SELECT COUNT(*) AS n FROM eventos WHERE tipo = 'prueba_planta'
                  AND severidad = 'informativo' AND ts >= date('now','-365 day')""")["n"]
    ind.append({"id": "pruebas_planta", "nombre": "Ejercicios mensuales de la planta en 12 meses", "valor": n,
                "unidad": "de 12", "meta": "12 de 12", "cumple": n >= 12, "muestras": n})

    # 6. Minutos sobre el rango recomendado
    m = ambiente.minutos_sobre_recomendado(30)
    ind.append({"id": "temperatura", "nombre": "Minutos-sensor sobre 27 °C en 30 días", "valor": m, "unidad": "min",
                "meta": "tendencia a la baja", "cumple": None, "muestras": None})

    # 7. Cuentas con autenticación multifactor
    tot = db.uno("SELECT COUNT(*) AS n FROM usuarios WHERE activo = 1 AND password_hash IS NOT NULL")["n"]
    con = db.uno("""SELECT COUNT(DISTINCT u.id) AS n FROM usuarios u JOIN credenciales c ON c.usuario_id = u.id
                    WHERE u.activo = 1 AND c.revocada = 0""")["n"]
    pct = round(100 * con / tot, 1) if tot else None
    ind.append({"id": "mfa", "nombre": "Cuentas activas con passkey registrada", "valor": pct, "unidad": "%",
                "meta": "100 %", "cumple": None if pct is None else pct == 100, "muestras": tot})

    # 8. Revocación en bajas
    bajas = db.consultar("SELECT datos FROM eventos WHERE tipo = 'usuario_baja'")
    ok = sum(1 for b in bajas if _datos(b).get("credenciales_revocadas") is not None)
    pct = round(100 * ok / len(bajas), 1) if bajas else None
    ind.append({"id": "revocacion", "nombre": "Bajas con revocación inmediata de credenciales", "valor": pct,
                "unidad": "%", "meta": "100 % en 24 h", "cumple": None if pct is None else pct == 100, "muestras": len(bajas)})

    # 9. Integridad de la bitácora
    v = bitacora.verificar()
    ind.append({"id": "integridad", "nombre": "Integridad de la cadena de hash de la bitácora",
                "valor": 100.0 if v["integra"] else 0.0, "unidad": "%", "meta": "100 %", "cumple": v["integra"],
                "muestras": v["total"]})
    return ind
