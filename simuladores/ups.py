"""sim-ups: UPS en línea con conmutador de transferencia (ATS) y planta de emergencia.

Reproduce lo que reportaría la tarjeta de gestión de un UPS real, con los nombres
de variable de Network UPS Tools (NUT):
  ups.status       OL (en línea), OL CHRG (cargando), OB (en batería), OB LB (batería baja), OFF
  battery.charge   porcentaje de carga
  battery.runtime  autonomía restante en segundos
  ups.load         carga en % de la potencia nominal
  input.voltage / output.voltage

Autonomía: t = 60 · E · η / P  (E energía útil en Wh, η eficiencia del inversor, P carga en W).
La descarga de la batería se acelera con FACTOR_TIEMPO para que la demostración dure
minutos; el arranque de la planta corre en segundos reales para medir el tipo 10 de NFPA 110.

Comandos en dc/cmd/ups: corte_acometida, retorno_acometida, falla_planta, reparar_planta,
prueba_mensual, fijar_arranque {segundos}.
"""

import os
import time

from comun import Dispositivo, env_float

E_UTIL = env_float("ENERGIA_UTIL_WH", 864)
ETA = env_float("EFICIENCIA_INVERSOR", 0.90)
CARGA_W = env_float("CARGA_W", 566.2)
NOMINAL_W = env_float("POTENCIA_NOMINAL_W", 1500)
FACTOR = env_float("FACTOR_TIEMPO", 30)
LB_PCT = env_float("BATERIA_BAJA_PCT", 25)
VOLTAJE = env_float("VOLTAJE_NOMINAL", 120)

d = Dispositivo(os.getenv("NOMBRE", "UPS-01"))
s = {
    "acometida": True, "ats": "red", "energia_wh": E_UTIL, "salida": True,
    "planta": {"estado": "parada", "t_arranque_s": env_float("PLANTA_ARRANQUE_S", 7.0), "falla": False,
               "inicio_arranque": None},
    "t_corte": None, "t_en_linea": None, "prueba": None,
}


def autonomia_s() -> float:
    return max(0.0, s["energia_wh"] * ETA / CARGA_W * 3600)


def comando(_t, c):
    a = c.get("accion")
    p = s["planta"]
    if a == "corte_acometida" and s["acometida"]:
        s.update(acometida=False, t_corte=time.time(), t_en_linea=None, salida=True)
        if s["ats"] == "red":
            s["ats"] = "ninguna"  # la carga queda en el inversor del UPS
        d.log.warning("CORTE de acometida")
    elif a == "retorno_acometida" and not s["acometida"]:
        s.update(acometida=True, ats="red", t_corte=None, t_en_linea=None, salida=True)
        p.update(estado="parada", inicio_arranque=None)
        d.log.info("retorno de acometida; planta en enfriamiento y parada")
    elif a == "falla_planta":
        p["falla"] = True
        if p["estado"] in ("arrancando", "en_linea"):
            p["estado"] = "falla"
            if s["ats"] == "planta":
                s["ats"] = "ninguna"
        d.log.warning("planta marcada con falla")
    elif a == "reparar_planta":
        p["falla"] = False
        if p["estado"] == "falla":
            p.update(estado="parada", inicio_arranque=None)
    elif a == "fijar_arranque" and c.get("segundos"):
        p["t_arranque_s"] = float(c["segundos"])
        d.log.info("tiempo de arranque de la planta: %.1f s", p["t_arranque_s"])
    elif a == "prueba_mensual" and s["acometida"] and not s["prueba"]:
        s["prueba"] = {"inicio": time.time(), "arranque_ok": not p["falla"]}
        d.log.info("inicia ejercicio mensual de la planta")


def paso():
    p = s["planta"]
    ahora = time.time()
    dt_sim = 1.0 * FACTOR

    if not s["acometida"]:
        if p["estado"] == "parada" and not p["falla"]:
            p.update(estado="arrancando", inicio_arranque=ahora)
        elif p["estado"] == "parada" and p["falla"]:
            p["estado"] = "falla"
        if p["estado"] == "arrancando" and ahora - p["inicio_arranque"] >= p["t_arranque_s"]:
            if p["falla"]:
                p["estado"] = "falla"
            else:
                p["estado"] = "en_linea"
                s["ats"] = "planta"
                s["t_en_linea"] = p["inicio_arranque"] + p["t_arranque_s"]
    # Ejercicio mensual con acometida presente (NFPA 110: 30 min con carga).
    if s["prueba"]:
        transcurrido_sim = (ahora - s["prueba"]["inicio"]) * FACTOR
        if transcurrido_sim >= 30 * 60:
            d.publicar("dc/energia/prueba", {
                "equipo": "PLANTA-01", "tipo": "ejercicio_mensual", "duracion_min": 30,
                "t_arranque_s": p["t_arranque_s"],
                "resultado": "exitosa" if s["prueba"]["arranque_ok"] and p["t_arranque_s"] <= 10 else "fallida"})
            s["prueba"] = None

    alimentada = s["acometida"] or (s["ats"] == "planta" and p["estado"] == "en_linea")
    if alimentada:
        s["energia_wh"] = min(E_UTIL, s["energia_wh"] + E_UTIL * 0.02 * dt_sim / 60)  # recarga
        s["salida"] = True
        status = "OL" if s["energia_wh"] >= E_UTIL * 0.999 else "OL CHRG"
    elif s["salida"]:
        s["energia_wh"] = max(0.0, s["energia_wh"] - (CARGA_W / ETA) * dt_sim / 3600)
        if s["energia_wh"] <= 0:
            s["salida"] = False
            status = "OFF"
        else:
            lb = autonomia_s() <= (E_UTIL * ETA / CARGA_W * 3600) * LB_PCT / 100
            status = "OB LB" if lb else "OB"
    else:
        status = "OFF"

    d.publicar("dc/energia/ups", {
        "equipo": d.nombre, "ts": ahora, "acometida": s["acometida"], "ats": s["ats"],
        "ups.status": status, "battery.charge": round(100 * s["energia_wh"] / E_UTIL, 1),
        "battery.runtime": round(autonomia_s()) if s["salida"] else 0,
        "ups.load": round(100 * CARGA_W / NOMINAL_W, 1) if s["salida"] else 0,
        "ups.realpower": CARGA_W if s["salida"] else 0,
        "input.voltage": VOLTAJE if s["acometida"] else (VOLTAJE if s["ats"] == "planta" else 0.0),
        "output.voltage": VOLTAJE if s["salida"] else 0.0,
        "planta": {"estado": p["estado"], "t_arranque_s": p["t_arranque_s"], "prueba_en_curso": bool(s["prueba"])},
        "evento": {"t_corte": s["t_corte"], "t_en_linea": s["t_en_linea"]},
        "factor_tiempo": FACTOR, "energia_util_wh": E_UTIL, "eficiencia": ETA, "carga_w": CARGA_W,
    })


if __name__ == "__main__":
    d.suscribir("dc/cmd/ups", comando)
    d.log.info("UPS simulado: E=%.0f Wh, η=%.2f, P=%.1f W, autonomía de diseño %.1f min, factor x%.0f",
               E_UTIL, ETA, CARGA_W, E_UTIL * ETA / CARGA_W * 60, FACTOR)
    d.arrancar(paso, 1.0)
