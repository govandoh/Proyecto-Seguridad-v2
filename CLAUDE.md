# CLAUDE.md · Plataforma DCIM del Operador Postal (sesión local)

Instrucciones permanentes para Claude Code. Léelas completas antes de ejecutar cualquier
comando. El estado detallado, las decisiones y el backlog están en `docs/HANDOFF.md`.

## 1. Contexto

Proyecto del curso Seguridad y Auditoría de Sistemas (UMG, 2026), grupo de Gerardo Ovando,
Mario Culajay y Sergio Sánchez. El modelo de seguridad protege el *hardware* del
datacenter de un Operador Postal Designado con el Triángulo de la Ciberresiliencia
(Protección, Detección, Respuesta) sobre ISO/IEC 27001:2022, NFPA, IEEE, ASHRAE y NIST.

La plataforma v2 ya está construida y probada como procesos locales. Esta sesión la
despliega en el laboratorio real del usuario, la valida contra la topología GNS3 y
construye lo que falte. El usuario trabaja en Windows, en el disco D:.

## 2. Reglas de la sesión

1. **Repositorio público del grupo**: `github.com/govandoh/Proyecto-Seguridad-v2`. Nunca se
   suben `.env`, `datos/`, bases `*.db`, `migracion/`, `evidencia/` ni credenciales; revisar
   `git status` antes de cada *commit*. El despliegue en la VM de Azure `dcim` para el equipo
   auditor (`docs/DESPLIEGUE_NUBE.md`) copia el código con `desplegar.ps1`; el acceso a la VM
   es solo por Tailscale.
2. **La topología GNS3 no se edita por archivo.** `D:\PROYECTO-SEGURIDAD\*.gns3` y
   `project-files\` se leen, nunca se escriben: GNS3 está abierto y sobrescribe el archivo.
   Los cambios de topología los hace el usuario en la interfaz de GNS3; tú le das los pasos.
3. **Docker de la GNS3 VM es compartido con GNS3.** Los nodos Docker de la topología son
   contenedores de ese mismo motor. Solo se usan comandos acotados al proyecto
   (`docker compose ...` dentro de `~/plataforma`). Prohibido `docker system prune`,
   `docker rm` o `docker stop` sobre contenedores ajenos al proyecto `plataforma-dcim`.
4. **Contraseñas.** Todo comando que pida contraseña (primer `ssh`, `sudo` en la VM) lo
   ejecuta el usuario; tú le das el comando exacto y esperas su confirmación.
5. Antes de dar algo por terminado se prueba: comandos reales, eventos en la bitácora
   o captura de pantalla, no suposiciones.
6. Pide confirmación antes de comandos destructivos: `docker compose down -v` (borra la
   base, los usuarios y las passkeys), borrar `datos/`, cambios en adaptadores de
   VirtualBox o en netplan de la VM.

### Reglas del código que no se rompen

1. **Bitácora de solo inserción.** Nunca `UPDATE` ni `DELETE` sobre `eventos`. Un acuse o
   corrección es un evento nuevo con `ref_id`. Todo evento se registra con
   `bitacora.registrar(modulo, tipo, severidad, descripcion, control_iso, norma, actor, ...)`.
2. **Cada evento lleva control ISO/IEC 27001:2022 y norma técnica.** Si agregas un tipo
   crítico, agrega su procedimiento en `app/procedimientos.py`.
3. **Frontend sin HTML inyectado.** Usa `el()` y `svg()` de `static/js/comun.js`
   (textContent). Prohibido `innerHTML` con datos. La CSP es `script-src 'self'` y
   `style-src 'self'`: nada de scripts, estilos ni atributos `style` en línea.
4. **Mutaciones de la API** exigen la cabecera `X-Plataforma: 1` (la envía `api()` de
   `comun.js`). Las acciones administrativas usan `permiso_con_reauth("administrar")`.
5. **Roles**: `ver`, `acusar`, `simular`, `auditar`, `administrar` en
   `app/auth/dependencias.py`. No amplíes permisos sin actualizar `docs/SEGURIDAD.md`.
6. **Sin privilegios**: la web corre como uid 10001 con FS de solo lectura; solo
   `sensor-red` tiene `CAP_NET_RAW`. No vuelvas a `sudo uvicorn`.
7. **Dependencias con versión fija** en cada `requirements.txt`.
8. **Simulador = física, plataforma = norma.** Los umbrales normativos viven en
   `app/config.py` y los módulos; los simuladores solo reproducen el comportamiento.
9. **Contratos MQTT** documentados en `docs/MQTT_TOPICOS.md`. Si cambias un tópico,
   actualiza también `broker/acl`.
10. Código, mensajes y documentación en español; nombres de norma en su forma oficial.

### Redacción académica

Si redactas texto para el documento del curso: tercera persona y voz pasiva, sin guiones
largos, sin paréntesis salvo en citas, palabras en inglés en cursiva, negrita solo con
impacto real, sin muletillas y con normas APA 7.

## 3. Entorno

| Elemento | Valor esperado (verificar en la Fase 0) |
|---|---|
| Equipo | Windows x64, disco de trabajo D: |
| Código | `D:\PROYECTO-SEGURIDAD\plataforma` (este directorio) |
| Topología GNS3 | `D:\PROYECTO-SEGURIDAD` (archivo `.gns3` y `project-files\`) |
| GNS3 VM | VirtualBox, `192.168.56.101`, usuario `gns3`, SSH por llave |
| Red de control | adaptador solo anfitrión `192.168.56.0/24` |
| Red del laboratorio | `10.10.10.0/24`; la VM tiene `eth2 = 10.10.10.1/24` en modo promiscuo |
| Topología esperada | SW-CIRC-A y SW-CIRC-B (Open vSwitch); SRV-TRAZA .51, CAM-01 .52, CAM-02 .53 en A; LECT-01 .54 en B; nodo Cloud con eth2 en A. PC-NAVE .99 (`alpine-1`) en B, autorizado. A agregar: CAM-03 .55 en B y PC-INTRUSO .66 en A, fuera del inventario |
| Shell de Claude Code | Git Bash (`/d/PROYECTO-SEGURIDAD/plataforma`); PowerShell con `powershell -Command` |

## 4. Modo de ejecución: localhost

"Localhost" significa que el navegador de Windows abre `http://localhost:8000`. Los
servicios corren dentro de la GNS3 VM porque solo ahí existe `eth2` para capturar el
tráfico real. La plataforma se publica únicamente en `127.0.0.1:8000` de la VM y Windows
llega por un túnel SSH. Nada queda expuesto a otra red.

```
Navegador Windows ── http://localhost:8000 ── túnel SSH ──► VM 127.0.0.1:8000 ──► contenedor plataforma
```

`http://localhost` es contexto seguro para WebAuthn: no hace falta archivo `hosts`, CA ni
Caddy. Se activa con `./scripts/generar_env.sh localhost`, que escribe en `.env`:
`RP_ID=localhost`, `ORIGENES=http://localhost:8000` y
`COMPOSE_FILE=docker-compose.yml:docker-compose.localhost.yml`. El proxy Caddy queda en
el perfil `https` y no arranca.

Limitación: la passkey en el teléfono por QR (flujo híbrido) puede rechazar el RP ID
`localhost`. En modo localhost se usan Windows Hello, una llave FIDO2 o el autenticador
virtual de Chrome. Para la demostración con el teléfono se cambia al modo HTTPS con
`plataforma.test` (ver `docs/DESPLIEGUE_GNS3.md`).

Modo alternativo sin VM: `MODO_RED=demo` genera el tráfico de red sin GNS3.

## 5. Arquitectura y código

| Servicio (docker compose) | Directorio | Función |
|---|---|---|
| `plataforma` | `plataforma/app`, `plataforma/static` | FastAPI: reglas, bitácora SQLite con SHA-256, API, WebSocket, MFA (bcrypt + WebAuthn) y tablero HTML/JS |
| `broker` | `broker/` | Mosquitto 2 con usuario y ACL por servicio |
| `sensor-red` | `sensor-red/capturador.py` | Scapy sobre `eth2`, `network_mode: host`, solo `CAP_NET_RAW`; `MODO=captura` o `demo` |
| `sim-ups` | `simuladores/ups.py` | UPS + transferencia + planta, variables NUT (`ups.status`, `battery.runtime`) |
| `sim-ambiente` | `simuladores/ambiente.py` | Temperatura de entrada por rack, humo y supresión; la climatización depende de la energía |
| `sim-puerta` | `simuladores/puerta.py` | Tarjeta + PIN, coacción, puerta forzada y mantenida abierta |
| `proxy` (perfil `https`) | `proxy/Caddyfile` | HTTPS con CA local para `plataforma.test` |

Archivos clave del backend: `app/main.py` (arranque, CSP, CSRF, WebSocket), `app/api.py`
(tablero, consola de simulación, administración), `app/auth/rutas.py` (alta, login,
passkey, reautenticación), `app/modulos/{red,energia,ambiente,acceso}.py` (reglas),
`app/bitacora.py`, `app/indicadores.py`, `app/procedimientos.py`, `app/config.py`
(todas las variables de entorno). Frontend: `static/js/app.js` (estado, WebSocket,
resumen, bitácora), `vistas-dc.js` (red, energía, ambiente, accesos),
`vistas-control.js` (simulación, administración), `comun.js`, `webauthn.js`, `graficas.js`.

Contrato de mensajes MQTT: `docs/MQTT_TOPICOS.md`. Diseño: `docs/ARQUITECTURA.md`.
Seguridad y correcciones V1 a V10: `docs/SEGURIDAD.md`. Guion de demo: `docs/GUIA_DEMO.md`.

## 6. Estado actual

| Aspecto | Estado |
|---|---|
| Backend, frontend, simuladores y capturador en modo demo | Funcionan; prueba de punta a punta con Chromium y autenticador WebAuthn virtual (`scripts/prueba_e2e.py`) |
| Escenarios verificados | transferencia 7.4 s cumple tipo 10; 14.06 s no cumple; batería baja y apagado; temperatura crítica; sensor mudo; humo y descarga; coacción; tarjeta revocada; puerta forzada y mantenida; intentos repetidos; intruso; sustitución por MAC; cascada PoE; pérdida de visibilidad |
| `docker compose config` | Válido, en ambos modos |
| **No probado** | `docker compose build` y `up` reales (no se pudieron descargar imágenes); captura real en `eth2`; passkey con Windows Hello, llave o teléfono |

## 7. Plan de trabajo

Cada fase termina mostrando al usuario la evidencia del criterio de aceptación.

### Fase 0. Verificación del entorno (solo lectura)

1. En Windows: `ssh -V`, `tar --version`, `python --version` (opcional), navegador Chrome o Edge.
2. SSH sin contraseña: `ssh -o BatchMode=yes gns3@192.168.56.101 "echo ok"`. Si falla, el
   usuario configura la llave (ver `INICIO.md`).
3. En la VM: `docker --version`, `docker compose version`, `free -h`, `ip -br addr`,
   `ip link show eth2` (debe decir PROMISC), `timedatectl`, `curl -sI https://registry-1.docker.io/v2/ | head -1`
   (salida a internet para descargar imágenes).
4. Tráfico: `sudo timeout 8 tcpdump -i eth2 -n arp` (lo corre el usuario si pide contraseña).
5. Topología, leyendo el `.gns3` sin modificarlo:
   ```powershell
   $f = Get-ChildItem D:\PROYECTO-SEGURIDAD\*.gns3 | Select-Object -First 1
   $p = Get-Content $f.FullName -Raw | ConvertFrom-Json
   $p.topology.nodes | Select-Object name, node_type, node_id | Format-Table -AutoSize
   $n = @{}; $p.topology.nodes | ForEach-Object { $n[$_.node_id] = $_.name }
   $p.topology.links | ForEach-Object { ($_.nodes | ForEach-Object { $n[$_.node_id] + ":" + $_.adapter_number }) -join " <-> " }
   ```
   Buscar además configuraciones persistentes de red de los nodos Docker en
   `project-files\docker\<node_id>\etc\network\interfaces`.
6. Entregar una tabla "esperado vs encontrado" (nodos, enlaces, IP, VM, Docker, eth2) y
   proponer el ajuste de las fases 1 a 3.

**Aceptación:** tabla completa y sin cambios en ningún archivo.

### Fase 1. Preparar la GNS3 VM

- Plugin de Compose si falta (el usuario ejecuta con `sudo`; comando en `docs/DESPLIEGUE_GNS3.md` §1).
- `sudo timedatectl set-ntp true` (sellos de tiempo válidos, control 8.17).
- Si `v1` sigue corriendo (`pgrep -af uvicorn`), detenerla: la captura ahora la hace `sensor-red`.
- Memoria de la VM: 4 GB recomendados.

**Aceptación:** `docker compose version` responde y no hay otro proceso en el puerto 8000 de la VM.

### Fase 2. Desplegar en modo localhost

1. Crear `scripts/windows/desplegar.ps1` que empaquete el código sin `datos/`, `.env`,
   `capturas/` ni `__pycache__` (`tar -czf`), lo copie con `scp` a `~/plataforma` en la VM y
   ejecute allí `docker compose up -d --build`. En el primer despliegue, antes del `up`:
   `./scripts/generar_env.sh localhost` y `sed -i 's/^MODO_RED=.*/MODO_RED=captura/' .env`.
   El script no debe sobrescribir el `.env` existente de la VM. Como el código vive en
   Windows, el script normaliza los finales de línea en la VM antes de ejecutar nada:
   `sed -i 's/\r$//' broker/entrypoint.sh scripts/*.sh` (un `.sh` con CRLF falla en Linux).
2. Verificar: `docker compose ps` (6 servicios `running`, `plataforma` healthy),
   `docker compose logs --tail 50 <servicio>` de cada uno.
3. Obtener el código de alta: `docker compose logs plataforma | grep "CÓDIGO DE ALTA"`.
4. Corregir lo que falle en el primer arranque (tabla de la sección 8) y documentar cada
   corrección en `docs/DESPLIEGUE_GNS3.md`.

**Aceptación:** `curl -s http://127.0.0.1:8000/salud` en la VM devuelve `{"estado":"ok","mqtt":true}`.

### Fase 3. Túnel, alta y primer ingreso

1. Crear `scripts/windows/tunel.ps1`: `ssh -N -L 8000:127.0.0.1:8000 gns3@192.168.56.101`,
   con aviso si el puerto 8000 de Windows ya está ocupado.
2. El usuario abre `http://localhost:8000/alta`, usa el código y registra la passkey con
   Windows Hello, llave FIDO2 o el autenticador virtual de Chrome (DevTools → More tools → WebAuthn).
3. Cerrar sesión y volver a entrar con contraseña + passkey.

**Aceptación:** eventos `passkey_registrada` y `auth_exitosa` en la bitácora; pestaña Red en "captura real eth2".

### Fase 4. Topología

Pasos para el usuario en la interfaz de GNS3 (no por archivo):

| Nodo | Acción |
|---|---|
| CAM-03 | Alpine nuevo conectado a SW-CIRC-B, IP 10.10.10.55/24 |
| PC-NAVE | `alpine-1` en SW-CIRC-B, IP 10.10.10.99/24, autorizado en el inventario |
| PC-INTRUSO | Alpine conectado a SW-CIRC-A, IP 10.10.10.66/24, fuera del inventario y apagado hasta la demo |
| Todos los Alpine | Clic derecho → *Edit config*: IP estática persistente en `/etc/network/interfaces`. Clic derecho → *Configure* → *Start command*: `ping -i 1 10.10.10.1`, para que el latido arranque solo |

**Aceptación:** los 5 equipos del inventario aparecen "En línea" con su MAC registrada.

### Fase 5. Validación de la demostración

Recorrer `docs/GUIA_DEMO.md` con el usuario. Por cada paso, confirmar el evento esperado:

```bash
ssh gns3@192.168.56.101 "cd ~/plataforma && docker compose exec -T plataforma python -c \"import sqlite3;c=sqlite3.connect('/app/datos/plataforma.db');[print(r) for r in c.execute('select id,severidad,tipo,descripcion from eventos order by id desc limit 15')]\""
```

**Aceptación:** los 15 pasos del guion con su evento y la cadena de hash íntegra.

### Fase 6. Construcción pendiente (en orden, previa confirmación del usuario)

1. `scripts/windows/logs.ps1` y `detener.ps1` (atajos de `docker compose logs -f` y `down` por SSH).
2. Reporte imprimible del incidente: página `/reporte` con los eventos de un rango, hashes y
   estado de la cadena, estilos de impresión para "Guardar como PDF" desde el navegador
   (evidencia para el auditor). Requiere rol auditor o administrador.
3. Confirmación de la caída de conmutadores con la API REST del servidor GNS3 (estado del
   nodo SW-CIRC-B): el evento `cascada_poe` pasa de inferido a confirmado.
4. Modo HTTPS con `plataforma.test` para la passkey en el teléfono.
5. Opcional: 802.1X real con FreeRADIUS según `GUIA_INFRAESTRUCTURA.md`.

## 8. Problemas previsibles en el primer arranque

| Síntoma | Causa probable | Acción |
|---|---|---|
| `docker compose` desconoce `name:` o las anclas `x-seguro` | Compose v1 o plugin antiguo | Instalar el plugin v2 |
| Error al descargar imágenes | La VM no tiene salida por NAT (eth1) | Revisar el adaptador NAT en VirtualBox y `ping 8.8.8.8` |
| `broker` en bucle de reinicio | Falta una `MQTT_PASS_*` o permisos del `entrypoint.sh` | Revisar `.env`; `docker compose logs broker` |
| `plataforma` unhealthy | Permisos del volumen `datos_plataforma` o error de import | `docker compose logs plataforma` |
| `sensor-red`: "Interface eth2 not found" | La interfaz no existe o cambió de nombre | `ip -br link` en la VM; ajustar `IFACE` en `.env` |
| Red sin equipos en línea | Los Alpine no emiten o eth2 sin promiscuo | `tcpdump -i eth2 -n arp`; servicio `lab-promisc` de la guía de infraestructura |
| WebAuthn "SecurityError" | Se abrió por IP en lugar de `localhost` | Usar `http://localhost:8000` por el túnel |
| El túnel no conecta | Puerto 8000 ocupado en Windows | `netstat -ano | findstr :8000` |
| `broker` o un script: `/bin/sh^M: bad interpreter` | Finales de línea CRLF por edición en Windows | `sed -i 's/\r$//' broker/entrypoint.sh scripts/*.sh` en la VM |

## 9. Referencia rápida

```bash
# En la VM (~/plataforma)
docker compose ps
docker compose logs -f plataforma
docker compose restart plataforma
docker compose up -d --build            # tras copiar cambios
docker compose down                     # detiene solo este proyecto
docker compose down -v                  # además borra la base: nuevo código de alta
```

| Tarjeta | Titular | PIN | Coacción | Estado |
|---|---|---|---|---|
| C-1001 | Técnico de turno A | 1357 | 1358 | activa |
| C-1002 | Custodio de la sala | 2468 | 2469 | activa |
| C-1003 | Exempleado de mantenimiento | 1111 | 1112 | revocada |

Variables configurables: `plataforma/app/config.py` y `.env.example`.
Ejecución sin Docker (Linux, modo demo): `scripts/ejecutar_local.sh`.

Verificaciones estáticas después de cada cambio (en la VM si Windows no tiene Python o Node):

```bash
python3 -m pyflakes plataforma/app simuladores sensor-red
for f in plataforma/static/js/*.js; do node --check "$f"; done
docker compose config -q
```

Prueba de punta a punta (`scripts/prueba_e2e.py`, Chromium con autenticador WebAuthn
virtual): necesita una base nueva y un código de alta conocido. Solo se ejecuta contra un
stack de prueba en modo demo y con autorización del usuario, porque exige `down -v`.
