**WAIT - you're right, I was confusing myself!**

Let me correct my understanding:

---

## You're Correct About Entry Logic

```
Reference high = 100, low = 80
Next candle: O=98, H=102, L=78

What happens:
- High touched 102 → ENTRY TRIGGERED at 100 (that's the rule)
- Low touched 78 → After entry, check if it hit SL at 80

We ENTERED. Trade happened. Now check if SL hit.
```

**You don't care WHEN the high broke** - if it broke, you entered at 100. Period.

The only question is: **After entering at 100, did we get stopped at 80 or not?**

If low = 78, then yes, stopped at 80 for -20 loss.

**I was overthinking it. Your logic is clean and simple. My bad!**

---

## Okay, Let's Move On

You're right - backtest discussion is done. You'll figure out the strategy through CSV testing.

Let me create a complete project document now...

---

# 🤖 OPTIONS TRADING BOT - PROJECT DOCUMENT

## 📋 PROJECT OVERVIEW

**Goal:** Build an automated options trading bot that trades NIFTY ATM options (CE/PE) during high volatility periods using breakout strategies.

**Trading Instrument:** NIFTY Index Options (ATM strike)  
**Trading Windows:** 
- Morning: 9:15 AM - 9:40 AM (volatility window)
- Evening: 3:00 PM - 3:30 PM (volatility window)

**Broker:** Upstox (using Upstox API v2 + WebSocket for live data)

---

## 🎯 WHAT WE'RE TRYING TO ACHIEVE

### Primary Objective
Test whether trading NIFTY options using breakout strategies during volatile periods is profitable.

### Secondary Objectives
1. **Compare trading modes:**
   - Independent mode: CE and PE trade separately without coordination
   - Coordinated mode: Only one position (either CE or PE) active at a time

2. **Test multiple strategies:**
   - Strategy will be modular (plug-and-play from `strategies/` folder)
   - Initial strategy: Red Candle High Break
   - Future strategies: Continuous Green, Support/Resistance, etc.

3. **Build confidence through testing:**
   - CSV backtest first (historical 1-min candle data)
   - Paper trading second (live market, no real money)
   - Real trading last (after proven profitable)

---

## 🏗️ ARCHITECTURE DECISIONS

### ✅ DECISION 1: Two Separate Programs (CE and PE)

**Why:**
- Easier to test independent vs coordinated modes
- True parallel processing (no sequential delays)
- Can run CE-only or PE-only for isolated testing
- Simple to compare results side-by-side
- Natural isolation (one crash doesn't kill both)

**How they work:**
- Both use **same Upstox access token** (same account)
- CE program subscribes to CE instrument only
- PE program subscribes to PE instrument only
- Both can run simultaneously on different websocket connections

---

### ✅ DECISION 2: Modular Strategy System

**Why:**
- Easy to swap strategies (change one import in config)
- Test multiple strategies without rewriting code
- Clean separation: strategy logic vs execution logic
- Strategies are discovered through CSV backtesting

**Structure:**
```
strategies/
├── base_strategy.py           # Abstract base class
├── red_candle_high_break.py   # Strategy A
├── continuous_green.py        # Strategy B
└── [future strategies]        # Strategy C, D, E...
```

**All strategies implement:**
- `find_reference_candle()` - Identify setup
- `check_entry_signal()` - Detect entry (tick-by-tick)
- `check_exit_signal()` - Manage position (trailing SL, targets)

---

### ✅ DECISION 3: Independent Mode First, Then Coordinated

**Phase 1: Independent Mode (Week 1-2)**
- CE and PE trade freely without knowing about each other
- Both can have positions simultaneously
- Simpler to implement (no coordination needed)
- Collect data: P&L, win rate, drawdown

**Phase 2: Coordinated Mode (Week 3-4)**
- Only one position at a time (either CE or PE)
- Simple coordination via shared file (`position_lock.json`)
- Compare results with independent mode

**Decision made after testing:** Pick whichever mode is more profitable

---

### ✅ DECISION 4: Tick-by-Tick Entry Detection

**Critical requirement:**
- Don't wait for candle close to enter
- Check **every tick** if breakout happened
- Enter immediately when high breaks (not at next candle close)

**Why:** Scalping volatile periods requires instant entry. Waiting 1 minute = missing the entire move.

**Example:**
```
9:16 Red candle closes: H=100, L=80
9:17:02 Price hits 100.5 → ENTER NOW
9:17:59 Price at 110 → Already in profit
```

If we waited for 9:17 candle close, we'd enter at 110 (terrible entry).

---

## 📊 DATA COLLECTION & BACKTESTING

### What We Already Have
- ✅ Program that saves 1-min OHLC data during volatility windows
- ✅ Data format: `timestamp, open, high, low, close, volume, oi`
- ✅ Historical data from multiple days

### How Backtesting Works

**Step 1: CSV Backtest (Offline)**
- Test strategy on historical 1-min candles
- Simulate entries/exits using OHLC data
- Handle ambiguous cases (flag or skip)
- Compare independent vs coordinated modes
- Output: Expected P&L, win rate, max drawdown

**Step 2: Strategy Refinement**
- Adjust entry rules, trailing SL, targets
- Re-run backtest until profitable
- Save best strategy to `strategies/` folder

**Step 3: Live Paper Trading**
- Run bot with real market data
- Execute trades in paper mode (no real orders)
- Verify backtest results hold in live conditions

**Step 4: Real Trading**
- Start small (1 lot)
- Monitor for 1-2 weeks
- Scale up if profitable

---

## 🔧 TECHNICAL COMPONENTS

### Core Modules

**1. Data Streamer** (`data_streamer.py`)
- Connects to Upstox WebSocket
- Receives tick-by-tick price updates
- Processes ticks for CE or PE instrument
- Triggers strategy checks on every tick

**2. Candle Aggregator** (`core/candle_aggregator.py`)
- Converts ticks into 1-min candles (OHLC)
- Maintains candle history
- Detects when new candle forms
- Used for reference candle identification

**3. Strategy Engine** (`strategies/*.py`)
- Pluggable strategy classes
- Identifies reference candles (wait for candle close)
- Monitors for entry signals (tick-by-tick, don't wait)
- Manages exits (trailing SL, targets, time-based)

**4. Position Manager** (`core/position_manager.py`)
- Tracks active position (entry price, SL, timestamp)
- Updates trailing stop loss
- Calculates P&L
- Thread-safe for parallel processing

**5. Trade Logger** (`core/trade_logger.py`)
- Logs all trades to CSV
- Records: entry time, exit time, P&L, reason
- Separate logs for CE and PE
- Used for analysis and backtesting validation

**6. Coordination Service** (`coordination_service.py` - Optional)
- Simple Flask API or file-based locking
- Ensures only one position active (CE or PE)
- Used only in coordinated mode

**7. Scheduler** (`scheduler.py`)
- Finds ATM strike at market open
- Fetches CE/PE instrument keys from Upstox
- Saves to `option_keys.txt`
- Starts/stops streaming at configured times

---

## 🎮 CONFIGURATION SYSTEM

**Single config file:** `config.py`

```python
# ============ STRATEGY SELECTION ============
from strategies.red_candle_high_break import RedCandleHighBreak
ACTIVE_STRATEGY = RedCandleHighBreak

STRATEGY_PARAMS = {
    'max_candles_for_break': 2,
    'trailing_sl_points': 5,
}

# ============ TRADING MODE ============
COORDINATION_ENABLED = False  # Toggle independent/coordinated

# ============ INSTRUMENT ============
# Set by scheduler, read by both CE and PE programs
# Stored in: option_keys.txt

# ============ RISK MANAGEMENT ============
MAX_TRADES_PER_DAY = 3
MAX_LOSS_PER_DAY = 500
PROFIT_TARGET_PER_DAY = 1000

# ============ TIMING ============
MARKET_START = "09:15"
MARKET_END = "15:30"
VOLATILITY_WINDOWS = [
    ("09:15", "09:40"),
    ("15:00", "15:30"),
]
```

---

## 🚀 EXECUTION FLOW

### Daily Workflow

**Step 1: Pre-Market (Before 9:15 AM)**
```
Scheduler runs:
1. Fetch NIFTY spot price
2. Calculate ATM strike
3. Get next expiry date
4. Fetch CE/PE instrument keys from Upstox API
5. Save to option_keys.txt
```

**Step 2: Market Open (9:15 AM)**
```
CE Program starts:
1. Load CE instrument key from option_keys.txt
2. Connect to Upstox WebSocket
3. Subscribe to CE instrument
4. Start strategy monitoring

PE Program starts (parallel):
1. Load PE instrument key from option_keys.txt
2. Connect to Upstox WebSocket (same token, different connection)
3. Subscribe to PE instrument
4. Start strategy monitoring
```

**Step 3: During Trading (9:15-9:40, 3:00-3:30)**
```
Both programs (in parallel):
1. Receive ticks continuously
2. Update current 1-min candle
3. On candle close → check if reference candle
4. On every tick → check if entry signal (if reference found)
5. If entry signal → check coordination (if enabled)
6. Enter trade → log to CSV
7. On every tick → check exit signals (trailing SL, target)
8. Exit trade → log to CSV
9. Check daily limits (max trades, max loss, profit target)
```

**Step 4: Market Close (3:30 PM)**
```
Both programs:
1. Close any open positions
2. Stop WebSocket
3. Save final logs
4. Generate daily P&L summary
```

---

## 📈 TESTING ROADMAP

### Week 1-2: CSV Backtesting
- Test red candle high break strategy
- Compare independent vs coordinated
- Refine trailing SL rules
- Identify which mode is better
- **Outcome:** Best strategy + best mode identified

### Week 3: Build Live Bot
- Implement chosen architecture (2 programs confirmed)
- Implement chosen mode (independent or coordinated)
- Implement tick-by-tick entry detection
- Test on paper trading account

### Week 4-5: Paper Trading
- Run bot live during volatility windows
- Monitor performance vs backtest
- Fix any bugs or timing issues
- Verify P&L matches expectations

### Week 6+: Real Trading (if profitable)
- Start with 1 lot size
- Monitor for 1-2 weeks
- Scale up gradually if consistent profits

---

## ⚠️ KNOWN LIMITATIONS & SOLUTIONS

### Limitation 1: OHLC Backtesting Inaccuracy
**Problem:** 1-min candles can't show exact tick-by-tick price movement  
**Solution:** 
- Flag ambiguous cases (entry/exit unclear)
- Run pessimistic/optimistic scenarios
- Accept ±10-20% variance from backtest
- Validate with live paper trading

### Limitation 2: Slippage & Latency
**Problem:** Real orders have execution delay, price may move  
**Solution:**
- Assume 0.5-1 point slippage in backtest
- Use limit orders with buffer in live trading
- Monitor actual fill prices vs expected

### Limitation 3: Coordination Race Conditions
**Problem:** Both programs might detect signal simultaneously  
**Solution:**
- Use file locking (`FileLock`) for coordination
- First to acquire lock gets to enter
- Acceptable 100-200ms delay for coordination check

### Limitation 4: Upstox API Rate Limits
**Problem:** Too many API calls may get throttled  
**Solution:**
- Use WebSocket for price data (not REST API)
- Cache instrument keys daily
- Batch order placement if multiple signals

---

## 🎯 SUCCESS CRITERIA

### Backtest Success:
- ✅ Win rate > 55%
- ✅ Profit factor > 1.5
- ✅ Max drawdown < 30% of capital
- ✅ Consistent across multiple days

### Paper Trading Success:
- ✅ Live P&L within 20% of backtest
- ✅ No major bugs or missed entries
- ✅ System runs stable for 2 weeks

### Real Trading Success:
- ✅ Profitable after 1 month
- ✅ Meets risk management rules
- ✅ Scalable to multiple lots

---

## 🔮 FUTURE ENHANCEMENTS

1. **Multiple Strategies Running**
   - Run Strategy A on CE, Strategy B on PE
   - Compare which strategy performs better on which side

2. **Advanced Coordination**
   - Allow opposite side entry if current side in profit
   - Dynamic position sizing based on conviction

3. **Machine Learning**
   - Use historical data to predict best entry times
   - Optimize trailing SL dynamically

4. **Multi-Strike Trading**
   - Trade ATM +/- 100 strikes simultaneously
   - Spread strategies (iron condor, straddle)

5. **Real-time Dashboard**
   - Web UI to monitor both bots
   - Live P&L, position status
   - Manual override controls

---

## 📝 SUMMARY OF DECISIONS

| Topic | Decision | Reason |
|-------|----------|--------|
| **Architecture** | 2 separate programs (CE + PE) | Easier testing, true parallelism |
| **Coordination** | Start independent, then test coordinated | Independent is simpler to build |
| **Strategy** | Modular plugin system | Easy to swap and test strategies |
| **Entry Detection** | Tick-by-tick (not candle close) | Critical for scalping volatility |
| **Backtesting** | CSV first, then live paper trade | Cheap and fast strategy validation |
| **Access Token** | Same token for both programs | Single Upstox account, multiple connections |
| **Data Source** | Upstox WebSocket (ltpc) | Real-time tick data |
| **Risk Management** | Daily limits (trades, loss, profit) | Prevent over-trading and blow-ups |

---

## 🎬 NEXT IMMEDIATE STEPS

1. **This Week:** CSV backtest red candle strategy
2. **Next Week:** Build CE and PE programs (independent mode)
3. **Week 3:** Paper trade and validate
4. **Week 4:** Decide on real trading

---

**Does this document capture everything we discussed? Anything missing or need clarification?**