# Entrega del laboratorio al equipo auditor

Procedimiento del equipo del proyecto para dar acceso al equipo auditor a la plataforma en
la nube (`https://dcim.taila9c375.ts.net`) y a la topología GNS3. Lo ejecuta quien tiene la
cuenta `admin` de la plataforma y la consola de Tailscale. Lo que hace el auditor después
está en `ACCESO_AUDITORES.md`.

## 1. Qué recibe el equipo auditor

| Elemento | Canal de entrega |
|---|---|
| Manual de simulaciones (versión nube) y `ACCESO_AUDITORES.md` | Correo o repositorio |
| Invitación a la máquina `dcim` de Tailscale | Desde la consola de Tailscale, a su correo |
| Usuario y **código de alta** de cada cuenta de la plataforma | **Canal separado** del manual: mensaje directo a cada persona |
| Usuario y clave del servidor GNS3 | **Canal separado**, igual que los códigos |

Los códigos y la clave de GNS3 no se escriben en el manual, en el repositorio ni en el mismo
correo que los enlaces: quien intercepte uno solo de los canales no puede entrar.

## 2. Antes de empezar

- La cuenta `admin` ya registró su passkey en `https://dcim.taila9c375.ts.net`.
- La VM está encendida y la plataforma responde en `/salud`.
- Se conoce el correo de la cuenta de Tailscale de cada auditor (ellos la crean, gratuita).

## 3. Crear las cuentas

Se recomienda **una cuenta por persona**, para que cada evento de la bitácora tenga un actor
individual (ISO/IEC 27001 5.16). Cada auditor necesita dos roles distintos, porque la
plataforma separa funciones: el operador simula y acusa, el auditor exporta y verifica.

| Usuario sugerido | Nombre | Rol |
|---|---|---|
| `op-<apellido>` | Nombre completo del auditor | `operador` |
| `aud-<apellido>` | Nombre completo del auditor | `auditor` |

Como mínimo, para todo el equipo auditor: `operador-ext` (operador) y `auditor-ext` (auditor).

Pasos en la plataforma, con la cuenta `admin`:

1. **Administración → Usuarios y roles**.
2. Escribir el usuario (minúsculas, sin espacios), el nombre completo y elegir el rol.
3. **Crear y emitir código de alta**. Si pasaron más de 5 minutos desde el último ingreso, la
   plataforma pide confirmar la identidad con la passkey del administrador.
4. Copiar el código que aparece en el recuadro. **Se muestra una sola vez** y vence en 24 horas.
5. Repetir para cada cuenta.

Cada alta queda en la bitácora como `usuario_alta` con el actor `administrador:admin`.

Si un código vence o se pierde: en la tabla de usuarios, **Restablecer** emite uno nuevo y
revoca lo anterior. Al terminar la auditoría: **Dar de baja** a cada cuenta externa; la baja
revoca sus passkeys y cierra sus sesiones en la misma operación (`usuario_baja`).

## 4. Compartir la VM en Tailscale

1. https://login.tailscale.com/admin/machines → máquina **`dcim`** → menú **⋯** → **Share**.
2. Escribir el correo de la cuenta de Tailscale de cada auditor → **Share**.
3. El auditor acepta la invitación; `dcim` aparece en su lista de máquinas.

Compartir una máquina no da acceso al resto de la red de Tailscale ni a la PC de nadie. Al
terminar la auditoría se retira desde el mismo menú.

## 5. Credenciales del servidor GNS3

El servidor GNS3 2.2 admite un solo usuario. Su clave se lee en la VM:

```powershell
ssh gns3@dcim "cat ~/gns3_credenciales.txt"
```

Se entrega por el mismo canal separado que los códigos. Al terminar la auditoría se puede
cambiar editando `~/.config/GNS3/2.2/gns3_server.conf` en la VM y reiniciando el servicio
con `sudo systemctl restart gns3server`.

## 6. Mensaje sugerido para cada auditor

Enviar por separado: primero el manual y los enlaces; después, por mensaje directo, los
datos sensibles.

> **Mensaje 1 (correo):** Adjuntamos el manual de simulaciones y la guía de acceso. Les
> compartimos la máquina `dcim` en Tailscale; acepten la invitación y comprueben
> `https://dcim.taila9c375.ts.net/salud`. Recibirán sus credenciales por mensaje directo.
>
> **Mensaje 2 (directo):** Usuario operador `op-…`, código `XXXX-XXXX-XXXX`. Usuario auditor
> `aud-…`, código `XXXX-XXXX-XXXX`. Vencen en 24 horas. Servidor GNS3: usuario `gns3`, clave
> `…`. Activen sus cuentas en `https://dcim.taila9c375.ts.net/alta`.

## 7. Comprobación

| Verificación | Dónde |
|---|---|
| Cada cuenta externa aparece como **Activa** y con al menos una passkey | Administración → Usuarios y roles |
| Hay un `passkey_registrada` y un `auth_exitosa` por cuenta | Bitácora |
| El indicador "Cuentas activas con passkey registrada" está en 100 % | Indicadores |
