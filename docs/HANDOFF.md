# Handoff: estado del proyecto y siguientes pasos

Resumen de las sesiones del 25 y 26 de septiembre de 2026 para continuar en Claude Code
desde Windows, con el código en `D:\PROYECTO-SEGURIDAD\plataforma`, en modo localhost y
sin repositorios remotos. Las instrucciones operativas están en `CLAUDE.md`; esta hoja
guarda el estado, las decisiones y el backlog.

## 1. Qué se entregó

| Entregable | Estado |
|---|---|
| Documento del Entregable 2 (Word y PDF, APA 7) | Completo. IEEE 446-1995 se retiró por estar inactiva en el catálogo IEEE. Vive fuera del repositorio |
| Plataforma v2 (`Proyecto-Seguridad-v2.zip`, extraída en `D:\PROYECTO-SEGURIDAD\plataforma`) | Construida y probada en modo demo sin Docker |
| Documentación técnica en `docs/` | Completa: arquitectura, despliegue, guion de demo, seguridad, tópicos MQTT |

## 2. Qué hace la plataforma v2

| Frente | Implementación | Norma y control |
|---|---|---|
| Red | Captura pasiva de eth2 en `sensor-red`; lista de permitidos; MAC registrada por primer uso; intrusos, sustitución, desconexión, cascada PoE, pérdida de visibilidad, capturador caído, límite contra inundación | IEEE 802.1X, 802.1AR, 802.3bt; ISO 7.2, 7.8, 8.16, 8.20 |
| Energía | `sim-ups` con variables NUT; máquina de estados NORMAL → CORTE → UPS_EN_BATERIA → TRANSFERENCIA_GENERADOR → BATERIA_BAJA → APAGADO; transferencia medida contra tipo 10; ejercicio mensual | NFPA 110, NFPA 111, IEEE 1188; ISO 7.11, 7.13 |
| Ambiente | Temperatura de entrada por rack con histéresis; sensor mudo; humo con descarga de agente limpio a los 30 s abortable; la climatización depende de la energía | ASHRAE TC 9.9 clase A1, NFPA 72, NFPA 2001; ISO 7.5 |
| Acceso físico | Tarjeta + PIN, PIN de coacción con alerta silenciosa, tarjeta revocada, intentos repetidos, puerta forzada y mantenida abierta | NFPA 731; ISO 7.2, 7.4, 5.18 |
| Autenticación | Contraseña bcrypt + passkey WebAuthn con UV obligatoria; alta con código de un solo uso; roles operador, auditor y administrador; reautenticación para acciones sensibles; bloqueo por intentos; sesión de 15 min | NIST SP 800-63B-4; ISO 5.15 a 5.18, 8.5 |
| Evidencia | Bitácora de solo inserción con cadena SHA-256, verificación, exportación CSV, acuses como eventos, procedimientos por alerta, 9 indicadores | ISO 8.15, 5.26; NIST SP 800-53 AU-9 |

Arquitectura: 7 servicios en `docker-compose.yml` (plataforma, proxy Caddy, broker
Mosquitto con ACL, sensor-red, sim-ups, sim-ambiente, sim-puerta). Ver `docs/ARQUITECTURA.md`.

## 3. Decisiones tomadas

| Decisión | Motivo |
|---|---|
| La biometría se usa solo para desbloquear la passkey en el teléfono | El documento de autenticación descarta la biometría como barrera de acceso al *hardware*; la huella no sale del dispositivo |
| Modo localhost por túnel SSH como modo de trabajo | `http://localhost` es contexto seguro para WebAuthn: sin archivo hosts, sin CA y sin exponer nada a la red |
| HTTPS con Caddy y `plataforma.test` como modo opcional (perfil `https`) | Necesario para la passkey en el teléfono por QR, que puede rechazar el RP ID `localhost` |
| Código en Windows, ejecución en la GNS3 VM | Solo la VM tiene `eth2` hacia la topología; Claude Code opera la VM por SSH |
| Frontend HTML + JS sin compilación, topología en SVG propio | Construcción rápida y CSP estricta; vis-network inyecta estilos en línea |
| SQLite | Un solo escritor, archivo fácil de auditar |
| Descarga de batería acelerada x30, arranque de planta en tiempo real | La demo dura minutos y la transferencia sigue siendo comparable con 10 s |
| CAM-03 agregado a SW-CIRC-B | Con un solo equipo no se distingue la caída del switch de la del equipo |
| Puertos: 127.0.0.1:8000 en modo localhost, 443 en modo https | El 80 lo usa el servidor de GNS3 en la VM |

## 4. Qué se probó y qué no

**Probado** con `scripts/prueba_e2e.py` y escenarios por MQTT, en modo demo y sin Docker:
alta con código, login de dos factores, rechazo de contraseña, reautenticación, todos los
eventos de la sección 2, acuse, creación de usuario con código y cadena de hash íntegra.
Sin errores de CSP en consola.

**No probado**:
- `docker compose up --build`: el entorno anterior no podía descargar imágenes de Docker Hub. Solo se validó `docker compose config`. **Es la primera tarea.**
- Captura real en eth2 con la topología GNS3.
- Passkey en un teléfono físico con el flujo de QR y Bluetooth.
- Rendimiento dentro de la GNS3 VM con la topología encendida.

## 5. Backlog priorizado

### P0 · Poner en marcha (fases 0 a 5 de `CLAUDE.md`)

| # | Tarea | Criterio de aceptación |
|---|---|---|
| T0 | Verificar el entorno sin modificar nada: Windows, SSH a la VM, Docker y Compose, eth2, topología leída del `.gns3` | Tabla "esperado vs encontrado" |
| T1 | Preparar la VM: plugin de Docker Compose, `timedatectl set-ntp true`, detener la v1, RAM de 4 a 8 GB, cambiar la contraseña de `gns3` | `docker compose version` responde; puerto 8000 libre |
| T2 | Crear `scripts/windows/desplegar.ps1` y desplegar en modo localhost con `MODO_RED=captura` | 6 servicios en `running`, `plataforma` healthy, `/salud` con `"mqtt": true` |
| T3 | Crear `scripts/windows/tunel.ps1`, activar `admin` con passkey (Windows Hello, llave o autenticador virtual) | Eventos `passkey_registrada` y `auth_exitosa` |
| T4 | Topología: CAM-03 (.55) en SW-CIRC-B; PC-NAVE (.99) autorizado; PC-INTRUSO (.66) en SW-CIRC-A, fuera del inventario; IP y latido persistentes en los Alpine | 5 equipos en línea con MAC registrada, en "captura real eth2" |
| T5 | Crear `operador1` y `auditor1`; segunda passkey para `admin` | Indicador "Cuentas con passkey" en 100 % |
| T6 | Ensayar `docs/GUIA_DEMO.md` completo | 15 pasos con su evento; cadena íntegra; CSV exportado |
| T7 | Opcional: modo https con `plataforma.test` y passkey en el teléfono | Ingreso con QR y huella del teléfono |

### P1 · Ajustes esperables después del ensayo

- Calibrar `UMBRAL_DESCONEXION_S` e `INTERVALO_REVISION_S` si hay falsas desconexiones con tráfico real.
- Confirmar que el cambio de MAC en un Alpine de GNS3 dispara `suplantacion` (requiere NET_ADMIN en el nodo).
- Revisar la lectura del tablero en el proyector: tamaño de fuente y contraste.
- Al cerrar el ensayo, verificar los filtros de la bitácora (módulo y severidad), el alta y retiro de equipos desde Administración y las acciones Autorizar y Retirar de la pestaña Red (agregadas el 2 de octubre de 2026 para recuperar lo que hacía la v1).
- Actualizar la sección 2.5 del Entregable 2 con las fases completadas, respetando las reglas de redacción de `CLAUDE.md`.

### P2 · Mejoras opcionales

| Mejora | Valor |
|---|---|
| Reporte PDF de incidente: bitácora filtrada + indicadores | El plan original pedía exportación CSV y PDF |
| Pruebas unitarias con pytest, ejecutadas en la VM: cadena de hash, máquina de energía, histéresis, coacción | Evidencia de calidad para la auditoría |
| Scripts `logs.ps1` y `detener.ps1` para operar la VM desde Windows | Menos comandos manuales durante la demo |
| Consultar la API de GNS3 para confirmar el estado de los switches | Distingue caída de switch y caída de equipo con certeza |
| Eventos reales de FreeRADIUS para 802.1X | Cierra la brecha entre la detección por MAC y la norma |
| Simuladores como nodos Docker dentro de GNS3 | El sensor ambiental queda afectado por la cascada PoE |
| TLS en MQTT | Pendiente conocido de `docs/SEGURIDAD.md` |

## 5 bis. Sesión del 2 de octubre de 2026 (dónde quedamos)

| Fase | Estado |
|---|---|
| 0 a 2 | Completas. Stack v2 en `~/plataforma` de la VM, modo localhost, captura real en eth2, `/salud` con `mqtt: true`. Compose v5.5.1 en `~/.docker/cli-plugins`. Llave SSH instalada |
| 3 | Completa. `admin` y `operador` con passkey del teléfono por QR (`hybrid`); Windows Hello bloqueado por la directiva de la organización del equipo |
| 4 | Casi completa (3 de octubre). Edit config persistente con IP y latido en todos los Alpine; CAM-03 en SW-CIRC-B eth3 con .55 y MAC registrada; PC-INTRUSO en SW-CIRC-A eth5, apagado. Un error de copia dio a CAM-03 la IP .53 y la plataforma lo detectó como `suplantacion` (evento 82). Falta corregir el Edit config de PC-INTRUSO, que tiene .53 en lugar de .66 |
| 5 y 6 | Pendientes |

Cambios de código de esta sesión: `scripts/windows/desplegar.ps1` y `tunel.ps1`; `app/recuperar.py` (recuperación de emergencia por consola); tipo de passkey guardado como `multi_device`; acciones Autorizar y Retirar en la pestaña Red; etiquetas en el formulario de inventario; intruso de la demo cambiado de .99 a .66.

Siguiente entregable pedido por el usuario: manual de uso que muestre las simulaciones y la funcionalidad de la plataforma.

La v1 (`sudo uvicorn` en `192.168.56.101:8000`, `~/plataforma-postal`) sigue corriendo; detenerla cuando el usuario lo confirme. Las IPs actuales de los Alpine son temporales (`ip addr add` por consola) y se pierden si el nodo se reinicia.

## 5 ter. Sesión del 8 de octubre de 2026

- Fase 5: ensayo ejecutado el 3 de octubre; resultados en `REGISTRO_VALIDACION.md` (pendientes los pasos de tablero 2, 11, 13, 14 y 15; hallazgos H1 y H2 abiertos).
- Manual para el equipo auditor: `docs/MANUAL_SIMULACIONES.md` (marco normativo, escenarios, trazabilidad).
- Nube aprobada: Azure for Students + Tailscale + base migrada (`docs/DESPLIEGUE_NUBE.md`, `docs/ACCESO_AUDITORES.md`). Listos `docker-compose.nube.yml`, modo `nube` de `generar_env.sh`, `-Modo/-Dominio` en `desplegar.ps1` y `scripts/nube/preparar_vm.sh`. Copia de la base en `migracion\plataforma_migracion.db` (188 eventos, último hash `b4d838ee…`). Falta: crear la VM y la cuenta de Tailscale (usuario) y ejecutar los pasos 2 a 7.

## 6. Riesgos del primer arranque en Docker

| Punto | Qué revisar si falla |
|---|---|
| `broker` | `entrypoint.sh` crea `passwd` y hace `chown mosquitto`; si reinicia en bucle, revisar variables `MQTT_PASS_*` en `.env` |
| `plataforma` | Volumen `datos_plataforma` debe ser escribible por uid 10001; FS de solo lectura con `/tmp` en tmpfs |
| `sensor-red` | `network_mode: host`, `CAP_NET_RAW`, `HOME=/tmp`; si Scapy no abre eth2, revisar el servicio `lab-promisc` y los permisos |
| `proxy` | Solo en modo https (`--profile https`). Carpeta `datos/caddy` creada por `generar_env.sh`; CA en `datos/caddy/caddy/pki/authorities/local/root.crt` |
| Finales de línea | El código se edita en Windows: un `.sh` con CRLF falla en la VM; normalizar con `sed -i 's/\r$//'` |
| Túnel SSH | Requiere llave SSH sin contraseña hacia `gns3@192.168.56.101` y el puerto 8000 libre en Windows |
| Memoria | 7 contenedores + switches + Alpine; si la VM se queda corta, subir RAM antes de optimizar |
| Versión de Docker en la VM | Si es antigua y falla la sintaxis de Compose, actualizar el plugin antes de tocar el YAML |

## 7. Datos de prueba

- Admin inicial: `admin`, código en `docker compose logs plataforma | grep "CÓDIGO DE ALTA"` (fijo con `ADMIN_CODIGO_ALTA` en `.env`).
- URL de trabajo: `http://localhost:8000` con el túnel abierto; activación en `/alta`.
- Tarjetas: C-1001 PIN 1357 (coacción 1358), C-1002 PIN 2468 (coacción 2469), C-1003 revocada.
- Autonomía de diseño: `60 · 864 · 0.90 / 566.2 = 82.4 min`; batería baja a 20.6 min.
