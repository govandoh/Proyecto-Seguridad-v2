"""Prueba de punta a punta con Chromium y un autenticador WebAuthn virtual.

El autenticador virtual del protocolo DevTools simula una passkey con verificación
de usuario (la "biometría" del dispositivo), igual que el panel WebAuthn de Chrome.

Uso:  python3 scripts/prueba_e2e.py [URL] [CODIGO_ALTA] [carpeta_capturas]
Requiere: pip install playwright  (y un Chromium instalado para Playwright)
"""

import sys
import time

from playwright.sync_api import expect, sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CODIGO = sys.argv[2] if len(sys.argv) > 2 else "ABCD-EFGH-JKLM"
CAPTURAS = sys.argv[3] if len(sys.argv) > 3 else "capturas"
PASSWORD = "frase larga de prueba del laboratorio"
errores = []


def paso(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sim(page, dispositivo, cuerpo):
    r = page.request.post(f"{URL}/api/sim/{dispositivo}", data=cuerpo, headers={"X-Plataforma": "1"})
    assert r.ok, r.text()


with sync_playwright() as p:
    import os
    os.makedirs(CAPTURAS, exist_ok=True)
    nav = p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 1440, "height": 900}, locale="es-GT")
    page = ctx.new_page()
    page.on("console", lambda m: m.type in ("error", "warning") and errores.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
    cdp = ctx.new_cdp_session(page)
    cdp.send("WebAuthn.enable")
    cdp.send("WebAuthn.addVirtualAuthenticator", {"options": {
        "protocol": "ctap2", "transport": "internal", "hasResidentKey": True,
        "hasUserVerification": True, "isUserVerified": True, "automaticPresenceSimulation": True}})

    paso("Alta del administrador con código de un solo uso")
    page.goto(f"{URL}/alta")
    page.fill("#usuario", "admin")
    page.fill("#codigo", CODIGO)
    page.fill("#password", PASSWORD)
    page.fill("#password2", PASSWORD)
    page.click("#f-alta button[type=submit]")
    expect(page.locator("#f-passkey")).to_be_visible()
    page.fill("#nombre", "Teléfono virtual")
    page.screenshot(path=f"{CAPTURAS}/01_alta_passkey.png")
    page.click("#f-passkey button[type=submit]")
    page.wait_for_url("**/app#resumen", timeout=10000)
    paso("Alta completa, tablero cargado")
    page.wait_for_timeout(3000)
    page.screenshot(path=f"{CAPTURAS}/02_resumen.png", full_page=True)

    paso("Cierre de sesión y nuevo ingreso con contraseña + passkey")
    page.click("#salir")
    page.wait_for_url("**/login")
    page.fill("#usuario", "admin")
    page.fill("#password", "incorrecta-del-todo")
    page.click("#f-pass button[type=submit]")
    expect(page.locator("#error")).to_contain_text("incorrectos")
    page.fill("#password", PASSWORD)
    page.click("#f-pass button[type=submit]")
    page.wait_for_url("**/app*", timeout=10000)
    paso("Ingreso con dos factores correcto")

    paso("Escenario: corte de energía, temperatura, coacción, intruso y cascada PoE")
    sim(page, "ups", {"accion": "corte_acometida"})
    sim(page, "ambiente", {"accion": "fijar", "sensor": "T-RACK-A", "valor": 34})
    sim(page, "puerta", {"accion": "leer", "tarjeta": "C-1001", "pin": "1358"})
    sim(page, "puerta", {"accion": "leer", "tarjeta": "C-1003", "pin": "1111"})
    sim(page, "red", {"accion": "conectar_intruso"})
    sim(page, "red", {"accion": "sustituir", "nombre": "CAM-02"})
    sim(page, "red", {"accion": "apagar_switch", "switch": "SW-CIRC-B"})
    page.wait_for_timeout(16000)
    for tab in ["resumen", "red", "energia", "ambiente", "accesos", "bitacora", "indicadores", "simulacion", "admin"]:
        page.click(f".pestanas button[data-tab={tab}]")
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{CAPTURAS}/03_{tab}.png", full_page=True)
        paso(f"captura de {tab}")

    paso("Acuse de una alerta con su procedimiento")
    page.click(".pestanas button[data-tab=resumen]")
    page.wait_for_timeout(800)
    page.locator(".alerta button").first.click()
    expect(page.locator(".modal")).to_be_visible()
    page.screenshot(path=f"{CAPTURAS}/04_procedimiento.png")
    page.fill(".modal input", "Verificado en cámara; se avisó a mantenimiento")
    page.click(".modal .boton.primario")
    page.wait_for_timeout(1000)

    paso("Administración: alta de un operador con código")
    page.click(".pestanas button[data-tab=admin]")
    page.wait_for_timeout(800)
    page.fill("input[aria-label=Usuario]", "operador1")
    page.fill("input[aria-label=Nombre]", "Operador de turno")
    page.locator("button", has_text="Crear y emitir código de alta").click()
    expect(page.locator(".codigo-alta")).to_be_visible(timeout=10000)
    page.screenshot(path=f"{CAPTURAS}/05_codigo_alta.png", full_page=True)

    paso("Verificación de la cadena de hash")
    page.click(".pestanas button[data-tab=bitacora]")
    page.locator("button", has_text="Verificar cadena").click()
    expect(page.locator("#v-bitacora .estado.ok")).to_be_visible(timeout=5000)

    sim(page, "ups", {"accion": "retorno_acometida"})
    sim(page, "red", {"accion": "restaurar"})
    sim(page, "ambiente", {"accion": "liberar"})
    nav.close()

print("\nErrores o advertencias de consola:", len(errores))
for e in errores:
    print("  ", e)
print("PRUEBA E2E COMPLETA")
