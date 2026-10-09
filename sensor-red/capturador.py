"""sensor-red: capturador pasivo del tráfico de la topología GNS3.

Corre separado de la aplicación web (hallazgo V6 del Entregable 2): solo este
contenedor tiene la capacidad CAP_NET_RAW, y la web se ejecuta sin privilegios.
Cada segundo publica en dc/red/observacion los pares MAC/IP vistos en eth2. La
clasificación contra el inventario ocurre en la plataforma.

MODO=captura  lee paquetes reales de IFACE con Scapy (GNS3 VM, eth2)
MODO=demo     genera el tráfico de los equipos del laboratorio para ensayar sin GNS3;
              acepta comandos en dc/cmd/red: apagar_switch, encender_switch,
              conectar_intruso, desconectar_intruso, sustituir {nombre}, restaurar
"""

import json
import logging
import os
import random
import threading
import time

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s capturador: %(message)s")
log = logging.getLogger("capturador")

MODO = os.getenv("MODO", "captura")
IFACE = os.getenv("IFACE", "eth2")
IGNORAR = {"0.0.0.0", os.getenv("IP_CAPTURA", "10.10.10.1")}

_vistos: dict[str, str] = {}
_paquetes = 0
_error: str | None = None
_lock = threading.Lock()

cliente = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"sensor-red-{os.getpid()}")
if os.getenv("MQTT_USER", "sensor"):
    cliente.username_pw_set(os.getenv("MQTT_USER", "sensor"), os.getenv("MQTT_PASS") or None)
cliente.reconnect_delay_set(1, 10)


def ver(mac: str, ip: str):
    global _paquetes
    with _lock:
        _paquetes += 1
        if ip and ip not in IGNORAR and mac:
            _vistos[mac.lower()] = ip


# ------------------------------------------------------------------ modo captura
def captura_real():
    from scapy.all import ARP, IP, Ether, conf, sniff
    conf.sniff_promisc = False  # el modo promiscuo lo fija el servicio lab-promisc de la VM

    def procesar(pkt):
        if not pkt.haslayer(Ether):
            return
        mac = pkt[Ether].src
        if pkt.haslayer(ARP):
            ver(pkt[ARP].hwsrc or mac, pkt[ARP].psrc)
        elif pkt.haslayer(IP):
            ver(mac, pkt[IP].src)

    global _error
    while True:
        try:
            log.info("capturando en %s", IFACE)
            _error = None
            sniff(iface=IFACE, prn=procesar, store=0)
        except Exception as e:
            _error = str(e)[:120]
            log.error("no se pudo capturar en %s (%s); reintento en 5 s", IFACE, e)
            time.sleep(5)


# ------------------------------------------------------------------ modo demostración
EQUIPOS = {
    "SRV-TRAZA": ("10.10.10.51", "02:42:0a:0a:0a:33", "SW-CIRC-A"),
    "CAM-01": ("10.10.10.52", "02:42:0a:0a:0a:34", "SW-CIRC-A"),
    "CAM-02": ("10.10.10.53", "02:42:0a:0a:0a:35", "SW-CIRC-A"),
    "LECT-01": ("10.10.10.54", "02:42:0a:0a:0a:36", "SW-CIRC-B"),
    "CAM-03": ("10.10.10.55", "02:42:0a:0a:0a:37", "SW-CIRC-B"),
}
demo = {"apagados": set(), "intruso": False, "sustituidos": {}}


def comando(_c, _u, msg):
    try:
        c = json.loads(msg.payload.decode())
    except Exception:
        return
    a = c.get("accion")
    if a == "apagar_switch" and c.get("switch"):
        demo["apagados"].add(c["switch"])
    elif a == "encender_switch" and c.get("switch"):
        demo["apagados"].discard(c["switch"])
    elif a == "conectar_intruso":
        demo["intruso"] = True
    elif a == "desconectar_intruso":
        demo["intruso"] = False
    elif a == "sustituir" and c.get("nombre") in EQUIPOS:
        demo["sustituidos"][c["nombre"]] = "02:42:de:ad:%02x:%02x" % (random.randint(0, 255), random.randint(0, 255))
    elif a == "restaurar":
        demo.update(apagados=set(), intruso=False, sustituidos={})
    log.info("demo: %s", a)


def trafico_demo():
    while True:
        caidos_por_uplink = "SW-CIRC-A" in demo["apagados"]  # el punto de captura cuelga de A
        for nombre, (ip, mac, sw) in EQUIPOS.items():
            if sw in demo["apagados"] or caidos_por_uplink:
                continue
            ver(demo["sustituidos"].get(nombre, mac), ip)
        if demo["intruso"] and not caidos_por_uplink:
            ver("02:42:0a:0a:0a:66", "10.10.10.66")
        time.sleep(1)


# ------------------------------------------------------------------ publicación
def publicar():
    global _paquetes
    while True:
        time.sleep(1)
        with _lock:
            hosts = [{"mac": m, "ip": ip} for m, ip in _vistos.items()]
            n = _paquetes
            _vistos.clear()
            _paquetes = 0
        cliente.publish("dc/red/observacion", json.dumps({"ts": time.time(), "modo": MODO, "iface": IFACE,
                                                          "paquetes": n, "hosts": hosts, "error": _error}), qos=0)


if __name__ == "__main__":
    host, puerto = os.getenv("MQTT_HOST", "127.0.0.1"), int(os.getenv("MQTT_PORT", "1883"))
    while True:
        try:
            cliente.connect(host, puerto, keepalive=30)
            break
        except Exception as e:
            log.warning("broker %s:%s no disponible (%s)", host, puerto, e)
            time.sleep(3)
    if MODO == "demo":
        cliente.on_message = comando
        cliente.on_connect = lambda c, u, f, rc, p: c.subscribe("dc/cmd/red", qos=1)
        threading.Thread(target=trafico_demo, daemon=True).start()
        log.warning("MODO DEMO: el tráfico es generado, no capturado")
    else:
        threading.Thread(target=captura_real, daemon=True).start()
    cliente.loop_start()
    publicar()
