import asyncio
import threading
import time
from collections import deque
from datetime import datetime, timedelta
import pytz
from upstox.data_streamer import DataStreamer
from scheduler import TradingScheduler

IST = pytz.timezone('Asia/Kolkata')

class BotManager:
    def __init__(self, live_feed_server=None):
        self.live_feed_server = live_feed_server
        self.lock = threading.Lock()
        self.running = False
        self.bot_thread = None
        self.log_buffer = deque(maxlen=200)
        self.positions = {
            "CE": {"trade1": None, "trade2": None},
            "PE": {"trade1": None, "trade2": None},
        }
        self.strikes = {}
        self.mode = "idle"
        self.instruments = []
        self.stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
        }
        self._data_streamer = None

    def emit_log(self, message):
        timestamp = datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]
        entry = {"type": "log", "timestamp": timestamp, "message": message}
        self.log_buffer.append(entry)

    def _patch_print(self):
        import builtins
        original_print = builtins.print
        def patched_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            original_print(*args, **kwargs)
            self.emit_log(msg)
        builtins.print = patched_print

    def _restore_print(self):
        import builtins
        builtins.print = builtins.__original_print__ if hasattr(builtins, "__original_print__") else builtins.print

    def get_status(self):
        with self.lock:
            pos_data = {}
            for inst in ["CE", "PE"]:
                pos_data[inst] = {
                    "trade1": self.positions[inst]["trade1"],
                    "trade2": self.positions[inst]["trade2"],
                }
            return {
                "running": self.running,
                "mode": self.mode,
                "connected": self._data_streamer is not None,
                "instruments": self.instruments,
                "strikes": self.strikes,
                "positions": pos_data,
                "stats": self.stats,
            }

    def _bot_loop(self, instruments):
        self._patch_print()
        try:
            self.mode = "starting"

            from settings_db import apply_settings_to_config
            config_overrides = apply_settings_to_config()

            def create_streamer(session_name, ce_key, pe_key):
                ds = DataStreamer(
                    session_name=session_name,
                    instruments=instruments,
                    ce_key=ce_key,
                    pe_key=pe_key,
                )
                ds.live_feed_server = self.live_feed_server
                ds.price_history = {}
                ds.bot_manager = self
                self._data_streamer = ds
                return ds

            scheduler = TradingScheduler(create_streamer)
            scheduler.log = lambda msg: self.emit_log(msg)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(scheduler.start())

        except Exception as e:
            self.emit_log(f"Bot error: {e}")
        finally:
            self.mode = "stopped"
            self.running = False
            self._data_streamer = None
            self._restore_print()

    def start(self, instruments=None):
        with self.lock:
            if self.running:
                return {"status": "error", "message": "Bot already running"}

            now = datetime.now(IST)
            market_end = datetime.strptime("15:30", "%H:%M").replace(
                year=now.year, month=now.month, day=now.day, tzinfo=IST
            )
            if now > market_end:
                return {"status": "error", "message": "Market closed"}

            self.instruments = instruments if instruments else ["CE", "PE"]
            self.running = True
            self.mode = "starting"
            self.log_buffer.clear()

            self.bot_thread = threading.Thread(
                target=self._bot_loop,
                args=(self.instruments,),
                daemon=True,
            )
            self.bot_thread.start()

            return {"status": "starting", "message": f"Bot starting with {', '.join(self.instruments)}"}

    def stop(self):
        with self.lock:
            if not self.running:
                return {"status": "error", "message": "Bot not running"}
            self.running = False
            self.mode = "stopping"
            self.emit_log("Stop requested")

            if hasattr(self, "_data_streamer") and self._data_streamer:
                self._data_streamer.close()

            self.mode = "stopped"
            return {"status": "stopped", "message": "Bot stopped"}
