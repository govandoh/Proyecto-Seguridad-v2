# Arranque diario del laboratorio

Hoja corta para encender todo en orden y saber qué hacer si algo falla. El detalle está en
`DESPLIEGUE_GNS3.md` y `GUIA_INFRAESTRUCTURA.md`.

## 1. Orden de encendido

| # | Acción | Cómo se comprueba |
|---|---|---|
| 1 | Abrir GNS3 en Windows. Arranca la GNS3 VM en VirtualBox | En *Servers Summary*, "GNS3 VM" en verde |
| 2 | Abrir el proyecto `D:\PROYECTO-SEGURIDAD\Topologia\Topologia.gns3` | Se ven SW-CIRC-A, SW-CIRC-B, los Alpine y Cloud1 |
| 3 | Botón ▶ *Start all nodes*. Dejar PC-INTRUSO apagado | Todos los nodos en verde salvo PC-INTRUSO |
| 4 | Revisar que el enlace de Cloud1 sea **eth2** con SW-CIRC-A eth4 | *Topology Summary*: `eth2 <=> eth4 SW-CIRC-A` |
| 5 | Nada que hacer: cada Alpine levanta su IP y su ping al arrancar (sección 2) | La pestaña Red muestra los equipos "En línea" |
| 6 | Abrir el túnel en **PowerShell de Windows**, no en la VM (ver abajo) | Dejar esa ventana abierta |
| 7 | Entrar a **http://localhost:8000** con contraseña y passkey del teléfono | Tablero con "Captura real eth2" |

Los scripts de `scripts\windows\` se ejecutan en Windows, nunca dentro de la VM:

```powershell
cd D:\PROYECTO-SEGURIDAD\Proyecto-Seguridad-v2\Proyecto-Seguridad-v2
powershell -ExecutionPolicy Bypass -File .\scripts\windows\tunel.ps1
```

La plataforma v2 arranca sola con la VM (Docker con `restart: unless-stopped`).

## 1 bis. Cuándo ejecutar `desplegar.ps1`

**No forma parte del arranque diario.** Se ejecuta solo en estos casos:

| Caso | ¿Desplegar? |
|---|---|
| Encender el laboratorio para trabajar o para la demo | **No** |
| Se modificó código en Windows (carpetas `plataforma`, `simuladores`, `sensor-red`, `broker`, `docker-compose*.yml`) | **Sí** |
| La VM se reinstaló o se borró `~/plataforma` | **Sí**: crea `.env` nuevo y genera un código de alta para `admin` |
| `docker compose ps` muestra servicios caídos que no vuelven con `docker compose up -d` | Sí, como segundo intento |
| Durante la demostración | **Nunca**: reinicia el capturador y registra una pérdida de visibilidad |

Se ejecuta en PowerShell de Windows:

```powershell
cd D:\PROYECTO-SEGURIDAD\Proyecto-Seguridad-v2\Proyecto-Seguridad-v2
powershell -ExecutionPolicy Bypass -File .\scripts\windows\desplegar.ps1
```

Qué hace: empaqueta el código (sin `datos/` ni `.env`), lo copia a `~/plataforma` en la VM,
corrige los finales de línea de Windows, crea el `.env` solo si no existe y ejecuta
`docker compose up -d --build`. Conserva la base, los usuarios, las passkeys y la bitácora.
Tarda de 1 a 3 minutos; al final muestra los 6 servicios. Después hay que volver a abrir el
túnel si estaba cerrado.

## 2. IP y latido de los Alpine

Cada Alpine tiene la IP y el latido fijos en *clic derecho → Edit config*
(`/etc/network/interfaces`), y se aplican solos al arrancar el nodo:

```
auto eth0
iface eth0 inet static
	address 10.10.10.5X
	netmask 255.255.255.0
	up ping -i 1 10.10.10.1 >/dev/null 2>&1 &
```

Al crear un nodo nuevo, revisar que su `address` no repita la de otro: dos equipos con la
misma IP disparan la alerta `suplantacion`.

Solo si un nodo no levanta la IP, se pone a mano en su consola (se pierde al reiniciar):

```sh
ip addr add 10.10.10.5X/24 dev eth0
ip link set eth0 up
(ping -i 1 10.10.10.1 >/dev/null 2>&1 &)
```

| Nodo | IP | Conmutador |
|---|---|---|
| SRV-TRAZA | 10.10.10.51 | SW-CIRC-A |
| CAM-01 | 10.10.10.52 | SW-CIRC-A |
| CAM-02 | 10.10.10.53 | SW-CIRC-A |
| LECT-01 | 10.10.10.54 | SW-CIRC-B |
| CAM-03 | 10.10.10.55 | SW-CIRC-B |
| PC-NAVE (`alpine-1`) | 10.10.10.99 | SW-CIRC-B |
| PC-INTRUSO | 10.10.10.66 | SW-CIRC-A, solo en la demo |

El `ping` hacia 10.10.10.1 no recibe respuesta y es normal: la plataforma detecta a los
equipos por sus solicitudes ARP, no por la respuesta.

No usar `Ctrl+C` en la consola de un contenedor: puede detenerlo. Por eso el ping va en
segundo plano.

## 3. Comprobaciones rápidas

En PowerShell, desde la carpeta del proyecto:

```powershell
ssh gns3@192.168.56.101 "cd ~/plataforma && docker compose ps"        # 6 servicios Up; plataforma (healthy)
ssh gns3@192.168.56.101 "curl -s http://127.0.0.1:8000/salud"          # {"estado":"ok","mqtt":true}
ssh gns3@192.168.56.101 "cd ~/plataforma && docker compose logs --tail 20 sensor-red"   # "capturando en eth2"
```

## 4. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| Los nodos se ven en verde, pero la consola no abre o rechaza la conexión | La VM perdió el proyecto. *File → Close project* y volver a abrirlo; luego ▶ *Start all nodes* |
| Red sin equipos en línea | Los Alpine perdieron la IP: repetir la sección 2. Revisar que Cloud1 use **eth2** |
| Todos los equipos caen a la vez (`perdida_visibilidad`) | SW-CIRC-A apagado, enlace de Cloud1 roto o `sensor-red` reiniciado (pasa en cada despliegue) |
| `http://localhost:8000` no carga | El túnel está cerrado: `.\scripts\windows\tunel.ps1`. Si dice puerto ocupado, ya hay un túnel abierto |
| Pide sesión de nuevo | La sesión vence a los 15 min de inactividad. Volver a entrar |
| La passkey no aparece o falla | Elegir **"Save another way" → "Cambiar" → "iPhone, iPad o dispositivo Android"** y escanear el QR con el teléfono. Bluetooth encendido en la PC y en el teléfono |
| Windows Hello "no disponible en este momento" | El equipo tiene una cuenta de organización que lo bloquea. Usar el teléfono |
| El autenticador virtual de Chrome (DevTools → WebAuthn) | Solo para pruebas. Si es la única passkey de una cuenta y se cierra DevTools, la cuenta queda bloqueada |
| Cuenta bloqueada o sin passkey válida | En la VM: `cd ~/plataforma && docker compose exec plataforma python -m app.recuperar admin`. Da un código nuevo para `/alta`, conserva la bitácora y registra la recuperación |
| `ssh` pide contraseña | La llave no está instalada en la VM. Ver `DESPLIEGUE_GNS3.md` §8 |
| Los cambios de la página no se ven | Recargar con `Ctrl+F5` |

## 5. Lo que no se debe hacer

- Editar `Topologia.gns3` o `project-files\` a mano con GNS3 abierto: los cambios de topología se hacen en la interfaz.
- `docker system prune`, `docker rm` o `docker stop` sobre contenedores ajenos a `plataforma-dcim`: los nodos de GNS3 son contenedores del mismo Docker.
- `docker compose down -v`: borra la base, los usuarios, las passkeys y la bitácora. Para recuperar una cuenta basta `app.recuperar`.
- Redesplegar durante la demostración: reinicia el capturador y deja un evento de pérdida de visibilidad.

## 6. Datos de prueba

| Tarjeta | Titular | PIN | Coacción | Estado |
|---|---|---|---|---|
| C-1001 | Técnico de turno A | 1357 | 1358 | activa |
| C-1002 | Custodio de la sala | 2468 | 2469 | activa |
| C-1003 | Exempleado de mantenimiento | 1111 | 1112 | revocada |

Cuentas: `admin` (administrador) y `operador` (operador), ambas con passkey en el teléfono.
