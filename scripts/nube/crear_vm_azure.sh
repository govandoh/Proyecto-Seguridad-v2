#!/usr/bin/env bash
# Crea la VM "dcim" del laboratorio en Azure, sin ningún puerto abierto a Internet.
# La VM entra a Tailscale en su primer arranque (cloud-init) y desde ahí se administra.
#
# Se ejecuta en Azure Cloud Shell (Bash):
#   export TS_AUTHKEY='tskey-auth-...'      # clave de un solo uso que entrega Gerardo
#   bash crear_vm_azure.sh
# Opcional: REGION=<región> o TAMANOS="Standard_X Standard_Y" para fijar región o tamaños.
set -euo pipefail

TS_AUTHKEY="${TS_AUTHKEY:?Defina antes: export TS_AUTHKEY='tskey-auth-...'}"
GRUPO="rg-dcim"

# Las suscripciones Azure for Students solo permiten algunas regiones (política
# "allowed locations") y tienen cuotas de vCPU por familia de tamaño. El script prueba las
# regiones permitidas, ordenadas por cercanía a Guatemala, y en cada una varios tamaños, hasta
# que una combinación funcione. REGION y TAMANOS permiten fijarlos.
PERMITIDAS="$(az policy assignment list --query "[].parameters.listOfAllowedLocations.value[]" -o tsv 2>/dev/null | tr -d '\r' | tr '[:upper:]' '[:lower:]' | sort -u || true)"
[ -n "$PERMITIDAS" ] && echo "== Regiones permitidas por la suscripción: $(echo $PERMITIDAS)"
if [ -n "${REGION:-}" ]; then
  REGIONES="$REGION"
else
  REGIONES=""
  for r in southcentralus centralus eastus2 eastus northcentralus westus3 westus2 westus mexicocentral brazilsouth chilecentral canadacentral; do
    if [ -z "$PERMITIDAS" ] || echo "$PERMITIDAS" | grep -qx "$r"; then REGIONES="$REGIONES $r"; fi
  done
  for r in $PERMITIDAS; do echo "$REGIONES" | grep -qw "$r" || REGIONES="$REGIONES $r"; done
fi
# 4 vCPU primero (recomendado); 2 vCPU como respaldo. Familia D antes que B: las suscripciones de
# estudiante suelen tener cuota 0 en la familia B (standardBSFamily).
TAMANOS="${TAMANOS:-Standard_D4as_v5 Standard_D4s_v5 Standard_D2as_v5 Standard_D2s_v5 Standard_B4ms Standard_B2ms}"
echo "== Orden de prueba: regiones [$(echo $REGIONES)], tamaños [$(echo $TAMANOS)]"
VM="dcim"
# Llave pública SSH de Gerardo (es pública; la privada nunca sale de su equipo).
LLAVE="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIE6dgK9K6LzopT/Gfy3CcCtNWDD/RVm6SrnMyKkncnNY govan@MSI-gns3vm"

INIT="$(mktemp)"
cat > "$INIT" <<EOF
#cloud-config
runcmd:
  - curl -fsSL https://tailscale.com/install.sh | sh
  - tailscale up --auth-key=${TS_AUTHKEY} --hostname=dcim
EOF

ERR="$(mktemp)"
trap 'rm -f "$INIT" "$ERR"' EXIT

echo "== Grupo de recursos $GRUPO"
if [ "$(az group exists -n "$GRUPO")" = "true" ]; then
  if az vm show -g "$GRUPO" -n "$VM" -o none 2>/dev/null; then
    echo "La VM $VM ya existe en $GRUPO; no se crea otra."; exit 0
  fi
  echo "   ya existe, de un intento anterior"
else
  az group create -n "$GRUPO" -l "$(echo $REGIONES | awk '{print $1}')" -o none
fi

# Quita los restos de un intento fallido (red, IP, NIC) para poder reintentar en otra región.
limpiar() {
  for tipo in Microsoft.Network/networkInterfaces Microsoft.Network/publicIPAddresses \
              Microsoft.Network/networkSecurityGroups Microsoft.Network/virtualNetworks Microsoft.Compute/disks; do
    ids="$(az resource list -g "$GRUPO" --resource-type "$tipo" --query "[].id" -o tsv | tr -d '\r')"
    [ -n "$ids" ] && az resource delete --ids $ids -o none 2>/dev/null || true
  done
}

creada=""
for REGION in $REGIONES; do
  limpiar
  for TAMANO in $TAMANOS; do
    echo "== Probando $TAMANO en $REGION"
    if az vm create -g "$GRUPO" -n "$VM" -l "$REGION" \
        --image Canonical:ubuntu-24_04-lts:server:latest \
        --size "$TAMANO" \
        --admin-username gns3 --ssh-key-values "$LLAVE" \
        --os-disk-size-gb 64 --storage-sku StandardSSD_LRS \
        --public-ip-sku Standard --nsg-rule NONE \
        --custom-data "$INIT" -o none 2>"$ERR"; then
      creada="$TAMANO en $REGION"; break 2
    fi
    motivo="$(grep -hoE '(Code|code)"?: ?"?[A-Za-z]+' "$ERR" | sort -u | tr '\n' ' ' || true)"
    echo "   no se pudo: ${motivo:-ver detalle abajo}"
    grep -hE 'Message: ' "$ERR" | head -1 | cut -c1-240 | sed 's/^/   /' || true
  done
done
[ -n "$creada" ] || { echo "Ninguna combinación funcionó. Envíe esta salida a Gerardo."; exit 1; }

echo "== Apagado automático diario a las 23:00 de Guatemala (05:00 UTC)"
az vm auto-shutdown -g "$GRUPO" -n "$VM" --time 0500 -o none

echo "== Reglas de entrada del grupo de seguridad (deben ser solo las predeterminadas de Azure)"
az network nsg rule list -g "$GRUPO" --nsg-name "${VM}NSG" -o table || true

echo
az vm show -d -g "$GRUPO" -n "$VM" \
  --query "{vm:name, tamano:hardwareProfile.vmSize, region:location, estado:powerState, ip:publicIps}" -o table
echo
echo "Listo ($creada). En unos 2 minutos 'dcim' debe aparecer en la consola de Tailscale de Gerardo."
echo "Si no aparece: portal -> VM dcim -> Ayuda -> Diagnóstico de arranque -> Registro serie."
