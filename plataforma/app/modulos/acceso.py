"""Módulo de ACCESO FÍSICO a la sala de servidores.

La plataforma actúa como servidor de control de acceso: la lectora (sim-puerta)
envía tarjeta y PIN, aquí se valida y se ordena abrir o no la cerradura.

Reglas de la especificación de autenticación:
  - tarjeta (posesión) + PIN (conocimiento); ninguno abre por separado
  - PIN de coacción: el último dígito incrementado en uno abre la puerta y
    dispara una alerta silenciosa a la central (NFPA 731)
  - credencial revocada: se niega y se alerta (ISO/IEC 27001 5.18)
  - puerta forzada y puerta mantenida abierta los reporta el controlador
"""

import threading
import time
from collections import defaultdict, deque

import bcrypt

from .. import bitacora, config, db
from ..bus import bus
from ..realtime import hub

MODULO = "acceso"
_lock = threading.RLock()
_denegados: dict[str, deque] = defaultdict(deque)
_ultima_apertura_autorizada: dict[str, float] = {}
_puertas: dict[str, dict] = {}
_recientes: deque = deque(maxlen=50)


def pin_coaccion(pin: str) -> str:
    return pin[:-1] + str((int(pin[-1]) + 1) % 10)


def _pin_bajo_coaccion(pin_ingresado: str, pin_hash: bytes) -> bool:
    """El PIN de coacción es el PIN real con el último dígito + 1; se deshace el cambio y se verifica."""
    if not pin_ingresado or not pin_ingresado[-1].isdigit():
        return False
    original = pin_ingresado[:-1] + str((int(pin_ingresado[-1]) - 1) % 10)
    return bcrypt.checkpw(original.encode(), pin_hash)


def _responder(lectora: str, abrir: bool, motivo: str):
    bus.publicar("dc/acceso/cmd", {"lectora": lectora, "accion": "abrir" if abrir else "denegar", "motivo": motivo})
    if abrir:
        _ultima_apertura_autorizada[lectora] = time.time()


def procesar_lectura(_topico: str, d: dict):
    lectora = str(d.get("lectora", "LECT-01"))[:24]
    tarjeta = str(d.get("tarjeta", ""))[:32]
    pin = str(d.get("pin", ""))[:12]
    with _lock:
        t = db.uno("SELECT * FROM tarjetas WHERE tarjeta = ?", (tarjeta,))
        if not t:
            _registrar_denegado(lectora, tarjeta, "tarjeta desconocida")
            _responder(lectora, False, "tarjeta_desconocida")
            return
        titular = t["titular"]
        if t["estado"] == "revocada":
            bitacora.registrar(MODULO, "credencial_revocada_usada", "critico",
                               f"Intento con la tarjeta revocada {tarjeta} de {titular} en {lectora}",
                               "5.18; 7.2", "NFPA 731", datos={"tarjeta": tarjeta, "lectora": lectora})
            _nota(lectora, tarjeta, titular, "revocada")
            _responder(lectora, False, "revocada")
            return
        h = t["pin_hash"].encode()
        if pin and bcrypt.checkpw(pin.encode(), h):
            bitacora.registrar(MODULO, "ingreso_autorizado", "informativo",
                               f"Ingreso autorizado de {titular} con tarjeta {tarjeta} y PIN en {lectora}",
                               "7.2", "NFPA 731", datos={"tarjeta": tarjeta, "lectora": lectora})
            _denegados[tarjeta].clear()
            _nota(lectora, tarjeta, titular, "autorizado")
            _responder(lectora, True, "valido")
            return
        if pin and _pin_bajo_coaccion(pin, h):
            # La puerta abre como si nada; la alerta es silenciosa para quien está frente a la lectora.
            bitacora.registrar(MODULO, "ingreso_bajo_coaccion", "critico",
                               f"PIN de coacción de {titular} ({tarjeta}) en {lectora}: la puerta se abrió y se alertó en silencio",
                               "7.2", "NFPA 731", datos={"tarjeta": tarjeta, "lectora": lectora, "silenciosa": True})
            _nota(lectora, tarjeta, titular, "coaccion")
            _responder(lectora, True, "valido")
            return
        _registrar_denegado(lectora, tarjeta, "PIN incorrecto", titular)
        _responder(lectora, False, "pin_incorrecto")


def _registrar_denegado(lectora, tarjeta, motivo, titular=None):
    ahora = time.time()
    q = _denegados[tarjeta]
    q.append(ahora)
    while q and ahora - q[0] > 300:
        q.popleft()
    bitacora.registrar(MODULO, "ingreso_denegado", "advertencia",
                       f"Ingreso denegado en {lectora}: {motivo} (tarjeta {tarjeta or 'sin dato'})",
                       "7.2", "NFPA 731", datos={"tarjeta": tarjeta, "lectora": lectora, "motivo": motivo})
    _nota(lectora, tarjeta, titular or "?", "denegado")
    if len(q) == config.DENEGADOS_MAX:
        bitacora.registrar(MODULO, "intentos_repetidos", "critico",
                           f"{config.DENEGADOS_MAX} intentos denegados en 5 min con la tarjeta {tarjeta} en {lectora}",
                           "7.2", "NFPA 731", datos={"tarjeta": tarjeta, "lectora": lectora})


def _nota(lectora, tarjeta, titular, resultado):
    item = {"ts": time.time(), "lectora": lectora, "tarjeta": tarjeta, "titular": titular, "resultado": resultado}
    _recientes.appendleft(item)
    hub.publicar("acceso_lectura", item)


def procesar_puerta(_topico: str, d: dict):
    lectora = str(d.get("lectora", "LECT-01"))[:24]
    estado = d.get("estado")
    motivo = d.get("motivo", "")
    with _lock:
        _puertas[lectora] = {"estado": estado, "motivo": motivo, "ts": time.time()}
        if estado == "abierta":
            autorizada = time.time() - _ultima_apertura_autorizada.get(lectora, 0) < 10
            if motivo == "forzada" or not autorizada:
                bitacora.registrar(MODULO, "puerta_forzada", "critico",
                                   f"La puerta de {lectora} se abrió sin un acceso válido previo", "7.2; 7.4", "NFPA 731",
                                   datos={"lectora": lectora})
        elif estado == "mantenida_abierta":
            bitacora.registrar(MODULO, "puerta_mantenida_abierta", "advertencia",
                               f"La puerta de {lectora} lleva más de {config.PUERTA_ABIERTA_MAX_S:.0f} s abierta",
                               "7.2; 7.4", "NFPA 731", datos={"lectora": lectora})
    hub.publicar("acceso_puerta", {"lectora": lectora, "estado": estado, "motivo": motivo})


def estado() -> dict:
    with _lock:
        return {"puertas": {k: dict(v) for k, v in _puertas.items()}, "recientes": list(_recientes)[:20],
                "tarjetas": db.consultar("SELECT tarjeta, titular, estado, zonas FROM tarjetas ORDER BY tarjeta")}
