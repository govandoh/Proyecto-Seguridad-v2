"""Utilidades comunes de los dispositivos simulados."""

import json
import logging
import os
import threading
import time

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def env_float(nombre, defecto):
    try:
        return float(os.getenv(nombre, defecto))
    except ValueError:
        return float(defecto)


class Dispositivo:
    """Cliente MQTT con reconexión automática y despacho de comandos."""

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.log = logging.getLogger(nombre)
        self.manejadores = {}
        self.cliente = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"{nombre}-{os.getpid()}")
        usuario = os.getenv("MQTT_USER", "sim")
        if usuario:
            self.cliente.username_pw_set(usuario, os.getenv("MQTT_PASS") or None)
        self.cliente.on_connect = self._on_connect
        self.cliente.on_message = self._on_message
        self.cliente.reconnect_delay_set(1, 10)
        self.lock = threading.RLock()

    def suscribir(self, topico, funcion):
        self.manejadores[topico] = funcion

    def publicar(self, topico, datos, retener=False):
        self.cliente.publish(topico, json.dumps(datos, ensure_ascii=False), qos=0, retain=retener)

    def _on_connect(self, cliente, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self.log.error("conexión MQTT rechazada: %s", reason_code)
            return
        self.log.info("conectado al broker")
        for t in self.manejadores:
            cliente.subscribe(t, qos=1)

    def _on_message(self, cliente, userdata, msg):
        try:
            datos = json.loads(msg.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        for filtro, funcion in self.manejadores.items():
            if mqtt.topic_matches_sub(filtro, msg.topic) and isinstance(datos, dict):
                try:
                    with self.lock:
                        funcion(msg.topic, datos)
                except Exception:
                    self.log.exception("error en %s", msg.topic)

    def arrancar(self, paso, periodo=1.0):
        host, puerto = os.getenv("MQTT_HOST", "127.0.0.1"), int(os.getenv("MQTT_PORT", "1883"))
        while True:
            try:
                self.cliente.connect(host, puerto, keepalive=30)
                break
            except Exception as e:
                self.log.warning("broker %s:%s no disponible (%s); reintento", host, puerto, e)
                time.sleep(3)
        self.cliente.loop_start()
        siguiente = time.monotonic()
        while True:
            with self.lock:
                try:
                    paso()
                except Exception:
                    self.log.exception("error en el ciclo")
            siguiente += periodo
            time.sleep(max(0.0, siguiente - time.monotonic()))
