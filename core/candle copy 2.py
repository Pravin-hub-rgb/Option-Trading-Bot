from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

class CandleAggregator:
    def __init__(self, symbol):
        self.symbol = symbol
        self.candle_history = []
        self.current_candle = None
        self.current_minute = None
        self.processed_minutes = set()  # Track which minutes we've seen from OHLC

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def add_tick(self, ltp, timestamp):
        """
        Add a tick to build candles (original method)
        Still used for real-time updates
        """
        # Align timestamp to minute boundary
        minute = timestamp.replace(second=0, microsecond=0)
        
        # Check if new minute (new candle)
        if minute != self.current_minute:
            if self.current_candle:
                # Only add to history if not already added by OHLC
                minute_key = self.current_candle['timestamp'].strftime('%Y-%m-%d %H:%M')
                if minute_key not in self.processed_minutes:
                    # Log closed candle with symbol
                    print(f"[{self.now()}] 🕯️ Candle closed: Symbol={self.symbol}, Time={self.current_candle['timestamp']}, OHLC={self.current_candle['open']:.2f},{self.current_candle['high']:.2f},{self.current_candle['low']:.2f},{self.current_candle['close']:.2f}")
                    self.candle_history.append(self.current_candle)
                    self.processed_minutes.add(minute_key)
            
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
            print(f"[{self.now()}] 🕯️ Candle (FULL): Symbol={self.symbol}, Time={minute}, OHLC={open_price:.2f},{high_price:.2f},{low_price:.2f},{close_price:.2f}")
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