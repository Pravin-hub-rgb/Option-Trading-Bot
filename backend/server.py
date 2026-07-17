import asyncio
import logging
import threading
import uvicorn
from settings_db import load_settings
from api_server import create_app
from bot_manager import BotManager
from live_feed_server import LiveFeedServer

logging.basicConfig(level=logging.INFO)

load_settings()

live_feed = LiveFeedServer()
bot_manager = BotManager(live_feed_server=live_feed)
app = create_app(bot_manager)

def _start_ws():
    asyncio.run(live_feed.start())

threading.Thread(target=_start_ws, daemon=True).start()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)
