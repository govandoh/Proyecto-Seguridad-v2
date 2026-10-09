"""Configuración central, tomada de variables de entorno (ver .env.example)."""

import os
from pathlib import Path


def _bool(nombre: str, defecto: bool) -> bool:
    v = os.getenv(nombre)
    if v is None:
        return defecto
    return v.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


def _float(nombre: str, defecto: float) -> float:
    try:
        return float(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = Path(os.getenv("DATOS_DIR", BASE_DIR / "datos"))
DATOS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("DB_PATH", DATOS_DIR / "plataforma.db"))
STATIC_DIR = BASE_DIR / "static"

# --- Bus MQTT
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "plataforma")
MQTT_PASS = os.getenv("MQTT_PASS", "")

# --- WebAuthn / sesiones
RP_ID = os.getenv("RP_ID", "plataforma.test")
RP_NAME = os.getenv("RP_NAME", "Plataforma DCIM - Operador Postal")
ORIGENES = [o.strip() for o in os.getenv("ORIGENES", f"https://{RP_ID}").split(",") if o.strip()]
COOKIE_SECURE = _bool("COOKIE_SECURE", True)
SESION_INACTIVIDAD_MIN = int(os.getenv("SESION_INACTIVIDAD_MIN", "15"))
REAUTH_MIN = _float("REAUTH_MIN", 5)
MAX_INTENTOS = int(os.getenv("MAX_INTENTOS", "5"))
BLOQUEO_MIN = int(os.getenv("BLOQUEO_MIN", "15"))
CODIGO_ALTA_HORAS = int(os.getenv("CODIGO_ALTA_HORAS", "24"))
ADMIN_USUARIO = os.getenv("ADMIN_USUARIO", "admin")
ADMIN_CODIGO_ALTA = os.getenv("ADMIN_CODIGO_ALTA", "")  # vacío = se genera y se imprime en el log
API_DOCS = _bool("API_DOCS", False)

# --- Red
UMBRAL_DESCONEXION_S = _float("UMBRAL_DESCONEXION_S", 8)
INTERVALO_REVISION_S = _float("INTERVALO_REVISION_S", 3)
CAPTURADOR_TIMEOUT_S = _float("CAPTURADOR_TIMEOUT_S", 10)
MAX_NO_AUTORIZADOS_MIN = int(os.getenv("MAX_NO_AUTORIZADOS_MIN", "10"))

# --- Ambiente (ASHRAE TC 9.9, clase A1, temperatura de entrada de aire)
TEMP_MIN_RECOMENDADA = _float("TEMP_MIN_RECOMENDADA", 18)
TEMP_MAX_RECOMENDADA = _float("TEMP_MAX_RECOMENDADA", 27)
TEMP_MAX_PERMISIBLE = _float("TEMP_MAX_PERMISIBLE", 32)
HISTERESIS_C = _float("HISTERESIS_C", 0.5)
SENSOR_TIMEOUT_S = _float("SENSOR_TIMEOUT_S", 15)

# --- Energía (NFPA 110 / NFPA 111 / IEEE 1188)
ENERGIA_UTIL_WH = _float("ENERGIA_UTIL_WH", 864)
EFICIENCIA_INVERSOR = _float("EFICIENCIA_INVERSOR", 0.90)
BATERIA_BAJA_PCT = _float("BATERIA_BAJA_PCT", 25)
NFPA110_TIPO_S = _float("NFPA110_TIPO_S", 10)
UPS_TIMEOUT_S = _float("UPS_TIMEOUT_S", 10)

# --- Acceso físico
PUERTA_ABIERTA_MAX_S = _float("PUERTA_ABIERTA_MAX_S", 30)
DENEGADOS_MAX = int(os.getenv("DENEGADOS_MAX", "3"))
