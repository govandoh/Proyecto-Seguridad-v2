# Seguridad de la plataforma

## 1. Correcciones de los hallazgos V1 a V10 (Entregable 2, sección 2.6.2)

| ID | Hallazgo en la v1 | Corrección en la v2 | Dónde |
|---|---|---|---|
| V1 | XSS almacenado por el nombre del dispositivo en la bitácora y en `innerHTML` | Todo el texto se inserta con `textContent`; CSP `script-src 'self'` sin `unsafe-inline`; nombres validados con expresión regular | `static/js/comun.js` (`el`), `app/main.py` (CSP), `modulos/red.py` |
| V2 | API y tablero sin autenticación; cualquiera autorizaba intrusos | Contraseña bcrypt + passkey WebAuthn, roles, reautenticación para cambiar el inventario | `app/auth/`, `app/api.py` |
| V3 | POST sin protección contra falsificación | Cookie `SameSite=Strict`, cabecera obligatoria `X-Plataforma` y verificación de `Origin` | `app/main.py` |
| V4 | Swagger expuesto y credenciales por defecto en la VM | `/api/docs` deshabilitado salvo `API_DOCS=true`; la guía de despliegue pide cambiar la contraseña de la VM | `app/main.py`, `docs/DESPLIEGUE_GNS3.md` |
| V5 | Dependencias sin versión fija | `requirements.txt` con versiones exactas | `*/requirements.txt` |
| V6 | Toda la aplicación como root por `sudo` | Captura en el contenedor `sensor-red` con solo `CAP_NET_RAW`; la web corre con el usuario `plataforma` (uid 10001), sistema de archivos de solo lectura y `no-new-privileges` | `docker-compose.yml`, Dockerfiles |
| V7 | Bitácora alterable, sin actor y con hora local | Solo inserción, cadena SHA-256, campo `actor`, verificación y exportación con hashes; sellos UTC | `app/bitacora.py` |
| V8 | Autorización solo por IP y relación IP-MAC en memoria | MAC registrada en el inventario por primer uso; su cambio se detecta aun después de reiniciar | `modulos/red.py` |
| V9 | Un evento crítico por cada MAC aleatoria | Límite de `MAX_NO_AUTORIZADOS_MIN` avisos por minuto y un evento de inundación | `modulos/red.py` |
| V10 | Entradas sin validar | Modelos Pydantic con longitudes y patrones; `ipaddress` para IP; lista cerrada de comandos de simulación | `app/api.py`, `modulos/red.py` |

Se corrigió además la regla de cascada PoE, que no se disparaba en conmutadores con un
solo equipo, y se agregaron los eventos `perdida_visibilidad` y `capturador_caido`.

## 2. Autenticación (NIST SP 800-63B-4)

| Requisito | Implementación |
|---|---|
| Dos factores independientes | Contraseña (conocimiento) + passkey (posesión, con verificación de usuario local) |
| Resistencia a *phishing* | La firma WebAuthn queda ligada al origen `https://plataforma.test`; un sitio falso no puede reutilizarla |
| Verificación de usuario | `userVerification: required`: huella, rostro o PIN en el autenticador |
| Contraseña | bcrypt con costo 12, mínimo 12 caracteres, sin reglas de composición, bloqueo de contraseñas comunes |
| Limitación de intentos | 5 fallos bloquean la cuenta 15 minutos y generan `auth_bloqueo` crítico |
| Ciclo de vida | Alta con código de un solo uso de 24 h; restablecimiento revoca passkeys; baja revoca todo en la misma transacción |
| Recuperación de emergencia | Si ningún administrador puede entrar: `docker compose exec plataforma python -m app.recuperar <usuario>` en la GNS3 VM. Revoca las passkeys, borra la contraseña, cierra las sesiones, emite un código nuevo y registra `usuario_restablecido` con actor `consola:recuperacion` en la cadena de hash. Exige acceso a la VM, no a la web |
| Sesión | Token aleatorio de 256 bits en cookie `HttpOnly`, `Secure`, `SameSite=Strict`; en la base solo su SHA-256; expira a los 15 min sin actividad |
| Acciones sensibles | Reautenticación con passkey en los últimos 5 min (`REAUTH_MIN`) |
| Métodos descartados | SMS y correo como segundo factor, por su baja resistencia a *phishing* |

La biometría no se usa como barrera de acceso al *hardware*, conforme a la
especificación de autenticación del proyecto: aquí solo desbloquea la passkey dentro
del teléfono, y lo que se revoca es la clave pública registrada.

## 3. Roles

| Acción | Operador | Auditor | Administrador |
|---|:-:|:-:|:-:|
| Ver tablero, eventos e indicadores | ✓ | ✓ | ✓ |
| Acusar alertas | ✓ | | ✓ |
| Consola de simulación | ✓ | | ✓ |
| Verificar la cadena | ✓ | ✓ | ✓ |
| Exportar la bitácora | | ✓ | ✓ |
| Usuarios, tarjetas e inventario (con reautenticación) | | | ✓ |

## 4. Controles de ISO/IEC 27001:2022 cubiertos

| Control | Implementación |
|---|---|
| 5.15 Control de acceso, 5.18 Derechos de acceso | Roles y revocación inmediata |
| 5.16 Gestión de identidades | Alta con código, baja, registro de MAC de dispositivos |
| 5.17 Información de autenticación | bcrypt, código de alta con SHA-256, sesiones con hash |
| 5.26 Respuesta a incidentes | Procedimientos por tipo de alerta y acuse registrado |
| 7.2 Entrada física, 7.4 Monitoreo de la seguridad física | Tarjeta + PIN, coacción, puerta forzada |
| 7.5 Amenazas físicas y ambientales | Umbrales ASHRAE, humo y supresión |
| 7.8 Emplazamiento y protección de equipos | Desconexión y cascada PoE |
| 7.11 Servicios de suministro | Máquina de estados de energía |
| 7.13 Mantenimiento de equipos | Ejercicio mensual de la planta |
| 8.5 Autenticación segura | Contraseña + passkey |
| 8.15 Registro, 8.16 Monitoreo | Bitácora encadenada, tablero en vivo |
| 8.20 Seguridad de redes | Lista de permitidos, detección de intrusos |

## 5. Pendientes conocidos

- MQTT sin TLS dentro de la red interna de Docker; en producción se activaría TLS y OSDP con canal seguro para las lectoras.
- La hora depende del reloj de la VM: se recomienda `timedatectl set-ntp true` en la GNS3 VM (control 8.17).
- La autenticación 802.1X real con FreeRADIUS sigue como opción de la guía de infraestructura; la plataforma detecta por MAC e IP.
