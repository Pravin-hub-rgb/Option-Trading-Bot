"""
Position Manager: Handles single position lifecycle with trailing stop loss
"""
from datetime import datetime
from config import INITIAL_SL_POINTS, TRAILING_TRIGGER, TRAILING_STEP

class PositionManager:
    def __init__(self, initial_sl_points=INITIAL_SL_POINTS, 
                 trailing_trigger=TRAILING_TRIGGER, 
                 trailing_step=TRAILING_STEP):
        """
        Initialize Position Manager
        
        Args:
            initial_sl_points: Points below entry for initial SL (default: 5)
            trailing_trigger: Profit points to trigger first SL move (default: 5)
            trailing_step: Points to trail by (default: 5)
        """
        self.position = None
        self.initial_sl_points = initial_sl_points
        self.trailing_trigger = trailing_trigger
        self.trailing_step = trailing_step
    
    def is_in_position(self):
        """Check if currently holding a position"""
        return self.position is not None
    
    def open_position(self, entry_price, entry_time, symbol):
        """
        Open new position
        
        Args:
            entry_price: Actual entry price (LTP when breakout detected)
            entry_time: Timestamp of entry
            symbol: Instrument symbol (e.g., NIFTY21NOV2525900CE)
        
        Returns:
            dict: Position details
        """
        self.position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'stop_loss': entry_price - self.initial_sl_points,
            'highest_price': entry_price,
            'last_ltp': entry_price
        }
        return self.position.copy()
    
    def update_trailing_sl(self, current_ltp):
        """
        Update trailing stop loss based on current price
        
        Args:
            current_ltp: Current last traded price
        
        Returns:
            tuple: (sl_moved: bool, new_sl: float)
        """
        if not self.position:
            return False, None
        
        self.position['last_ltp'] = current_ltp
        
        # Track highest price reached
        if current_ltp > self.position['highest_price']:
            self.position['highest_price'] = current_ltp
        
        profit = self.position['highest_price'] - self.position['entry_price']
        old_sl = self.position['stop_loss']
        
        # Calculate new SL based on profit milestones
        if profit >= self.trailing_trigger:
            # Reached at least +5 profit
            # Calculate how many milestones passed
            milestones_passed = int((profit - self.trailing_trigger) / self.trailing_step)
            new_sl = self.position['entry_price'] + (milestones_passed * self.trailing_step)
            
            # Only update if new SL is higher
            if new_sl > self.position['stop_loss']:
                self.position['stop_loss'] = new_sl
                return True, new_sl
        
        return False, old_sl
    
    def check_exit(self, current_ltp):
        """
        Check if stop loss hit
        
        Args:
            current_ltp: Current last traded price
        
        Returns:
            bool: True if should exit (SL hit)
        """
        if not self.position:
            return False
        
        return current_ltp <= self.position['stop_loss']
    
    def close_position(self, exit_price, exit_time):
        """
        Close position and return trade summary
        
        Args:
            exit_price: Actual exit price
            exit_time: Timestamp of exit
        
        Returns:
            dict: Trade summary with all details
        """
        if not self.position:
            return None
        
        duration = (exit_time - self.position['entry_time']).total_seconds()
        pnl = exit_price - self.position['entry_price']
        
        trade_summary = {
            'symbol': self.position['symbol'],
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'pnl': pnl,
            'entry_time': self.position['entry_time'],
            'exit_time': exit_time,
            'duration_seconds': duration,
            'sl_initial': self.position['entry_price'] - self.initial_sl_points,
            'sl_final': self.position['stop_loss'],
            'highest_price': self.position['highest_price']
        }
        
        self.position = None
        return trade_summary
    
    def get_current_state(self):
        """Get current position state for logging"""
        if not self.position:
            return None
        return self.position.copy()
    
    def get_current_sl(self):
        """Get current stop loss value"""
        if not self.position:
            return None
        return self.position['stop_loss']