# Protocolo de validación de la demostración (Fase 5)

Ensayo completo del guion de `GUIA_DEMO.md` contra la topología real. Por cada paso se
confirma que la acción produce el evento esperado en la bitácora. Los resultados se anotan
en `REGISTRO_VALIDACION.md`.

**Criterio de aceptación:** los 15 pasos con su evento y la cadena de hash íntegra.

## 1. Antes de empezar

| # | Verificación | Cómo |
|---|---|---|
| 1 | Laboratorio encendido | Pasos 1 a 7 de `ARRANQUE.md` |
| 2 | Seis equipos autorizados en línea, PC-INTRUSO **apagado** | Pestaña Red |
| 3 | Tres cuentas con passkey: `admin`, `operador` y `auditor1` | `auditor1` aún no existe: crearlo en Administración con rol `auditor` y registrar su passkey en una ventana de incógnito (paso 15) |
| 4 | Estado inicial de energía y ambiente limpio | Simulación: Restablecer acometida, Reparar planta, Arranque normal 7 s, Restaurar climatización, Liberar sensores, Restablecer detección |
| 5 | Línea base de la bitácora | `.\scripts\windows\evidencia.ps1 -Ultimos 1` y anotar el `id` y la cadena íntegra |
| 6 | No redesplegar durante el ensayo | Reinicia el capturador y registra una pérdida de visibilidad |

Para ver los eventos de un paso: `.\scripts\windows\evidencia.ps1 -Desde <id anterior>`.
Con `-Csv` guarda además el archivo en `evidencia\`.

## 2. Pasos

Antes de cada paso se anota el último `id`; después se ejecuta la acción, se espera el
tiempo indicado y se corre `evidencia.ps1 -Desde <id>`.

| # | Acción | Dónde | Evento esperado | Espera |
|---|---|---|---|---|
| 1 | Cerrar sesión y entrar con contraseña y passkey del teléfono | `/login` | `auth_exitosa` | inmediato |
| 2 | Revisar el estado normal | Resumen y Red | ninguno nuevo: 6 equipos en línea, UPS en OL, temperatura en rango | n/a |
| 3 | Encender **PC-INTRUSO** (10.10.10.66) | GNS3: clic derecho, Start | `dispositivo_no_autorizado` (crítico) | unos segundos |
| 4 | En la consola de CAM-02: `ip link set eth0 down; ip link set eth0 address 02:42:de:ad:be:ef; ip link set eth0 up` | Consola del Alpine | `suplantacion` (crítico) | unos segundos |
| 5 | Tarjeta C-1001 con PIN **1358** (coacción) | Simulación → Puerta | `ingreso_bajo_coaccion` (crítico); la puerta abre | inmediato |
| 6 | Tarjeta C-1003 con PIN 1111 | Simulación → Puerta | `credencial_revocada_usada` (crítico) | inmediato |
| 7 | Cortar acometida | Simulación → Energía | `perdida_acometida`, `ups_en_bateria`, `transferencia_planta` (cumple tipo 10, unos 7 s) | 15 s |
| 8 | Falla de planta | Simulación → Energía | `falla_planta`, luego `temperatura_alta` o `temperatura_critica`, `bateria_baja`, `apagado_controlado` | varios minutos (descarga acelerada x30) |
| 9 | Detener **SW-CIRC-B** | GNS3: clic derecho, Stop | un solo `cascada_poe` con LECT-01, CAM-03 y PC-NAVE | unos 8 a 11 s (umbral de 8 s y revisión cada 3 s) |
| 10 | Detectar humo y abortar antes de 30 s | Simulación → Ambiente | `alarma_humo`, `supresion_abortada` | 30 s máximo |
| 11 | Atender una alerta crítica | Resumen → Atender | `acuse` con `ref_id` del evento atendido | inmediato |
| 12 | Restablecer (ver 3) | GNS3 y Simulación | `retorno_acometida`, `dispositivo_reconectado` | 1 minuto |
| 13 | Verificar la cadena y exportar CSV | Bitácora | `verificacion_cadena` y `exportacion`; "Íntegra: N eventos" | inmediato |
| 14 | Mostrar indicadores | Indicadores | ninguno: detección, transferencia, MFA e integridad calculados | n/a |
| 15 | Entrar como `auditor1`: puede ver y exportar; no puede acusar ni simular | Ventana de incógnito | `auth_exitosa` de `auditor1`; pestañas Simulación y Administración ocultas; "Atender" abre el procedimiento sin botón de acuse | inmediato |

### Aclaraciones por paso

- **Paso 4.** CAM-02 conserva su MAC registrada `02:42:70:ba:6a:00`; la nueva MAC dispara
  la sospecha de sustitución.
- **Paso 8.** Con la acometida cortada y la planta fallida, la climatización se apaga y la
  sala se calienta. Si el ensayo debe ser corto, la secuencia completa puede acortarse
  fijando la temperatura en Simulación → Ambiente.
- **Paso 9.** Los tres equipos autorizados que cuelgan de SW-CIRC-B aparecen en un solo
  evento. Si apareciera una caída por equipo, comprobar que CAM-03 y PC-NAVE estén en
  SW-CIRC-B en la topología.
- **Paso 12, restablecer.** Acometida (Simulación → Energía), reparar planta, encender
  SW-CIRC-B, apagar PC-INTRUSO y devolver la MAC de CAM-02:
  `ip link set eth0 down; ip link set eth0 address 02:42:70:ba:6a:00; ip link set eth0 up`.
  Atender con un acuse las alertas críticas que queden pendientes.
- **Paso 15.** El rol auditor no ve las pestañas Simulación ni Administración. Puede abrir
  el procedimiento de una alerta con "Atender", pero la ventana le indica que no puede
  registrar el acuse. Sí puede verificar la cadena y exportar.

## 3. Variantes que conviene ensayar

| Variante | Acción | Evento esperado |
|---|---|---|
| Transferencia fuera de norma | "Arranque lento, 14 s" y luego cortar acometida | `transferencia_fuera_de_tipo` |
| Sensor mudo | Silenciar T-RACK-B | `sensor_mudo` a los 15 s |
| Pérdida de visibilidad | Detener SW-CIRC-A | `perdida_visibilidad`, no cinco caídas |
| Intentos repetidos | Tres PIN incorrectos con C-1002 | `intentos_repetidos` |
| Reautenticación | Esperar 5 minutos y crear un usuario | La plataforma pide la passkey otra vez |

## 4. Cierre

1. `.\scripts\windows\evidencia.ps1 -Desde <id de la línea base> -Csv` guarda todos los eventos del ensayo.
2. Confirmar "Cadena de hash ÍNTEGRA".
3. Exportar también el CSV desde la pestaña Bitácora y anotar el hash del último evento.
4. Completar `REGISTRO_VALIDACION.md` y adjuntar las capturas de pantalla de los pasos 3, 7, 9 y 13.
5. Cualquier paso que no produzca su evento se anota como hallazgo y se corrige antes de la demostración.
