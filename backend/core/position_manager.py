"""
Position Manager: Handles single position lifecycle with trailing stop loss
"""
from datetime import datetime

class PositionManager:
    def __init__(self, initial_sl_points=4, 
                 trailing_trigger=5, 
                 trailing_step=5):
        """
        Initialize Position Manager
        
        Args:
            initial_sl_points: Points below entry for initial SL (default: 4)
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
        from settings_db import get_as_dict
        s = get_as_dict()
        sl_points = int(s.get('initial_sl_points', self.initial_sl_points))
        self.position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'stop_loss': entry_price - sl_points,
            'sl_initial': entry_price - sl_points,
            'highest_price': entry_price,
            'lowest_price': entry_price,
            'sl_rungs_locked': 0,
            'bank_active': True,
            'bank_taken': False,
            'bank_proved': False,
            'ticks_seen': 0,
            'peak_tick': 0,
            'bank_touched': False,
            'first_bank_tick': None,
            'was_above_bank': False,
            'dips_below_bank': 0,
            'last_ltp': entry_price,
            # Raw tick series, kept for the shadow study's chart. Purely
            # observational - nothing in the exit ladder ever reads this.
            'tick_path': [],
        }
        return self.position.copy()
    
    def track_price(self, current_ltp):
        """
        Track max favourable / adverse excursion for the open position.
        
        Purely observational - it never influences the trailing SL decision, so
        adding it cannot change live trading behaviour. Called on every tick
        BEFORE check_exit() so the exit tick's price is captured too.
        
        The path summary answers questions that MFE alone cannot: did the price
        dip back below the first rung after touching it? That is what decides
        whether a runner would have survived the new first-rung rule.
        """
        if not self.position or current_ltp is None:
            return
        p = self.position
        profit = current_ltp - p['entry_price']

        if current_ltp > p['highest_price']:
            p['highest_price'] = current_ltp
            p['peak_tick'] = p['ticks_seen']
        if current_ltp < p['lowest_price']:
            p['lowest_price'] = current_ltp

        p['ticks_seen'] += 1
        p['tick_path'].append(round(float(current_ltp), 2))

        # Observation only - this never influences an exit.
        bank = self.get_dip_watch_level()
        if bank > 0:
            if profit >= bank:
                if not p['bank_touched']:
                    p['bank_touched'] = True
                    p['first_bank_tick'] = p['ticks_seen']
                    p['was_above_bank'] = True
                elif p['was_above_bank']:
                    p['was_above_bank'] = True
            else:
                if p['bank_touched'] and p['was_above_bank']:
                    # came back down after touching the first rung
                    p['dips_below_bank'] += 1
                p['was_above_bank'] = False
    
    def get_mfe(self):
        """Max favourable excursion in points (highest LTP - entry)."""
        if not self.position:
            return None
        return self.position['highest_price'] - self.position['entry_price']
    
    def get_mae(self):
        """Max adverse excursion in points (entry - lowest LTP)."""
        if not self.position:
            return None
        return self.position['entry_price'] - self.position['lowest_price']
    
    def get_dip_watch_level(self):
        """
        OBSERVATION ONLY. The price level at which we start counting dips.

        This has no effect whatsoever on when a trade exits - it only decides
        what gets written to the `dips_below_bank` column so the "what if we
        banked earlier" study can be evaluated later on real data. The live
        exit ladder in update_trailing_sl() does not read this.
        """
        from settings_db import get_as_dict
        s = get_as_dict()
        try:
            level = float(s.get('observe_dip_level', 5) or 0)
        except (TypeError, ValueError):
            return 0.0
        return level if level > 0 else 0.0

    def update_trailing_sl(self, current_ltp):
        """
        Update trailing stop loss based on current price.

        THIS IS THE LIVE EXIT LOGIC and it is the original, unchanged ladder:
        once the trade is up by `trailing_trigger`, the stop ratchets up in
        `trailing_step` increments and never moves back down. The first rung
        only covers charges (entry+1).

        The "what if we banked earlier" study does NOT live here. It lives in
        smart_pnl.py as a read-only simulation. See track_price() for the
        observation-only DIP_WATCH_LEVEL threshold.
        
        Args:
            current_ltp: Current last traded price
        
        Returns:
            tuple: (sl_moved: bool, new_sl: float)
        """
        if not self.position:
            return False, None
        
        from settings_db import get_as_dict
        s = get_as_dict()
        trailing_trigger = int(s.get('trailing_trigger', self.trailing_trigger))
        trailing_step = int(s.get('trailing_step', self.trailing_step))
        
        self.position['last_ltp'] = current_ltp
        
        profit = current_ltp - self.position['entry_price']
        old_sl = self.position['stop_loss']
        
        # Calculate new SL based on profit milestones
        if profit >= trailing_trigger:
            # Reached at least the trigger. Count how many milestones passed.
            milestones_passed = int((profit - trailing_trigger) / trailing_step)
            # The first milestone moves the stop to true break-even
            # (entry + 1 pt, to cover brokerage/STT/charges); higher rungs
            # follow the normal trailing step.
            new_sl = self.position['entry_price'] + (
                1.0 if milestones_passed == 0 else milestones_passed * trailing_step
            )
            
            # Only update if new SL is higher
            if new_sl > self.position['stop_loss']:
                self.position['stop_loss'] = new_sl
                self.position['sl_rungs_locked'] = self.position.get('sl_rungs_locked', 0) + 1
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

    def set_manual_sl(self, value):
        """Manually set SL. Auto-trailing can still move it UP from here."""
        if not self.position:
            return False
        self.position['stop_loss'] = value
        return True

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
            'sl_initial': self.position.get('sl_initial', self.position['entry_price'] - self.initial_sl_points),
            'sl_final': self.position['stop_loss'],
            'highest_price': self.position['highest_price'],
            'mfe_points': round(self.position['highest_price'] - self.position['entry_price'], 2),
            'mae_points': round(self.position['entry_price'] - self.position['lowest_price'], 2),
            'sl_rungs_locked': self.position.get('sl_rungs_locked', 0),
            'bank_taken': self.position.get('bank_taken', False),
            'bank_proved': self.position.get('bank_proved', False),
            'ticks_seen': self.position.get('ticks_seen', 0),
            'peak_tick': self.position.get('peak_tick', 0),
            'bank_touched': self.position.get('bank_touched', False),
            'first_bank_tick': self.position.get('first_bank_tick'),
            'dips_below_bank': self.position.get('dips_below_bank', 0),
            'tick_path': list(self.position.get('tick_path') or []),
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

    def get_unrealized_pnl(self, current_ltp):
        """Get unrealized P&L at current price"""
        if not self.position:
            return None
        return current_ltp - self.position['entry_price']

    def get_tp_levels(self, current_ltp=None):
        """Get next 5 take-profit milestone levels from entry price"""
        if not self.position:
            return []
        entry = self.position['entry_price']
        return [entry + self.trailing_trigger + i * self.trailing_step for i in range(5)]