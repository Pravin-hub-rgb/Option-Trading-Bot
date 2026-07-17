import asyncio
import json
import logging

logger = logging.getLogger(__name__)

class LiveFeedServer:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.server = None
        self._loop = None

    async def handler(self, websocket):
        self.clients.add(websocket)
        try:
            async for _ in websocket:
                pass
        except Exception:
            pass
        finally:
            self.clients.discard(websocket)

    async def start(self):
        import websockets
        self._loop = asyncio.get_running_loop()
        self.server = await websockets.serve(self.handler, self.host, self.port)
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
        await self.server.wait_closed()

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def broadcast(self, message):
        if not self.clients:
            return
        data = json.dumps(message, default=str)
        dead = set()
        for ws in self.clients:
            try:
                await ws.send(data)
            except Exception:
                dead.add(ws)
        self.clients -= dead

    def broadcast_sync(self, message):
        if not self._loop or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)
