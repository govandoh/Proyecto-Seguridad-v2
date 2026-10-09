#!/usr/bin/env bash
# Crea .env a partir de .env.example con contraseñas aleatorias para el broker.
#   ./scripts/generar_env.sh                     modo https     (https://plataforma.test, Caddy con CA local)
#   ./scripts/generar_env.sh localhost           modo localhost (http://localhost:8000 por túnel SSH)
#   ./scripts/generar_env.sh nube <dominio>      modo nube      (https://<dominio> por tailscale serve, captura en br-lab)
set -euo pipefail
cd "$(dirname "$0")/.."
MODO="${1:-https}"
DOMINIO="${2:-}"
if [ -f .env ]; then echo ".env ya existe; no se sobrescribe (bórrelo para regenerarlo)"; exit 0; fi
if [ "$MODO" = "nube" ] && [ -z "$DOMINIO" ]; then echo "Uso: $0 nube <dominio, p. ej. dcim.tailnet.ts.net>"; exit 1; fi
aleatorio() { head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24; }
sed -e "s/^MQTT_PASS_PLATAFORMA=.*/MQTT_PASS_PLATAFORMA=$(aleatorio)/" \
    -e "s/^MQTT_PASS_SENSOR=.*/MQTT_PASS_SENSOR=$(aleatorio)/" \
    -e "s/^MQTT_PASS_SIM=.*/MQTT_PASS_SIM=$(aleatorio)/" .env.example > .env
if [ "$MODO" = "localhost" ]; then
  sed -i -e "s#^RP_ID=.*#RP_ID=localhost#" -e "s#^ORIGENES=.*#ORIGENES=http://localhost:8000#" .env
  echo "COMPOSE_FILE=docker-compose.yml:docker-compose.localhost.yml" >> .env
elif [ "$MODO" = "nube" ]; then
  sed -i -e "s#^RP_ID=.*#RP_ID=${DOMINIO}#" -e "s#^ORIGENES=.*#ORIGENES=https://${DOMINIO}#" \
         -e "s#^IFACE=.*#IFACE=br-lab#" -e "s#^MODO_RED=.*#MODO_RED=captura#" .env
  echo "COMPOSE_FILE=docker-compose.yml:docker-compose.nube.yml" >> .env
fi
chmod 600 .env
mkdir -p datos/caddy
echo ".env creado en modo $MODO con contraseñas aleatorias del broker"
