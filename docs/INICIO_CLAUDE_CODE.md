# Cómo iniciar la sesión de Claude Code (Windows, disco D:, localhost)

Claude Code corre en Windows sobre `D:\PROYECTO-SEGURIDAD\plataforma`. Los contenedores
corren dentro de la GNS3 VM, que es la única con `eth2` hacia la topología, y Claude Code
los opera por SSH. El navegador abre la plataforma en `http://localhost:8000` por un túnel
SSH. No se usa GitHub ni ningún repositorio remoto.

```
D:\PROYECTO-SEGURIDAD\
├── PROYECTO-SEGURIDAD.gns3        topología (solo lectura para Claude Code)
├── project-files\                 archivos de GNS3
└── plataforma\                    código de la plataforma v2 (aquí se abre Claude Code)
    ├── CLAUDE.md                  instrucciones que Claude Code carga solo
    └── docs\HANDOFF.md            estado, decisiones y backlog
```

## 1. Requisitos en Windows

| Requisito | Comprobación en PowerShell |
|---|---|
| Claude Code con cuenta Pro, Max, Team, Enterprise o Console | `claude --version` |
| Git for Windows (Claude Code lo usa como shell en Windows) | `git --version` |
| Cliente OpenSSH (incluido en Windows 10 y 11) | `ssh -V` |
| `tar` (incluido en Windows 10 y 11) | `tar --version` |
| GNS3 abierto, GNS3 VM en verde y la topología encendida | Interfaz de GNS3 |

Si falta Claude Code, el instalador nativo para Windows se ejecuta en PowerShell con
`irm https://claude.ai/install.ps1 | iex`. Si ese comando cambió, la guía vigente está en
https://docs.claude.com (sección Claude Code, instalación).

## 2. Colocar el código en D:

Descargue `Proyecto-Seguridad-v2.zip` de la conversación y en PowerShell:

```powershell
Expand-Archive -Path "$HOME\Downloads\Proyecto-Seguridad-v2.zip" -DestinationPath "D:\PROYECTO-SEGURIDAD"
Rename-Item "D:\PROYECTO-SEGURIDAD\Proyecto-Seguridad-v2" "plataforma"
Test-Path "D:\PROYECTO-SEGURIDAD\plataforma\CLAUDE.md"     # debe decir True
```

GNS3 ignora carpetas que no sean suyas dentro del proyecto. Si prefiere separarlas,
use otra ruta en D: y ajuste la tabla "Entorno" de `CLAUDE.md`.

## 3. Llave SSH hacia la GNS3 VM (una sola vez)

Claude Code no puede escribir contraseñas, así que necesita una llave. En PowerShell:

```powershell
ssh-keygen -t ed25519                     # Enter tres veces: ruta por defecto y sin frase
type $HOME\.ssh\id_ed25519.pub | ssh gns3@192.168.56.101 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
ssh -o BatchMode=yes gns3@192.168.56.101 "echo llave-ok"   # debe responder sin pedir contraseña
```

La contraseña por defecto de la VM es `gns3`. Si la IP de su VM es otra, la ve en GNS3:
Edit → Preferences → GNS3 VM, o en la consola de la VM en VirtualBox.

Los comandos con `sudo` en la VM los ejecutará usted cuando Claude Code se los indique.

## 4. Abrir Claude Code

```powershell
cd D:\PROYECTO-SEGURIDAD\plataforma
claude
```

Claude Code lee `CLAUDE.md` al iniciar; no hace falta `/init`. Apruebe los comandos a
medida que los pida y no use el modo que omite permisos.

## 5. Primer mensaje

```text
Lee CLAUDE.md y docs/HANDOFF.md completos. Trabajamos en localhost y sin repositorios remotos.
GNS3 está abierto con la topología encendida en D:\PROYECTO-SEGURIDAD y la GNS3 VM en 192.168.56.101; la llave SSH ya funciona.

Ejecuta la Fase 0 de CLAUDE.md, solo lectura:
1. Herramientas en Windows y acceso SSH sin contraseña a la VM.
2. En la VM: versión de Docker y de Compose, memoria, eth2 y modo promiscuo, reloj, salida a internet.
3. Mi topología: lee el archivo .gns3 sin modificarlo y lista nodos, tipos y enlaces; revisa si los Alpine tienen IP persistente en project-files.
4. Entrégame una tabla "esperado vs encontrado" y el plan ajustado de las fases 1 a 3.
No cambies ningún archivo ni levantes contenedores todavía.
```

## 6. Mensajes para las fases siguientes

**Fases 1 y 2: preparar la VM y desplegar**

```text
Ejecuta las fases 1 y 2 de CLAUDE.md. Dame los comandos con sudo para que yo los corra.
Crea scripts/windows/desplegar.ps1, despliega en modo localhost con MODO_RED=captura y corrige lo que falle en el primer arranque con el cambio mínimo, documentando cada corrección en docs/DESPLIEGUE_GNS3.md.
No ejecutes docker compose down -v sin preguntarme ni toques contenedores que no sean del proyecto plataforma-dcim.
Al final muéstrame docker compose ps, la respuesta de /salud y el código de alta del administrador.
```

**Fase 3: túnel y alta**

```text
Ejecuta la fase 3: crea scripts/windows/tunel.ps1, ábrelo y guíame para activar admin en http://localhost:8000/alta con Windows Hello o el autenticador virtual de Chrome. Confirma en la bitácora los eventos passkey_registrada y auth_exitosa.
```

**Fase 4: topología**

```text
Ejecuta la fase 4: dame los pasos en la interfaz de GNS3 para agregar CAM-03 y PC-NAVE y dejar IP y latido persistentes en los Alpine. Después de cada paso, verifica en la plataforma que los equipos aparezcan en línea con su MAC registrada.
```

**Fase 5: ensayo de la demostración**

```text
Lee docs/GUIA_DEMO.md y ensayemos la demostración en modo captura. En cada paso dime qué hago en GNS3 o en el tablero y confirma en la bitácora el evento con su control y su norma. Anota en docs/HANDOFF.md los ajustes que resulten.
```

**Fase 6: construcción pendiente**

```text
Revisa la Fase 6 de CLAUDE.md y el backlog P1 y P2 de docs/HANDOFF.md. Propón el orden y el alcance de cada tarea, espera mi confirmación y luego constrúyela con sus pruebas.
```

## 7. Si algo sale mal

| Problema | Acción |
|---|---|
| `ssh` pide contraseña | Repita el punto 3; revise que `authorized_keys` tenga permisos 600 |
| Claude Code no ve el contexto | Confirme que lo abrió en `D:\PROYECTO-SEGURIDAD\plataforma`, donde está `CLAUDE.md` |
| `http://localhost:8000` no carga | El túnel no está abierto o el puerto 8000 de Windows está ocupado |
| La VM se queda sin memoria | Apague la VM, súbale RAM en VirtualBox y vuelva a encender la topología |
| El teléfono no acepta la passkey | Esperable con `localhost`: use Windows Hello ahora y el modo https para la demo con teléfono |
