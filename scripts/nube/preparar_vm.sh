#!/usr/bin/env bash
# Prepara una VM Ubuntu 24.04 (Azure) para la topología GNS3 y la plataforma DCIM.
# Se ejecuta en la VM como el usuario administrador (sudo sin contraseña de Azure):
#   bash ~/plataforma/scripts/nube/preparar_vm.sh
# Es idempotente: puede repetirse sin efectos secundarios.
#
# Instala: Docker Engine + Compose, gns3-server (misma versión que el cliente de Windows),
# ubridge, Tailscale, la red del laboratorio br-lab (10.10.10.1/24) y el cortafuegos.
set -euo pipefail

GNS3_VERSION="${GNS3_VERSION:-2.2.61}"
USUARIO="$(id -un)"
HOGAR="$(getent passwd "$USUARIO" | cut -d: -f6)"
paso() { printf '\n== %s\n' "$*"; }

paso "Paquetes base"
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq ca-certificates curl gnupg pipx \
  python3-dev build-essential software-properties-common ufw libcap2-bin

paso "Docker Engine y Compose (repositorio oficial)"
if ! command -v docker >/dev/null; then
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -q
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
fi
sudo usermod -aG docker "$USUARIO"

paso "Módulo openvswitch (lo usa la imagen gns3/openvswitch)"
if ! sudo modprobe openvswitch 2>/dev/null; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq "linux-modules-extra-$(uname -r)" || true
  sudo modprobe openvswitch
fi
echo openvswitch | sudo tee /etc/modules-load.d/openvswitch.conf >/dev/null

paso "ubridge (PPA de GNS3)"
if ! command -v ubridge >/dev/null; then
  sudo add-apt-repository -y ppa:gns3/ppa
  sudo apt-get update -q
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq ubridge
fi
sudo setcap cap_net_admin,cap_net_raw=ep "$(command -v ubridge)"

paso "gns3-server $GNS3_VERSION"
if ! "$HOGAR/.local/bin/gns3server" --version 2>/dev/null | grep -q "$GNS3_VERSION"; then
  pipx install --force "gns3-server==$GNS3_VERSION"
fi
CONF_DIR="$HOGAR/.config/GNS3/2.2"
mkdir -p "$CONF_DIR" "$HOGAR/GNS3/projects" "$HOGAR/GNS3/images"
if [ ! -f "$CONF_DIR/gns3_server.conf" ]; then
  CLAVE="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)"
  cat > "$CONF_DIR/gns3_server.conf" <<EOF
[Server]
host = 0.0.0.0
port = 3080
auth = True
user = gns3
password = $CLAVE
projects_path = $HOGAR/GNS3/projects
images_path = $HOGAR/GNS3/images
ubridge_path = $(command -v ubridge)
console_start_port_range = 5000
console_end_port_range = 10000
udp_start_port_range = 10000
udp_end_port_range = 20000
EOF
  chmod 600 "$CONF_DIR/gns3_server.conf"
  printf 'Servidor GNS3\nusuario=gns3\nclave=%s\n' "$CLAVE" > "$HOGAR/gns3_credenciales.txt"
  chmod 600 "$HOGAR/gns3_credenciales.txt"
fi

paso "Red del laboratorio: br-lab 10.10.10.1/24 con el par veth lab-gns <-> lab-br"
# El nodo Cloud de GNS3 se conecta a lab-gns (como hoy a eth2 de la GNS3 VM). Lo que entra por
# lab-gns sale por lab-br al puente br-lab, donde está la IP 10.10.10.1 y donde captura sensor-red.
sudo tee /etc/systemd/system/lab-red.service >/dev/null <<'EOF'
[Unit]
Description=Red del laboratorio DCIM (br-lab 10.10.10.1/24 y veth para el Cloud de GNS3)
After=network.target
Before=docker.service gns3server.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'ip link show br-lab >/dev/null 2>&1 || ip link add br-lab type bridge; \
  ip link show lab-gns >/dev/null 2>&1 || ip link add lab-gns type veth peer name lab-br; \
  ip link set lab-br master br-lab; ip addr replace 10.10.10.1/24 dev br-lab; \
  ip link set br-lab up; ip link set lab-br up; ip link set lab-gns up; \
  ip link set br-lab promisc on; ip link set lab-br promisc on; ip link set lab-gns promisc on'
ExecStop=/bin/sh -c 'ip link del lab-gns 2>/dev/null; ip link del br-lab 2>/dev/null; true'

[Install]
WantedBy=multi-user.target
EOF

paso "Servicio gns3server"
sudo tee /etc/systemd/system/gns3server.service >/dev/null <<EOF
[Unit]
Description=Servidor GNS3 $GNS3_VERSION
After=network-online.target docker.service lab-red.service
Wants=network-online.target
Requires=docker.service

[Service]
User=$USUARIO
Group=$USUARIO
SupplementaryGroups=docker
ExecStart=$HOGAR/.local/bin/gns3server
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now lab-red.service gns3server.service

paso "Servicio dcim-topologia: abre el proyecto y enciende los nodos al arrancar la VM"
sudo tee /etc/systemd/system/dcim-topologia.service >/dev/null <<EOF
[Unit]
Description=Abre la topología GNS3 del laboratorio y enciende sus nodos (salvo PC-INTRUSO)
After=gns3server.service lab-red.service
Requires=gns3server.service

[Service]
Type=oneshot
User=$USUARIO
ExecStart=$HOGAR/plataforma/scripts/nube/arrancar_topologia.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable dcim-topologia.service

paso "Imágenes de la topología"
sudo docker pull -q alpine:latest
sudo docker pull -q gns3/openvswitch:latest
sudo docker pull -q freeradius/freeradius-server:latest

paso "Tailscale"
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

paso "Cortafuegos: solo SSH y la interfaz de Tailscale"
sudo ufw default deny incoming >/dev/null
sudo ufw default allow outgoing >/dev/null
sudo ufw allow in on tailscale0 >/dev/null
sudo ufw allow 22/tcp >/dev/null
sudo ufw --force enable >/dev/null

paso "Reloj (control 8.17)"
timedatectl | grep -E 'synchronized|NTP' || true

paso "Resumen"
ip -br addr show br-lab; ip -br link show lab-gns
systemctl is-active lab-red gns3server docker
"$HOGAR/.local/bin/gns3server" --version
docker compose version 2>/dev/null || sudo docker compose version
echo
echo "Listo. Siguiente: sudo tailscale up --hostname=dcim  (abrir el enlace que imprime)"
echo "Credenciales del servidor GNS3 en $HOGAR/gns3_credenciales.txt"
