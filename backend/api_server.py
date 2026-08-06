import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

import requests
from settings_db import get_settings_meta, save_setting, reset_settings, load_settings, get_setting
from trade_log_reader import load_all_trades, load_trade_pnl, load_trade_stats
from bot_manager import BotManager

def create_app(bot_manager):
    app = FastAPI(title="Options Trading Bot API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
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
        trades = load_all_trades(year=year)
        return {"trades": trades, "count": len(trades)}

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

    @app.delete("/api/trades/{trade_id}")
    async def delete_trade(trade_id: int):
        from db import get_conn, init_db
        init_db()
        conn = get_conn()
        result = conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Trade not found")
        return {"status": "deleted"}

    @app.get("/api/ticks/{instrument}/{slot}")
    async def get_ticks(instrument: str, slot: int):
        if not bot_manager.live_feed_server:
            return {"ticks": []}
        ticks = bot_manager.live_feed_server.get_tick_history(instrument, slot)
        return {"ticks": ticks}

    class SlBody(BaseModel):
        sl: float

    @app.post("/api/position/{instrument}/{slot}/sl")
    async def modify_sl(instrument: str, slot: int, body: SlBody):
        if not bot_manager._data_streamer:
            raise HTTPException(status_code=400, detail="Bot not running")
        ok = bot_manager._data_streamer.modify_sl(instrument, slot, body.sl)
        if not ok:
            raise HTTPException(status_code=400, detail="No active position found")
        return {"status": "ok", "sl": body.sl}

    @app.get("/api/token/status")
    async def token_status():
        token = get_setting("access_token")
        return {"exists": bool(token)}

    @app.get("/api/token/check")
    async def check_token():
        token = get_setting("access_token")
        if not token:
            return {"valid": False, "message": "No access token configured."}
        try:
            headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
            resp = requests.get(
                "https://api.upstox.com/v2/market-quote/ltp",
                headers=headers,
                params={"instrument_key": "NSE_INDEX|Nifty 50"},
                timeout=10,
            )
            if resp.status_code == 200:
                return {"valid": True, "message": "Token is valid"}
            return {"valid": False, "message": f"Token rejected (HTTP {resp.status_code})"}
        except Exception as e:
            return {"valid": False, "message": f"Token check failed: {e}"}

    class TokenBody(BaseModel):
        token: str

    @app.post("/api/token/validate")
    async def validate_token(body: TokenBody):
        try:
            save_setting("access_token", body.token)
            headers = {"Accept": "application/json", "Authorization": f"Bearer {body.token}"}
            results = []
            successes = 0
            for symbol in ["RELIANCE", "TCS", "HDFCBANK"]:
                try:
                    url = f"https://api.upstox.com/v2/market-quote/ltp?instrument_key=NSE_EQ%7C{symbol}"
                    r = requests.get(url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        successes += 1
                        results.append(f"OK {symbol}")
                    else:
                        results.append(f"FAIL {symbol}: HTTP {r.status_code}")
                except Exception as e:
                    results.append(f"FAIL {symbol}: {e}")
            if successes > 0:
                return {"valid": True, "test_results": results, "message": f"{successes}/3 tests passed"}
            return {"valid": False, "test_results": results, "message": "All tests failed — token invalid"}
        except Exception as e:
            return {"valid": False, "message": f"Error: {e}"}

    @app.get("/api/logs/stream")
    async def stream_logs(request: Request):
        async def event_generator():
            sent_id = 0
            for entry in list(bot_manager.log_buffer):
                sent_id = max(sent_id, entry.get("id", 0))
                yield f"data: {json.dumps(entry)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                for entry in list(bot_manager.log_buffer):
                    if entry.get("id", 0) > sent_id:
                        sent_id = entry.get("id", 0)
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

def start_api_server(bot_manager, host="127.0.0.1", port=8002):
    app = create_app(bot_manager)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    return server
