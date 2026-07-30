from datetime import datetime
import pytz

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

    def add_listener(self, callback):
        self.listeners.append(callback)

    def _notify(self, event_type, candle):
        for cb in self.listeners:
            cb(event_type, candle)

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

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
