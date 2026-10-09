# Registro de validación de la demostración

Se completa durante el ensayo descrito en `VALIDACION_DEMO.md`. Una fila por paso; la
evidencia es el `id` del evento en la bitácora y, cuando aplica, una captura.

| Dato | Valor |
|---|---|
| Fecha y hora de inicio | 2026-10-03, 23:04 (hora de la VM, UTC) |
| Responsable | Gerardo Ovando |
| Último `id` antes del ensayo (línea base) | 98 |
| Modo de red | Captura real en eth2 |
| Cuentas usadas | admin, operador, auditor1 |

## Resultados por paso

Resultado: **OK**, **Falla** o **Parcial**.

| # | Paso | Evento esperado | `id` obtenido | Resultado | Observaciones |
|---|---|---|---|---|---|
| 1 | Ingreso con contraseña y passkey | `auth_exitosa` | 126 | OK | admin con passkey del teléfono |
| 2 | Estado normal | 6 equipos en línea | n/a | Pendiente | Revisar en el tablero |
| 3 | Encender PC-INTRUSO | `dispositivo_no_autorizado` | 172 | Parcial | Evento correcto (10.10.10.66, 02:42:05:65:6f:00), pero el arranque saturó la VM y generó los eventos falsos 136 a 171. Ver hallazgo H1 |
| 4 | Cambio de MAC de CAM-02 | `suplantacion` | 173 | OK | MAC 02:42:de:ad:be:ef frente a la registrada 02:42:70:ba:6a:00; MAC restaurada después |
| 5 | PIN de coacción | `ingreso_bajo_coaccion` | 99 | OK | C-1001 con 1358; la puerta abrió |
| 6 | Tarjeta revocada | `credencial_revocada_usada` | 100 | OK | C-1003 |
| 7 | Corte de acometida | `perdida_acometida`, `ups_en_bateria`, `transferencia_planta` | 101 a 103 | OK | Tiempo de transferencia: 7.47 s, cumple el tipo 10 |
| 8 | Falla de planta | `falla_planta`, `temperatura_*`, `bateria_baja`, `apagado_controlado` | 104 a 110 | OK | Batería baja con 20.4 min; apagado 2 min 44 s después de la falla |
| 9 | Detener SW-CIRC-B | `cascada_poe` (un solo evento) | 178 | OK | Equipos listados: PC-NAVE, LECT-01, CAM-03 |
| 10 | Humo y aborto | `alarma_humo`, `supresion_abortada` | 116, 117 | OK | Aborto a los 10 s |
| 11 | Atender una alerta | `acuse` con `ref_id` | | Pendiente | Requiere el tablero |
| 12 | Restablecer | `retorno_acometida`, `dispositivo_reconectado` | 111, 179 a 181 | OK | Incidente eléctrico cerrado tras 273 s; SW-CIRC-B reiniciado. Falta apagar PC-INTRUSO |
| 13 | Verificar y exportar | `verificacion_cadena`, `exportacion` | | Pendiente | Requiere el tablero |
| 14 | Indicadores | Valores calculados | n/a | Pendiente | Requiere el tablero |
| 15 | Rol auditor | Puede ver y exportar, no acusar ni simular | | Pendiente | Cuenta auditor1 lista |

## Variantes

| Variante | Evento esperado | `id` obtenido | Resultado |
|---|---|---|---|
| Transferencia de 14 s | `transferencia_fuera_de_tipo` | 121 | OK, 14.47 s |
| Sensor mudo | `sensor_mudo` | 123 | OK |
| Pérdida de visibilidad | `perdida_visibilidad` | | Pendiente; el 164 fue un falso positivo de H1 |
| Intentos repetidos | `intentos_repetidos` | 132 | OK |
| Reautenticación | Solicita la passkey | n/a | Pendiente |
| Descarga del agente limpio | `supresion_descargada` a los 30 s | 127 | OK, 23:18:50 → 23:19:20 |
| Puerta forzada | `puerta_forzada` | 133 | OK |
| Puerta mantenida abierta | `puerta_mantenida_abierta` | 135 | OK |

## Cierre

| Dato | Valor |
|---|---|
| Último `id` del ensayo | |
| Cadena de hash | Íntegra / Rota |
| Total de eventos encadenados | |
| Hash del último evento | |
| Archivo CSV de evidencia | `evidencia\eventos_<fecha>.csv` |
| Pasos con falla | |

## Hallazgos y correcciones

| # | Hallazgo | Corrección | Estado |
|---|---|---|---|
| H1 | Al encender PC-INTRUSO, la GNS3 VM con 1 CPU llegó a una carga de 25 durante unos 3 min. Se registraron eventos falsos: `capturador_caido`, `sensor_mudo`, `ups_sin_comunicacion`, `cascada_poe` de SW-CIRC-B y `perdida_visibilidad` (136 a 171) | Asignar 2 o más CPU a la GNS3 VM en VirtualBox y repetir el paso 3 | Abierto |
| H2 | Los pasos 5 a 10 y las variantes se enviaron directamente al broker MQTT, por lo que no registran `comando_simulado` con actor | Repetirlos desde la pestaña Simulación en el ensayo final | Abierto |
| H3 | El 3 de octubre la configuración de CAM-03 tenía la IP de CAM-02 y la plataforma lo detectó como `suplantacion` (evento 82) | Corregido a 10.10.10.55 | Cerrado |
