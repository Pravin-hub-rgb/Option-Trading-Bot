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
        # MUST be reentrant. stop() holds this lock and then calls
        # _force_exit_live_positions(), which re-enters through
        # DataStreamer.exit_position() -> `with self.bot_manager.lock`.
        # With a plain Lock that self-deadlocks, which blocks the whole
        # FastAPI event loop and takes every endpoint down with it.
        self.lock = threading.RLock()
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
        self._log_counter = 0

    def emit_log(self, message):
        self._log_counter += 1
        timestamp = datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]
        entry = {"id": self._log_counter, "type": "log", "timestamp": timestamp, "message": message}
        self.log_buffer.append(entry)

    def _patch_print(self):
        import builtins
        if hasattr(builtins, "__original_print__"):
            return
        builtins.__original_print__ = builtins.print
        def patched_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            builtins.__original_print__(*args, **kwargs)
            self.emit_log(msg)
        builtins.print = patched_print

    def _restore_print(self):
        import builtins
        if hasattr(builtins, "__original_print__"):
            builtins.print = builtins.__original_print__
            del builtins.__original_print__

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
            from settings_db import get_setting

            def create_streamer(session_name, ce_key=None, pe_key=None, ce_strike=None, pe_strike=None, prescan_keys=None):
                ds = DataStreamer(
                    session_name=session_name,
                    instruments=instruments,
                    ce_key=ce_key,
                    pe_key=pe_key,
                    ce_strike=ce_strike,
                    pe_strike=pe_strike,
                    prescan_keys=prescan_keys,
                    live_feed_server=self.live_feed_server,
                    bot_manager=self,
                    access_token=get_setting("access_token"),
                )
                with self.lock:
                    self._data_streamer = ds
                    if ce_strike:
                        self.strikes = {"CE": str(ce_strike), "PE": str(pe_strike or "")}
                return ds

            self._scheduler = TradingScheduler(create_streamer)
            self._scheduler.log = lambda msg: self.emit_log(msg)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._scheduler.start())

        except Exception as e:
            self.emit_log(f"Bot error: {e}")
        finally:
            with self.lock:
                self.mode = "stopped"
                self.running = False
            if hasattr(self, '_scheduler') and self._scheduler:
                self._scheduler.stop()
                self._scheduler = None
            with self.lock:
                self._data_streamer = None
            self._restore_print()

    def start(self, instruments=None):
        with self.lock:
            if self.running:
                return {"status": "error", "message": "Bot already running"}

            from settings_db import get_setting
            import requests
            token = get_setting("access_token")
            if not token:
                return {"status": "error", "message": "No access token configured. Update in Settings."}
            try:
                headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
                r = requests.get(
                    "https://api.upstox.com/v2/market-quote/ltp",
                    headers=headers,
                    params={"instrument_key": "NSE_INDEX|Nifty 50"},
                    timeout=10,
                )
                if r.status_code != 200:
                    return {"status": "error", "message": "Access token invalid or expired. Update in Settings."}
            except Exception as e:
                return {"status": "error", "message": f"Token validation failed: {e}"}

            now = datetime.now(IST)
            market_end = datetime.strptime("15:30", "%H:%M").replace(
                year=now.year, month=now.month, day=now.day, tzinfo=IST
            )
            if now > market_end:
                return {"status": "error", "message": "Market closed"}

            self.instruments = instruments if instruments else ["CE", "PE"]
            self.positions = {
                "CE": {"trade1": None, "trade2": None},
                "PE": {"trade1": None, "trade2": None},
            }
            self.strikes = {}
            self.stats = {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
            }
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

    def _force_exit_live_positions(self):
        """Exit all open positions at their last known LTP before shutdown."""
        streamer = self._data_streamer
        if not streamer or not hasattr(streamer, 'components'):
            return

        now = datetime.now(IST)
        for inst_type in ['CE', 'PE']:
            comp = streamer.components.get(inst_type)
            if not comp:
                continue
            pm = comp.get('position_manager')
            if not pm or not pm.is_in_position():
                continue
            last_ltp = pm.position['last_ltp']
            exit_reason = "Bot Stopped - Manual Exit"
            self.emit_log(f"Force exiting {inst_type} at LTP {last_ltp:.2f} ({exit_reason})")
            try:
                streamer.exit_position(inst_type, last_ltp, now, exit_reason)
            except Exception as e:
                self.emit_log(f"Force exit failed for {inst_type}: {e}")

    def stop(self):
        with self.lock:
            if not self.running:
                return {"status": "error", "message": "Bot not running"}
            self.running = False
            self.mode = "stopping"
            self.emit_log("Stop requested")

            if hasattr(self, "_data_streamer") and self._data_streamer:
                self._force_exit_live_positions()
                self._data_streamer.close()
            if hasattr(self, "_scheduler") and self._scheduler:
                self._scheduler.stop()
                self._scheduler = None

            self.mode = "stopped"
            return {"status": "stopped", "message": "Bot stopped"}
