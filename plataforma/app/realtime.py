"""Difusión en tiempo real hacia el tablero por WebSocket.

Los módulos corren en hilos (callbacks de MQTT y evaluadores periódicos); el
hub reenvía cada mensaje al bucle de asyncio de FastAPI de forma segura.
"""

import asyncio
import json
import logging

log = logging.getLogger("realtime")


class Hub:
    def __init__(self):
        self.clientes = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def vincular(self, loop):
        self.loop = loop

    async def conectar(self, ws):
        self.clientes.add(ws)

    def desconectar(self, ws):
        self.clientes.discard(ws)

    async def _difundir(self, texto: str):
        muertos = []
        for ws in list(self.clientes):
            try:
                await ws.send_text(texto)
            except Exception:
                muertos.append(ws)
        for ws in muertos:
            self.clientes.discard(ws)

    def publicar(self, tipo: str, datos):
        """Seguro para llamar desde cualquier hilo."""
        if not self.loop or not self.clientes:
            return
        texto = json.dumps({"tipo": tipo, "datos": datos}, ensure_ascii=False, default=str)
        try:
            asyncio.run_coroutine_threadsafe(self._difundir(texto), self.loop)
        except RuntimeError:
            log.debug("bucle cerrado, mensaje descartado")


hub = Hub()
