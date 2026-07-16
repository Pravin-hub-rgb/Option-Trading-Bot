from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

class CandleAggregator:
    def __init__(self, symbol):
        self.symbol = symbol
        self.candle_history = []
        self.current_candle = None
        self.current_minute = None

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def add_tick(self, ltp, timestamp):
        # Align timestamp to minute boundary
        minute = timestamp.replace(second=0, microsecond=0)
        
        # Check if new minute (new candle)
        if minute != self.current_minute:
            if self.current_candle:
                # Log closed candle with symbol
                print(f"[{self.now()}] 🕯️ Candle closed: Symbol={self.symbol}, Time={self.current_candle['timestamp']}, OHLC={self.current_candle['open']:.2f},{self.current_candle['high']:.2f},{self.current_candle['low']:.2f},{self.current_candle['close']:.2f}")
                self.candle_history.append(self.current_candle)
            # Start new candle
            self.current_candle = {
                'timestamp': minute,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'symbol': self.symbol
            }
            self.current_minute = minute
            return True
        
        # Update existing candle
        self.current_candle['high'] = max(self.current_candle['high'], ltp)
        self.current_candle['low'] = min(self.current_candle['low'], ltp)
        self.current_candle['close'] = ltp
        return False

    def get_candle_history(self):
        return self.candle_history

    def get_current_candle(self):
        return self.current_candle