import asyncio
import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

from settings_db import get_settings_meta, save_setting, reset_settings, load_settings
from trade_log_reader import load_all_trades, load_trade_pnl, load_trade_stats
from bot_manager import BotManager

logger = logging.getLogger(__name__)

def create_app(bot_manager):
    app = FastAPI(title="Options Trading Bot API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3002", "http://127.0.0.1:3002"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/status")
    async def get_status():
        return bot_manager.get_status()

    class StartBody(BaseModel):
        instruments: list[str] | None = None

    @app.post("/api/start")
    async def start_bot(body: StartBody):
        result = bot_manager.start(instruments=body.instruments)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result

    @app.post("/api/stop")
    async def stop_bot():
        result = bot_manager.stop()
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result

    @app.get("/api/trades")
    async def get_trades(year: int | None = None):
        return {"trades": load_all_trades(year=year), "count": 0}

    @app.get("/api/trades/pnl")
    async def get_trades_pnl(year: int | None = None):
        return {"days": load_trade_pnl(year=year)}

    @app.get("/api/trades/stats")
    async def get_trades_stats():
        return load_trade_stats()

    @app.get("/api/settings")
    async def get_settings():
        return {"settings": get_settings_meta()}

    class SettingBody(BaseModel):
        value: str

    @app.put("/api/settings/{key}")
    async def update_setting(key: str, body: SettingBody):
        if save_setting(key, body.value):
            return {"status": "saved"}
        raise HTTPException(status_code=404, detail="Setting not found")

    @app.post("/api/settings/reset")
    async def reset_settings_endpoint():
        reset_settings()
        return {"status": "reset"}

    @app.get("/api/logs/stream")
    async def stream_logs(request: Request):
        async def event_generator():
            sent = len(bot_manager.log_buffer)
            for entry in list(bot_manager.log_buffer):
                yield f"data: {json.dumps(entry)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                while len(bot_manager.log_buffer) > sent:
                    entry = bot_manager.log_buffer[sent]
                    sent += 1
                    yield f"data: {json.dumps(entry)}\n\n"
                await asyncio.sleep(0.2)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return app

def start_api_server(bot_manager, host="0.0.0.0", port=8002):
    app = create_app(bot_manager)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    return server
