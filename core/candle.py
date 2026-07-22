from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

class CandleAggregator:
    def __init__(self, symbol, debug=False):
        self.symbol = symbol
        self.debug = debug  # Control debug logging
        self.candle_history = []
        self.current_candle = None
        self.current_minute = None
        self.processed_minutes = set()  # Track which minutes we've seen from OHLC

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def update_from_ohlc(self, timestamp, open_price, high_price, low_price, close_price):
        """
        Update/create candle from Upstox's pre-aggregated OHLC data
        This gives us ACCURATE highs/lows matching charts!
        
        Args:
            timestamp: Candle timestamp (minute boundary)
            open_price: Open price from Upstox
            high_price: High price from Upstox (ACCURATE!)
            low_price: Low price from Upstox (ACCURATE!)
            close_price: Close price from Upstox
        
        Returns:
            bool: True if new candle added to history
        """
        minute = timestamp.replace(second=0, microsecond=0)
        minute_key = minute.strftime('%Y-%m-%d %H:%M')
        
        # Check if we've already processed this minute
        if minute_key in self.processed_minutes:
            return False
        
        # Create candle from OHLC data
        candle = {
            'timestamp': minute,
            'open': open_price,
            'high': high_price,  # ← ACCURATE from Upstox!
            'low': low_price,    # ← ACCURATE from Upstox!
            'close': close_price,
            'symbol': self.symbol
        }
        
        # If this is a completed candle (not current minute)
        current_time = datetime.now(IST).replace(second=0, microsecond=0)
        
        if minute < current_time:
            # Historical/completed candle - add to history
            # REMOVED: Candle (FULL) log
            self.candle_history.append(candle)
            self.processed_minutes.add(minute_key)
            return True
        
        elif minute == current_time:
            # Current minute - update current candle
            if self.current_minute != minute:
                # New minute, set as current
                self.current_candle = candle
                self.current_minute = minute
            else:
                # Update current candle with OHLC data (more accurate than tick aggregation)
                self.current_candle['open'] = open_price
                self.current_candle['high'] = max(self.current_candle['high'], high_price)
                self.current_candle['low'] = min(self.current_candle['low'], low_price)
                self.current_candle['close'] = close_price
        
        return False

    def get_candle_history(self):
        """Get list of completed candles"""
        return self.candle_history

    def get_current_candle(self):
        """Get current forming candle"""
        return self.current_candle 
