# 🚨 CRITICAL FIXES - TWO BUGS FOUND!

## BUG #1: Wait Timing Not Working ❌

### Problem:
```python
# CURRENT CODE (BROKEN):
live_selection_time = "09:15:40"
current_time = datetime.now(IST).strftime("%H:%M:%S")  # Gets time ONCE

if current_time < live_selection_time:  # Checks ONCE
    self.wait_until(live_selection_time, "Live premium selection")  # Waits

# Then IMMEDIATELY runs prepare_session() whether wait happened or not!
self.log(f"🔍 Fetching live premiums and selecting strikes...")
if not self.prepare_session():  # ← Runs at 09:15:00, not 09:15:40!
```

### Why it fails:
- `current_time` is captured ONCE before the if statement
- The if only controls whether to WAIT
- But `prepare_session()` runs immediately after, regardless of waiting
- So it runs at 09:15:00 instead of 09:15:40!

### Evidence from logs:
```
[09:15:00.777] ⏳ Waiting for live premium selection at 09:15:40
[09:15:00.777] 🔍 Fetching live premiums and selecting strikes...  ← IMMEDIATELY!
[09:15:02.518] ✅ Live CE: 25700 (110.05), PE: 25600 (109.60)
```

### Fix:
```python
# FIXED CODE:
live_selection_time = "09:15:40"

# ALWAYS wait (no if statement)
self.log(f"⏳ Waiting for live premium selection at {live_selection_time}")
self.wait_until(live_selection_time, "Live premium selection")  # Blocks until 09:15:40

# Now this runs at 09:15:40!
self.log(f"🔍 Fetching live premiums and selecting strikes...")
if not self.prepare_session():
```

Also fixed `time_to_seconds()` to handle HH:MM:SS format:
```python
def time_to_seconds(self, time_str):
    parts = time_str.split(":")
    h = int(parts[0])
    m = int(parts[1])
    s = int(parts[2]) if len(parts) == 3 else 0  # ← ADDED: Handle seconds
    return h * 3600 + m * 60 + s
```

---

## BUG #2: Key Swapping in data_streamer.py ❌

### Problem:
```python
# CURRENT CODE (BROKEN):
self.CE_KEY = keys["CE_SYMBOL"]      # ❌ SWAPPED!
self.CE_SYMBOL = keys["CE_KEY"]      # ❌ SWAPPED!
self.PE_KEY = keys["PE_SYMBOL"]      # ❌ SWAPPED!
self.PE_SYMBOL = keys["PE_KEY"]      # ❌ SWAPPED!
```

### Evidence from logs:
```
[09:15:02.518] ✅ Live CE: 25700 (110.05), PE: 25600 (109.60)
[09:15:02.519] ✅ Loaded: CE=NSE_FO|42530, PE=NSE_FO|42527
                              ↑↑↑↑↑           ↑↑↑↑↑
                    These are instrument IDs, NOT strike numbers!
```

The file contains:
```
CE_KEY=NSE_FO|NIFTY25DEC1625700CE
CE_SYMBOL=NSE_FO|NIFTY25DEC1625700CE
```

But data_streamer swaps them!

### Fix:
```python
# FIXED CODE:
self.CE_KEY = keys["CE_KEY"]          # ✅ CORRECT!
self.CE_SYMBOL = keys["CE_SYMBOL"]    # ✅ CORRECT!
self.PE_KEY = keys["PE_KEY"]          # ✅ CORRECT!
self.PE_SYMBOL = keys["PE_SYMBOL"]    # ✅ CORRECT!
```

Also improved validation logging:
```python
ce_strike = int(keys.get("CE_STRIKE", 0))
pe_strike = int(keys.get("PE_STRIKE", 0))

print(f"[{self.now()}] 📊 Selected strikes: CE={ce_strike} (₹{ce_premium:.2f}), PE={pe_strike} (₹{pe_premium:.2f})")
```

---

## FILES TO REPLACE:

### 1. Replace `scheduler.py` with `scheduler_FIXED.py`
Changes:
- ✅ Removed the `if current_time < live_selection_time:` check
- ✅ Always calls `wait_until()` to ensure it waits until 09:15:40
- ✅ Fixed `time_to_seconds()` to handle HH:MM:SS format
- ✅ Removed unnecessary `current_time` variable captures

### 2. Replace `data_streamer.py` with `data_streamer_FIXED.py`
Changes:
- ✅ Fixed key loading (no more swapping!)
- ✅ Improved validation logging to show strike numbers
- ✅ Better error handling in validation

---

## EXPECTED BEHAVIOR AFTER FIX:

```
[09:15:00.000] 🚀 Bot Started
[09:15:00.000] 📊 Trading: CE, PE
[09:15:00.000] ⏳ Waiting for market open at 09:15
[09:15:00.000] ⏳ Market open in XXm

[09:15:00.000] ⏳ Waiting for live premium selection at 09:15:40
[09:15:05.000] ⏳ Live premium selection in 35s
[09:15:10.000] ⏳ Live premium selection in 30s
...
[09:15:35.000] ⏳ Live premium selection in 5s
[09:15:40.000] ⏳ Live premium selection in 0s

[09:15:40.100] 🔍 Fetching live premiums and selecting strikes...  ← NOW at 09:15:40!
[09:15:40.200] 🔧 Preparing session with live premiums...
[09:15:40.400] Expiry: 2026-02-10
[09:15:40.600] Fetching chain for 2026-02-10...
[09:15:40.800] Chain fetched – 98 strikes
[09:15:40.801] Scanning ≥ ₹100 ...
[09:15:40.802] ✅ Live CE: 25700 (110.05), PE: 25600 (109.60)

[09:15:40.900] 🚀 Starting streaming with selected strikes...
[09:15:40.950] 🚀 Starting streaming...
[09:15:41.000] ✅ Loaded: CE=NSE_FO|NIFTY25DEC1625700CE, PE=NSE_FO|NIFTY25DEC1625600PE
                              ↑↑↑↑↑ MATCHES 25700!     ↑↑↑↑↑ MATCHES 25600!
[09:15:41.001] 📊 Selected strikes: CE=25700 (₹110.05), PE=25600 (₹109.60)
[09:15:41.002] 📊 Trading: CE, PE

[09:15:43.000] ✅ WebSocket connected
[09:15:45.000] 📡 Subscribed to instruments
[09:15:45.100] 📡 Live data streaming started

[09:16:00.000] 📈 Strategy starting! Trading active...
[09:16:XX.XXX] [CE] 🚀 ENTRY at 112.50 | SL: 107.50  ← Entry around ₹110-115!
```

---

## VALIDATION CHECKLIST:

After applying fixes, verify:

✅ prepare_session() runs at 09:15:40 (NOT 09:15:00)
✅ "Loaded" message shows strike numbers (25700, 25600), not random IDs (42530)
✅ Selected strikes match loaded strikes
✅ First entry price is ~₹110-120 range (NOT ₹300+)

---

## DEPLOYMENT STEPS:

1. **Backup current files:**
   ```bash
   cp scheduler.py scheduler.py.backup
   cp upstox/data_streamer.py upstox/data_streamer.py.backup
   ```

2. **Replace with fixed versions:**
   ```bash
   cp scheduler_FIXED.py scheduler.py
   cp data_streamer_FIXED.py upstox/data_streamer.py
   ```

3. **Delete option_keys.txt:**
   ```bash
   rm option_keys.txt
   ```

4. **Test tomorrow at market open**

---

**Both bugs MUST be fixed together! One without the other won't work properly.**
