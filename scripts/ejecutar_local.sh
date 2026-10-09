#!/usr/bin/env bash
# Ejecuta toda la plataforma sin Docker, como procesos locales, en modo demostración.
# Útil para desarrollar o si la GNS3 VM no tiene docker compose.
#   Requisitos: python3 >= 3.10, mosquitto y mosquitto_passwd en el PATH.
#   Uso:        ./scripts/ejecutar_local.sh        (Ctrl+C detiene todo)
#   Abrir:      http://localhost:8000   (WebAuthn acepta localhost como contexto seguro)
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
TMP="${TMP_PLATAFORMA:-$RAIZ/datos/local}"
MODO_RED="${MODO_RED:-demo}"
mkdir -p "$TMP"
PASS_PLAT="local-plataforma"; PASS_SENSOR="local-sensor"; PASS_SIM="local-sim"

# Broker con usuarios y ACL, igual que en Docker.
sed -e "s#/mosquitto/config#$TMP#g" -e "s#0.0.0.0#127.0.0.1#" "$RAIZ/broker/mosquitto.conf" > "$TMP/mosquitto.conf"
[ "$(id -u)" = "0" ] && echo "user root" >> "$TMP/mosquitto.conf"
cp "$RAIZ/broker/acl" "$TMP/acl"; rm -f "$TMP/passwd"; ( umask 077; : > "$TMP/passwd" )
mosquitto_passwd -b "$TMP/passwd" plataforma "$PASS_PLAT"
mosquitto_passwd -b "$TMP/passwd" sensor "$PASS_SENSOR"
mosquitto_passwd -b "$TMP/passwd" sim "$PASS_SIM"
chmod 0700 "$TMP/passwd" "$TMP/acl"

PIDS=()
trap 'kill "${PIDS[@]}" 2>/dev/null || true' EXIT INT TERM
mosquitto -c "$TMP/mosquitto.conf" > "$TMP/broker.log" 2>&1 & PIDS+=($!)
sleep 1

export MQTT_HOST=127.0.0.1 MQTT_PORT=1883
( cd "$RAIZ/plataforma" && DATOS_DIR="$TMP" RP_ID="${RP_ID:-localhost}" \
  ORIGENES="${ORIGENES:-http://localhost:8000}" MQTT_USER=plataforma MQTT_PASS="$PASS_PLAT" \
  ADMIN_CODIGO_ALTA="${ADMIN_CODIGO_ALTA:-}" API_DOCS="${API_DOCS:-true}" \
  python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$TMP/plataforma.log" 2>&1 ) & PIDS+=($!)
sleep 2
( cd "$RAIZ/simuladores" && MQTT_USER=sim MQTT_PASS="$PASS_SIM" FACTOR_TIEMPO="${FACTOR_TIEMPO:-30}" python3 ups.py > "$TMP/sim-ups.log" 2>&1 ) & PIDS+=($!)
( cd "$RAIZ/simuladores" && MQTT_USER=sim MQTT_PASS="$PASS_SIM" python3 ambiente.py > "$TMP/sim-ambiente.log" 2>&1 ) & PIDS+=($!)
( cd "$RAIZ/simuladores" && MQTT_USER=sim MQTT_PASS="$PASS_SIM" python3 puerta.py > "$TMP/sim-puerta.log" 2>&1 ) & PIDS+=($!)
( cd "$RAIZ/sensor-red" && MQTT_USER=sensor MQTT_PASS="$PASS_SENSOR" MODO="$MODO_RED" python3 capturador.py > "$TMP/sensor-red.log" 2>&1 ) & PIDS+=($!)

echo "Plataforma en http://localhost:8000  (registros en $TMP)"
grep -h "CÓDIGO DE ALTA" "$TMP/plataforma.log" || cat "$TMP/CODIGO_ALTA_ADMIN.txt" 2>/dev/null || true
wait
