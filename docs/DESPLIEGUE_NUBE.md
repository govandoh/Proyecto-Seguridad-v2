# Despliegue en Azure con acceso por Tailscale

Una VM de Azure ejecuta el servidor de GNS3 con la topología y la plataforma. El equipo
auditor entra por Tailscale: la plataforma en `https://dcim.<tailnet>.ts.net` con
certificado válido y GNS3 en `http://dcim.<tailnet>.ts.net:3080`. La IP pública de Azure no
expone ningún servicio.

```
Auditor (Tailscale) ── https://dcim.<tailnet>.ts.net ──► tailscale serve ──► 127.0.0.1:8000 plataforma
                    └─ http://dcim.<tailnet>.ts.net:3080 ──► gns3server 2.2.61

VM Azure Ubuntu 24.04
 ├─ gns3server + ubridge + Docker  →  SW-CIRC-A/B (OVS), Alpine, Cloud1
 ├─ br-lab 10.10.10.1/24 ◄── lab-br ═veth═ lab-gns ◄── Cloud1
 └─ docker compose plataforma-dcim (6 servicios); sensor-red captura en br-lab
```

Diferencias con la GNS3 VM local:

| Elemento | Local (VirtualBox) | Nube (Azure) |
|---|---|---|
| Punto de captura | `eth2` de la VM | `br-lab`; el Cloud se conecta a `lab-gns` |
| Ping de los Alpine a 10.10.10.1 | Sin respuesta | Con respuesta: el tráfico llega a la pila de la VM |
| Acceso a la plataforma | Túnel SSH a `http://localhost:8000` | `https://dcim.<tailnet>.ts.net` |
| RP ID de WebAuthn | `localhost` | `dcim.<tailnet>.ts.net`; la passkey por QR funciona sin restricciones |
| CPU | 1 | 4 (B4ms) |

## 1. Azure (en el portal)

La VM la crea quien administra la suscripción, con las instrucciones detalladas de
**[CREAR_VM_AZURE.md](CREAR_VM_AZURE.md)** (portal o Azure CLI). Resumen:

1. Activar **Azure for Students** con el correo de la universidad.
2. **Máquinas virtuales → Crear**:

| Campo | Valor |
|---|---|
| Grupo de recursos | `rg-dcim` (nuevo) |
| Nombre | `dcim` |
| Región | Una permitida para la suscripción de estudiante, por ejemplo East US 2 |
| Imagen | Ubuntu Server 24.04 LTS, x64 Gen2 |
| Tamaño | **Standard_B4ms** (4 vCPU, 16 GB). Si la cuota no lo permite, Standard_B2ms |
| Autenticación | Clave pública SSH; usuario **`gns3`**; usar una clave existente y pegar `C:\Users\govan\.ssh\id_ed25519.pub` |
| Puertos de entrada | SSH (22) |
| Disco del sistema | Standard SSD, 64 GB |
| Administración | Apagado automático diario, por ejemplo 23:00, zona horaria de Centroamérica |

3. Al crearla: **Redes → regla SSH → Origen = Mi dirección IP**. Es temporal; se borra en el paso 4.
4. **Cost Management → Presupuestos**: alerta al 50 % y al 80 % del crédito.

Costo de referencia de B4ms: alrededor de 0.17 USD por hora encendida, más el disco. Con la
VM apagada (desasignada) fuera de las sesiones de auditoría, el crédito alcanza. Verificar
el precio vigente en la calculadora de Azure.

## 2. Preparar la VM

Desde Windows, con la IP pública que muestra el portal. Si la VM se creó con Tailscale desde
el arranque (sección 0 de `CREAR_VM_AZURE.md`), se usa `dcim` en lugar de la IP y el paso 3
se reduce a activar `tailscale serve`:

```powershell
ssh gns3@<IP pública> "mkdir -p ~/plataforma"
tar -czf $env:TEMP\p.tgz --exclude=./datos --exclude=./.env --exclude=*.db --exclude=./migracion --exclude=./evidencia -C . .
scp $env:TEMP\p.tgz gns3@<IP pública>:~/
ssh gns3@<IP pública> "tar -xzf ~/p.tgz -C ~/plataforma && rm ~/p.tgz && sed -i 's/\r$//' ~/plataforma/scripts/nube/*.sh && bash ~/plataforma/scripts/nube/preparar_vm.sh"
```

`preparar_vm.sh` instala Docker y Compose, `gns3-server==2.2.61`, ubridge, el módulo
`openvswitch`, la red `br-lab`, Tailscale y el cortafuegos. Es idempotente. Las
credenciales del servidor GNS3 quedan en `~/gns3_credenciales.txt`.

## 3. Tailscale

1. Crear la cuenta en tailscale.com e instalar Tailscale en Windows.
2. Consola de administración → **DNS**: activar **MagicDNS** y **HTTPS Certificates**.
3. En la VM:
   ```bash
   sudo tailscale up --hostname=dcim           # abrir el enlace que imprime y aprobar
   sudo tailscale serve --bg 8000              # https://dcim.<tailnet>.ts.net -> 127.0.0.1:8000
   tailscale status
   ```
4. Desde Windows, comprobar `ssh gns3@dcim "echo ok"`.
5. **Borrar la regla SSH del NSG** en el portal de Azure. Desde aquí todo entra por Tailscale.

## 4. Migrar la base de datos

La copia consistente está en `migracion\plataforma_migracion.db` (tomada con la API de
respaldo de SQLite). Antes de subirla conviene repetir la copia para incluir los últimos
eventos locales. Se coloca en el volumen **antes** del primer arranque:

```powershell
scp migracion\plataforma_migracion.db gns3@dcim:~/plataforma_migracion.db
ssh gns3@dcim "docker volume create --label com.docker.compose.project=plataforma-dcim --label com.docker.compose.volume=datos_plataforma plataforma-dcim_datos_plataforma && docker run --rm -v plataforma-dcim_datos_plataforma:/datos -v ~/:/origen:ro alpine sh -c 'cp /origen/plataforma_migracion.db /datos/plataforma.db && chown -R 10001 /datos' && shred -u ~/plataforma_migracion.db"
```

El `chown -R` debe incluir la carpeta `/datos`, no solo el archivo: SQLite crea su diario en
la misma carpeta, y con la carpeta a nombre de `root` la plataforma falla al arrancar con
`attempt to write a readonly database`.

## 5. Desplegar la plataforma

```powershell
.\scripts\windows\desplegar.ps1 -VM gns3@dcim -Modo nube -Dominio dcim.<tailnet>.ts.net
```

En el primer despliegue crea el `.env` con `RP_ID` y `ORIGENES` del dominio, `IFACE=br-lab` y
`COMPOSE_FILE=docker-compose.yml:docker-compose.nube.yml`. Con la base migrada no se genera
código de alta nuevo.

Verificación de la migración: `.\scripts\windows\evidencia.ps1 -VM gns3@dcim -Desde <último id local - 1>`
debe mostrar el último evento local con el mismo hash, seguido de `plataforma_iniciada`, y la
cadena íntegra.

**Passkeys.** Las registradas con `localhost` no valen en el dominio nuevo:

```powershell
ssh gns3@dcim "cd ~/plataforma && docker compose exec plataforma python -m app.recuperar admin"
```

Con el código, `admin` se da de alta en `https://dcim.<tailnet>.ts.net/alta` y registra su
passkey. Después, en Administración, **Restablecer** a `operador` y `auditor1`.

## 6. Topología

1. En el GNS3 local: **File → Export portable project** (`Topologia.gns3project`).
2. En el cliente GNS3: **Edit → Preferences → Server**: desmarcar *Enable local server*;
   Host `dcim.<tailnet>.ts.net`, puerto `3080`, autenticación con las credenciales de
   `~/gns3_credenciales.txt`.
3. **File → Import portable project** y elegir el archivo exportado.
4. Clic derecho en **Cloud1 → Configure**: quitar `eth2` y agregar **`lab-gns`**. Reconectar
   Cloud1 `lab-gns` con SW-CIRC-A `eth4`.
5. Arrancar todos los nodos menos PC-INTRUSO.

Para volver a usar la topología local, se marca otra vez *Enable local server* en el paso 2.

## 7. Verificación

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `https://dcim.<tailnet>.ts.net/salud` desde un equipo con Tailscale | `{"estado":"ok","mqtt":true}`, certificado válido |
| 2 | Interfaz web de GNS3, `http://dcim.<tailnet>.ts.net:3080` | Topología completa, nodos en verde |
| 3 | Pestaña Red | "Captura real br-lab", 6 equipos en línea con su MAC |
| 4 | Encender PC-INTRUSO | Solo `dispositivo_no_autorizado`, sin eventos de saturación (cierra el hallazgo H1) |
| 5 | Registrar una passkey con un teléfono por QR | `passkey_registrada` con transporte `hybrid` |
| 6 | Desde fuera de Tailscale, `nmap` a la IP pública | Ningún puerto abierto |

## 8. Operación y costo

| Acción | Cómo |
|---|---|
| Encender para una sesión | Portal de Azure → VM `dcim` → Iniciar. Los servicios y la plataforma arrancan solos; en GNS3 se abre el proyecto y se encienden los nodos |
| Apagar | Portal → Detener (desasigna y deja de cobrar CPU). El apagado automático lo hace cada noche |
| Actualizar el código | `desplegar.ps1 -VM gns3@dcim -Modo nube -Dominio ...` |
| Dar acceso a un auditor | Consola de Tailscale → máquina `dcim` → **Share** con su correo; crear sus cuentas en Administración |
| Cerrar la auditoría | Exportar la bitácora, instantánea del disco y borrar el grupo de recursos `rg-dcim` |
