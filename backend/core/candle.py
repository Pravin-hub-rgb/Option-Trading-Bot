from datetime import datetime
import pytz
import threading

IST = pytz.timezone('Asia/Kolkata')

class CandleAggregator:
    def __init__(self, symbol, debug=False):
        self.symbol = symbol
        self.debug = debug
        self.candle_history = []
        self.current_candle = None
        self.current_minute = None
        self.processed_minutes = set()
        self.listeners = []
        self._lock = threading.Lock()
        self.hold_minute = None
        self.pending_held_candle = None

    def add_listener(self, callback):
        self.listeners.append(callback)

    def _notify(self, event_type, candle):
        for cb in self.listeners:
            cb(event_type, candle)

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def arm_hold(self, minute):
        """Hold back the given minute's candle from history until confirmed.
        Used for the 09:15 candle: strategy must not see it until REST confirms it."""
        with self._lock:
            self.hold_minute = minute

    def release_hold(self):
        """Release the held candle (WS fallback path). Returns it or None."""
        with self._lock:
            candle = self.pending_held_candle
            self.pending_held_candle = None
            self.hold_minute = None
        return candle

    def get_pending_held(self):
        """Thread-safe read of the parked (held) candle without releasing it."""
        with self._lock:
            return self.pending_held_candle

    def commit_corrected_candle(self, candle):
        """Commit a corrected candle (REST-confirmed or WS fallback) into history.
        Returns True if committed, False if the minute was already processed."""
        with self._lock:
            minute_key = candle['timestamp'].strftime('%Y-%m-%d %H:%M')
            if minute_key in self.processed_minutes:
                self.hold_minute = None
                self.pending_held_candle = None
                return False
            self.candle_history.append(candle)
            self.processed_minutes.add(minute_key)
            self.hold_minute = None
            self.pending_held_candle = None
        self._notify("candle_closed", candle)
        return True

    def update_from_ohlc(self, timestamp, open_price, high_price, low_price, close_price, feed_time=None):
        minute = timestamp.replace(second=0, microsecond=0)
        minute_key = minute.strftime('%Y-%m-%d %H:%M')
        
        if minute_key in self.processed_minutes:
            return False
        
        candle = {
            'timestamp': minute,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'symbol': self.symbol
        }
        
        # Use the feed's own trade timestamp (ltt) to decide if a candle is
        # complete, NOT datetime.now() at processing time. Wall-clock time can
        # be milliseconds late relative to the minute boundary, which would
        # otherwise let a still-forming candle get committed to history early
        # with only a partial high/low.
        ref_time = feed_time if feed_time else datetime.now(IST)
        current_time = ref_time.replace(second=0, microsecond=0)
        
        if minute < current_time:
            with self._lock:
                # Re-check under lock: the REST commit thread may have already
                # processed this minute while we were waiting.
                if minute_key in self.processed_minutes:
                    return False
                if self.hold_minute is not None and minute == self.hold_minute:
                    self.pending_held_candle = candle
                    return False
                self.candle_history.append(candle)
                self.processed_minutes.add(minute_key)
            self._notify("candle_closed", candle)
            return True
        
        elif minute == current_time:
            if self.current_minute != minute:
                self.current_candle = candle
                self.current_minute = minute
            else:
                self.current_candle['high'] = max(self.current_candle['high'], high_price)
                self.current_candle['low'] = min(self.current_candle['low'], low_price)
                self.current_candle['close'] = close_price
            self._notify("candle_updated", self.current_candle)
        
        return False

    def get_candle_history(self):
        return self.candle_history

    def get_current_candle(self):
        return self.current_candle
