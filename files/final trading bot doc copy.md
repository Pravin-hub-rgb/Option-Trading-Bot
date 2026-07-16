# 🤖 NIFTY OPTIONS TRADING BOT - COMPLETE SPECIFICATION

## 📋 EXECUTIVE SUMMARY

### What This Bot Does
Automated options trading system that trades NIFTY Index Options (CE and PE) during high volatility periods using a Red Candle High Break strategy.

### Key Features
- **Independent Trading**: CE and PE trade separately without coordination
- **Strike Selection**: Targets options with ~₹100 premium (90-110 range)
- **Scalping Strategy**: Breakout-based entries with trailing stop loss
- **Risk Management**: Max 2 trades per side per day (stop after first win OR two losses)
- **Flexible Timing**: Works even if started late (9:12, 9:20, etc.)

### Validated Performance
- Backtested on 5 days of 1-minute OHLC data
- Independent mode showed better results than coordinated
- Strategy proven profitable in volatile morning session (9:15-9:30)

---

## 🏗️ SYSTEM ARCHITECTURE

### Design Decision: Single Program with Dual Instance

**Architecture Choice:** One main program that can be run twice (once for CE, once for PE)

```bash
# Terminal 1: CE Trader
python main.py --instrument CE

# Terminal 2: PE Trader
python main.py --instrument PE
```

**Why This Approach:**
- ✅ Single codebase to maintain
- ✅ Share common modules (candle aggregator, strategy, logger)
- ✅ Easy to run CE-only or PE-only for testing
- ✅ True parallel processing (separate processes)
- ✅ Clean isolation (one crash doesn't affect other)

---

## 📁 FILE STRUCTURE

```
nifty_options_bot/
├── main.py                          # Entry point (accepts --instrument flag)
├── config.py                        # All configuration parameters
├── option_keys.txt                  # Generated daily (CE/PE instrument keys)
│
├── core/
│   ├── candle.py                    # CandleAggregator: Tick → 1-min candles
│   ├── position_manager.py         # NEW: Position tracking, trailing SL
│   ├── trade_logger.py              # CSV logging (exists, may need tweaks)
│   └── trader.py                    # Trade execution wrapper
│
├── strategies/
│   └── red_candle_high_break.py     # Strategy implementation (exists)
│
├── upstox/
│   ├── MarketDataFeedV3_pb2.py      # Protobuf definitions (exists)
│   ├── data_streamer.py             # WebSocket connection (exists)
│   └── strike_selector.py           # NEW: Find ~₹100 premium strikes
│
├── scheduler.py                     # Modified: Adaptive timing logic
│
└── logs/
    ├── ce_trades_2025-11-18.csv
    └── pe_trades_2025-11-18.csv
```

---

## ⏰ TIMING & EXECUTION FLOW

### Phase 1: Strike Selection (9:09 - 9:14)

**Time Window:** 9:09:00 AM - 9:14:30 AM

```
1. Wait until 9:09 AM (pre-open price finalized)
2. Fetch NIFTY spot price
3. Calculate ATM strike (round to nearest 50)
4. Check ATM ± 5 strikes (total 11 strikes):
   - ATM - 250
   - ATM - 200
   - ATM - 150
   - ATM - 100
   - ATM - 50
   - ATM
   - ATM + 50
   - ATM + 100
   - ATM + 150
   - ATM + 200
   - ATM + 250

5. For each strike, get CE and PE premiums
6. Filter: Premium between ₹90-₹110
7. If multiple found: Pick closest to ₹100
8. If none found: Pick closest to ₹100 from all 11 strikes
9. Save to option_keys.txt:
   CE_KEY=NSE_FO|12345
   CE_SYMBOL=NIFTY21NOV2525900CE
   CE_STRIKE=25900
   CE_PREMIUM=98.50
   PE_KEY=NSE_FO|67890
   PE_SYMBOL=NIFTY21NOV2525850PE
   PE_STRIKE=25850
   PE_PREMIUM=103.20

Note: CE and PE strikes can be different!
```

---

### Phase 2: Connection Preparation (9:14:30 - 9:14:59)

```
Both traders start:
1. Load instrument key from option_keys.txt
2. Connect to Upstox WebSocket
3. Subscribe to instrument (CE or PE)
4. Wait for ticks to start flowing
5. Initialize candle aggregator
6. Initialize position manager
7. Initialize strategy state

Status by 9:14:59:
✅ Connected to WebSocket
✅ Subscribed to instrument
✅ Ready to receive first tick at 9:15:00.000
```

---

### Phase 3: Trading Session (9:15:00 - 9:30:00 Entry Window)

```
Strategy Active Period: 9:15:00 - 9:30:00
Position Monitoring: Until 3:30 PM or SL hit

For EVERY tick received:
│
├─ Update current 1-min candle (OHLC)
│
├─ If candle closes (minute boundary):
│  ├─ Log candle: timestamp, O, H, L, C
│  ├─ Check if red candle (O > C)
│  │  ├─ If YES: Set as reference OR shift reference
│  │  └─ If NO: Continue
│  └─ Increment candles_since_reference counter
│
├─ If reference candle exists:
│  ├─ Check: candles_since_reference > 2?
│  │  └─ If YES: Reset reference (timeout)
│  │
│  ├─ Check: Current LTP > reference.high?
│  │  └─ If YES and not in position and can_trade:
│  │     ├─ ENTER at current LTP
│  │     ├─ Set initial SL = entry - 5 points
│  │     ├─ Log entry to CSV
│  │     └─ trades_taken += 1
│  │
│  └─ If new red candle appears while waiting:
│     └─ Shift reference to new red candle
│
└─ If in position:
   ├─ Update trailing SL:
   │  ├─ Profit ≥ 5 points: SL = entry (cost-to-cost)
   │  ├─ Profit ≥ 10 points: SL = entry + 5
   │  ├─ Profit ≥ 15 points: SL = entry + 10
   │  └─ Continue pattern...
   │
   ├─ Check exit: LTP ≤ current_SL?
   │  └─ If YES:
   │     ├─ EXIT at current LTP
   │     ├─ Calculate P&L
   │     ├─ Log exit to CSV
   │     └─ Check trade limits:
   │        ├─ If P&L > 0: can_trade = False (stop after win)
   │        └─ If trades_taken ≥ 2: can_trade = False (max 2 trades)
   │
   └─ Continue monitoring...

After 9:30 AM:
├─ Stop looking for new entries
└─ But continue monitoring active position until SL hit
```

---

## 🎯 STRATEGY SPECIFICATION: Red Candle High Break

### Entry Logic

#### Stage 1: Find Reference Red Candle
```
Condition: Candle's Open > Close (red/bearish candle)

Action:
1. Mark this candle as reference
2. Note reference.high (entry trigger level)
3. Reset candles_since_reference = 0

Example:
  9:16 candle closes: O=145.50, H=147.20, L=143.80, C=144.00
  → This is RED (145.50 > 144.00)
  → reference.high = 147.20
```

#### Stage 2: Wait for Breakout (Max 2 Candles)
```
Monitor next 2 candles for breakout:

If ANY tick's LTP > reference.high:
  → ENTER at current LTP (not at reference.high!)
  
Example:
  Reference.high = 147.20
  9:17:23 - Tick arrives: LTP = 147.50
  → Breakout detected!
  → ENTER at 147.50 (market execution)
  → Initial SL = 147.50 - 5 = 142.50
```

#### Stage 3: Reference Candle Shifting (IMPORTANT!)
```
If another red candle appears BEFORE breakout:
  → Shift reference to the NEW red candle
  → Reset candles_since_reference = 0
  
Example:
  9:16 Red candle: high = 147.20 (reference set)
  9:17 Checking for breakout...
  9:18 Another red candle: high = 149.00
  → SHIFT reference to 9:18 candle
  → New reference.high = 149.00
  → Continue waiting for breakout above 149.00
  
This ensures we're always using the MOST RECENT red candle.
```

#### Stage 4: Timeout
```
If no breakout within 2 candles after reference:
  → Reset reference
  → Look for new red candle
  
Example:
  9:16 Red candle found
  9:17 No breakout (candles_since = 1)
  9:18 No breakout (candles_since = 2)
  9:19 Timeout! Reset, look for new red candle
```

---

### Exit Logic: Trailing Stop Loss

#### Initial Stop Loss
```
Entry Price - 5 points

Example:
  Entry at 147.50
  Initial SL = 142.50
```

#### Trailing Stop Loss Rules
```
Milestone 1: Price reaches Entry + 5
  → Move SL to Entry (cost-to-cost)
  
Milestone 2: Price reaches Entry + 10
  → Move SL to Entry + 5 (trail by 5 points)
  
Milestone 3: Price reaches Entry + 15
  → Move SL to Entry + 10 (trail by 5 points)
  
Continue pattern...

Example Trade:
  Entry: 147.50, Initial SL: 142.50
  
  Price reaches 152.50 (+5):
    → SL moves to 147.50 (break-even)
  
  Price reaches 157.50 (+10):
    → SL moves to 152.50 (locked in +5 profit)
  
  Price reaches 162.50 (+15):
    → SL moves to 157.50 (locked in +10 profit)
  
  Price drops to 157.50:
    → EXIT at 157.50
    → P&L = +10 points
```

#### Exit Conditions
```
1. Trailing SL Hit:
   - LTP ≤ current_SL
   - Most common exit
   
2. No time-based exit:
   - Trade can run till 3:30 PM if SL never hit
   - Even if entered at 9:16, can exit at 11:00 AM
```

---

### Trade Limit Rules (Per Side)

```
Rule: "Stop After First Win OR Two Losses"

CE Side State Machine:
  Initial: can_trade = True, trades_taken = 0
  
  Trade 1 Exits:
    ├─ If P&L > 0 (WIN):
    │  └─ can_trade = False → STOP for the day
    │
    └─ If P&L ≤ 0 (LOSS):
       ├─ trades_taken = 1
       └─ can_trade = True → Can take Trade 2
  
  Trade 2 Exits:
    └─ can_trade = False → STOP (regardless of result)

PE Side: Completely independent state machine

Examples:
  Best case: CE wins Trade 1, PE wins Trade 1
    → Total: 2 trades, both profitable
  
  Worst case: CE loses Trade 1 & 2, PE loses Trade 1 & 2
    → Total: 4 trades, all losses
  
  Mixed: CE wins Trade 1 (stops), PE loses Trade 1 & 2
    → Total: 3 trades
```

---

## ⚙️ CONFIGURATION PARAMETERS

### config.py Structure

```python
# ========== UPSTOX CREDENTIALS ==========
ACCESS_TOKEN = "your_token_here"  # Update daily

# ========== TIMING ==========
STRIKE_SELECTION_START = "09:09:00"
STRIKE_SELECTION_END = "09:14:30"
CONNECTION_START = "09:14:30"  # Start traders, connect WebSocket
STRATEGY_START = "09:15:00"    # Begin strategy execution
ENTRY_WINDOW_END = "09:30:00"  # No new entries after this
MARKET_CLOSE = "15:30:00"

# ========== STRIKE SELECTION ==========
TARGET_PREMIUM_MIN = 90   # ₹90
TARGET_PREMIUM_MAX = 110  # ₹110
TARGET_PREMIUM_IDEAL = 100
ATM_OFFSET_RANGE = 5      # Check ATM ± 5 strikes (11 total)
STRIKE_STEP = 50          # NIFTY strikes are 50 points apart

# ========== STRATEGY PARAMETERS ==========
MAX_WAIT_CANDLES = 2           # Timeout after 2 candles
ALLOW_REFERENCE_SHIFT = True   # Shift to newer red candle

# ========== RISK MANAGEMENT ==========
INITIAL_SL_POINTS = 5          # Points below entry
TRAILING_TRIGGER = 5           # Move to cost after +5 profit
TRAILING_STEP = 5              # Then trail by 5 points

# ========== TRADE LIMITS (PER SIDE) ==========
STOP_AFTER_FIRST_WIN = True
MAX_TRADES_PER_SIDE = 2        # Max 2 trades if first loses

# ========== LOGGING ==========
LOG_LEVEL = "VERBOSE"          # VERBOSE or MINIMAL
LOG_EVERY_TICK = True          # Log all ticks (for debugging)
LOG_CANDLE_UPDATES = True      # Log OHLC updates

# ========== DISCONNECTION HANDLING ==========
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY_SECONDS = 5
ALERT_ON_DISCONNECT = True     # Print loud alerts

# ========== CANDLE CONVENTION ==========
CANDLE_TIMESTAMP_STYLE = "next_minute"  # Industry standard
# Candle 9:15:00-9:15:59 is timestamped as 9:16:00
```

---

## 🔧 IMPLEMENTATION GUIDE

### What Exists (Your Current Code)
- ✅ `core/candle.py` - CandleAggregator
- ✅ `core/trader.py` - Trade execution wrapper
- ✅ `core/trade_logger.py` - CSV logging
- ✅ `strategies/red_candle_high_break.py` - Strategy logic
- ✅ `data_streamer.py` - WebSocket connection
- ✅ `scheduler.py` - Timing management
- ✅ `MarketDataFeedV3_pb2.py` - Protobuf definitions

### What Needs to Be Created
1. ⭐ `core/position_manager.py` - NEW module
2. ⭐ `upstox/strike_selector.py` - NEW module
3. ⭐ Modified `main.py` - Accept --instrument flag

### What Needs to Be Modified
1. 🔄 `data_streamer.py` - Support single instrument (CE or PE)
2. 🔄 `scheduler.py` - Adaptive timing logic
3. 🔄 `strategies/red_candle_high_break.py` - May need tweaks
4. 🔄 `config.py` - Add all new parameters

---

## 📦 CORE MODULES SPECIFICATION

### 1. core/position_manager.py (NEW)

```python
"""
Manages a single position's lifecycle:
- Entry tracking
- Trailing stop loss updates
- Exit detection
- P&L calculation
"""

class PositionManager:
    def __init__(self, initial_sl_points=5, trailing_trigger=5, trailing_step=5):
        self.position = None
        self.initial_sl_points = initial_sl_points
        self.trailing_trigger = trailing_trigger
        self.trailing_step = trailing_step
    
    def is_in_position(self) -> bool:
        """Returns True if currently holding position"""
        return self.position is not None
    
    def open_position(self, entry_price: float, entry_time, symbol: str):
        """
        Open new position
        
        Args:
            entry_price: Actual entry price (current LTP when breakout detected)
            entry_time: Timestamp of entry
            symbol: Instrument symbol (CE or PE)
        """
        self.position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'stop_loss': entry_price - self.initial_sl_points,
            'highest_price': entry_price,
            'last_ltp': entry_price
        }
        return self.position
    
    def update_trailing_sl(self, current_ltp: float):
        """
        Update trailing stop loss based on current price
        
        Returns: (sl_moved: bool, new_sl: float)
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
            milestones_passed = int((profit - self.trailing_trigger) / self.trailing_step)
            new_sl = self.position['entry_price'] + (milestones_passed * self.trailing_step)
            
            if new_sl > self.position['stop_loss']:
                self.position['stop_loss'] = new_sl
                return True, new_sl
        
        return False, old_sl
    
    def check_exit(self, current_ltp: float) -> bool:
        """
        Check if stop loss hit
        
        Returns: True if should exit
        """
        if not self.position:
            return False
        
        return current_ltp <= self.position['stop_loss']
    
    def close_position(self, exit_price: float, exit_time) -> dict:
        """
        Close position and return trade summary
        
        Returns: {
            'entry_price': float,
            'exit_price': float,
            'pnl': float,
            'entry_time': timestamp,
            'exit_time': timestamp,
            'duration_seconds': int
        }
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
            'sl_final': self.position['stop_loss']
        }
        
        self.position = None
        return trade_summary
    
    def get_current_state(self) -> dict:
        """Returns current position state for logging"""
        if not self.position:
            return None
        return self.position.copy()
```

---

### 2. upstox/strike_selector.py (NEW)

```python
"""
Find CE and PE strikes with premium near ₹100

Logic:
1. Get NIFTY spot price
2. Calculate ATM strike
3. Check ATM ± 5 strikes (11 total)
4. Filter: premium 90-110
5. Pick closest to 100
6. Fallback: closest from all 11 strikes
"""

import requests
from config import ACCESS_TOKEN, TARGET_PREMIUM_MIN, TARGET_PREMIUM_MAX

class StrikeSelector:
    def __init__(self):
        self.base_url = "https://api.upstox.com/v2"
        self.headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Accept': 'application/json'
        }
    
    def get_nifty_spot(self) -> float:
        """Fetch current NIFTY 50 spot price"""
        endpoint = f"{self.base_url}/market-quote/quotes?instrument_key=NSE_INDEX|Nifty 50"
        response = requests.get(endpoint, headers=self.headers)
        data = response.json()
        
        spot = float(data['data']['NSE_INDEX:Nifty 50']['last_price'])
        return spot
    
    def get_atm_strike(self, spot_price: float) -> int:
        """Calculate ATM strike (round to nearest 50)"""
        return round(spot_price / 50) * 50
    
    def get_strikes_to_check(self, atm_strike: int) -> list:
        """Generate list of 11 strikes to check (ATM ± 5)"""
        strikes = []
        for i in range(-5, 6):  # -5 to +5 inclusive
            strikes.append(atm_strike + (i * 50))
        return strikes
    
    def get_option_premium(self, strike: int, expiry: str, option_type: str) -> float:
        """
        Get premium for specific strike
        
        Args:
            strike: Strike price (e.g., 25900)
            expiry: Expiry date (YYYY-MM-DD)
            option_type: 'CE' or 'PE'
        """
        # Build instrument key format: NSE_FO|NIFTY{expiry}{strike}{CE/PE}
        # Need to query option chain API
        # Implementation depends on Upstox API format
        pass
    
    def find_best_strike(self, strikes_data: list, target_premium: float = 100) -> dict:
        """
        Find strike with premium closest to target
        
        Args:
            strikes_data: List of {'strike': int, 'premium': float}
            target_premium: Target premium (default 100)
        
        Returns: {'strike': int, 'premium': float, 'instrument_key': str}
        """
        # Filter in range
        in_range = [s for s in strikes_data 
                   if TARGET_PREMIUM_MIN <= s['premium'] <= TARGET_PREMIUM_MAX]
        
        if in_range:
            # Pick closest to target
            best = min(in_range, key=lambda x: abs(x['premium'] - target_premium))
        else:
            # Fallback: closest from all strikes
            best = min(strikes_data, key=lambda x: abs(x['premium'] - target_premium))
        
        return best
    
    def select_strikes(self) -> dict:
        """
        Main method: Find CE and PE strikes
        
        Returns: {
            'ce': {'strike': int, 'premium': float, 'instrument_key': str, 'symbol': str},
            'pe': {'strike': int, 'premium': float, 'instrument_key': str, 'symbol': str}
        }
        """
        # 1. Get spot
        spot = self.get_nifty_spot()
        print(f"[STRIKE_SELECTOR] NIFTY Spot: {spot}")
        
        # 2. Calculate ATM
        atm = self.get_atm_strike(spot)
        print(f"[STRIKE_SELECTOR] ATM Strike: {atm}")
        
        # 3. Get strikes to check
        strikes_to_check = self.get_strikes_to_check(atm)
        print(f"[STRIKE_SELECTOR] Checking strikes: {strikes_to_check}")
        
        # 4. Get next expiry
        expiry = self.get_next_expiry()
        
        # 5. Fetch premiums for all strikes
        ce_data = []
        pe_data = []
        
        for strike in strikes_to_check:
            ce_premium = self.get_option_premium(strike, expiry, 'CE')
            pe_premium = self.get_option_premium(strike, expiry, 'PE')
            
            ce_data.append({'strike': strike, 'premium': ce_premium})
            pe_data.append({'strike': strike, 'premium': pe_premium})
        
        # 6. Find best CE and PE
        best_ce = self.find_best_strike(ce_data)
        best_pe = self.find_best_strike(pe_data)
        
        return {
            'ce': best_ce,
            'pe': best_pe
        }
```

---

### 3. Modified main.py

```python
"""
Entry point for trading bot

Usage:
  python main.py --instrument CE
  python main.py --instrument PE
"""

import argparse
import sys
from datetime import datetime
import pytz
from config import STRATEGY_START, ENTRY_WINDOW_END
from data_streamer import DataStreamer
from core.position_manager import PositionManager
from core.trade_logger import TradeLogger
from strategies.red_candle_high_break import RedCandleHighBreak

IST = pytz.timezone('Asia/Kolkata')

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='NIFTY Options Trading Bot')
    parser.add_argument('--instrument', type=str, required=True, 
                       choices=['CE', 'PE'],
                       help='Instrument to trade (CE or PE)')
    args = parser.parse_args()
    
    instrument = args.instrument
    
    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] Starting {instrument} Trader")
    
    # Load instrument key from option_keys.txt
    with open('option_keys.txt', 'r') as f:
        keys = dict(line.strip().split('=') for line in f)
    
    instrument_key = keys[f'{instrument}_KEY']
    symbol = keys[f'{instrument}_SYMBOL']
    
    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] Trading: {symbol} ({instrument_key})")
    
    # Initialize components
    position_manager = PositionManager()
    strategy = RedCandleHighBreak()
    trade_logger = TradeLogger(instrument=instrument, symbol=symbol)
    
    # Initialize data streamer
    streamer = DataStreamer(
        instrument_key=instrument_key,
        symbol=symbol,
        instrument=instrument,
        position_manager=position_manager,
        strategy=strategy,
        trade_logger=trade_logger
    )
    
    # Start streaming
    streamer.run()

if __name__ == "__main__":
    main()
```

---

## 🧪 TESTING CHECKLIST

### Pre-Deployment (Paper Trading)

- [ ] Strike selector finds correct strikes (premium ~100)
- [ ] CE and PE can have different strikes
- [ ] WebSocket connects successfully before 9:15
- [ ] First 9:15 candle is captured completely
- [ ] Red candle detection works
- [ ] Entry triggers at correct price (LTP when breakout detected)
- [ ] Initial SL = entry - 5 points
- [ ] Trailing SL updates at correct milestones
- [ ] Exit triggers when SL hit
- [ ] Trade limits enforced (stop after 1 win or 2 losses)
- [ ] Both CE and PE trade independently
- [ ] Late start works (starting at 9:20, 9:25)
- [ ] Logs are verbose and complete
- [ ] CSV trade logs have all required fields
- [ ] Reconnection works if WebSocket drops

### Live Trading Readiness

- [ ] Paper trading P&L matches backtest (within ±20%)
- [ ] No crashes or bugs for 1 week
- [ ] Trade limits working correctly
- [ ] System handles market volatility
- [ ] Can monitor both terminals simultaneously

---

## 🚀 DEPLOYMENT PROCEDURE

### Daily Startup Sequence

```bash
# 1. Update ACCESS_TOKEN in config.py (daily)
nano config.py

# 2. Run strike selector (9:09 AM)
python -c "from upstox.strike_selector import StrikeSelector; StrikeSelector().select_strikes()"

# 3. Start CE trader (9:14:30 AM)
python main.py --instrument CE

# 4. Start PE trader (in separate terminal)
python main.py --instrument PE

# 5. Monitor both terminals until 3:30 PM
```

### Late Start (e.g., 9:20 AM)

```bash
# Check if option_keys.txt exists and is from today
# If yes, skip strike selection
# If no, run strike selector

# Start traders immediately
python main.py --instrument CE
python main.py --instrument PE

# Entry window open until 9:30, then monitor only
```

---

## 📊 LOGGING FORMAT

### Terminal Output (Real-time)

```
[09:09:15.123] [STRIKE_SELECTOR] NIFTY Spot: 25847.30
[09:09:15.456] [STRIKE_SELECTOR] ATM Strike: 25850
[09:09:15.789] [STRIKE_SELECTOR] CE: 25900, Premium: 98.50 ✅
[09:09:16.012] [STRIKE_SELECTOR] PE: 25800, Premium: 103.20 ✅

[09:14:35.123] [CE_TRADER] Connecting to WebSocket...
[09:14:36.456] [CE_TRADER] ✅ Connected
[09:14:36.789] [CE_TRADER] Subscribed to NIFTY21NOV2525900CE

[09:15:00.123] [CE_TRADER] 📊 Tick: LTP=98.50
[09:15:05.456] [CE_TRADER] 📊 Tick: LTP=99.20
[09:16:00.012] [CE_TRADER] 🕯️ Candle closed: O=98.50, H=102.30, L=97.80, C=100.50
[09:16:00.013] [CE_TRADER] ❌ Not a red candle (O < C)

[09:17:00.123] [CE_TRADER] 🕯️ Candle closed: O=145.50, H=147.20, L=143.80, C=144.00
[09:17:00.124] [CE_TRADER] 🔴 RED CANDLE detected! Reference high=147.20

[09:17:23.456] [CE_TRADER] 📊 Tick: LTP=147.50
[09:17:23.457] [CE_TRADER] 🚀 BREAKOUT! Entry at 147.50, Initial SL=142.50

[09:18:45.678] [CE_TRADER] 📊 Tick: LTP=152.60
[09:18:45.679] [CE_TRADER] 📈 Trailing SL moved to 147.50 (cost-to-cost)

[09:19:12.345] [CE_TRADER] 📊 Tick: LTP=157.80
[09:19:12.346] [CE_TRADER] 📈 Trailing SL moved to 152.50 (trailing +5)

[09:20:34.567] [CE_TRADER] 📊 Tick: LTP=152.40
[09:20:34.568] [CE_TRADER] 🚪 EXIT at 152.40, SL Hit, P&L=+4.90
[09:20:34.569] [CE_TRADER] ✅ First win! Stopping for the day.
```

### CSV Trade Log Format

**File: `logs/ce_trades_2025-11-18.csv`**

```csv
date,time_entry,time_exit,side,symbol,entry_price,exit_price,sl_initial,sl_final,pnl,exit_reason,duration_sec,reference_high
2025-11-18,09:17:23,09:20:34,CE,NIFTY21NOV2525900CE,147.50,152.40,142.50,152.50,4.90,Trailing SL Hit,191,147.20
```

**Fields Explanation:**
- `date`: Trading date
- `time_entry`: Entry timestamp (HH:MM:SS)
- `time_exit`: Exit timestamp (HH:MM:SS)
- `side`: CE or PE
- `symbol`: Full option symbol
- `entry_price`: Actual entry price (LTP when breakout detected)
- `exit_price`: Actual exit price (LTP when SL hit)
- `sl_initial`: Initial stop loss (entry - 5)
- `sl_final`: Final trailing stop loss when exited
- `pnl`: Profit/Loss in points
- `exit_reason`: Why trade exited (Trailing SL Hit, Stop Loss Hit, etc.)
- `duration_sec`: Trade duration in seconds
- `reference_high`: High of reference red candle

---

## 🔍 TROUBLESHOOTING GUIDE

### Issue 1: No Strikes Found with Premium 90-110

**Symptoms:**
```
[09:09:15] [STRIKE_SELECTOR] ⚠️ No CE strikes in range 90-110
[09:09:15] [STRIKE_SELECTOR] Using fallback: 25950CE, Premium=78.40
```

**Cause:** Market conditions (very high/low volatility)

**Solution:** 
- Bot will use closest to 100 (auto-fallback)
- Consider widening range in config (e.g., 80-120)
- Or skip trading that day (manual decision)

---

### Issue 2: WebSocket Disconnected During Trade

**Symptoms:**
```
[09:18:45] [CE_TRADER] ⚠️ WebSocket disconnected!
[09:18:45] [CE_TRADER] Position active: Entry=147.50, SL=142.50
[09:18:50] [CE_TRADER] 🔄 Reconnect attempt 1/3...
```

**Solution:**
- Bot auto-reconnects (3 attempts, 5 sec delay)
- If reconnect succeeds → resumes monitoring
- If fails → loud alerts, position remains in market
- Manual intervention: Check broker app, manage position manually

---

### Issue 3: Late Start (After 9:15)

**Symptoms:**
```
[09:22:30] [SCHEDULER] ⚠️ Late start at 09:22
[09:22:30] [SCHEDULER] Entry window open until 09:30
```

**Solution:**
- Bot adapts automatically
- Checks if option_keys.txt exists from today
- If yes → uses existing strikes
- If no → runs quick strike selection
- Starts monitoring immediately (no waiting)

---

### Issue 4: Missing First Candle (9:15)

**Symptoms:**
```
[09:15:00] [CE_TRADER] No ticks received yet
[09:16:00] [CE_TRADER] 🕯️ First candle: O=145.50...
```

**Cause:** WebSocket connected too late (after 9:15)

**Solution:**
- Ensure bot starts at 9:14:30 (before market open)
- First candle (9:15) is critical for red candle detection
- If missed, strategy starts from 9:16 candle

---

### Issue 5: Both CE and PE Enter Simultaneously

**Symptoms:**
```
[09:17:23] [CE_TRADER] 🚀 ENTRY at 147.50
[09:17:24] [PE_TRADER] 🚀 ENTRY at 138.20
```

**Cause:** Both had reference candles and broke high at same time

**Solution:**
- **This is expected in independent mode!**
- Not a bug - both can trade simultaneously
- Monitor both positions separately
- Each has its own trade limits

---

## 📈 PERFORMANCE METRICS

### What to Track Daily

**Per Side (CE and PE):**
- Total trades taken
- Win rate (%)
- Average P&L per trade
- Max profit trade
- Max loss trade
- Total P&L for the day

**Combined:**
- Total trades (CE + PE)
- Overall win rate
- Overall P&L
- Days profitable vs days loss

**Weekly Review:**
- Which side (CE or PE) performs better?
- Which time (9:15-9:20 vs 9:20-9:30) gives more signals?
- Are trade limits optimal? (should it be 3 trades instead of 2?)
- Is trailing SL too tight/loose?

---

## 🎯 OPTIMIZATION OPPORTUNITIES

### Parameters to Test/Tweak

1. **Initial SL Distance**
   - Current: 5 points
   - Test: 4, 6, 7 points
   - Trade-off: Tighter SL = more stop-outs, Wider = larger losses

2. **Trailing Trigger**
   - Current: Move to cost at +5 profit
   - Test: +3, +7, +10 profit
   - Trade-off: Earlier protection vs letting winners run

3. **Trailing Step**
   - Current: Trail by 5 points
   - Test: 3, 7, 10 points
   - Trade-off: Tighter trailing = more exits, Wider = bigger retracements

4. **Max Wait Candles**
   - Current: 2 candles after reference
   - Test: 1, 3 candles
   - Trade-off: Less wait = fewer trades, More wait = more trades

5. **Trade Limits**
   - Current: 2 max per side
   - Test: 3 trades allowed
   - Risk: More trades = more opportunities or more losses?

6. **Premium Range**
   - Current: 90-110
   - Test: 80-120, 95-105
   - Trade-off: Wider range = always finds strikes, Narrower = more selective

---

## 🔐 RISK MANAGEMENT

### Position Sizing (NOT IMPLEMENTED YET)

Currently trades 1 lot. For scaling:

```python
# Future enhancement
def calculate_position_size(capital, risk_per_trade):
    """
    Calculate lot size based on capital and risk
    
    Args:
        capital: Total trading capital
        risk_per_trade: Max loss per trade (e.g., 500 rupees)
    
    Returns: Number of lots to trade
    """
    sl_points = 5  # Initial SL distance
    points_value = 50  # NIFTY option: 1 point = ₹50
    loss_per_lot = sl_points * points_value  # 5 * 50 = ₹250
    
    max_lots = risk_per_trade / loss_per_lot
    return int(max_lots)

# Example:
# Capital: ₹100,000
# Risk per trade: ₹1,000
# Lots = 1000 / 250 = 4 lots
```

### Circuit Breakers

**Daily Loss Limit (Future Enhancement):**
```python
# In config.py
MAX_DAILY_LOSS = 2000  # Stop if down ₹2000 for the day

# In trader logic
total_pnl = sum(all_trades_today)
if total_pnl <= -MAX_DAILY_LOSS:
    print("[TRADER] 🛑 Daily loss limit hit! Stopping.")
    can_trade = False
```

**Profit Target (Future Enhancement):**
```python
# In config.py
DAILY_PROFIT_TARGET = 3000  # Stop if up ₹3000

# In trader logic
if total_pnl >= DAILY_PROFIT_TARGET:
    print("[TRADER] ✅ Daily profit target hit! Stopping.")
    can_trade = False
```

---

## 📞 ALERTS & NOTIFICATIONS (FUTURE)

### Optional Enhancements

**SMS/Email Alerts:**
```python
# When to send alerts:
1. Position entered
2. Trailing SL moved to cost (break-even)
3. Position exited (with P&L)
4. Trade limits hit (done for the day)
5. WebSocket disconnected with active position
6. Strike selection failed
7. Daily P&L summary at 3:30 PM
```

**Telegram Bot Integration:**
```python
# Real-time updates to your phone
import requests

def send_telegram(message):
    bot_token = "your_bot_token"
    chat_id = "your_chat_id"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={'chat_id': chat_id, 'text': message})

# Usage:
send_telegram(f"🚀 CE Entry at 147.50, SL=142.50")
```

---

## 🧩 INTEGRATION WITH YOUR EXISTING CODE

### Modifications Needed

#### 1. data_streamer.py

**Current:** Monitors both CE and PE in single instance

**Required Change:** Accept single instrument as parameter

```python
class DataStreamer:
    def __init__(self, instrument_key, symbol, instrument, 
                 position_manager, strategy, trade_logger):
        """
        Args:
            instrument_key: Upstox instrument key (e.g., NSE_FO|12345)
            symbol: Human-readable symbol (e.g., NIFTY21NOV2525900CE)
            instrument: 'CE' or 'PE'
            position_manager: PositionManager instance
            strategy: Strategy instance (RedCandleHighBreak)
            trade_logger: TradeLogger instance
        """
        self.instrument_key = instrument_key
        self.symbol = symbol
        self.instrument = instrument
        self.position_manager = position_manager
        self.strategy = strategy
        self.trade_logger = trade_logger
        
        # Trade limits state
        self.trades_taken = 0
        self.can_trade = True
```

**Key Changes:**
- Remove dual CE/PE tracking
- Focus on single instrument
- Trade limits managed per instance

---

#### 2. strategies/red_candle_high_break.py

**Verify it implements:**

```python
class RedCandleHighBreak:
    def __init__(self):
        self.reference_candle = None
        self.candles_since_reference = 0
        self.max_wait_candles = 2
    
    def check_entry(self, current_ltp, candle_history):
        """
        Check if entry signal exists
        
        Returns: {
            'enter': True/False,
            'entry_price': float (current LTP),
            'reference_high': float
        } or None
        """
        # Stage 1: Find reference red candle
        if not self.reference_candle:
            last_candle = candle_history[-1] if candle_history else None
            if last_candle and self.is_red_candle(last_candle):
                self.reference_candle = last_candle
                self.candles_since_reference = 0
                return None
        
        # Stage 2: Check for breakout or timeout
        if self.reference_candle:
            self.candles_since_reference += 1
            
            # Check for newer red candle (shift reference)
            last_candle = candle_history[-1] if candle_history else None
            if last_candle and self.is_red_candle(last_candle):
                self.reference_candle = last_candle
                self.candles_since_reference = 0
                return None
            
            # Check timeout
            if self.candles_since_reference > self.max_wait_candles:
                self.reference_candle = None
                return None
            
            # Check breakout
            if current_ltp > self.reference_candle['high']:
                return {
                    'enter': True,
                    'entry_price': current_ltp,
                    'reference_high': self.reference_candle['high']
                }
        
        return None
    
    def is_red_candle(self, candle):
        """Check if candle is red (bearish)"""
        return candle['open'] > candle['close']
    
    def reset(self):
        """Reset strategy state after trade exit"""
        self.reference_candle = None
        self.candles_since_reference = 0
```

---

#### 3. scheduler.py

**Add Adaptive Timing Logic:**

```python
def run_adaptive():
    """Adaptive scheduler that handles late starts"""
    current_time = datetime.now(IST).strftime("%H:%M")
    
    # Phase 1: Before 9:15 (normal start)
    if current_time < "09:15":
        print("[SCHEDULER] Normal start sequence")
        run_strike_selector()
        wait_until("09:14:30")
        start_traders()
        wait_until("09:15")
        activate_strategy()
    
    # Phase 2: Late start (9:15 - 9:30)
    elif "09:15" <= current_time <= "09:30":
        print(f"[SCHEDULER] Late start at {current_time}")
        
        if option_keys_exist_and_fresh():
            print("[SCHEDULER] Using existing strikes")
        else:
            print("[SCHEDULER] Running strike selection...")
            run_strike_selector()
        
        start_traders()
        activate_strategy()  # Start immediately
        print(f"[SCHEDULER] Entry window closes at 09:30")
    
    # Phase 3: After entry window (9:30 - 3:30)
    elif "09:30" < current_time < "15:30":
        print(f"[SCHEDULER] Started after entry window")
        print("[SCHEDULER] Monitor-only mode")
        
        if position_exists():
            start_traders(monitor_only=True)
        else:
            print("[SCHEDULER] No positions to monitor")
    
    # Phase 4: Market closed
    else:
        print("[SCHEDULER] Market closed")

def option_keys_exist_and_fresh():
    """Check if option_keys.txt exists and is from today"""
    import os
    from datetime import date
    
    if not os.path.exists('option_keys.txt'):
        return False
    
    file_date = date.fromtimestamp(os.path.getmtime('option_keys.txt'))
    return file_date == date.today()
```

---

## 📚 REFERENCE: Key Formulas

### 1. ATM Strike Calculation
```
ATM = round(spot_price / 50) * 50

Examples:
  Spot = 25,847.30 → ATM = 25,850
  Spot = 25,823.10 → ATM = 25,800
  Spot = 25,875.90 → ATM = 25,900
```

### 2. Strikes to Check (ATM ± 5)
```
strikes = [ATM - 250, ATM - 200, ATM - 150, ATM - 100, ATM - 50,
           ATM,
           ATM + 50, ATM + 100, ATM + 150, ATM + 200, ATM + 250]

Example (ATM = 25,850):
  [25,600, 25,650, 25,700, 25,750, 25,800,
   25,850,
   25,900, 25,950, 26,000, 26,050, 26,100]
```

### 3. Trailing Stop Loss Calculation
```
profit = highest_price_reached - entry_price

if profit >= 5:
    milestones = floor((profit - 5) / 5)
    new_sl = entry + (milestones * 5)

Examples:
  Entry=147.50, High=152.50 → profit=5 → milestones=0 → SL=147.50 (cost)
  Entry=147.50, High=157.50 → profit=10 → milestones=1 → SL=152.50
  Entry=147.50, High=162.50 → profit=15 → milestones=2 → SL=157.50
  Entry=147.50, High=167.50 → profit=20 → milestones=3 → SL=162.50
```

### 4. P&L Calculation
```
P&L = exit_price - entry_price

In Rupees (per lot):
  P&L_rupees = P&L * 50  # NIFTY option multiplier

Example:
  Entry=147.50, Exit=152.40 → P&L=4.90 points
  P&L_rupees = 4.90 * 50 = ₹245
```

---

## 🎓 APPENDIX A: Strategy Examples

### Example 1: Clean Win Trade

```
Timeline:
09:16:00 - Candle closes: O=145.50, H=147.20, L=143.80, C=144.00
           → RED CANDLE (O > C)
           → Reference set: high=147.20
           → Candles_since = 0

09:17:23 - Tick arrives: LTP=147.50
           → Breakout detected (147.50 > 147.20)
           → ENTER at 147.50
           → Initial SL = 142.50

09:18:45 - Tick arrives: LTP=152.60
           → Profit = 5.10
           → Trailing SL moves to 147.50 (cost)

09:19:12 - Tick arrives: LTP=157.80
           → Profit = 10.30
           → Trailing SL moves to 152.50

09:20:34 - Tick arrives: LTP=152.40
           → SL Hit (152.40 <= 152.50)
           → EXIT at 152.40
           → P&L = +4.90 points = ₹245

Result: WIN, Stop trading for the day (first win rule)
```

---

### Example 2: Stop Loss Hit

```
Timeline:
09:16:00 - Red candle: high=147.20 (reference set)

09:17:15 - Tick: LTP=147.80
           → ENTER at 147.80
           → Initial SL = 142.80

09:17:45 - Tick: LTP=145.20
           → Still above SL, monitoring

09:18:10 - Tick: LTP=142.70
           → SL Hit (142.70 <= 142.80)
           → EXIT at 142.70
           → P&L = -5.10 points = -₹255

Result: LOSS, Can take Trade 2
```

---

### Example 3: Reference Candle Shift

```
Timeline:
09:16:00 - Red candle: high=147.20
           → Reference set
           → Waiting for breakout

09:17:00 - Green candle: high=146.50
           → No breakout yet
           → Candles_since = 1

09:18:00 - Red candle: high=149.00
           → SHIFT reference to this new red candle
           → Reference.high = 149.00
           → Candles_since = 0 (reset)

09:18:45 - Tick: LTP=149.50
           → ENTER at 149.50 (broke new reference high)
```

---

### Example 4: Timeout (No Entry)

```
Timeline:
09:16:00 - Red candle: high=147.20
           → Reference set

09:17:00 - Green candle: high=146.80
           → No breakout
           → Candles_since = 1

09:18:00 - Green candle: high=146.50
           → No breakout
           → Candles_since = 2

09:19:00 - Green candle: high=145.90
           → Timeout! (candles_since > 2)
           → Reset reference
           → Look for new red candle

Result: No trade taken
```

---

## 🎓 APPENDIX B: Trade Limit State Machine

### CE Side Example (Full Day)

```
Initial State:
  trades_taken = 0
  can_trade = True

Scenario A: Win on First Trade
  09:17 - Trade 1 ENTER
  09:20 - Trade 1 EXIT: P&L = +4.90
          trades_taken = 1
          can_trade = False (stop after first win)
  09:25 - Signal detected, but skipped (can_trade=False)
  
  End of day: 1 trade, +4.90 profit

Scenario B: Two Losses
  09:17 - Trade 1 ENTER
  09:20 - Trade 1 EXIT: P&L = -5.10
          trades_taken = 1
          can_trade = True (can take Trade 2)
  09:25 - Trade 2 ENTER
  09:28 - Trade 2 EXIT: P&L = -4.80
          trades_taken = 2
          can_trade = False (max 2 trades)
  09:29 - Signal detected, but skipped (can_trade=False)
  
  End of day: 2 trades, -9.90 loss

Scenario C: Loss Then Win
  09:17 - Trade 1 ENTER
  09:20 - Trade 1 EXIT: P&L = -5.10
          trades_taken = 1
          can_trade = True
  09:25 - Trade 2 ENTER
  09:28 - Trade 2 EXIT: P&L = +6.20
          trades_taken = 2
          can_trade = False (stop after win, even if Trade 2)
  
  End of day: 2 trades, +1.10 profit
```

---

## 🎓 APPENDIX C: File Contents Examples

### option_keys.txt (Generated Daily)
```
CE_KEY=NSE_FO|52175
CE_SYMBOL=NIFTY21NOV2525900CE
CE_STRIKE=25900
CE_PREMIUM=98.50
PE_KEY=NSE_FO|52176
PE_SYMBOL=NIFTY21NOV2525850PE
PE_STRIKE=25850
PE_PREMIUM=103.20
```

### config.py (Complete)
```python
# ========== UPSTOX ==========
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlf..."  # Update daily

# ========== TIMING ==========
STRIKE_SELECTION_START = "09:09:00"
STRIKE_SELECTION_END = "09:14:30"
CONNECTION_START = "09:14:30"
STRATEGY_START = "09:15:00"
ENTRY_WINDOW_END = "09:30:00"
MARKET_CLOSE = "15:30:00"

# ========== STRIKE SELECTION ==========
TARGET_PREMIUM_MIN = 90
TARGET_PREMIUM_MAX = 110
TARGET_PREMIUM_IDEAL = 100
ATM_OFFSET_RANGE = 5  # Check ATM ± 5 strikes
STRIKE_STEP = 50

# ========== STRATEGY ==========
MAX_WAIT_CANDLES = 2
ALLOW_REFERENCE_SHIFT = True

# ========== RISK MANAGEMENT ==========
INITIAL_SL_POINTS = 5
TRAILING_TRIGGER = 5
TRAILING_STEP = 5

# ========== TRADE LIMITS ==========
STOP_AFTER_FIRST_WIN = True
MAX_TRADES_PER_SIDE = 2

# ========== LOGGING ==========
LOG_LEVEL = "VERBOSE"
LOG_EVERY_TICK = True
LOG_CANDLE_UPDATES = True

# ========== DISCONNECTION ==========
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY_SECONDS = 5
ALERT_ON_DISCONNECT = True

# ========== CANDLE CONVENTION ==========
CANDLE_TIMESTAMP_STYLE = "next_minute"
```

---

## ✅ IMPLEMENTATION SUMMARY

### What You Already Have (Working)
1. ✅ Core candle aggregation (`core/candle.py`)
2. ✅ Trade logging (`core/trade_logger.py`)
3. ✅ Red candle strategy logic (`strategies/red_candle_high_break.py`)
4. ✅ WebSocket streaming (`data_streamer.py`)
5. ✅ Basic scheduler (`scheduler.py`)
6. ✅ Protobuf definitions (`MarketDataFeedV3_pb2.py`)

### What Needs to Be Created
1. ⭐ `core/position_manager.py` - Trailing SL logic
2. ⭐ `upstox/strike_selector.py` - Find ~₹100 premium strikes
3. ⭐ Modified `main.py` - Accept --instrument flag

### What Needs Modification
1. 🔄 `data_streamer.py` - Single instrument focus
2. 🔄 `scheduler.py` - Adaptive timing
3. 🔄 `config.py` - Add all parameters

### Estimated Implementation Time
- New modules: 4-6 hours
- Modifications: 2-3 hours
- Testing: 2-3 days (paper trading)
- **Total: 1 week to production-ready**

---

## 🎯 SUCCESS CRITERIA

### Backtest Validation
- ✅ Backtested on 5 days of data
- ✅ Independent mode better than coordinated
- ✅ Strategy profitable in morning volatility

### Paper Trading Goals (Week 1)
- [ ] No crashes or bugs
- [ ] All entries/exits logged correctly
- [ ] Trade limits enforced
- [ ] P&L within ±20% of backtest expectations

### Live Trading Goals (Week 2+)
- [ ] Consistent daily execution
- [ ] Positive P&L over 10 days
- [ ] Max drawdown acceptable
- [ ] Ready to scale (increase lots)

---

## 📞 SUPPORT & MAINTENANCE

### Daily Checklist
- [ ] Update ACCESS_TOKEN in config.py
- [ ] Ensure option_keys.txt deleted (fresh selection)
- [ ] Start strike selector at 9:09 AM
- [ ] Start both traders at 9:14:30 AM
- [ ] Monitor until 9:30 (entry window)
- [ ] Check positions periodically until 3:30 PM
- [ ] Review trade logs at end of day

### Weekly Review
- [ ] Calculate win rate, avg P&L
- [ ] Identify patterns (which times work best?)
- [ ] Check if parameters need tweaking
- [ ] Verify system stability

### Monthly Analysis
- [ ] Compare live vs backtest performance
- [ ] Decide on scaling (more lots?)
- [ ] Consider strategy modifications
- [ ] Update documentation with learnings

---

## 🚀 NEXT STEPS

1. **Review this document thoroughly**
2. **Create new modules** (position_manager, strike_selector)
3. **Modify existing code** (data_streamer, scheduler, main.py)
4. **Test strike selection** (run manually at 9:09 AM)
5. **Paper trade for 1 week** (monitor closely)
6. **Validate P&L matches backtest** (within ±20%)
7. **Go live with small size** (1 lot per side)
8. **Scale gradually** (2 lots, then 3 lots, etc.)

---

## 📄 DOCUMENT VERSION

**Version:** 1.0  
**Date:** November 18, 2025  
**Status:** Complete Specification  
**Next Update:** After 1 week of paper trading

---

**This document contains everything needed to implement and deploy the NIFTY Options Trading Bot. Save this for reference in future chats or when starting fresh implementation.**