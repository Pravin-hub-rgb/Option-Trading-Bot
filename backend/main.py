import asyncio
import logging
import threading
from live_feed_server import LiveFeedServer
from api_server import start_api_server
from bot_manager import BotManager
from settings_db import load_settings, get_as_dict

logging.basicConfig(level=logging.INFO)

def main():
    load_settings()
    get_as_dict()  # populate settings cache

    live_feed = LiveFeedServer()

    bot_manager = BotManager(live_feed_server=live_feed)

    ws_thread = threading.Thread(
        target=lambda: asyncio.run(live_feed.start()),
        daemon=True,
    )
    ws_thread.start()

    api_server = start_api_server(bot_manager, host="0.0.0.0", port=8002)

    api_thread = threading.Thread(
        target=api_server.run,
        daemon=True,
    )
    api_thread.start()

    # http://localhost:3002
    print("Dashboard: http://localhost:3002")
    print("API: http://localhost:8002/api/status")
    print("WS: ws://localhost:8765")

    try:
        api_thread.join()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
