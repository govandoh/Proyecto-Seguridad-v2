# Crear la VM de Azure para el laboratorio

Instrucciones para quien administra la suscripción de Azure del grupo. Solo se crea la
máquina; la instalación del software, Tailscale y la migración las hace Gerardo por SSH
siguiendo `DESPLIEGUE_NUBE.md`.

**Antes de empezar, pedir a Gerardo:**

1. Su **llave pública SSH**: una línea que empieza con `ssh-ed25519`. Es pública, se puede
   enviar por chat. Nunca se pide ni se envía la llave privada.
2. Una **clave de autenticación de Tailscale** (`tskey-auth-...`), de un solo uso. Con ella la
   VM entra a la red privada de Tailscale al arrancar y **no se abre ningún puerto a
   Internet**, ni siquiera SSH. Así no importa que la IP pública de Gerardo cambie.

## 0. Acceso sin IP fija: Tailscale desde el primer arranque (recomendado)

Gerardo genera la clave en la consola de Tailscale: **Settings → Keys → Generate auth key**,
con *Reusable* desactivado, *Ephemeral* desactivado, *Pre-approved* activado y vencimiento de
1 día. La clave solo sirve para registrar una máquina, una vez, y caduca sola.

Al crear la VM se pega este bloque como **datos personalizados** (*custom data*, cloud-init),
reemplazando la clave:

```yaml
#cloud-config
runcmd:
  - curl -fsSL https://tailscale.com/install.sh | sh
  - tailscale up --auth-key=tskey-auth-REEMPLAZAR --ssh --hostname=dcim
```

| Dónde se pega | Cómo |
|---|---|
| Portal | Pestaña **Opciones avanzadas → Datos personalizados** (*Custom data*) |
| Azure CLI | Guardar el bloque en `cloud-init.yml` y agregar `--custom-data cloud-init.yml` a `az vm create` |

Con esta opción:

- En **Reglas de puerto de entrada** se elige **Ninguno**, y el paso 9 de la opción A y la
  regla `ssh-gerardo` de la opción B se omiten.
- Unos 2 minutos después de crearla, la VM aparece como `dcim` en la consola de Tailscale de
  Gerardo, que entra con `ssh gns3@dcim` desde cualquier red.
- Si la VM no aparece, se revisa en el portal: VM `dcim` → **Ayuda → Diagnóstico de
  arranque → Registro serie**, buscando la salida de `tailscale up`.

La alternativa, abrir SSH solo para la IP pública de Gerardo, obliga a editar la regla cada
vez que esa IP cambia (hotspot, otra red, reinicio del módem).

## 1. Especificaciones

| Campo | Valor | Motivo |
|---|---|---|
| Suscripción | Azure for Students | Crédito sin tarjeta |
| Grupo de recursos | `rg-dcim` | Permite borrar todo de una vez al terminar |
| Nombre de la VM | `dcim` | Lo usan los scripts y la documentación |
| Región | Una permitida para la suscripción de estudiante; preferible **East US 2** o **Central US** (latencia baja desde Guatemala) | Algunas regiones están bloqueadas para estudiantes |
| Imagen | **Ubuntu Server 24.04 LTS, x64 Gen2** | El script de instalación está probado para esta versión |
| Tamaño | **Standard_B4ms** (4 vCPU, 16 GB) | Con 1 CPU la VM se satura al encender nodos (hallazgo H1). Si la cuota no lo permite: **Standard_B2ms** (2 vCPU, 8 GB) |
| Usuario administrador | **`gns3`** | Los scripts asumen ese usuario |
| Autenticación | **Clave pública SSH**, sin contraseña | Pegar la llave de Gerardo |
| Disco del sistema | Standard SSD, **64 GB** | Imágenes Docker de la topología y de la plataforma |
| IP pública | Sí, estándar | La VM la necesita para salir a Internet (descargas); no se usa para entrar |
| Puertos de entrada | **Ninguno** con la sección 0; si no, SSH solo desde la IP de Gerardo | Nada queda expuesto |
| Datos personalizados | Bloque cloud-init de la sección 0 | Tailscale desde el primer arranque |
| Apagado automático | Diario a las **23:00**, zona horaria (UTC-06:00) Centroamérica | Ahorra crédito |

Costo de referencia de B4ms: alrededor de 0.17 USD por hora encendida, más el disco.
Verificar en la calculadora de precios de Azure antes de crear.

## 2. Opción A: portal de Azure

1. **Máquinas virtuales → Crear → Máquina virtual de Azure.**
2. Pestaña **Aspectos básicos**: suscripción, grupo de recursos `rg-dcim` (Crear nuevo),
   nombre `dcim`, región, imagen **Ubuntu Server 24.04 LTS - x64 Gen2**, tamaño
   **Standard_B4ms** (Ver todos los tamaños).
3. **Cuenta de administrador**: tipo **Clave pública SSH**, usuario `gns3`, origen
   **Usar clave pública existente** y pegar la llave de Gerardo.
4. **Reglas de puerto de entrada**: **Permitir los puertos seleccionados → SSH (22)**. Se
   restringe en el paso 9.
5. Pestaña **Discos**: Standard SSD, tamaño 64 GiB.
6. Pestaña **Redes**: dejar la red virtual y la IP pública que propone.
7. Pestaña **Administración**: activar **Apagado automático**, 23:00, zona (UTC-06:00)
   Centroamérica.
8. **Revisar y crear → Crear.** No descargar ni generar ningún par de claves.
9. Al terminar: VM `dcim` → **Redes → Configuración de red** → regla de entrada **SSH** →
   **Origen: Direcciones IP**, **Direcciones IP de origen: `<IP de Gerardo>/32`** → Guardar.

## 3. Opción B: Azure CLI (Cloud Shell)

En el portal, abrir **Cloud Shell** (Bash) y reemplazar los dos valores:

```bash
LLAVE='ssh-ed25519 AAAA...pegar la llave completa de Gerardo...'
IP_GERARDO='x.x.x.x'
REGION='eastus2'

az group create -n rg-dcim -l "$REGION"
az vm create -g rg-dcim -n dcim \
  --image Canonical:ubuntu-24_04-lts:server:latest \
  --size Standard_B4ms \
  --admin-username gns3 --ssh-key-values "$LLAVE" \
  --os-disk-size-gb 64 --storage-sku StandardSSD_LRS \
  --public-ip-sku Standard --nsg-rule NONE
az network nsg rule create -g rg-dcim --nsg-name dcimNSG -n ssh-gerardo \
  --priority 1000 --direction Inbound --access Allow --protocol Tcp \
  --source-address-prefixes "$IP_GERARDO/32" --destination-port-ranges 22
az vm auto-shutdown -g rg-dcim -n dcim --time 0500      # 05:00 UTC = 23:00 en Guatemala
az vm show -d -g rg-dcim -n dcim --query "{ip:publicIps, tamano:hardwareProfile.vmSize, estado:powerState}" -o table
```

Si `Standard_B4ms` falla por cuota, repetir `az vm create` con `--size Standard_B2ms`.
El nombre del grupo de seguridad puede variar; se comprueba con `az network nsg list -g rg-dcim -o table`.

## 4. Presupuesto

**Cost Management → Presupuestos → Agregar**: ámbito `rg-dcim`, monto según el crédito
restante, alertas al 50 % y al 80 % al correo del administrador.

## 5. Qué enviar a Gerardo

| Dato | Ejemplo |
|---|---|
| IP pública de la VM | `20.x.x.x` |
| Tamaño creado | `Standard_B4ms` |
| Región | `East US 2` |
| Confirmación de que SSH solo admite la IP de Gerardo | Captura de la regla |

Con eso Gerardo comprueba el acceso (`ssh gns3@<IP>`) y sigue con `DESPLIEGUE_NUBE.md`,
paso 2. Cuando Tailscale funcione, avisará para **borrar la regla SSH** del grupo de
seguridad: desde ese momento la VM no tiene ningún puerto abierto a Internet.

## 6. Operación diaria

| Acción | Dónde |
|---|---|
| Encender antes de una sesión de trabajo o auditoría | VM `dcim` → Iniciar |
| Apagar al terminar | VM `dcim` → Detener (desasigna y deja de cobrar CPU) |
| Si cambia la IP de Gerardo antes de activar Tailscale | Editar el origen de la regla SSH |
| Al cerrar la auditoría | Borrar el grupo de recursos `rg-dcim`, después de que Gerardo exporte la evidencia |

No se debe agregar otra regla de entrada, ni instalar o cambiar software en la VM sin
coordinarlo: la configuración la hacen los scripts del repositorio.
