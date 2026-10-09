"""Procedimientos de respuesta por tipo de evento.

Equivalen a los procedimientos de operación de emergencia (EOP) que un centro de
datos mantiene junto a su tablero: qué hace el operador de turno cuando una
alerta aparece. El tablero los muestra al abrir la alerta y exige acuse.
"""

PROCEDIMIENTOS = {
    "perdida_acometida": {
        "titulo": "Pérdida de acometida eléctrica",
        "norma": "NFPA 110; NFPA 111; ISO/IEC 27001 7.11",
        "pasos": [
            "Confirmar en el panel de Energía que el UPS tomó la carga (estado OB).",
            "Verificar el arranque de la planta y cronometrar la transferencia contra el tipo 10.",
            "Avisar al custodio de la sala y a mantenimiento eléctrico.",
            "Si la planta no entra, preparar la desconexión de cargas no críticas.",
        ],
    },
    "transferencia_fuera_de_tipo": {
        "titulo": "Transferencia a planta fuera del tipo 10",
        "norma": "NFPA 110",
        "pasos": [
            "Registrar el tiempo medido y el estado de la planta.",
            "Abrir una orden de mantenimiento para el arranque y el conmutador de transferencia.",
            "Programar una prueba de verificación después de la corrección.",
        ],
    },
    "falla_planta": {
        "titulo": "Falla de la planta de emergencia",
        "norma": "NFPA 110; ISO/IEC 27001 7.11",
        "pasos": [
            "La carga queda solo en baterías: vigilar la autonomía restante.",
            "Desconectar cargas no críticas según la prioridad del custodio.",
            "Llamar a mantenimiento de la planta.",
            "Preparar el apagado ordenado de SRV-TRAZA si la autonomía baja del umbral.",
        ],
    },
    "bateria_baja": {
        "titulo": "Batería baja del UPS",
        "norma": "NFPA 111; IEEE 1188",
        "pasos": [
            "Desconectar cargas no críticas: cámaras de zonas sin actividad.",
            "Notificar al responsable de trazabilidad el posible apagado.",
            "Iniciar el cierre ordenado de aplicaciones en SRV-TRAZA.",
        ],
    },
    "apagado_controlado": {
        "titulo": "Apagado controlado por autonomía agotada",
        "norma": "ISO/IEC 27001 7.11; ISO 22301",
        "pasos": [
            "Confirmar que SRV-TRAZA cerró sus servicios sin corrupción de datos.",
            "Activar el plan de continuidad del negocio.",
            "Al volver la energía, arrancar en orden: red, almacenamiento, servidor.",
        ],
    },
    "temperatura_critica": {
        "titulo": "Temperatura de entrada sobre el máximo permisible",
        "norma": "ASHRAE TC 9.9; ISO/IEC 27001 7.5",
        "pasos": [
            "Revisar el estado de la climatización y su alimentación eléctrica.",
            "Verificar que las puertas del rack y los paneles ciegos estén en su lugar.",
            "Si la temperatura sigue subiendo, apagar cargas no críticas.",
            "Escalar a mantenimiento de climatización.",
        ],
    },
    "sensor_mudo": {
        "titulo": "Sensor sin lecturas",
        "norma": "ISO/IEC 27001 7.4 y 7.5",
        "pasos": [
            "No confiar en el panel para esa zona hasta restablecer el sensor.",
            "Verificar en sitio la temperatura con un termómetro portátil.",
            "Revisar la alimentación PoE y el cableado del sensor.",
        ],
    },
    "alarma_humo": {
        "titulo": "Alarma de humo por aspiración",
        "norma": "NFPA 72; NFPA 2001; NFPA 75",
        "pasos": [
            "Verificar la alarma con la cámara de la sala.",
            "Si es un falso positivo, abortar la descarga antes de 30 s.",
            "Si es real, evacuar la sala y permitir la descarga del agente limpio.",
            "Avisar a bomberos y al custodio.",
        ],
    },
    "supresion_descargada": {
        "titulo": "Descarga del agente limpio",
        "norma": "NFPA 2001",
        "pasos": [
            "Mantener la sala cerrada durante el tiempo de retención del agente.",
            "No reingresar hasta que el responsable de seguridad lo autorice.",
            "Programar la recarga del sistema de supresión.",
        ],
    },
    "ingreso_bajo_coaccion": {
        "titulo": "Ingreso bajo coacción",
        "norma": "NFPA 731; ISO/IEC 27001 7.2",
        "pasos": [
            "No responder por radio ni teléfono a la persona en la puerta.",
            "Observar la sala por las cámaras sin alertar al atacante.",
            "Notificar a seguridad física y a la policía según el protocolo.",
        ],
    },
    "credencial_revocada_usada": {
        "titulo": "Uso de una credencial revocada",
        "norma": "ISO/IEC 27001 5.18 y 7.2",
        "pasos": [
            "Identificar al titular de la tarjeta y su fecha de baja.",
            "Revisar las cámaras de la puerta en el momento del intento.",
            "Recuperar la tarjeta física y reportar a Talento Humano.",
        ],
    },
    "intentos_repetidos": {
        "titulo": "Intentos de acceso repetidos",
        "norma": "ISO/IEC 27001 7.2; NFPA 731",
        "pasos": [
            "Revisar la cámara de la puerta.",
            "Bloquear temporalmente la tarjeta si el titular no confirma los intentos.",
        ],
    },
    "puerta_forzada": {
        "titulo": "Puerta forzada",
        "norma": "NFPA 731; ISO/IEC 27001 7.2 y 7.4",
        "pasos": [
            "Enviar a seguridad física a la sala de servidores.",
            "Revisar las cámaras y conservar la grabación como evidencia.",
            "Verificar la presencia de todos los equipos del inventario.",
        ],
    },
    "dispositivo_no_autorizado": {
        "titulo": "Equipo no autorizado en la red",
        "norma": "IEEE 802.1X; ISO/IEC 27001 8.20",
        "pasos": [
            "Ubicar la toma por la MAC y el conmutador.",
            "Deshabilitar el puerto si el equipo no está en el inventario.",
            "Si es legítimo, darlo de alta con reautenticación del administrador.",
        ],
    },
    "suplantacion": {
        "titulo": "Posible sustitución de equipo",
        "norma": "IEEE 802.1AR; ISO/IEC 27001 7.2",
        "pasos": [
            "Comparar la MAC observada con la registrada en el inventario.",
            "Inspeccionar físicamente el equipo y su sello.",
            "Aislar el puerto hasta confirmar la identidad del dispositivo.",
        ],
    },
    "cascada_poe": {
        "titulo": "Caída de conmutador con pérdida de PoE",
        "norma": "IEEE 802.3bt; ISO/IEC 27001 7.8 y 7.11",
        "pasos": [
            "Verificar la alimentación del conmutador y su circuito eléctrico.",
            "Asumir que las cámaras y lectoras afectadas están ciegas: vigilancia en sitio.",
            "Restablecer el conmutador y confirmar el retorno de cada equipo.",
        ],
    },
    "perdida_visibilidad": {
        "titulo": "Pérdida de visibilidad de la red",
        "norma": "ISO/IEC 27001 8.16",
        "pasos": [
            "Revisar el conmutador del punto de captura, SW-CIRC-A, y el enlace eth2.",
            "Mientras dure, ningún evento de red es confiable.",
        ],
    },
    "capturador_caido": {
        "titulo": "Capturador de red detenido",
        "norma": "ISO/IEC 27001 8.16",
        "pasos": [
            "Revisar el contenedor sensor-red con docker compose ps y sus registros.",
            "Confirmar que eth2 existe y está en modo promiscuo.",
        ],
    },
    "inundacion_red": {
        "titulo": "Inundación de identidades en la red",
        "norma": "ISO/IEC 27001 8.20",
        "pasos": [
            "Identificar el puerto de origen del tráfico con MAC aleatorias.",
            "Aplicar límite de MAC por puerto o deshabilitar el puerto.",
        ],
    },
    "auth_bloqueo": {
        "titulo": "Cuenta bloqueada por intentos fallidos",
        "norma": "NIST SP 800-63B-4; ISO/IEC 27001 8.5",
        "pasos": [
            "Contactar al titular por un canal distinto para confirmar los intentos.",
            "Si no los reconoce, restablecer su alta y revisar el origen de los intentos.",
        ],
    },
}

GENERICO = {
    "titulo": "Evento crítico",
    "norma": "ISO/IEC 27001 5.24 a 5.26",
    "pasos": ["Analizar el evento, contenerlo y documentar la respuesta."],
}


def para(tipo: str) -> dict:
    return PROCEDIMIENTOS.get(tipo, GENERICO)
