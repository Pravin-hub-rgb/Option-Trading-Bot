# Live Premium Workflow Implementation

## Overview

This document outlines the changes to convert the NIFTY options trading bot from pre-market delta/gap estimation to live premium-based strike selection.

## Current vs New Workflow

### Current Workflow (Pre-Market Estimation)
```
9:09:00 → Run delta/gap estimation strike selector
9:14:30 → Connect to WebSocket
9:15:00 → Market opens, start streaming
9:16:00 → Check 9:15 candle, start strategy with pre-selected strikes
```

### New Workflow (Live Premium)
```
9:15:00 → Connect to WebSocket
9:15:40 → Fetch option chain, scan live premiums, select strikes ≥ ₹100
9:16:00 → Check 9:15 candle, start strategy with live-selected strikes
```

## Key Changes

### 1. Remove Pre-Market Components
- Remove delta/gap estimation logic from `upstox/strike_selector.py`
- Remove 9:09 strike selection timing from `scheduler.py`
- Remove previous close fetching and gap calculation

### 2. Add Live Premium Selection
- Use option chain API at 9:15:40 to get live premiums
- Filter strikes with LTP ≥ ₹100
- Select strikes closest to ₹100 (same logic as `test_live_premium_scanning.py`)
- Save selected strikes to `option_keys.txt`

### 3. Update Scheduler Timing
- Remove 9:09 strike selection step
- Add 9:15:40 live premium scanning
- Keep 9:16:00 strategy start timing

### 4. Simplified Strike Selection Logic
```python
def find_strikes_ge_target(chain, target=100):
    # Same logic as test_live_premium_scanning.py
    # Filter strikes with LTP >= target
    # Return closest to target
```

## Implementation Steps

### Step 1: Create Live Premium Selector
- Create new method in `upstox/strike_selector.py`
- Use option chain API to fetch live premiums
- Apply same filtering logic as test script

### Step 2: Update Scheduler
- Modify `scheduler.py` timing sequence
- Replace pre-market selection with live premium scanning
- Add 9:15:40 option chain fetch

### Step 3: Update Data Streamer
- No changes needed to trading logic
- Strategy remains exactly the same
- Only strike selection changes

## Benefits

1. **More Accurate**: Uses actual market premiums instead of estimates
2. **Simpler**: Removes complex delta/gap calculations
3. **Reliable**: No dependency on previous close accuracy
4. **Consistent**: Same logic as successful test script

## Files to Modify

1. `scheduler.py` - Update timing and remove pre-market selection
2. `upstox/strike_selector.py` - Replace with live premium logic
3. `LIVE_PREMIUM_WORKFLOW.md` - This documentation

## Files Unchanged

- `strategies/red_candle_high_break.py` - Strategy logic unchanged
- `core/candle.py` - Candle aggregation unchanged
- `core/position_manager.py` - Position management unchanged
- `core/trade_logger.py` - Logging unchanged
- `upstox/data_streamer.py` - Data streaming unchanged

## Testing

1. Run `test_live_premium_scanning.py` to verify option chain logic
2. Test new workflow during market hours
3. Compare strike selection accuracy vs previous method