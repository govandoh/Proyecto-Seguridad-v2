# Guía de Infraestructura — Replicación del Entorno de Red

Este documento describe **toda la infraestructura que NO está en el código**:
la GNS3 VM, la topología, los adaptadores de red y los ajustes del sistema.
Sin esto, la plataforma no tiene red que monitorear. Síguelo en orden.

> Todo el laboratorio corre **dentro de la GNS3 VM**. El equipo anfitrión
> (Windows) solo dibuja la topología y abre el tablero en el navegador.

---

## 1. Direccionamiento (mapa de referencia)

| Elemento | Red / IP | Notas |
|----------|----------|-------|
| Adaptador host-only (VirtualBox) | 192.168.56.0/24 | Control de GNS3 y acceso al tablero |
| GNS3 VM (eth0) | 192.168.56.101 | Por aquí se abre el tablero desde Windows |
| GNS3 VM (eth1) | NAT (10.0.x.x) | Salida a internet de la VM |
| **Topología del laboratorio** | **10.10.10.0/24** | Red interna de los switches |
| GNS3 VM (eth2, pie en la topología) | 10.10.10.1/24 | Puente por donde la plataforma "ve" la red |
| SRV-TRAZA (Alpine) | 10.10.10.51 | Cuelga de SW-CIRC-A |
| CAM-01 (Alpine) | 10.10.10.52 | Cuelga de SW-CIRC-A |
| CAM-02 (Alpine) | 10.10.10.53 | Cuelga de SW-CIRC-A |
| LECT-01 (Alpine) | 10.10.10.54 | Cuelga de SW-CIRC-B |
| CAM-03 (Alpine) | 10.10.10.55 | Cuelga de SW-CIRC-B (v2: permite distinguir la caída del conmutador) |
| PC-NAVE (Alpine `alpine-1`) | 10.10.10.99 | Cuelga de SW-CIRC-B; autorizado en el inventario |
| PC-INTRUSO (Alpine) | 10.10.10.66 | Cuelga de SW-CIRC-A; fuera del inventario, apagado hasta la demo |

---

## 2. Software base (equipo anfitrión)

1. Habilitar **virtualización (VT-x / AMD-V)** en el BIOS/UEFI.
2. Instalar **VirtualBox**.
3. Instalar **GNS3** (instalador todo-en-uno) e importar la **GNS3 VM** en VirtualBox.
4. En VirtualBox, confirmar que existe el adaptador **"VirtualBox Host-Only
   Ethernet Adapter"** (red 192.168.56.0/24 con DHCP habilitado). Si no existe,
   crearlo en *Herramientas → Red → Redes solo-anfitrión → Crear*.
5. En GNS3: *Help → Setup Wizard* → "Run appliances in the GNS3 VM" →
   motor **VirtualBox** → seleccionar **GNS3 VM**. Servidor local en
   **192.168.56.1**, puerto 3080. La VM debe quedar en verde.

---

## 3. Tercer adaptador de red de la GNS3 VM (el puente)

Con la GNS3 VM **apagada**, en VirtualBox:

1. *GNS3 VM → Configuración → Red → Adaptador 3*: habilitar.
2. "Conectado a" = **Red interna (Internal Network)**, nombre `topo-lab`.
3. *Avanzadas → Modo promiscuo* = **Permitir todo** (imprescindible).
4. Encender la VM. Este adaptador aparece dentro como **eth2**.

---

## 4. Configuración de red dentro de la GNS3 VM

Conectarse por SSH: `ssh gns3@192.168.56.101` (usuario y contraseña: `gns3`).

### 4.1 IP estática de eth2 (permanente, con netplan)

```bash
printf 'network:\n  version: 2\n  ethernets:\n    eth2:\n      dhcp4: false\n      dhcp6: false\n      addresses: [10.10.10.1/24]\n' | sudo tee /etc/netplan/90-lab.yaml
sudo chmod 600 /etc/netplan/90-lab.yaml
sudo netplan apply
```

### 4.2 Modo promiscuo y ajustes ARP (necesarios para la captura)

Hacer **permanentes** los ajustes del kernel (evita rehacerlos en cada arranque):

```bash
printf 'net.ipv4.conf.all.rp_filter=0\nnet.ipv4.conf.eth2.rp_filter=0\nnet.ipv4.conf.eth2.arp_ignore=0\nnet.ipv4.conf.eth2.arp_announce=0\n' | sudo tee /etc/sysctl.d/99-lab.conf
sudo sysctl --system
```

Poner eth2 en modo promiscuo a nivel de Linux en cada arranque. Crear un
servicio simple:

```bash
printf '[Unit]\nDescription=eth2 promiscuo lab\nAfter=network.target\n[Service]\nType=oneshot\nExecStart=/sbin/ip link set eth2 promisc on\nRemainAfterExit=yes\n[Install]\nWantedBy=multi-user.target\n' | sudo tee /etc/systemd/system/lab-promisc.service
sudo systemctl enable lab-promisc.service
sudo systemctl start lab-promisc.service
```

> Nota: originalmente estos ajustes se hacían a mano en cada sesión. Este
> paso los deja permanentes, que es lo recomendable para la demo.

---

## 5. Topología en GNS3

Crear un proyecto e importar `topologia.gns3project` (si se comparte), o
armarla a mano:

1. Dos switches **Open vSwitch**: `SW-CIRC-A` y `SW-CIRC-B`, unidos por un enlace (uplink).
2. Un nodo **Cloud** con la interfaz especial **eth2** agregada
   (marcar "Show special Ethernet interfaces"), conectado a **SW-CIRC-A**.
3. Nodos **Docker Alpine**: SRV-TRAZA, CAM-01, CAM-02 (a SW-CIRC-A), LECT-01 y
   CAM-03 (a SW-CIRC-B). PC-NAVE también a SW-CIRC-B. PC-INTRUSO a SW-CIRC-A, apagado hasta la prueba de intrusión.
4. (Opcional) Un nodo **Docker FreeRADIUS** como evidencia del autenticador 802.1X.

---

## 6. Configuración de cada endpoint Alpine (en cada arranque)

Los Alpine pierden su IP al reiniciar. En la consola de cada uno, ajustando la IP:

```bash
ip addr add 10.10.10.51/24 dev eth0    # .51 SRV-TRAZA, .52 CAM-01, .53 CAM-02, .54 LECT-01, .55 CAM-03, .99 PC-NAVE, .66 PC-INTRUSO
ip link set eth0 up
ping -i 1 10.10.10.1                    # latido continuo (dejar corriendo)
```

Ese `ping` continuo es el "latido" que la plataforma detecta como tráfico real.

---

## 7. Verificación del puente

Desde SSH en la VM, con los Alpine emitiendo:

```bash
sudo tcpdump -i eth2 -n arp
```

Deben verse llegar los `who-has ... tell 10.10.10.5X` de los endpoints. Con
eso confirmado, la plataforma podrá leer el tráfico.

---

## 8. Ejecutar la plataforma

Desde la versión 2 la plataforma corre con Docker Compose dentro de la GNS3 VM y ya no
necesita `sudo uvicorn`: la captura de eth2 la hace el contenedor `sensor-red` con solo
la capacidad CAP_NET_RAW. El procedimiento completo, con HTTPS, el archivo `hosts` de
Windows y el registro de la passkey, está en **[docs/DESPLIEGUE_GNS3.md](docs/DESPLIEGUE_GNS3.md)**.

```bash
cd ~/plataforma && ./scripts/generar_env.sh && docker compose up -d --build
```

Abrir en el navegador de Windows: `https://plataforma.test`

---

## 9. Notas del entorno (aprendidas en la implementación)

- **Dominio / firewall:** en equipos unidos a un dominio, el firewall puede
  bloquear ICMP (ping) entrante pero permitir TCP. Por eso la plataforma corre
  en la VM (no en Windows) y el tablero se abre por TCP en 192.168.56.101.
- **Cascada PoE (demo):** apagar **SW-CIRC-B**, no el A. El A hospeda el punto
  de captura (Cloud); apagarlo deja ciega a la plataforma, y la v2 lo reporta como
  `perdida_visibilidad` en lugar de cinco caídas.
- **Consolas de contenedor:** no usar Ctrl+C dentro de un contenedor (lo
  detiene). Para entrar a un contenedor: `docker ps` y `docker exec -it <ID> sh`.
- **Credenciales de la VM:** cambie la contraseña por defecto del usuario `gns3`
  con `passwd` antes de la demostración (hallazgo V4).
- **Reloj:** `sudo timedatectl set-ntp true` mantiene válidos los sellos de tiempo de la bitácora.
