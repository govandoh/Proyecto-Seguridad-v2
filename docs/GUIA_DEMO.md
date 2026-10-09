# Guion de la demostración en vivo

Duración estimada: 15 minutos. Preparación: stack levantado, topología GNS3 encendida
con los latidos activos, cuenta `admin` con passkey en el teléfono y una cuenta
`operador1` creada. Cada paso recorre una arista del Triángulo de la Ciberresiliencia
y deja un evento que al final se exporta como evidencia.

| # | Acción | Dónde | Qué se ve | Evidencia y norma |
|---|---|---|---|---|
| 1 | Iniciar sesión con contraseña y passkey del teléfono | `/login` | QR en la PC, huella en el teléfono, tablero en verde | `auth_exitosa`, ISO/IEC 27001 8.5, NIST SP 800-63B-4 |
| 2 | Mostrar el estado normal | Resumen y Red | 5 equipos en línea, UPS en OL, temperatura en rango | Inventario con MAC registrada |
| 3 | Encender PC-INTRUSO (10.10.10.66, fuera del inventario) | GNS3 | Alerta crítica y nodo NO AUTORIZADO en la topología | `dispositivo_no_autorizado`, IEEE 802.1X |
| 4 | Cambiar la MAC de CAM-02: `ip link set eth0 down; ip link set eth0 address 02:42:de:ad:be:ef; ip link set eth0 up` | Consola del Alpine | Alerta de posible sustitución | `suplantacion`, IEEE 802.1AR |
| 5 | PIN de coacción: C-1001 con PIN 1358 | Simulación → Puerta | La puerta abre; alerta silenciosa solo en el tablero | `ingreso_bajo_coaccion`, NFPA 731 |
| 6 | Tarjeta revocada C-1003 | Simulación → Puerta | Acceso denegado y alerta crítica | `credencial_revocada_usada`, ISO/IEC 27001 5.18 |
| 7 | Cortar la acometida | Simulación → Energía | CORTE → UPS EN BATERÍA → TRANSFERENCIA en unos 7 s | `transferencia_planta`: cumple el tipo 10 de NFPA 110 |
| 8 | Falla de planta | Simulación → Energía | Vuelve a batería; sin climatización la sala se calienta; batería baja y apagado ordenado | `falla_planta`, `temperatura_critica`, `bateria_baja`, `apagado_controlado` |
| 9 | Detener SW-CIRC-B | GNS3 | LECT-01 y CAM-03 sin PoE en un solo evento | `cascada_poe`, IEEE 802.3bt |
| 10 | Detectar humo y abortar antes de 30 s | Simulación → Ambiente | Alarma, cuenta regresiva, supresión abortada | `alarma_humo`, `supresion_abortada`, NFPA 72 y 2001 |
| 11 | Atender una alerta | Resumen → Atender | Procedimiento de respuesta y acuse con nota | Evento `acuse` con `ref_id`, ISO/IEC 27001 5.26 |
| 12 | Restablecer: acometida, reparar planta, encender SW-CIRC-B, apagar PC-INTRUSO | GNS3 y Simulación | Retorno a NORMAL con duración del incidente | `retorno_acometida`, `dispositivo_reconectado` |
| 13 | Verificar la cadena y exportar | Bitácora | "Íntegra: N eventos encadenados"; descarga del CSV | ISO/IEC 27001 8.15, NIST SP 800-53 AU-9 |
| 14 | Mostrar indicadores | Indicadores | Detección, transferencia, MFA e integridad calculados | Tabla 22 del Entregable 2 |
| 15 | Rol auditor | Otra sesión con cuenta auditor | Puede ver y exportar; no puede acusar ni simular | Mínimo privilegio, NIST SP 800-53 AC-6 |

## Variantes útiles

- **Transferencia fuera de norma**: "Arranque lento, 14 s" antes del corte. La plataforma
  registra `transferencia_fuera_de_tipo` y el indicador baja del 100 %.
- **Sensor mudo**: "Silenciar T-RACK-B". A los 15 s aparece `sensor_mudo`, el caso de la
  cámara sin señal que nadie atendía.
- **Pérdida de visibilidad**: detener SW-CIRC-A en GNS3. Todos los equipos callan a la vez
  y la plataforma lo reporta como pérdida del punto de captura, no como cinco caídas.
- **Intentos repetidos**: tres PIN incorrectos seguidos con C-1002 generan `intentos_repetidos`.
- **Reautenticación**: pasados 5 minutos, crear un usuario en Administración pide la
  passkey de nuevo antes de ejecutar la acción.
- **Sin GNS3**: con `MODO_RED=demo`, los pasos 3, 4 y 9 se ejecutan desde Simulación → Red.

## Datos de demostración

| Tarjeta | Titular | PIN | PIN de coacción | Estado |
|---|---|---|---|---|
| C-1001 | Técnico de turno A | 1357 | 1358 | activa |
| C-1002 | Custodio de la sala | 2468 | 2469 | activa |
| C-1003 | Exempleado de mantenimiento | 1111 | 1112 | revocada |
