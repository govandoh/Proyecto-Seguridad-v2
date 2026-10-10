#!/usr/bin/env bash
# Abre el proyecto GNS3 "Topologia" y enciende sus nodos, salvo PC-INTRUSO (se enciende en el
# escenario R1). Lo ejecuta el servicio dcim-topologia al arrancar la VM, y puede correrse a mano:
#   bash ~/plataforma/scripts/nube/arrancar_topologia.sh
# También desactiva el cierre automático del proyecto: sin eso, GNS3 lo cierra (y apaga los
# nodos) cuando se desconecta el último cliente, y la plataforma reporta pérdida de visibilidad.
set -euo pipefail

PROYECTO="${PROYECTO:-6e8687ec-a6b4-4bb1-9ed7-481ea40e4864}"
EXCLUIR="${EXCLUIR:-PC-INTRUSO}"
CLAVE="$(grep '^clave=' "$HOME/gns3_credenciales.txt" | cut -d= -f2)"
API="http://127.0.0.1:3080/v2"
c() { curl -sf -u "gns3:$CLAVE" "$@"; }

for _ in $(seq 1 60); do c "$API/version" >/dev/null && break; sleep 2; done
c -X POST "$API/projects/$PROYECTO/open" -d '{}' >/dev/null || true
c -X PUT "$API/projects/$PROYECTO" -d '{"auto_close": false, "auto_open": true}' >/dev/null

c "$API/projects/$PROYECTO/nodes" | python3 -c '
import json, sys
excluir = set(sys.argv[1].split(","))
orden = {"SW-CIRC-A": 0, "SW-CIRC-B": 1}
nodos = [n for n in json.load(sys.stdin) if n["node_type"] == "docker" and n["name"] not in excluir]
for n in sorted(nodos, key=lambda n: orden.get(n["name"], 2)):
    print(n["node_id"], n["name"], n["status"])
' "$EXCLUIR" | while read -r id nombre estado; do
  if [ "$estado" != "started" ]; then
    c -X POST "$API/projects/$PROYECTO/nodes/$id/start" -d '{}' >/dev/null && echo "encendido: $nombre"
  else
    echo "ya estaba encendido: $nombre"
  fi
done
# GNS3 a veces no aplica la MAC fijada en el proyecto al recrear un contenedor, y la plataforma
# lo reporta como suplantación. Se compara la MAC real de eth0 con la del proyecto y, si
# difiere, se reinicia ese nodo (hasta 3 intentos).
sleep 5
c "$API/projects/$PROYECTO/nodes" | python3 -c '
import json, sys
excluir = set(sys.argv[1].split(","))
for n in json.load(sys.stdin):
    mac = n["properties"].get("mac_address")
    if n["node_type"] == "docker" and n["name"] not in excluir and mac and not n["name"].startswith("SW-"):
        print(n["node_id"], n["name"], mac)
' "$EXCLUIR" | while read -r id nombre mac; do
  for intento in 1 2 3; do
    real="$(docker exec "GNS3.${nombre}.${PROYECTO}" cat /sys/class/net/eth0/address 2>/dev/null || true)"
    [ "$real" = "$mac" ] && break
    echo "MAC de $nombre es '$real', se esperaba $mac: reinicio $intento"
    c -X POST "$API/projects/$PROYECTO/nodes/$id/stop" -d '{}' >/dev/null || true
    sleep 2
    c -X POST "$API/projects/$PROYECTO/nodes/$id/start" -d '{}' >/dev/null || true
    sleep 4
  done
done
echo "Topología lista; $EXCLUIR queda apagado."
