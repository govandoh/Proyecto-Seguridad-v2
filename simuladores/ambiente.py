"""sim-ambiente: sensores de temperatura de entrada de aire, detección de humo y supresión.

Modelo térmico sencillo por rack: con la climatización encendida la temperatura
converge al punto de ajuste; sin climatización sube a razón constante. La
climatización es una carga de la planta, no del UPS, como en la mayoría de los
centros de datos: si no hay acometida ni planta en línea, se apaga.

Comandos en dc/cmd/ambiente: falla_clima, restaurar_clima, fijar {sensor, valor},
liberar {sensor}, humo, abortar_supresion, restablecer_humo, silenciar {sensor}, reactivar {sensor}.
"""

import os
import random
import time

from comun import Dispositivo, env_float

SENSORES = [x.strip() for x in os.getenv("SENSORES", "T-RACK-A,T-RACK-B").split(",") if x.strip()]
SETPOINT = env_float("SETPOINT_C", 22.0)
SUBIDA = env_float("SUBIDA_C_POR_S", 0.35)  # sin climatización, grados por segundo real
RETARDO_SUPRESION = env_float("RETARDO_SUPRESION_S", 30)
PERIODO = env_float("PERIODO_S", 2)

d = Dispositivo(os.getenv("NOMBRE", "SIM-AMBIENTE"))
sensores = {n: {"temp": SETPOINT + random.uniform(-0.8, 0.8), "fijo": None, "mudo": False} for n in SENSORES}
s = {"falla_clima": False, "energia_ok": True, "humo": "normal", "supresion": "armada", "t_humo": None}


def clima_encendido() -> bool:
    return s["energia_ok"] and not s["falla_clima"]


def energia(_t, u):
    s["energia_ok"] = bool(u.get("acometida")) or (u.get("ats") == "planta")


def comando(_t, c):
    a, sensor = c.get("accion"), c.get("sensor")
    objetivo = [sensor] if sensor in sensores else list(sensores)
    if a == "falla_clima":
        s["falla_clima"] = True
    elif a == "restaurar_clima":
        s["falla_clima"] = False
    elif a == "fijar" and c.get("valor") is not None:
        for n in objetivo:
            sensores[n]["fijo"] = float(c["valor"])
    elif a == "liberar":
        for n in objetivo:
            sensores[n]["fijo"] = None
    elif a == "silenciar":
        for n in objetivo:
            sensores[n]["mudo"] = True
    elif a == "reactivar":
        for n in objetivo:
            sensores[n]["mudo"] = False
    elif a == "humo" and s["humo"] == "normal":
        s.update(humo="activa", t_humo=time.time(), supresion="armada")
        alarma()
    elif a == "abortar_supresion" and s["humo"] == "activa" and s["supresion"] == "armada":
        s["supresion"] = "abortada"
        alarma()
    elif a == "restablecer_humo":
        s.update(humo="normal", supresion="armada", t_humo=None)
        alarma()
    d.log.info("comando %s aplicado", a)


def alarma():
    d.publicar("dc/ambiente/alarma", {"humo": s["humo"], "supresion": s["supresion"],
                                      "retardo_s": RETARDO_SUPRESION, "zona": "SALA-SERVIDORES"})


def paso():
    ahora = time.time()
    for n, x in sensores.items():
        if x["fijo"] is not None:
            x["temp"] += (x["fijo"] - x["temp"]) * 0.5
        elif clima_encendido():
            x["temp"] += (SETPOINT - x["temp"]) * 0.08 + random.uniform(-0.08, 0.08)
        else:
            x["temp"] = min(45.0, x["temp"] + SUBIDA * PERIODO * random.uniform(0.85, 1.15))
        if not x["mudo"]:
            d.publicar("dc/ambiente/lectura", {"sensor": n, "temp_c": round(x["temp"], 2),
                                               "humedad": round(random.uniform(42, 48), 1),
                                               "clima": clima_encendido(), "ts": ahora})
    if s["humo"] == "activa" and s["supresion"] == "armada" and ahora - s["t_humo"] >= RETARDO_SUPRESION:
        s["supresion"] = "descargada"
        alarma()
    if int(ahora) % 10 < PERIODO:
        alarma()


if __name__ == "__main__":
    d.suscribir("dc/cmd/ambiente", comando)
    d.suscribir("dc/energia/ups", energia)
    d.log.info("sensores %s, punto de ajuste %.1f °C", ", ".join(SENSORES), SETPOINT)
    d.arrancar(paso, PERIODO)
