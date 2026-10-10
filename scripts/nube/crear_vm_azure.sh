#!/usr/bin/env bash
# Crea la VM "dcim" del laboratorio en Azure, sin ningún puerto abierto a Internet.
# La VM entra a Tailscale en su primer arranque (cloud-init) y desde ahí se administra.
#
# Se ejecuta en Azure Cloud Shell (Bash):
#   export TS_AUTHKEY='tskey-auth-...'      # clave de un solo uso que entrega Gerardo
#   bash crear_vm_azure.sh
# Opcional: REGION=centralus bash crear_vm_azure.sh
set -euo pipefail

TS_AUTHKEY="${TS_AUTHKEY:?Defina antes: export TS_AUTHKEY='tskey-auth-...'}"
REGION="${REGION:-eastus2}"
GRUPO="rg-dcim"
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

echo "== Grupo de recursos $GRUPO en $REGION"
az group create -n "$GRUPO" -l "$REGION" -o none

creada=""
for TAMANO in Standard_B4ms Standard_B2ms; do
  echo "== Creando $VM con $TAMANO"
  if az vm create -g "$GRUPO" -n "$VM" \
      --image Canonical:ubuntu-24_04-lts:server:latest \
      --size "$TAMANO" \
      --admin-username gns3 --ssh-key-values "$LLAVE" \
      --os-disk-size-gb 64 --storage-sku StandardSSD_LRS \
      --public-ip-sku Standard --nsg-rule NONE \
      --custom-data "$INIT" -o none; then
    creada="$TAMANO"; break
  fi
  echo "   $TAMANO no disponible (cuota o región); se intenta el siguiente tamaño"
done
[ -n "$creada" ] || { echo "No se pudo crear la VM. Pruebe otra región: REGION=centralus bash $0"; exit 1; }

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
