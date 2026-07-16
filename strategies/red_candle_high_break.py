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
from config import MAX_WAIT_CANDLES, ALLOW_REFERENCE_SHIFT
from datetime import datetime

class RedCandleHighBreak:
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset strategy state (called after trade exit)"""
        self.reference_candle = None
        self.candles_since_reference = 0
        self.max_wait_candles = MAX_WAIT_CANDLES
        self.allow_reference_shift = ALLOW_REFERENCE_SHIFT
    
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
                    # Don't enter yet, just set reference
                    return None
            return None
        
        # STAGE 2: Have reference, checking for breakout or timeout
        
        # Check if newer red candle appeared (shift reference)
        if self.allow_reference_shift and candle_history:
            last_candle = candle_history[-1]
            if self.is_red_candle(last_candle) and last_candle != self.reference_candle:
                self.reference_candle = last_candle
                self.candles_since_reference = 0
                return None
        
        # Check for timeout
        if self.candles_since_reference > self.max_wait_candles:
            self.reset()
            return None
        
        # Check for breakout
        if current_ltp > self.reference_candle['high']:
            from config import INITIAL_SL_POINTS
            
            # CRITICAL FIX: Enter at reference high, NOT current LTP
            # This matches backtest behavior and prevents slippage
            entry_price = self.reference_candle['high']
            
            entry_signal = {
                'enter': True,
                'entry_price': entry_price,  # ← Enter at ref high (like backtest)
                'stop_loss': entry_price - INITIAL_SL_POINTS,  # ← SL from ref high
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