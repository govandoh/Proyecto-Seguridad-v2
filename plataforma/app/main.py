"""Plataforma de Monitoreo y Ciberresiliencia del Datacenter - Operador Postal Designado.

Arranque:  uvicorn app.main:app --host 0.0.0.0 --port 8000
En producción se sirve detrás de Caddy (HTTPS con CA local), requisito de WebAuthn.
"""

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import api, bitacora, config, db, seed
from .auth import rutas as auth_rutas
from .auth import seguridad
from .auth.dependencias import COOKIE
from .bus import bus
from .modulos import acceso, ambiente, energia, red
from .realtime import hub

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("plataforma")


def _evaluador(detener: threading.Event):
    """Revisa cada segundo los temporizadores de los módulos."""
    ultimo_red = ultimo_estado = 0.0
    while not detener.is_set():
        ahora = time.time()
        try:
            if ahora - ultimo_red >= config.INTERVALO_REVISION_S:
                ultimo_red = ahora
                red.revisar()
            ambiente.revisar()
            energia.revisar()
            if ahora - ultimo_estado >= 2:
                ultimo_estado = ahora
                red.publicar_estado()
                hub.publicar("energia", energia.estado())
        except Exception:
            log.exception("error en el evaluador")
        detener.wait(1)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    db.init_db()
    seed.sembrar()
    red.recargar_inventario()
    hub.vincular(asyncio.get_running_loop())
    bus.suscribir("dc/red/observacion", red.procesar_observacion)
    bus.suscribir("dc/energia/ups", energia.procesar_ups)
    bus.suscribir("dc/energia/prueba", energia.procesar_prueba)
    bus.suscribir("dc/ambiente/lectura", ambiente.procesar_lectura)
    bus.suscribir("dc/ambiente/alarma", ambiente.procesar_alarma)
    bus.suscribir("dc/acceso/lectura", acceso.procesar_lectura)
    bus.suscribir("dc/acceso/puerta", acceso.procesar_puerta)
    bus.iniciar()
    detener = threading.Event()
    threading.Thread(target=_evaluador, args=(detener,), daemon=True, name="evaluador").start()
    bitacora.registrar("sistema", "plataforma_iniciada", "informativo",
                       f"Plataforma iniciada; RP_ID={config.RP_ID}", "8.16", "")
    yield
    detener.set()
    bus.detener()


app = FastAPI(title="Plataforma DCIM - Operador Postal", version="2.0.0", lifespan=ciclo_de_vida,
              docs_url="/api/docs" if config.API_DOCS else None, redoc_url=None,
              openapi_url="/api/openapi.json" if config.API_DOCS else None)

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def seguridad_http(request: Request, call_next):
    # Defensa contra falsificación de solicitudes (V3): cabecera propia + origen permitido.
    if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
        origen = request.headers.get("origin")
        if request.headers.get("x-plataforma") != "1" or (origen and origen not in config.ORIGENES):
            return JSONResponse({"detail": "Solicitud rechazada por la protección CSRF"}, status_code=403)
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), publickey-credentials-get=(self), publickey-credentials-create=(self)"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


app.include_router(auth_rutas.router)
app.include_router(api.router)
app.include_router(api.admin)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


def _pagina(nombre: str):
    return FileResponse(config.STATIC_DIR / nombre, headers={"Cache-Control": "no-store"})


@app.get("/", include_in_schema=False)
def raiz(request: Request):
    s = seguridad.obtener_sesion(request.cookies.get(COOKIE))
    return RedirectResponse("/app" if s and s["etapa"] == "completa" else "/login")


@app.get("/login", include_in_schema=False)
def pagina_login():
    return _pagina("login.html")


@app.get("/alta", include_in_schema=False)
def pagina_alta():
    return _pagina("alta.html")


@app.get("/app", include_in_schema=False)
def pagina_app(request: Request):
    s = seguridad.obtener_sesion(request.cookies.get(COOKIE))
    if not s or s["etapa"] != "completa":
        return RedirectResponse("/login")
    return _pagina("app.html")


@app.get("/salud", include_in_schema=False)
def salud():
    return {"estado": "ok", "mqtt": bus.conectado.is_set()}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    s = seguridad.obtener_sesion(websocket.cookies.get(COOKIE), tocar=False)
    origen = websocket.headers.get("origin")
    if not s or s["etapa"] != "completa" or (origen and origen not in config.ORIGENES):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    await hub.conectar(websocket)
    try:
        while True:
            # El cliente envía un latido; se aprovecha para validar que la sesión sigue vigente.
            await websocket.receive_text()
            if not seguridad.obtener_sesion(websocket.cookies.get(COOKIE), tocar=False):
                await websocket.close(code=4401)
                break
    except WebSocketDisconnect:
        pass
    finally:
        hub.desconectar(websocket)
