"""Módulo de RED.

El contenedor sensor-red captura el tráfico de eth2 y publica cada segundo qué
pares MAC/IP vio. Aquí se clasifica cada equipo contra el inventario autorizado
(esquema permisivo: se prohíbe todo y se permite solo lo inventariado) y se
detectan conexiones no autorizadas, sustituciones, desconexiones, cascadas PoE,
pérdida de visibilidad y caída del propio capturador.

Correcciones respecto de la versión 1 (hallazgos del Entregable 2):
  V8  la MAC queda registrada en el inventario, la sustitución se detecta tras reiniciar
  V9  los eventos de equipos no autorizados tienen límite de frecuencia
  V10 las entradas se validan con ipaddress y expresiones regulares
  y la regla de cascada acepta conmutadores de un equipo y distingue la pérdida total de visibilidad.
"""

import ipaddress
import re
import threading
import time

from .. import bitacora, config, db
from ..realtime import hub

MODULO = "red"
TIPOS = ("servidor", "camara", "lectora", "sensor", "otro")
SWITCHES = ("SW-CIRC-A", "SW-CIRC-B")
RE_MAC = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")
RE_NOMBRE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,23}$")
IGNORAR = {"0.0.0.0", "10.10.10.1", "255.255.255.255"}

_lock = threading.RLock()
_inventario: dict[str, dict] = {}
_hosts: dict[str, dict] = {}          # mac -> host
_suplantaciones_avisadas: set[tuple[str, str]] = set()
_no_aut_ventana: list[float] = []
_no_aut_suprimidos = 0
_captura = {"ultima": 0.0, "modo": "desconocido", "iface": "", "paquetes": 0, "caido_avisado": False,
            "error": None, "error_avisado": False}
_visibilidad = {"perdida": False}


# ------------------------------------------------------------------ inventario
def recargar_inventario():
    global _inventario
    with _lock:
        _inventario = {f["ip"]: f for f in db.consultar("SELECT * FROM inventario")}


def inventario_listar() -> list[dict]:
    return db.consultar("SELECT * FROM inventario ORDER BY switch, nombre")


def validar_equipo(ip: str, nombre: str, tipo: str, switch: str, mac: str | None) -> dict:
    try:
        ip_ok = str(ipaddress.IPv4Address(ip.strip()))
    except ValueError:
        raise ValueError("IP inválida")
    nombre = nombre.strip().upper()
    if not RE_NOMBRE.match(nombre):
        raise ValueError("Nombre inválido: use mayúsculas, dígitos y guiones, de 2 a 24 caracteres")
    if tipo not in TIPOS:
        raise ValueError("Tipo inválido")
    if switch not in SWITCHES:
        raise ValueError("Conmutador inválido")
    mac_ok = None
    if mac:
        mac_ok = mac.strip().lower().replace("-", ":")
        if not RE_MAC.match(mac_ok):
            raise ValueError("MAC inválida")
    return {"ip": ip_ok, "nombre": nombre, "tipo": tipo, "switch": switch, "mac": mac_ok,
            "poe": 1 if tipo in ("camara", "lectora", "sensor") else 0}


def inventario_agregar(equipo: dict, actor: str):
    with db.transaccion() as con:
        con.execute("""INSERT INTO inventario (ip, nombre, tipo, switch, mac, poe)
                       VALUES (:ip,:nombre,:tipo,:switch,:mac,:poe)
                       ON CONFLICT(ip) DO UPDATE SET nombre=excluded.nombre, tipo=excluded.tipo,
                       switch=excluded.switch, mac=excluded.mac, poe=excluded.poe""", equipo)
    recargar_inventario()
    with _lock:
        for h in _hosts.values():
            if h["ip"] == equipo["ip"]:
                h["avisado_no_aut"] = False
    bitacora.registrar(MODULO, "inventario_alta", "informativo",
                       f"Equipo agregado o actualizado en el inventario autorizado: {equipo['nombre']} ({equipo['ip']})",
                       "5.16", "IEEE 802.1AR", actor=actor, datos=equipo)


def inventario_eliminar(ip: str, actor: str):
    with _lock:
        d = _inventario.get(ip)
    if not d:
        raise ValueError("La IP no está en el inventario")
    with db.transaccion() as con:
        con.execute("DELETE FROM inventario WHERE ip = ?", (ip,))
    recargar_inventario()
    with _lock:
        for mac in [m for m, h in _hosts.items() if h["ip"] == ip]:
            _hosts.pop(mac, None)
    bitacora.registrar(MODULO, "inventario_baja", "advertencia",
                       f"Equipo retirado del inventario: {d['nombre']} ({ip}); si sigue emitiendo se tratará como no autorizado",
                       "5.16", "IEEE 802.1AR", actor=actor, datos=d)


# ------------------------------------------------------------------ observaciones
def procesar_observacion(_topico: str, datos: dict):
    ahora = time.time()
    with _lock:
        if _captura["caido_avisado"]:
            _captura["caido_avisado"] = False
            bitacora.registrar(MODULO, "capturador_restablecido", "informativo",
                               "El capturador de red volvió a publicar observaciones", "8.16", "")
        error = datos.get("error")
        _captura.update(ultima=ahora, modo=str(datos.get("modo", "captura"))[:20],
                        iface=str(datos.get("iface", ""))[:20], paquetes=int(datos.get("paquetes", 0) or 0),
                        error=str(error)[:120] if error else None)
        if error and not _captura["error_avisado"]:
            _captura["error_avisado"] = True
            bitacora.registrar(MODULO, "capturador_caido", "critico",
                               f"El capturador no puede leer {_captura['iface']}: {str(error)[:120]}", "8.16", "")
        elif not error and _captura["error_avisado"]:
            _captura["error_avisado"] = False
    hosts = datos.get("hosts") or []
    if not isinstance(hosts, list):
        return
    for h in hosts[:256]:
        if isinstance(h, dict):
            _ver_host(str(h.get("mac", "")).lower(), str(h.get("ip", "")), ahora)


def _ver_host(mac: str, ip: str, ahora: float):
    if not RE_MAC.match(mac) or ip in IGNORAR:
        return
    try:
        ipaddress.IPv4Address(ip)
    except ValueError:
        return
    with _lock:
        inv = _inventario.get(ip)
        if _visibilidad["perdida"]:
            _visibilidad["perdida"] = False
            bitacora.registrar(MODULO, "visibilidad_restablecida", "informativo",
                               "La plataforma vuelve a ver tráfico de los equipos", "8.16", "")
        # Identidad: MAC registrada en el inventario (V8) o primer uso confiable.
        if inv:
            if inv.get("mac") and inv["mac"] != mac:
                clave = (ip, mac)
                if clave not in _suplantaciones_avisadas:
                    _suplantaciones_avisadas.add(clave)
                    bitacora.registrar(MODULO, "suplantacion", "critico",
                                       f"{inv['nombre']} ({ip}) aparece con la MAC {mac}; la registrada es {inv['mac']}. Posible sustitución de equipo",
                                       "7.2", "IEEE 802.1AR", datos={"ip": ip, "mac_observada": mac, "mac_registrada": inv["mac"]})
            elif not inv.get("mac"):
                with db.transaccion() as con:
                    con.execute("UPDATE inventario SET mac = ? WHERE ip = ? AND mac IS NULL", (mac, ip))
                inv["mac"] = mac
                bitacora.registrar(MODULO, "mac_registrada", "informativo",
                                   f"Se registró la MAC {mac} de {inv['nombre']} ({ip}) por primer uso",
                                   "5.16", "IEEE 802.1AR", datos={"ip": ip, "mac": mac})

        h = _hosts.get(mac)
        if h is None:
            h = {"mac": mac, "ip": ip, "primera": ahora, "ultima": ahora, "estado": "en_linea", "avisado_no_aut": False}
            _hosts[mac] = h
            if inv:
                bitacora.registrar(MODULO, "dispositivo_conectado", "informativo",
                                   f"Equipo conectado: {inv['nombre']} ({ip}, {mac})", "7.2", "IEEE 802.1X",
                                   datos={"ip": ip, "mac": mac, "switch": inv["switch"]})
        else:
            h["ultima"] = ahora
            h["ip"] = ip
            if h["estado"] == "caido":
                h["estado"] = "en_linea"
                nombre = inv["nombre"] if inv else f"equipo no autorizado {ip}"
                bitacora.registrar(MODULO, "dispositivo_reconectado", "informativo",
                                   f"{nombre} ({ip}, {mac}) volvió a la red", "7.8", "IEEE 802.3bt",
                                   datos={"ip": ip, "mac": mac})
        if not inv and not h["avisado_no_aut"]:
            h["avisado_no_aut"] = True
            _avisar_no_autorizado(ip, mac, ahora)


def _avisar_no_autorizado(ip: str, mac: str, ahora: float):
    """Límite de frecuencia (V9): un atacante con MAC aleatorias no inunda la bitácora."""
    global _no_aut_suprimidos
    _no_aut_ventana[:] = [t for t in _no_aut_ventana if ahora - t < 60]
    if len(_no_aut_ventana) < config.MAX_NO_AUTORIZADOS_MIN:
        _no_aut_ventana.append(ahora)
        bitacora.registrar(MODULO, "dispositivo_no_autorizado", "critico",
                           f"Equipo NO autorizado conectado a la red: {ip}, {mac}", "8.20", "IEEE 802.1X",
                           datos={"ip": ip, "mac": mac})
    else:
        _no_aut_suprimidos += 1
        if _no_aut_suprimidos == 1:
            bitacora.registrar(MODULO, "inundacion_red", "critico",
                               f"Más de {config.MAX_NO_AUTORIZADOS_MIN} identidades no autorizadas en un minuto; los avisos individuales se agrupan",
                               "8.20", "IEEE 802.1X")


# ------------------------------------------------------------------ evaluación periódica
def revisar():
    global _no_aut_suprimidos
    ahora = time.time()
    with _lock:
        if _captura["ultima"] and ahora - _captura["ultima"] > config.CAPTURADOR_TIMEOUT_S and not _captura["caido_avisado"]:
            _captura["caido_avisado"] = True
            bitacora.registrar(MODULO, "capturador_caido", "critico",
                               f"El capturador de red no publica desde hace más de {config.CAPTURADOR_TIMEOUT_S:.0f} s",
                               "8.16", "")
            return
        if _captura["caido_avisado"]:
            return
        if _no_aut_suprimidos and not [t for t in _no_aut_ventana if ahora - t < 60]:
            _no_aut_suprimidos = 0

        activos = [h for h in _hosts.values() if h["estado"] == "en_linea"]
        caidos = [h for h in activos if ahora - h["ultima"] > config.UMBRAL_DESCONEXION_S]
        if not caidos:
            return
        for h in caidos:
            h["estado"] = "caido"

        autorizados_activos = [h for h in activos if h["ip"] in _inventario]
        autorizados_caidos = [h for h in caidos if h["ip"] in _inventario]

        # Todos los autorizados callan a la vez: se perdió el punto de captura, no los equipos.
        if len(autorizados_activos) >= 2 and len(autorizados_caidos) == len(autorizados_activos):
            _visibilidad["perdida"] = True
            bitacora.registrar(MODULO, "perdida_visibilidad", "critico",
                               "Todos los equipos dejaron de emitir al mismo tiempo: probable caída de SW-CIRC-A o del enlace de captura. Los eventos de red no son confiables hasta restablecerla",
                               "8.16", "IEEE 802.3bt", datos={"equipos": [_inventario[h["ip"]]["nombre"] for h in autorizados_caidos]})
            return

        por_switch: dict[str, list] = {}
        for h in autorizados_caidos:
            por_switch.setdefault(_inventario[h["ip"]]["switch"], []).append(h)
        for sw, lista in por_switch.items():
            vistos_en_sw = [h for h in autorizados_activos if _inventario[h["ip"]]["switch"] == sw]
            nombres = [_inventario[h["ip"]]["nombre"] for h in lista]
            latencia = round(max(ahora - h["ultima"] for h in lista), 1)
            if len(lista) == len(vistos_en_sw) and len(lista) >= 2:
                bitacora.registrar(MODULO, "cascada_poe", "critico",
                                   f"Caída del conmutador {sw}: quedaron sin PoE {', '.join(nombres)}",
                                   "7.8; 7.11", "IEEE 802.3bt",
                                   datos={"switch": sw, "equipos": nombres, "latencia_deteccion_s": latencia})
                continue
            for h in lista:
                inv = _inventario[h["ip"]]
                unico = len(vistos_en_sw) == 1
                sev = "critico" if inv["poe"] else "advertencia"
                detalle = (f"; es el único equipo visto en {sw}, no se distingue la caída del equipo de la del conmutador"
                           if unico else "")
                bitacora.registrar(MODULO, "dispositivo_desconectado", sev,
                                   f"{inv['nombre']} ({h['ip']}) dejó de emitir{detalle}",
                                   "7.8", "IEEE 802.3bt",
                                   datos={"ip": h["ip"], "mac": h["mac"], "switch": sw, "latencia_deteccion_s": round(ahora - h["ultima"], 1)})

        for h in caidos:
            if h["ip"] not in _inventario:
                bitacora.registrar(MODULO, "dispositivo_desconectado", "informativo",
                                   f"El equipo no autorizado {h['ip']} ({h['mac']}) dejó de emitir", "8.20", "IEEE 802.1X")


# ------------------------------------------------------------------ estado para el tablero
def estado() -> dict:
    ahora = time.time()
    salida, vistas = [], set()
    with _lock:
        for h in _hosts.values():
            inv = _inventario.get(h["ip"])
            vistas.add(h["ip"])
            salida.append({
                "mac": h["mac"], "ip": h["ip"], "nombre": inv["nombre"] if inv else "DESCONOCIDO",
                "tipo": inv["tipo"] if inv else "desconocido", "switch": inv["switch"] if inv else "?",
                "autorizado": bool(inv), "estado": h["estado"], "visto_hace_s": round(ahora - h["ultima"], 1),
                "mac_registrada": inv.get("mac") if inv else None,
            })
        for ip, d in _inventario.items():
            if ip not in vistas:
                salida.append({"mac": d.get("mac"), "ip": ip, "nombre": d["nombre"], "tipo": d["tipo"],
                               "switch": d["switch"], "autorizado": True, "estado": "sin_trafico",
                               "visto_hace_s": None, "mac_registrada": d.get("mac")})
        captura = dict(_captura)
    salida.sort(key=lambda x: (x["autorizado"], x["switch"], x["nombre"]))
    edad = round(ahora - captura["ultima"], 1) if captura["ultima"] else None
    return {
        "equipos": salida,
        "captura": {"modo": captura["modo"], "iface": captura["iface"], "paquetes": captura["paquetes"],
                    "edad_s": edad, "error": captura["error"],
                    "activa": edad is not None and edad <= config.CAPTURADOR_TIMEOUT_S and not captura["error"]},
        "visibilidad_perdida": _visibilidad["perdida"],
    }


def publicar_estado():
    hub.publicar("red", estado())
