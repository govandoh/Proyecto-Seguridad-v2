# Despliegue en la GNS3 VM

Esta guía parte de la infraestructura ya montada según
[GUIA_INFRAESTRUCTURA.md](../GUIA_INFRAESTRUCTURA.md): GNS3 VM en VirtualBox,
adaptador solo anfitrión `192.168.56.0/24` y puente `eth2` hacia la topología
`10.10.10.0/24`. Se recomienda subir la memoria de la VM a 4 GB.

## 0. Dos modos de acceso

| Modo | Cómo se abre | Cuándo usarlo |
|---|---|---|
| localhost | `http://localhost:8000` en Windows por túnel SSH; `./scripts/generar_env.sh localhost` | Trabajo diario y ensayo. Sin archivo `hosts` ni CA. Passkey con Windows Hello, llave FIDO2 o autenticador virtual |
| https | `https://plataforma.test` con Caddy; `./scripts/generar_env.sh` y `docker compose --profile https up -d` | Demostración con la passkey en el teléfono por QR |

En modo localhost se omiten las secciones 4 y la parte de Caddy; el túnel se abre en Windows con
`ssh -N -L 8000:127.0.0.1:8000 gns3@192.168.56.101`.

## 1. Docker Compose en la VM

La GNS3 VM trae Docker porque lo usa para los nodos de contenedor. Falta verificar el
plugin de Compose:

```bash
ssh gns3@192.168.56.101
docker --version
docker compose version       # si responde, pase al punto 2
```

Si `docker compose` no existe, se instala el plugin oficial:

```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version
```

Si el usuario `gns3` no pertenece al grupo `docker`, anteponga `sudo` a los comandos.

## 2. Código y configuración

```bash
cd ~
git clone https://github.com/CMario21/Proyecto-Seguridad.git plataforma
cd plataforma && git checkout plataforma-v2
./scripts/generar_env.sh
nano .env      # revisar: MODO_RED=captura, IFACE=eth2, RP_ID=plataforma.test
```

Si la versión 1 sigue corriendo con `sudo uvicorn`, deténgala con `Ctrl+C` o
`sudo pkill -f uvicorn`: la captura de eth2 ahora la hace el contenedor `sensor-red`.

## 3. Levantar el stack

```bash
docker compose --profile https up -d --build      # modo https; en modo localhost basta docker compose up -d --build
docker compose ps                                  # 7 servicios en modo https, 6 en modo localhost
docker compose logs -f plataforma                  # Ctrl+C para salir
docker compose logs plataforma | grep "CÓDIGO DE ALTA"
```

El código de alta del administrador se genera una vez y vence en 7 días. Si se pierde:
`docker compose down -v` borra la base y genera uno nuevo en el siguiente arranque.

El puerto 80 de la VM queda libre para el servidor de GNS3; la plataforma solo publica
el 443.

## 4. Preparar Windows

**Nombre de host.** WebAuthn no acepta direcciones IP. Como administrador, edite
`C:\Windows\System32\drivers\etc\hosts` y agregue:

```
192.168.56.101  plataforma.test
```

Comprobación en PowerShell: `Test-NetConnection plataforma.test -Port 443`.

**Confiar en la CA local de Caddy.** Desde la VM:

```bash
docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ./root.crt
```

Desde Windows, copie el archivo e impórtelo al almacén de raíces de confianza:

```powershell
scp gns3@192.168.56.101:~/plataforma/root.crt .
Import-Certificate -FilePath .\root.crt -CertStoreLocation Cert:\LocalMachine\Root   # PowerShell como administrador
```

Cierre y vuelva a abrir Chrome o Edge. `https://plataforma.test` debe cargar sin advertencia.

## 5. Activar la cuenta y registrar la passkey

Abra `https://plataforma.test/alta`, escriba `admin`, el código y una contraseña de al
menos 12 caracteres. En el segundo paso el navegador ofrece dónde guardar la passkey:

| Opción | Cómo se usa | Requisitos |
|---|---|---|
| **Teléfono** (biometría real) | Elegir "Usar un teléfono o tableta", escanear el QR con la cámara y confirmar con huella o rostro | Bluetooth encendido en la PC y en el teléfono, ambos con internet. Android guarda la passkey en el Administrador de contraseñas de Google; iPhone en el Llavero de iCloud |
| Windows Hello | Confirmar con el PIN, la huella o el rostro del equipo | Windows Hello configurado |
| Llave FIDO2 | Insertar la llave USB y tocarla | Una llave FIDO2 |
| Autenticador virtual de Chrome | F12 → menú ⋮ → More tools → WebAuthn → "Enable virtual authenticator environment" → Add, con protocolo ctap2, transporte internal, resident key y user verification marcados | Solo existe mientras DevTools está abierto en esa pestaña: úselo como respaldo y registre también el teléfono |

La plantilla biométrica nunca sale del teléfono: la plataforma recibe una firma
criptográfica ligada al origen `https://plataforma.test`.

Después de la primera passkey, en **Administración → Mis passkeys** se registra una
segunda, por ejemplo Windows Hello o una llave, para no quedar fuera si se pierde el teléfono.

## 6. Ajustes a la topología GNS3

| Nodo | Cambio | Motivo |
|---|---|---|
| CAM-03 | Nuevo Alpine en `10.10.10.55`, colgado de SW-CIRC-B, con `ping -i 1 10.10.10.1` | SW-CIRC-B necesita dos equipos para que su caída se distinga de la de un equipo |
| PC-NAVE | Alpine `alpine-1` en `10.10.10.99`, conectado a SW-CIRC-B, autorizado en el inventario | Estación de trabajo de la nave |
| PC-INTRUSO | Alpine en `10.10.10.66` conectado a SW-CIRC-A, fuera del inventario y apagado hasta la demo | Equipo no autorizado para la prueba de intrusión |

## 7. Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| "El navegador rechazó el dominio" | Se abrió por IP. Use `https://plataforma.test` |
| Advertencia de certificado | Falta importar `root.crt` en Raíces de confianza del Equipo local o no se reinició el navegador |
| El QR del teléfono no conecta | Bluetooth apagado en la PC o sin internet en alguno de los dos |
| "Red: sin capturador" | `docker compose logs sensor-red`: la interfaz eth2 no existe o no está en modo promiscuo |
| Red sin equipos en línea | Los Alpine perdieron su IP al reiniciar; ver la sección 6 de la guía de infraestructura |
| `broker` reinicia en bucle | Falta alguna `MQTT_PASS_*` en `.env` |
| Código de alta vencido o administrador sin passkey válida | `docker compose exec plataforma python -m app.recuperar admin` emite un código nuevo y conserva la bitácora. `docker compose down -v` solo si se quiere una base vacía |
| Windows Hello "no disponible en este momento" | El equipo está vinculado a una cuenta de organización cuya directiva bloquea el PIN. Usar el teléfono por QR o una llave FIDO2 |
| La única passkey era el autenticador virtual de Chrome | Se pierde al desactivarlo o al cerrar DevTools. Registrar antes una segunda passkey real; si ya se perdió, usar `app.recuperar` |
| Probar sin GNS3 | `MODO_RED=demo` en `.env` y `docker compose up -d` |

## 8. Correcciones del primer despliegue (2 de octubre de 2026)

| Hallazgo | Corrección |
|---|---|
| La GNS3 VM (Ubuntu 26.04, Docker 29.6.2) no traía el plugin de Compose | Se instaló Docker Compose v5.5.1 para el usuario `gns3`, sin `sudo`: `mkdir -p ~/.docker/cli-plugins && curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose && chmod +x ~/.docker/cli-plugins/docker-compose` |
| El nodo Cloud1 estaba enlazado a `eth0` de la VM (red de control) y no a `eth2` | Se reconectó desde la interfaz de GNS3: Cloud1 `eth2` con SW-CIRC-A `eth4` |
| Los nodos aparecían iniciados en GNS3, pero las consolas rechazaban la conexión | El servidor de la VM había perdido el proyecto; se cerró y se volvió a abrir el proyecto en GNS3 |
| Los Alpine no reciben respuesta al hacer ping a 10.10.10.1 | Es esperado: el Cloud inyecta las tramas por `eth2` hacia afuera y la pila de la VM no las recibe. Las solicitudes ARP sí se capturan y bastan para detectar a los equipos |
| `desplegar.ps1` fallaba en la última orden con `"compose ps\r"` | PowerShell agrega CRLF al texto que se envía por tubería a `ssh`; el script remoto ahora se envía en base64 |
| Cada redespliegue que recrea `sensor-red` registra `perdida_visibilidad` y luego `visibilidad_restablecida` | Es el comportamiento correcto ante un capturador reiniciado; no se debe redesplegar durante la demostración |

Desde Windows, el despliegue y el acceso quedan en dos órdenes:

```powershell
.\scripts\windows\desplegar.ps1   # empaqueta, copia a ~/plataforma, crea .env solo la primera vez y hace up --build
.\scripts\windows\tunel.ps1       # http://localhost:8000 (dejar la ventana abierta)
```
