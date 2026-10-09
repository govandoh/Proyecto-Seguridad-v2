"""Cliente MQTT de la plataforma (paho-mqtt 2.x).

Tópicos (detalle en docs/MQTT_TOPICOS.md):
  dc/red/observacion      capturador -> plataforma
  dc/energia/ups          sim-ups -> plataforma
  dc/energia/prueba       sim-ups -> plataforma
  dc/ambiente/lectura     sim-ambiente -> plataforma
  dc/ambiente/alarma      sim-ambiente -> plataforma
  dc/acceso/lectura       sim-puerta -> plataforma
  dc/acceso/puerta        sim-puerta -> plataforma
  dc/acceso/cmd           plataforma -> sim-puerta
  dc/cmd/<dispositivo>    plataforma (consola de simulación) -> simuladores
"""

import json
import logging
import threading

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from . import config

log = logging.getLogger("bus")


class Bus:
    def __init__(self):
        self.manejadores: list[tuple[str, callable]] = []
        self.conectado = threading.Event()
        self.cliente = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="plataforma", clean_session=True)
        if config.MQTT_USER:
            self.cliente.username_pw_set(config.MQTT_USER, config.MQTT_PASS or None)
        self.cliente.on_connect = self._on_connect
        self.cliente.on_disconnect = self._on_disconnect
        self.cliente.on_message = self._on_message
        self.cliente.reconnect_delay_set(1, 10)

    def suscribir(self, filtro: str, funcion):
        self.manejadores.append((filtro, funcion))

    def iniciar(self):
        def _conectar():
            while True:
                try:
                    self.cliente.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
                    break
                except Exception as e:  # broker aún no disponible
                    log.warning("MQTT %s:%s no disponible (%s); reintento en 3 s", config.MQTT_HOST, config.MQTT_PORT, e)
                    threading.Event().wait(3)
            self.cliente.loop_forever(retry_first_connection=True)
        threading.Thread(target=_conectar, daemon=True, name="mqtt").start()

    def detener(self):
        try:
            self.cliente.disconnect()
        except Exception:
            pass

    def publicar(self, topico: str, datos: dict, retener: bool = False):
        self.cliente.publish(topico, json.dumps(datos, ensure_ascii=False), qos=1, retain=retener)

    # --- callbacks
    def _on_connect(self, cliente, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("MQTT rechazó la conexión: %s", reason_code)
            return
        log.info("MQTT conectado a %s:%s", config.MQTT_HOST, config.MQTT_PORT)
        for filtro, _ in self.manejadores:
            cliente.subscribe(filtro, qos=1)
        self.conectado.set()

    def _on_disconnect(self, cliente, userdata, flags, reason_code, properties):
        self.conectado.clear()
        log.warning("MQTT desconectado (%s)", reason_code)

    def _on_message(self, cliente, userdata, msg):
        try:
            datos = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            log.warning("mensaje no JSON en %s descartado", msg.topic)
            return
        if not isinstance(datos, dict):
            return
        for filtro, funcion in self.manejadores:
            if mqtt.topic_matches_sub(filtro, msg.topic):
                try:
                    funcion(msg.topic, datos)
                except Exception:
                    log.exception("error procesando %s", msg.topic)


bus = Bus()
