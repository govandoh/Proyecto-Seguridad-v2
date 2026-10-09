#!/bin/sh
# Genera el archivo de contraseñas del broker a partir de las variables de entorno.
set -e
: "${MQTT_PASS_PLATAFORMA:?falta MQTT_PASS_PLATAFORMA}"
: "${MQTT_PASS_SENSOR:?falta MQTT_PASS_SENSOR}"
: "${MQTT_PASS_SIM:?falta MQTT_PASS_SIM}"
mkdir -p /mosquitto/config
cp /config-base/mosquitto.conf /config-base/acl /mosquitto/config/
rm -f /mosquitto/config/passwd
touch /mosquitto/config/passwd
mosquitto_passwd -b /mosquitto/config/passwd plataforma "$MQTT_PASS_PLATAFORMA"
mosquitto_passwd -b /mosquitto/config/passwd sensor "$MQTT_PASS_SENSOR"
mosquitto_passwd -b /mosquitto/config/passwd sim "$MQTT_PASS_SIM"
chown -R mosquitto:mosquitto /mosquitto/config
chmod 0700 /mosquitto/config/passwd /mosquitto/config/acl
exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
