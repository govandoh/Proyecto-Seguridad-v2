"""Módulo de AMBIENTE.

Temperatura de entrada de aire por rack evaluada contra ASHRAE TC 9.9, clase A1:
recomendado de 18 a 27 °C y máximo permisible de 32 °C. Se aplica histéresis
para no generar eventos por oscilación alrededor de un umbral. La alarma de humo
por aspiración y la supresión por agente limpio se registran según NFPA 72 y
NFPA 2001. Un sensor que deja de reportar genera el evento sensor_mudo, el caso
de la cámara sin señal que nadie atendía.
"""

import threading
import time

from .. import bitacora, config, db
from ..realtime import hub
from ..util import hace, iso

MODULO = "ambiente"
_lock = threading.RLock()
_sensores: dict[str, dict] = {}
_alarma = {"humo": "normal", "supresion": "armada"}


def _clasificar(temp: float, previo: str) -> str:
    h = config.HISTERESIS_C
    lim_crit, lim_adv, lim_frio = config.TEMP_MAX_PERMISIBLE, config.TEMP_MAX_RECOMENDADA, config.TEMP_MIN_RECOMENDADA
    # Con histéresis: para salir de un estado la lectura debe cruzar el umbral por h grados.
    if temp > lim_crit or (previo == "critico" and temp > lim_crit - h):
        return "critico"
    if temp > lim_adv or (previo in ("advertencia", "critico") and temp > lim_adv - h):
        return "advertencia"
    if temp < lim_frio or (previo == "frio" and temp < lim_frio + h):
        return "frio"
    return "normal"


def procesar_lectura(_topico: str, d: dict):
    sensor = str(d.get("sensor", ""))[:24]
    try:
        temp = round(float(d.get("temp_c")), 1)
    except (TypeError, ValueError):
        return
    if not sensor or not (-20 <= temp <= 80):
        return
    ahora = time.time()
    with _lock:
        s = _sensores.setdefault(sensor, {"estado": "normal", "temp": temp, "ultima": ahora,
                                          "mudo": False, "ultimo_guardado": 0.0, "humedad": None})
        if s["mudo"]:
            s["mudo"] = False
            bitacora.registrar(MODULO, "sensor_restablecido", "informativo",
                               f"El sensor {sensor} volvió a reportar ({temp:.1f} °C)", "7.5", "ASHRAE TC 9.9")
        s.update(temp=temp, ultima=ahora, humedad=d.get("humedad"))
        nuevo = _clasificar(temp, s["estado"])
        if nuevo != s["estado"]:
            previo = s["estado"]
            s["estado"] = nuevo
            _registrar_cambio(sensor, temp, previo, nuevo)
        if ahora - s["ultimo_guardado"] >= 5:
            s["ultimo_guardado"] = ahora
            with db.transaccion() as con:
                con.execute("INSERT INTO lecturas VALUES (?,?,?)", (iso(), sensor, round(temp, 2)))
    hub.publicar("ambiente_lectura", {"sensor": sensor, "temp_c": round(temp, 2), "estado": nuevo,
                                      "ts": iso(), "humedad": d.get("humedad")})


def _registrar_cambio(sensor, temp, previo, nuevo):
    base = {"sensor": sensor, "temp_c": round(temp, 1), "previo": previo}
    if nuevo == "critico":
        bitacora.registrar(MODULO, "temperatura_critica", "critico",
                           f"{sensor}: {temp:.1f} °C, sobre el máximo permisible de {config.TEMP_MAX_PERMISIBLE:.0f} °C para clase A1",
                           "7.5", "ASHRAE TC 9.9", datos=base)
    elif nuevo == "advertencia":
        bitacora.registrar(MODULO, "temperatura_alta", "advertencia",
                           f"{sensor}: {temp:.1f} °C, fuera del rango recomendado de {config.TEMP_MIN_RECOMENDADA:.0f} a {config.TEMP_MAX_RECOMENDADA:.0f} °C",
                           "7.5", "ASHRAE TC 9.9", datos=base)
    elif nuevo == "frio":
        bitacora.registrar(MODULO, "temperatura_baja", "advertencia",
                           f"{sensor}: {temp:.1f} °C, bajo el rango recomendado", "7.5", "ASHRAE TC 9.9", datos=base)
    else:
        bitacora.registrar(MODULO, "temperatura_normal", "informativo",
                           f"{sensor}: {temp:.1f} °C, de vuelta en el rango recomendado", "7.5", "ASHRAE TC 9.9", datos=base)


def procesar_alarma(_topico: str, d: dict):
    humo = d.get("humo")
    sup = d.get("supresion")
    with _lock:
        if humo in ("activa", "normal") and humo != _alarma["humo"]:
            _alarma["humo"] = humo
            if humo == "activa":
                bitacora.registrar(MODULO, "alarma_humo", "critico",
                                   f"Detección de humo por aspiración en la sala; descarga del agente limpio en {d.get('retardo_s', 30)} s salvo aborto",
                                   "7.5", "NFPA 72; NFPA 2001", datos=d)
            else:
                bitacora.registrar(MODULO, "alarma_humo_normal", "informativo",
                                   "La detección de humo volvió a estado normal", "7.5", "NFPA 72")
        if sup in ("armada", "descargada", "abortada") and sup != _alarma["supresion"]:
            _alarma["supresion"] = sup
            if sup == "descargada":
                bitacora.registrar(MODULO, "supresion_descargada", "critico",
                                   "Descarga del agente limpio en la sala de servidores", "7.5", "NFPA 2001", datos=d)
            elif sup == "abortada":
                bitacora.registrar(MODULO, "supresion_abortada", "advertencia",
                                   "El operador abortó la descarga del agente limpio", "7.5", "NFPA 2001", datos=d)
    hub.publicar("ambiente_alarma", dict(_alarma))


def revisar():
    ahora = time.time()
    with _lock:
        for nombre, s in _sensores.items():
            if not s["mudo"] and ahora - s["ultima"] > config.SENSOR_TIMEOUT_S:
                s["mudo"] = True
                bitacora.registrar(MODULO, "sensor_mudo", "advertencia",
                                   f"El sensor {nombre} no reporta desde hace más de {config.SENSOR_TIMEOUT_S:.0f} s; su zona queda sin vigilancia térmica",
                                   "7.4; 7.5", "ASHRAE TC 9.9", datos={"sensor": nombre})


def estado() -> dict:
    ahora = time.time()
    with _lock:
        sensores = [{"sensor": n, "temp_c": round(s["temp"], 2), "estado": "mudo" if s["mudo"] else s["estado"],
                     "humedad": s["humedad"], "edad_s": round(ahora - s["ultima"], 1)}
                    for n, s in sorted(_sensores.items())]
        return {"sensores": sensores, "alarma": dict(_alarma),
                "umbrales": {"min_recomendada": config.TEMP_MIN_RECOMENDADA,
                             "max_recomendada": config.TEMP_MAX_RECOMENDADA,
                             "max_permisible": config.TEMP_MAX_PERMISIBLE}}


def historial(minutos: int = 30) -> list[dict]:
    return db.consultar("SELECT ts, sensor, valor FROM lecturas WHERE ts >= ? ORDER BY ts", (iso(hace(minutos)),))


def minutos_sobre_recomendado(dias: int = 30) -> float:
    """Aproximación con las muestras guardadas cada 5 s."""
    fila = db.uno("SELECT COUNT(*) AS n FROM lecturas WHERE ts >= ? AND valor > ?",
                  (iso(hace(minutos=dias * 1440)), config.TEMP_MAX_RECOMENDADA))
    return round((fila["n"] if fila else 0) * 5 / 60, 1)
