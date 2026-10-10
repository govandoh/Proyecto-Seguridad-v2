#!/usr/bin/env bash
# Crea la VM "dcim" del laboratorio en Azure, sin ningún puerto abierto a Internet.
# La VM entra a Tailscale en su primer arranque (cloud-init) y desde ahí se administra.
#
# Se ejecuta en Azure Cloud Shell (Bash):
#   export TS_AUTHKEY='tskey-auth-...'      # clave de un solo uso que entrega Gerardo
#   bash crear_vm_azure.sh
# Opcional: REGION=<región> bash crear_vm_azure.sh  (si no, elige la primera región permitida)
set -euo pipefail

TS_AUTHKEY="${TS_AUTHKEY:?Defina antes: export TS_AUTHKEY='tskey-auth-...'}"
GRUPO="rg-dcim"

# Las suscripciones Azure for Students solo permiten algunas regiones (política
# "allowed locations"). Si no se indica REGION, se toma la primera permitida de una lista
# ordenada por cercanía a Guatemala.
PERMITIDAS="$(az policy assignment list --query "[].parameters.listOfAllowedLocations.value[]" -o tsv 2>/dev/null | tr '[:upper:]' '[:lower:]' | sort -u || true)"
if [ -n "$PERMITIDAS" ]; then
  echo "== Regiones permitidas por la suscripción: $(echo $PERMITIDAS)"
fi
if [ -z "${REGION:-}" ]; then
  for r in southcentralus centralus eastus2 eastus northcentralus westus3 westus2 westus mexicocentral brazilsouth canadacentral; do
    if [ -z "$PERMITIDAS" ] || echo "$PERMITIDAS" | grep -qx "$r"; then REGION="$r"; break; fi
  done
  REGION="${REGION:-$(echo "$PERMITIDAS" | head -1)}"
fi
if [ -n "$PERMITIDAS" ] && ! echo "$PERMITIDAS" | grep -qx "$REGION"; then
  echo "La región $REGION no está permitida. Use una de: $(echo $PERMITIDAS)"; exit 1
fi
echo "== Región elegida: $REGION"
VM="dcim"
# Llave pública SSH de Gerardo (es pública; la privada nunca sale de su equipo).
LLAVE="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIE6dgK9K6LzopT/Gfy3CcCtNWDD/RVm6SrnMyKkncnNY govan@MSI-gns3vm"

INIT="$(mktemp)"
trap 'rm -f "$INIT"' EXIT
cat > "$INIT" <<EOF
#cloud-config
runcmd:
  - curl -fsSL https://tailscale.com/install.sh | sh
  - tailscale up --auth-key=${TS_AUTHKEY} --hostname=dcim
EOF

echo "== Grupo de recursos $GRUPO"
if [ "$(az group exists -n "$GRUPO")" = "true" ]; then
  echo "   ya existe (de un intento anterior); los recursos se crean en $REGION de todas formas"
else
  az group create -n "$GRUPO" -l "$REGION" -o none
fi

creada=""
for TAMANO in Standard_B4ms Standard_B2ms; do
  echo "== Creando $VM con $TAMANO"
  if az vm create -g "$GRUPO" -n "$VM" -l "$REGION" \
      --image Canonical:ubuntu-24_04-lts:server:latest \
      --size "$TAMANO" \
      --admin-username gns3 --ssh-key-values "$LLAVE" \
      --os-disk-size-gb 64 --storage-sku StandardSSD_LRS \
      --public-ip-sku Standard --nsg-rule NONE \
      --custom-data "$INIT" -o none; then
    creada="$TAMANO"; break
  fi
  echo "   $TAMANO no se pudo crear en $REGION; se intenta el siguiente tamaño"
done
[ -n "$creada" ] || { echo "No se pudo crear la VM en $REGION. Pruebe otra permitida: REGION=<región> bash $0"; exit 1; }

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
