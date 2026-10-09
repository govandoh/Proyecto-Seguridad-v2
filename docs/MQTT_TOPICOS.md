# Contrato de mensajes MQTT

Todos los mensajes son JSON en UTF-8. El broker no admite conexiones anónimas y cada
servicio tiene su usuario con una ACL mínima (`broker/acl`).

| Tópico | Publica | Consume | Contenido |
|---|---|---|---|
| `dc/red/observacion` | sensor-red, cada 1 s | plataforma | `{ts, modo, iface, paquetes, hosts:[{mac, ip}]}` |
| `dc/energia/ups` | sim-ups, cada 1 s | plataforma, sim-ambiente | ver abajo |
| `dc/energia/prueba` | sim-ups | plataforma | `{equipo, tipo:"ejercicio_mensual", duracion_min, t_arranque_s, resultado}` |
| `dc/ambiente/lectura` | sim-ambiente, cada 2 s por sensor | plataforma | `{sensor, temp_c, humedad, clima, ts}` |
| `dc/ambiente/alarma` | sim-ambiente | plataforma | `{humo:"activa"/"normal", supresion:"armada"/"descargada"/"abortada", retardo_s}` |
| `dc/acceso/lectura` | sim-puerta | plataforma | `{lectora, tarjeta, pin, ts}` |
| `dc/acceso/cmd` | plataforma | sim-puerta | `{lectora, accion:"abrir"/"denegar", motivo}` |
| `dc/acceso/puerta` | sim-puerta | plataforma | `{lectora, estado:"abierta"/"cerrada"/"mantenida_abierta", motivo}` |
| `dc/cmd/ups` | plataforma (consola) | sim-ups | `{accion, segundos?, actor}` |
| `dc/cmd/ambiente` | plataforma (consola) | sim-ambiente | `{accion, sensor?, valor?, actor}` |
| `dc/cmd/puerta` | plataforma (consola) | sim-puerta | `{accion, tarjeta?, pin?, actor}` |
| `dc/cmd/red` | plataforma (consola) | sensor-red en modo demo | `{accion, switch?, nombre?, actor}` |

## Telemetría del UPS (`dc/energia/ups`)

```json
{
  "equipo": "UPS-01", "ts": 1790403166.2, "acometida": false, "ats": "planta",
  "ups.status": "OL", "battery.charge": 97.4, "battery.runtime": 4812,
  "ups.load": 37.7, "ups.realpower": 566.2, "input.voltage": 120.0, "output.voltage": 120.0,
  "planta": {"estado": "en_linea", "t_arranque_s": 7.0, "prueba_en_curso": false},
  "evento": {"t_corte": 1790403150.1, "t_en_linea": 1790403157.1},
  "factor_tiempo": 30, "energia_util_wh": 864, "eficiencia": 0.9, "carga_w": 566.2
}
```

`ups.status` sigue la convención de Network UPS Tools: `OL` en línea, `OL CHRG` cargando,
`OB` en batería, `OB LB` batería baja, `OFF` sin salida.

## Comandos admitidos

| Dispositivo | Acciones |
|---|---|
| ups | `corte_acometida`, `retorno_acometida`, `falla_planta`, `reparar_planta`, `prueba_mensual`, `fijar_arranque {segundos}` |
| ambiente | `falla_clima`, `restaurar_clima`, `fijar {sensor, valor}`, `liberar`, `humo`, `abortar_supresion`, `restablecer_humo`, `silenciar {sensor}`, `reactivar {sensor}` |
| puerta | `leer {tarjeta, pin}`, `mantener {tarjeta, pin}`, `forzar` |
| red (solo demo) | `apagar_switch {switch}`, `encender_switch {switch}`, `conectar_intruso`, `desconectar_intruso`, `sustituir {nombre}`, `restaurar` |

La API `POST /api/sim/{dispositivo}` valida la acción contra esta lista antes de publicarla.

## Nota de seguridad

En el laboratorio la lectora envía el PIN por MQTT dentro de la red interna de Docker,
protegida por la ACL. En una instalación real la comunicación lectora-controlador usa
OSDP con canal seguro y el bus MQTT se configura con TLS.
