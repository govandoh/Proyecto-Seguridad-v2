"""sim-puerta: controlador de puerta de la sala de servidores con lectora de tarjeta y teclado.

La lectora envía la tarjeta y el PIN al servidor de control de acceso (la
plataforma) y ejecuta su decisión. El controlador reporta por sí mismo dos
alarmas clásicas de control de acceso: puerta forzada (se abre sin un acceso
válido) y puerta mantenida abierta.

En un sistema real la comunicación lectora-controlador usaría OSDP con canal
seguro; en el laboratorio la protege la red interna y la ACL del broker.

Comandos en dc/cmd/puerta: leer {tarjeta, pin}, forzar, mantener {tarjeta, pin}.
"""

import os
import time

from comun import Dispositivo, env_float

LECTORA = os.getenv("LECTORA", "LECT-01")
APERTURA_S = env_float("APERTURA_S", 5)
MAX_ABIERTA_S = env_float("PUERTA_ABIERTA_MAX_S", 30)

d = Dispositivo(os.getenv("NOMBRE", "SIM-PUERTA"))
s = {"estado": "cerrada", "desde": time.time(), "mantener": False, "pendiente_mantener": False, "avisado": False}


def publicar_puerta(estado, motivo=""):
    s.update(estado=estado, desde=time.time(), avisado=False if estado != "mantenida_abierta" else True)
    d.publicar("dc/acceso/puerta", {"lectora": LECTORA, "estado": estado, "motivo": motivo, "ts": time.time()})


def comando(_t, c):
    a = c.get("accion")
    if a in ("leer", "mantener"):
        s["pendiente_mantener"] = a == "mantener"
        d.publicar("dc/acceso/lectura", {"lectora": LECTORA, "tarjeta": c.get("tarjeta", ""),
                                         "pin": c.get("pin", ""), "ts": time.time()})
    elif a == "forzar" and s["estado"] == "cerrada":
        s["mantener"] = True
        publicar_puerta("abierta", "forzada")


def respuesta(_t, r):
    if r.get("lectora") != LECTORA:
        return
    if r.get("accion") == "abrir":
        s["mantener"] = s["pendiente_mantener"]
        publicar_puerta("abierta", "acceso_valido")
    else:
        d.log.info("acceso denegado: %s", r.get("motivo"))
    s["pendiente_mantener"] = False


def paso():
    abierta = s["estado"] in ("abierta", "mantenida_abierta")
    t = time.time() - s["desde"]
    if s["estado"] == "abierta" and not s["mantener"] and t >= APERTURA_S:
        publicar_puerta("cerrada", "cierre_automatico")
    elif s["estado"] == "abierta" and s["mantener"] and t >= MAX_ABIERTA_S:
        publicar_puerta("mantenida_abierta", "tiempo_excedido")
    elif s["estado"] == "mantenida_abierta" and t >= 15:
        s["mantener"] = False
        publicar_puerta("cerrada", "cierre_manual")
    elif not abierta and int(time.time()) % 15 == 0:
        d.publicar("dc/acceso/puerta", {"lectora": LECTORA, "estado": "cerrada", "motivo": "latido", "ts": time.time()})


if __name__ == "__main__":
    d.suscribir("dc/cmd/puerta", comando)
    d.suscribir("dc/acceso/cmd", respuesta)
    d.log.info("controlador de %s listo", LECTORA)
    d.arrancar(paso, 1.0)
