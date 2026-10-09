"""Módulo de ENERGÍA: máquina de estados del incidente eléctrico.

El simulador sim-ups reproduce la física (UPS, conmutador de transferencia y
planta) y reporta variables con los nombres de Network UPS Tools: ups.status
(OL, OB, LB, OFF), battery.charge, battery.runtime, ups.load. Aquí se evalúa la
norma: el tiempo de transferencia contra el tipo 10 de NFPA 110, el paso a
batería según NFPA 111 y el umbral de batería baja.

Estados: NORMAL -> CORTE_DETECTADO -> UPS_EN_BATERIA -> TRANSFERENCIA_GENERADOR
         -> BATERIA_BAJA -> APAGADO_CONTROLADO, con retorno a NORMAL.
"""

import threading
import time

from .. import bitacora, config, db
from ..realtime import hub
from ..util import hace, iso

MODULO = "energia"
_lock = threading.RLock()
_e = {
    "estado": "SIN_DATOS", "ultima": 0.0, "telemetria": {}, "t_corte": None,
    "transferencia_s": None, "falla_planta_avisada": False, "mudo_avisado": False,
    "ultima_muestra": 0.0, "incidente_inicio": None,
}


def autonomia_diseno_min() -> dict:
    cargas = db.consultar("SELECT * FROM cargas ORDER BY potencia_w DESC")
    p = sum(c["potencia_w"] for c in cargas) or 1.0
    t = 60 * config.ENERGIA_UTIL_WH * config.EFICIENCIA_INVERSOR / p
    return {"carga_w": round(p, 1), "energia_wh": config.ENERGIA_UTIL_WH,
            "eficiencia": config.EFICIENCIA_INVERSOR, "autonomia_min": round(t, 1),
            "umbral_bateria_baja_min": round(t * config.BATERIA_BAJA_PCT / 100, 1), "cargas": cargas}


def _cambiar(nuevo: str):
    anterior = _e["estado"]
    _e["estado"] = nuevo
    hub.publicar("energia_estado", {"anterior": anterior, "estado": nuevo})


def procesar_ups(_topico: str, t: dict):
    with _lock:
        _e["ultima"] = time.time()
        _e["telemetria"] = t
        if _e["mudo_avisado"]:
            _e["mudo_avisado"] = False
            bitacora.registrar(MODULO, "ups_comunicacion_restablecida", "informativo",
                               "Se restableció la comunicación con la tarjeta de gestión del UPS", "7.11", "NFPA 111")
        diseno = autonomia_diseno_min()
        status = str(t.get("ups.status", ""))
        acometida = bool(t.get("acometida"))
        ats = t.get("ats")
        planta = t.get("planta") or {}
        runtime_min = float(t.get("battery.runtime", 0) or 0) / 60.0
        estado = _e["estado"]

        if estado == "SIN_DATOS":
            _cambiar("NORMAL" if acometida else "UPS_EN_BATERIA")
            estado = _e["estado"]

        # Retorno de la acometida en cualquier estado previo al apagado.
        if acometida and ats == "red":
            if estado not in ("NORMAL",):
                dur = None
                if _e["incidente_inicio"]:
                    dur = round(time.time() - _e["incidente_inicio"], 1)
                bitacora.registrar(MODULO, "retorno_acometida", "informativo",
                                   f"Volvió la acometida; incidente cerrado{f' tras {dur} s' if dur is not None else ''}",
                                   "7.11", "NFPA 110", datos={"duracion_s": dur, "estado_previo": estado})
                _e.update(t_corte=None, transferencia_s=None, falla_planta_avisada=False, incidente_inicio=None)
                _cambiar("NORMAL")
            _muestra(runtime_min, t)
            return

        # Sin acometida.
        if estado == "NORMAL":
            _e["t_corte"] = (t.get("evento") or {}).get("t_corte") or time.time()
            _e["incidente_inicio"] = time.time()
            bitacora.registrar(MODULO, "perdida_acometida", "critico",
                               "Pérdida de la acometida eléctrica; inicia el conteo de transferencia",
                               "7.11", "NFPA 110", datos={"t_corte": _e["t_corte"]})
            _cambiar("CORTE_DETECTADO")
            estado = "CORTE_DETECTADO"

        if estado == "CORTE_DETECTADO" and status.startswith("OB"):
            bitacora.registrar(MODULO, "ups_en_bateria", "advertencia",
                               f"El UPS tomó la carga sin interrupción; autonomía reportada {runtime_min:.1f} min, de diseño {diseno['autonomia_min']} min",
                               "7.11", "NFPA 111", datos={"runtime_min": round(runtime_min, 1), "diseno_min": diseno["autonomia_min"]})
            _cambiar("UPS_EN_BATERIA")
            estado = "UPS_EN_BATERIA"

        if ats == "planta" and planta.get("estado") == "en_linea" and estado in ("CORTE_DETECTADO", "UPS_EN_BATERIA", "BATERIA_BAJA"):
            t_en_linea = (t.get("evento") or {}).get("t_en_linea") or time.time()
            trans = round(float(t_en_linea) - float(_e["t_corte"] or t_en_linea), 2)
            _e["transferencia_s"] = trans
            if trans <= config.NFPA110_TIPO_S:
                bitacora.registrar(MODULO, "transferencia_planta", "informativo",
                                   f"La planta tomó la carga en {trans} s: cumple el tipo {config.NFPA110_TIPO_S:.0f} de NFPA 110",
                                   "7.11", "NFPA 110", datos={"transferencia_s": trans, "cumple": True})
            else:
                bitacora.registrar(MODULO, "transferencia_fuera_de_tipo", "critico",
                                   f"La planta tomó la carga en {trans} s: NO cumple el tipo {config.NFPA110_TIPO_S:.0f} de NFPA 110",
                                   "7.11", "NFPA 110", datos={"transferencia_s": trans, "cumple": False})
            _cambiar("TRANSFERENCIA_GENERADOR")
            estado = "TRANSFERENCIA_GENERADOR"

        if planta.get("estado") == "falla" and not _e["falla_planta_avisada"]:
            _e["falla_planta_avisada"] = True
            bitacora.registrar(MODULO, "falla_planta", "critico",
                               "La planta de emergencia no arrancó o se detuvo: la carga depende solo de las baterías",
                               "7.11", "NFPA 110")
            if estado == "TRANSFERENCIA_GENERADOR":
                _cambiar("UPS_EN_BATERIA")
                estado = "UPS_EN_BATERIA"

        if estado in ("UPS_EN_BATERIA", "CORTE_DETECTADO") and status.startswith("OB") and \
                runtime_min <= diseno["umbral_bateria_baja_min"]:
            bitacora.registrar(MODULO, "bateria_baja", "critico",
                               f"Autonomía restante {runtime_min:.1f} min, bajo el umbral de {diseno['umbral_bateria_baja_min']} min",
                               "7.11", "NFPA 111; IEEE 1188", datos={"runtime_min": round(runtime_min, 1)})
            _cambiar("BATERIA_BAJA")
            estado = "BATERIA_BAJA"

        if estado == "BATERIA_BAJA" and (status.startswith("OFF") or runtime_min <= 0):
            bitacora.registrar(MODULO, "apagado_controlado", "critico",
                               "Autonomía agotada sin retorno de la acometida: apagado ordenado de las cargas",
                               "7.11", "ISO 22301")
            _cambiar("APAGADO_CONTROLADO")

        _muestra(runtime_min, t)


def procesar_prueba(_topico: str, d: dict):
    ok = bool(d.get("resultado") == "exitosa")
    t_arr = d.get("t_arranque_s")
    bitacora.registrar(MODULO, "prueba_planta", "informativo" if ok else "advertencia",
                       f"Ejercicio mensual de la planta: {d.get('duracion_min', '?')} min con carga, arranque en {t_arr} s, resultado {d.get('resultado')}",
                       "7.13", "NFPA 110", datos=d)


def _muestra(runtime_min: float, t: dict):
    ahora = time.time()
    if ahora - _e["ultima_muestra"] < 5:
        return
    _e["ultima_muestra"] = ahora
    with db.transaccion() as con:
        con.execute("INSERT INTO energia_muestras VALUES (?,?,?,?)",
                    (iso(), _e["estado"], t.get("ups.load"), round(runtime_min, 2)))


def revisar():
    with _lock:
        if _e["ultima"] and time.time() - _e["ultima"] > config.UPS_TIMEOUT_S and not _e["mudo_avisado"]:
            _e["mudo_avisado"] = True
            bitacora.registrar(MODULO, "ups_sin_comunicacion", "critico",
                               "La tarjeta de gestión del UPS no reporta: el estado eléctrico es desconocido",
                               "7.11", "NFPA 111")


def estado() -> dict:
    with _lock:
        edad = round(time.time() - _e["ultima"], 1) if _e["ultima"] else None
        return {"estado": _e["estado"], "telemetria": _e["telemetria"], "transferencia_s": _e["transferencia_s"],
                "edad_s": edad, "comunicacion": edad is not None and edad <= config.UPS_TIMEOUT_S,
                "diseno": autonomia_diseno_min(), "tipo_nfpa110_s": config.NFPA110_TIPO_S}


def historial(minutos: int = 30) -> list[dict]:
    return db.consultar("SELECT * FROM energia_muestras WHERE ts >= ? ORDER BY ts",
                        (iso(hace(minutos)),))
