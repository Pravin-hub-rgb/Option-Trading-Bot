"""
RED CANDLE HIGH BREAK STRATEGY

Logic:
1. Find first red candle (open > close)
2. Enter when price breaks above red candle high
3. Enter AT reference high (not current LTP - matches backtest)
4. Wait max 2 candles for breakout
5. If newer red candle appears while waiting, shift to it
6. Trailing stop loss management
"""
from datetime import datetime

class RedCandleHighBreak:
    def __init__(self, max_wait_candles=None, allow_reference_shift=None, initial_sl_points=None):
        self._max_wait_candles = max_wait_candles if max_wait_candles is not None else 2
        self._allow_reference_shift = allow_reference_shift if allow_reference_shift is not None else True
        self._initial_sl_points = initial_sl_points if initial_sl_points is not None else 5
        self.reset()
    
    def reset(self):
        """Reset strategy state (called after trade exit)"""
        self.reference_candle = None
        self.candles_since_reference = 0
        self.max_wait_candles = self._max_wait_candles
        self.allow_reference_shift = self._allow_reference_shift
    
    def is_red_candle(self, candle):
        """Check if candle is red (bearish): open > close"""
        if not candle:
            return False
        return candle['open'] > candle['close']
    
    def check_entry(self, current_ltp, candle_history):
        """
        Check if entry signal exists
        
        Args:
            current_ltp: Current last traded price
            candle_history: List of completed candles
        
        Returns:
            dict or None: {
                'enter': True,
                'entry_price': float (reference high - NOT current LTP),
                'stop_loss': float,
                'reference_high': float
            }
        """
        # STAGE 1: Looking for reference red candle
        if not self.reference_candle:
            if candle_history:
                last_candle = candle_history[-1]
                if self.is_red_candle(last_candle):
                    self.reference_candle = last_candle
                    self.candles_since_reference = 0
                    print(f"[STRATEGY] Reference SET: "
                          f"{last_candle['timestamp'].strftime('%H:%M')} "
                          f"O={last_candle['open']:.2f} H={last_candle['high']:.2f} "
                          f"L={last_candle['low']:.2f} C={last_candle['close']:.2f} | "
                          f"current_ltp={current_ltp:.2f}")
                    # Don't enter yet, just set reference
                    return None
            return None
        
        # STAGE 2: Have reference, checking for breakout or timeout
        
        # Check if newer red candle appeared (shift reference)
        if self.allow_reference_shift and candle_history:
            last_candle = candle_history[-1]
            if self.is_red_candle(last_candle) and last_candle != self.reference_candle:
                print(f"[STRATEGY] Reference SHIFTED: "
                      f"{last_candle['timestamp'].strftime('%H:%M')} "
                      f"O={last_candle['open']:.2f} H={last_candle['high']:.2f} "
                      f"L={last_candle['low']:.2f} C={last_candle['close']:.2f} | "
                      f"current_ltp={current_ltp:.2f}")
                self.reference_candle = last_candle
                self.candles_since_reference = 0
                return None
        
        # Check for timeout
        if self.candles_since_reference > self.max_wait_candles:
            self.reset()
            return None
        
        # Check for breakout
        if current_ltp > self.reference_candle['high']:
            from settings_db import get_as_dict
            s = get_as_dict()
            sl_points = int(s.get('initial_sl_points', self._initial_sl_points))
            entry_price = self.reference_candle['high']
            entry_signal = {
                'enter': True,
                'entry_price': entry_price,
                'stop_loss': entry_price - sl_points,
                'reference_high': self.reference_candle['high']
            }
            return entry_signal
        
        return None
    
    def on_new_candle_closed(self):
        """
        Called when a new candle closes (to increment counter)
        Must be called by data_streamer when is_new_candle == True
        """
        if self.reference_candle:
            self.candles_since_reference += 1
    
    def get_reference_info(self):
        """Get current reference candle info for logging"""
        if not self.reference_candle:
            return None
        return {
            'timestamp': self.reference_candle['timestamp'],
            'high': self.reference_candle['high'],
            'candles_waited': self.candles_since_reference
        }