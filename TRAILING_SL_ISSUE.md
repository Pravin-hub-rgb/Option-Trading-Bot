# Trailing Stop Loss Issue - Documentation

**Date:** 11 Feb 2026  
**Status:** Identified, Fix Pending  
**Priority:** High

---

## Issue Summary

The trailing stop loss (SL) mechanism is not capturing the **true candle high** from OHLC data, causing missed SL updates when the candle high exceeds the highest tick LTP captured.

### Real Example from Today's Trading

**PE Trade (Second Entry):**
```
[13:44:14] ENTRY at 100.50 | SL: 95.50
[13:49:20] SL moved to 100.50 (LTP: 105.60)     ← First trail at +5 profit
[13:50:34] SL moved to 105.50 (LTP: 110.55)     ← Second trail at +10 profit
[14:10:47] EXIT at 104.90 | P&L: 4.40           ← SL hit, but should have been at 110.50!
```

**Problem:** The 13:52 candle had a high of **115.65**, which should have triggered moving SL to **110.50** (entry + 10 points). But the SL remained at 105.50 and got hit when price retraced.

---

## Root Cause Analysis

### Current Data Flow (Problematic)

```
Upstox Feed
    ├──→ OHLC Candles (TRUE HIGH: 115.65) ──→ CandleAggregator ──→ Strategy
    │                                                  ↑
    └──→ Tick LTP (115.45, 115.30, etc.) ──────────────┘
              ↓
    PositionManager.update_trailing_sl(ltp)
              ↓
    highest_price = max(highest_price, ltp)  ← ONLY uses tick LTP!
```

**The Bug:** `position_manager.py` only tracks `highest_price` from **tick LTP data**, not from the **OHLC candle high**.

### Why Ticks Miss the True High

| Source | Value | Notes |
|--------|-------|-------|
| OHLC Candle High | 115.65 | True high from Upstox aggregation |
| Highest Tick Captured | ~115.45 | Ticks are sporadic, may miss exact high |
| Difference | 0.20 points | Enough to miss a trailing milestone |

**Result:** When profit calculation uses `115.45` instead of `115.65`:
- Actual profit: 115.65 - 100.50 = **15.15** → Should trigger SL at 110.50
- Captured profit: 115.45 - 100.50 = **14.95** → Only triggers SL at 105.50

---

## Affected Code

### File 1: `core/position_manager.py`

```python
def update_trailing_sl(self, current_ltp):
    """Update trailing stop loss based on current price"""
    if not self.position:
        return False, None
    
    self.position['last_ltp'] = current_ltp
    
    # ⚠️ BUG: Only tracks highest from ticks, not candle high!
    if current_ltp > self.position['highest_price']:
        self.position['highest_price'] = current_ltp
    
    profit = self.position['highest_price'] - self.position['entry_price']
    # ... rest of calculation
```

### File 2: `upstox/data_streamer.py`

```python
def process_tick(self, inst_type, ltp, timestamp):
    """Process a single tick"""
    # ...
    if comp['position_manager'].is_in_position():
        # ⚠️ BUG: Only passing LTP, not the candle high!
        sl_moved, new_sl = comp['position_manager'].update_trailing_sl(ltp)
```

---

## Streaming Mode Analysis

### Current Mode: FULL
```python
self.streamer.subscribe(keys_to_subscribe, "full")
```

**Pros:**
- ✅ Provides both LTP (real-time) and OHLC (accurate highs/lows)
- ✅ Best available option from Upstox

**Cons:**
- ❌ Code doesn't utilize the OHLC high for trailing SL

### Alternative Modes

| Mode | LTP | OHLC | Recommendation |
|------|-----|------|----------------|
| `ltpc` | ✅ | ❌ | Worse - no candle data |
| `full` | ✅ | ✅ | Current - best available |

**Verdict:** Already using the best streaming mode. The issue is in how we **use** the data, not the mode itself.

---

## Proposed Fix

### Solution: Pass Candle High to Position Manager

Modify the data flow to include candle high in trailing SL calculation:

```python
# In data_streamer.py - track candle high per instrument
self.candle_highs = {'CE': None, 'PE': None}

def process_ohlc_candles(self, inst_type, ohlc_list):
    # ... existing code ...
    for candle_data in i1_candles:
        high_price = float(candle_data.get('high', 0))
        # Track the highest high seen
        if self.candle_highs[inst_type] is None or high_price > self.candle_highs[inst_type]:
            self.candle_highs[inst_type] = high_price

def process_tick(self, inst_type, ltp, timestamp):
    # ...
    # Pass both LTP and candle high to position manager
    candle_high = self.candle_highs.get(inst_type)
    sl_moved, new_sl = comp['position_manager'].update_trailing_sl(ltp, candle_high)
```

```python
# In position_manager.py - accept optional candle high
def update_trailing_sl(self, current_ltp, candle_high=None):
    # Update from LTP
    if current_ltp > self.position['highest_price']:
        self.position['highest_price'] = current_ltp
    
    # Also update from candle high if provided and higher
    if candle_high is not None and candle_high > self.position['highest_price']:
        self.position['highest_price'] = candle_high
```

---

## Impact Assessment

### Frequency
- **Low to Medium** - Doesn't happen on every trade
- Only occurs when highest tick < candle high

### Risk
- **High** - Can cause missed profit protection
- In the example: Lost ~5 points of profit (exit at 104.90 vs potential 110.50)

### Trades Affected
- Only affects trades where price spikes quickly and retraces
- Most visible in volatile conditions

---

## Testing Recommendations

1. **Add debug logging** to track `highest_price` updates:
   ```
   [DEBUG] [PE] highest_price updated: 115.45 → 115.65 (from candle high)
   ```

2. **Log candle highs** separately from tick highs:
   ```
   [DEBUG] [PE] Tick high: 115.45 | Candle high: 115.65 | Diff: 0.20
   ```

3. **Backtest validation** - Compare trailing SL behavior with historical data

---

## Related Files

- `core/position_manager.py` - Main fix required
- `upstox/data_streamer.py` - Pass candle high to position manager
- `core/candle.py` - Already captures accurate OHLC (no changes needed)
- `config.py` - Trailing settings (no changes needed)

---

## Notes

- This is a **data synchronization issue** between tick-based and candle-based price feeds
- The FULL streaming mode is correct; the issue is in how we utilize the data
- Fix should be backward compatible (candle_high parameter is optional)

---

*Document created: 11 Feb 2026*  
*Author: Trading Bot Analysis*