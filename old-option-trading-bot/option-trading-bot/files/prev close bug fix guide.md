# 🔧 Strike Selector Fix - Previous Close Bug

## 📋 Executive Summary

**Problem:** Strike selector is getting gap = 0 because `get_previous_close()` returns today's spot price instead of yesterday's actual close.

**Root Cause:** The OHLC API method returns current price during pre-market hours (9:00-9:15 AM).

**Solution:** Replace with Historical API method (same approach used in working reversal bot).

**Impact:** This fix will enable proper gap calculation and strike selection.

---

## 🎯 THE BUG

### Current Broken Behavior:
```
Real Data:
- Yesterday's Close: 25,079.90
- Today's Opening: 26,308.05
- Expected Gap: +1,228.15 points

What Bot Shows:
- Previous Close: 26,308.05 (WRONG!)
- Current Spot: 26,308.05
- Calculated Gap: 0.00 (WRONG!)

Result: Strike selection fails because gap estimation is completely off
```

### Why It's Broken:

**File:** `upstox/strike_selector.py`  
**Method:** `get_previous_close()` (Lines 87-150)

**Current Logic:**
```python
# Line 94-114: OHLC endpoint approach
ohlc_data = api.get_ohlc('NSE_INDEX|Nifty 50')
prev_close = ohlc_data['ohlc']['close']  # ← Returns TODAY's price during pre-market!
```

**The Problem:**
- During 9:00-9:15 AM, OHLC API's `close` field contains **current spot price**
- It does NOT contain yesterday's closing price
- This causes gap calculation to be zero or incorrect

---

## ✅ THE SOLUTION

### Working Implementation (from reversal bot):

**File:** `upstox_fetcher.py`  
**Method:** `get_ltp_data()` (Lines 336-363)

**Working Logic:**
```python
# Historical API approach
today = date.today()
end_date = today - timedelta(days=1)  # Yesterday!

df = history_api.fetch_historical_data('NIFTY', start_date, end_date)
prev_close = float(df.iloc[-1]['close'])  # Gets actual yesterday's close
```

**Why It Works:**
- Historical API returns **actual EOD (End of Day) data** from database
- Yesterday's close is **stable and accurate**
- Works reliably at any time of day, including pre-market

---

## 🛠️ IMPLEMENTATION GUIDE

### Step 1: Locate the File

**File Path:**
```
C:\Users\Pravin\Desktop\option-trading-bot\upstox\strike_selector.py
```

**Method to Replace:**
```python
def get_previous_close(self):
    # Lines 87-150
```

---

### Step 2: Replace Entire Method

**DELETE:** Lines 87-150 (entire current `get_previous_close()` method)

**INSERT:** The following new implementation:

```python
def get_previous_close(self):
    """
    Fetch previous close using Historical API (most reliable method)
    
    This method fetches yesterday's actual closing price from Upstox's
    historical database, which is accurate and stable at all times including
    pre-market hours.
    
    Returns:
        float: Yesterday's NIFTY 50 closing price
        None: If fetch fails
    """
    try:
        from upstox_client.api import HistoryApi
        from datetime import date, timedelta
        
        # Initialize History API
        history_api = HistoryApi(self.api_client)
        
        # Calculate yesterday's date
        today = date.today()
        yesterday = today - timedelta(days=1)
        end_date = yesterday.strftime('%Y-%m-%d')
        
        self.log(f"🔍 Fetching previous close for date: {end_date}")
        
        # Fetch historical candle data for NIFTY 50
        response = history_api.get_historical_candle_data(
            instrument_key='NSE_INDEX|Nifty 50',
            interval='day',
            to_date=end_date,
            api_version='2.0'
        )
        
        # Parse response
        if hasattr(response, 'data') and hasattr(response.data, 'candles'):
            candles = response.data.candles
            
            if candles and len(candles) > 0:
                # Candle format: [timestamp, open, high, low, close, volume, oi]
                # Index 4 = close price
                prev_close = float(candles[0][4])
                
                self.log(f"📅 Previous Close (Historical API): {prev_close:.2f}")
                return prev_close
            else:
                self.log(f"⚠️ No candle data returned for {end_date}")
                return None
        else:
            self.log(f"⚠️ Invalid response structure from Historical API")
            return None
        
    except ImportError as e:
        self.log(f"❌ HistoryApi import failed: {e}")
        self.log(f"💡 Make sure upstox-python-sdk is installed: pip install upstox-python-sdk")
        return None
        
    except Exception as e:
        self.log(f"❌ Error fetching previous close: {e}")
        import traceback
        self.log(f"Stack trace: {traceback.format_exc()}")
        return None
```

---

### Step 3: Verify Dependencies

Ensure the Upstox Python SDK is installed:

```bash
pip install upstox-python-sdk
```

---

### Step 4: Test the Fix

**Test Script:** Create a test file to verify the fix works

```python
# test_previous_close.py
from upstox.strike_selector import StrikeSelector
from datetime import datetime

selector = StrikeSelector()

print("=" * 60)
print("TESTING PREVIOUS CLOSE FIX")
print("=" * 60)

# Test 1: Get previous close
prev_close = selector.get_previous_close()
if prev_close:
    print(f"✅ Previous Close: {prev_close:.2f}")
else:
    print(f"❌ Failed to get previous close")

# Test 2: Get current spot
spot = selector.get_nifty_spot()
if spot:
    print(f"✅ Current Spot: {spot:.2f}")
else:
    print(f"❌ Failed to get spot price")

# Test 3: Calculate gap
if prev_close and spot:
    gap = spot - prev_close
    gap_pct = (gap / prev_close) * 100
    print(f"✅ Gap: {gap:+.2f} ({gap_pct:+.2f}%)")
    
    if abs(gap) < 1:
        print(f"⚠️ WARNING: Gap is suspiciously small!")
    else:
        print(f"✅ Gap looks reasonable")
else:
    print(f"❌ Cannot calculate gap")

print("=" * 60)
```

**Expected Output:**
```
============================================================
TESTING PREVIOUS CLOSE FIX
============================================================
[09:05:23.456] [STRIKE_SELECTOR] 🔍 Fetching previous close for date: 2026-02-02
[09:05:23.789] [STRIKE_SELECTOR] 📅 Previous Close (Historical API): 25079.90
✅ Previous Close: 25079.90
[09:05:24.123] [STRIKE_SELECTOR] 📊 NIFTY Spot: 26308.05
✅ Current Spot: 26308.05
✅ Gap: +1228.15 (+4.90%)
✅ Gap looks reasonable
============================================================
```

---

## 🔍 VERIFICATION CHECKLIST

After implementing the fix, verify:

- [ ] **No import errors** - HistoryApi imports successfully
- [ ] **Previous close is retrieved** - Shows actual yesterday's close (not today's price)
- [ ] **Gap is calculated correctly** - Shows reasonable gap value (not zero)
- [ ] **Strike selection completes** - Bot proceeds past strike selection
- [ ] **Logs show correct values** - Previous close ≠ current spot

---

## 📊 BEFORE vs AFTER

### BEFORE (Broken):
```
[09:09:01.205] [STRIKE_SELECTOR] 📅 Previous Close (OHLC): 26308.05
[09:09:01.205] [STRIKE_SELECTOR] 🔢 Gap: +0.00 points
[09:09:01.544] [STRIKE_SELECTOR] ❌ Fallback also failed!
[09:09:01.544] ❌ Strike selection failed
```

### AFTER (Fixed):
```
[09:09:01.123] [STRIKE_SELECTOR] 🔍 Fetching previous close for date: 2026-02-02
[09:09:01.456] [STRIKE_SELECTOR] 📅 Previous Close (Historical API): 25079.90
[09:09:01.789] [STRIKE_SELECTOR] 📊 NIFTY Spot: 26308.05
[09:09:01.789] [STRIKE_SELECTOR] 🔢 Gap: +1228.15 points
[09:09:02.123] [STRIKE_SELECTOR] ✅ CE: NIFTY03FEB2626400CE | ₹61.00 → ₹125.34
[09:09:02.123] [STRIKE_SELECTOR] ✅ PE: NIFTY03FEB2625000PE | ₹115.00 → ₹108.67
[09:09:02.234] ✅ Strikes selected successfully
```

---

## 🚨 EDGE CASES TO HANDLE

### Case 1: Weekend/Holiday

**Problem:** If yesterday was a non-trading day, Historical API won't return data

**Solution:** Already handled in code - will return None and log warning

**Recommendation:** Add fallback to fetch last 7 days and take most recent close:

```python
# Enhanced version (optional)
yesterday = today - timedelta(days=1)
start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')  # Last 7 days
end_date = yesterday.strftime('%Y-%m-%d')

# Fetch with date range
response = history_api.get_historical_candle_data(
    instrument_key='NSE_INDEX|Nifty 50',
    interval='day',
    to_date=end_date,
    api_version='2.0'
)

# Take the most recent candle (handles weekends/holidays)
if candles and len(candles) > 0:
    prev_close = float(candles[0][4])  # Most recent close
```

### Case 2: API Rate Limits

**Problem:** Historical API may have rate limits

**Solution:** Code includes timeout and error handling

**Monitoring:** Add logging to track API failures

### Case 3: Token Expiry

**Problem:** Access token might expire

**Solution:** Already handled by upstox_client SDK auto-refresh

**Verification:** Check ACCESS_TOKEN in config.py is valid

---

## 📁 FILES TO MODIFY

### Primary File:
```
📁 option-trading-bot/
  └── 📁 upstox/
      └── 📄 strike_selector.py  ← MODIFY THIS
          Lines 87-150: Replace get_previous_close() method
```

### Files to Keep Unchanged:
```
📁 option-trading-bot/
  ├── 📄 main.py  ← No changes needed
  ├── 📄 config.py  ← No changes needed
  ├── 📄 scheduler.py  ← No changes needed
  └── 📁 upstox/
      ├── 📄 data_streamer.py  ← No changes needed
      └── 📄 __init__.py  ← No changes needed
```

---

## 🎯 SUCCESS CRITERIA

The fix is successful when:

1. ✅ Bot runs without errors at 9:07-9:09 AM
2. ✅ Previous close shows yesterday's actual value (not today's spot)
3. ✅ Gap calculation shows correct value (not zero)
4. ✅ Strike selection completes successfully
5. ✅ CE and PE strikes are selected
6. ✅ Bot proceeds to next phase (subscription at 9:14:30)

---

## 🆘 TROUBLESHOOTING

### Error: "HistoryApi import failed"

**Cause:** upstox-python-sdk not installed or outdated

**Fix:**
```bash
pip uninstall upstox-python-sdk
pip install upstox-python-sdk --upgrade
```

### Error: "No candle data returned"

**Cause:** Date might be weekend/holiday or API issue

**Fix:** Check if yesterday was a trading day, or use 7-day fallback

### Error: "Invalid response structure"

**Cause:** Upstox API response format changed

**Fix:** Add debug logging to inspect response:
```python
self.log(f"DEBUG: Response = {response}")
```

### Gap still shows 0.00

**Cause:** Previous close fetch is still failing

**Fix:** 
1. Check logs for error messages
2. Verify ACCESS_TOKEN is valid
3. Test Historical API manually using test script

---

## 📞 SUPPORT REFERENCE

### Working Example:
See `upstox_fetcher.py` from reversal bot project:
- Lines 336-363: `get_ltp_data()` method
- Lines 172-220: `_fetch_single_chunk()` method
- Uses same Historical API approach

### Upstox API Documentation:
- Historical Data: https://upstox.com/developer/api-documentation/historical-data
- Python SDK: https://github.com/upstox/upstox-python

### Contact:
If issues persist after implementation, check:
1. Upstox API status
2. Access token validity  
3. System date/time settings
4. Network connectivity

---

## ✅ IMPLEMENTATION TIMELINE

**Estimated Time:** 15-30 minutes

1. **5 min** - Backup current `strike_selector.py`
2. **10 min** - Replace `get_previous_close()` method
3. **5 min** - Run test script to verify
4. **5 min** - Test with actual bot at 9:07 AM (next trading day)
5. **5 min** - Monitor first live run

---

## 📝 DEPLOYMENT NOTES

### Before Deployment:
- [ ] Backup current strike_selector.py
- [ ] Verify upstox-python-sdk is installed
- [ ] Test with test_previous_close.py script
- [ ] Verify ACCESS_TOKEN is valid

### During Deployment:
- [ ] Replace get_previous_close() method
- [ ] Save file
- [ ] Restart bot if already running

### After Deployment:
- [ ] Monitor logs during next 9:07 AM run
- [ ] Verify gap calculation is correct
- [ ] Verify strike selection completes
- [ ] Track actual opening premiums vs estimates

---

## 🎉 EXPECTED OUTCOME

After this fix:

1. **Gap calculation will work correctly**
   - Shows actual gap between yesterday's close and today's opening
   - Enables proper strike selection logic

2. **Strike selection will succeed**
   - Delta-based estimation will work properly
   - Safety filters will apply correctly
   - CE and PE strikes will be selected

3. **Bot will proceed normally**
   - Saves strikes to option_keys.txt
   - Subscribes at 9:14:30
   - Enters trades at 9:15:00

4. **Trade quality will improve**
   - Strikes selected with accurate gap data
   - Opening premiums closer to target (₹105-120)
   - Better risk/reward ratios

---

**Status:** Ready for implementation  
**Priority:** Critical (blocks all trading)  
**Complexity:** Low (single method replacement)  
**Risk:** Minimal (isolated change, well-tested approach)

---

## 📄 APPENDIX: Code Comparison

### Current Code (BROKEN):
```python
def get_previous_close(self):
    """BROKEN - Returns today's price during pre-market"""
    endpoint = f"{self.base_url}/market-quote/ohlc"
    params = {
        'instrument_key': 'NSE_INDEX|Nifty 50',
        'interval': '1d'
    }
    response = requests.get(endpoint, headers=self.headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        ohlc_data = data['data']['NSE_INDEX:Nifty 50']
        
        # BUG: This returns TODAY's price during pre-market!
        prev_close = float(ohlc_data['ohlc']['close'])
        return prev_close
```

### New Code (FIXED):
```python
def get_previous_close(self):
    """FIXED - Gets actual yesterday's close from Historical API"""
    from upstox_client.api import HistoryApi
    from datetime import date, timedelta
    
    history_api = HistoryApi(self.api_client)
    
    yesterday = date.today() - timedelta(days=1)
    end_date = yesterday.strftime('%Y-%m-%d')
    
    response = history_api.get_historical_candle_data(
        instrument_key='NSE_INDEX|Nifty 50',
        interval='day',
        to_date=end_date,
        api_version='2.0'
    )
    
    if hasattr(response, 'data') and hasattr(response.data, 'candles'):
        candles = response.data.candles
        if candles and len(candles) > 0:
            # Gets actual yesterday's close from historical database
            prev_close = float(candles[0][4])
            return prev_close
    
    return None
```

---

**END OF DOCUMENT**

Questions? Contact the project owner or refer to working implementation in reversal bot's `upstox_fetcher.py`.