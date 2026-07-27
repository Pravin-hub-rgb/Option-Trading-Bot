# 🐛 CRITICAL BUG FIX: Race Condition in Strike Selection & Subscription

## 📋 Executive Summary

**Bug Type:** Race Condition  
**Severity:** CRITICAL (Trading wrong instruments)  
**Location:** `scheduler.py` - Line 147-165  
**Impact:** Bot subscribes to OLD/STALE strikes instead of LIVE premium-selected strikes  

---

## 🔴 THE PROBLEM EXPLAINED

### Current Broken Flow:
```
09:15:00.147 → Scheduler: start_streaming()
                └─> Creates DataStreamer thread
                
09:15:00.156 → DataStreamer.__init__() loads option_keys.txt
                └─> Reads STALE strikes (from yesterday or previous run)
                └─> Example: CE=25900, PE=25950 (premiums: ₹330, ₹196)
                
09:15:00.158 → DataStreamer: WebSocket connects

09:15:03.860 → DataStreamer: Subscribes to STALE strikes ❌
                └─> Now receiving data for WRONG instruments!
                
09:15:40.633 → Scheduler: prepare_session() runs
                └─> Fetches LIVE option chain
                └─> Finds strikes with premium ≥₹100
                └─> Example: CE=25950 (₹112), PE=25550 (₹105) ✅
                └─> Writes NEW strikes to option_keys.txt
                
09:16:00.646 → Strategy starts
                └─> But still trading on STALE strikes! ❌
```

### Evidence from Logs:
```
[09:15:00.156] ✅ Loaded: CE=NSE_FO|NIFTY25DEC1625900CE, PE=NSE_FO|NIFTY25DEC1625950PE
                          ↑ WRONG strikes (loaded before scheduler updates file)

[09:15:00.633] ✅ Live CE: 25950 (112.05), PE: 25550 (105.00)
                          ↑ CORRECT strikes (but DataStreamer already subscribed to old ones!)

[09:16:07.457] [CE] 🚀 ENTRY at 315.00
                          ↑ This is from the WRONG strike (25900 CE, not 25950 CE)
```

---

## 🎯 WHY THIS HAPPENS

### The Race Condition:

1. **DataStreamer** loads `option_keys.txt` in `__init__()` (line 30-43 of data_streamer.py)
2. **Scheduler** updates `option_keys.txt` in `prepare_session()` AFTER DataStreamer already started
3. **No mechanism exists** for DataStreamer to reload the file or re-subscribe

### Timeline Breakdown:
```
T+0.000s → Scheduler calls start_streaming()
T+0.009s → DataStreamer.__init__() executes, reads option_keys.txt
T+0.010s → DataStreamer has STALE strikes locked in memory
T+0.011s → WebSocket thread starts
T+3.703s → WebSocket subscribes to STALE strikes
T+40.476s → Scheduler updates option_keys.txt (TOO LATE!)
```

---

## ✅ THE SOLUTION

### New Correct Flow:
```
09:15:00 → Scheduler: Wait for market open
           
09:15:40 → Scheduler: prepare_session() FIRST
           └─> Fetch LIVE option chain
           └─> Find strikes ≥₹100 (closest to ₹100)
           └─> Write FRESH strikes to option_keys.txt ✅
           
09:15:41 → Scheduler: start_streaming() NOW
           └─> DataStreamer.__init__() loads FRESH option_keys.txt ✅
           └─> WebSocket connects
           └─> Subscribes to CORRECT strikes ✅
           
09:16:00 → Strategy starts with CORRECT instruments ✅
```

### Why 09:15:40 Timing?

1. **Market settles:** First 40 seconds allow premiums to stabilize
2. **Close to ₹100:** Premiums are closest to target at this time
3. **Minimal drift:** Only 20 seconds until 09:16:00 strategy start
4. **Safe buffer:** Enough time to fetch chain + subscribe (~2-3 seconds)

**Key Principle:** The later we fetch in the 09:15-09:16 window, the less time premiums have to drift away from our ₹100 target.

---

## 🔧 CODE CHANGES REQUIRED

### File: `scheduler.py`

**Location:** `async def start()` method (starting around line 130)

### BEFORE (Broken):
```python
async def start(self):
    self.is_running = True
    self.log(f"🚀 Bot Started")
    current_time = self.get_current_time_str()
    
    if current_time > MARKET_END:
        self.log(f"🔒 Market closed")
        return
    
    # STEP 1: Connect to WebSocket at 9:15:00
    connection_time = "09:15"
    if current_time < connection_time:
        self.log(f"⏳ Waiting to connect at {connection_time}")
        self.wait_until(connection_time, "Connection time")
    
    # STEP 2: Start streaming (Connect to WebSocket at 9:15:00)  ❌ WRONG ORDER!
    self.start_streaming()
    
    # STEP 3: Wait until 9:15:40 to fetch live premiums
    live_selection_time = "09:15:40"
    current_time = datetime.now(IST).strftime("%H:%M:%S")
    
    if current_time < live_selection_time:
        self.log(f"⏳ Waiting for live premium selection at {live_selection_time}")
        self.wait_until(live_selection_time, "Live premium selection")
    
    # STEP 4: Fetch live premiums and select strikes (at 9:15:40)  ❌ TOO LATE!
    if not self.prepare_session():
        self.log(f"❌ Live premium selection failed, exiting")
        self.stop_streaming()
        return
    
    # STEP 5: Wait until 9:16:00 to start strategy
    strategy_start_time = "09:16:00"
    current_time = datetime.now(IST).strftime("%H:%M:%S")
    
    if current_time < strategy_start_time:
        self.log(f"⏳ Waiting for strategy start at {strategy_start_time}")
        self.wait_until(strategy_start_time, "Strategy start")
    
    self.log(f"📈 Strategy starting! Trading active...")
    
    # STEP 6: Wait until market end (silent wait)
    while self.is_running and self.get_current_time_str() < MARKET_END:
        time.sleep(60)
    self.stop_streaming()
    self.log(f"✅ Done for today")
    self.is_running = False
```

### AFTER (Fixed):
```python
async def start(self):
    self.is_running = True
    self.log(f"🚀 Bot Started")
    current_time = self.get_current_time_str()
    
    if current_time > MARKET_END:
        self.log(f"🔒 Market closed")
        return
    
    # STEP 1: Wait until market opens
    market_open_time = "09:15"
    if current_time < market_open_time:
        self.log(f"⏳ Waiting for market open at {market_open_time}")
        self.wait_until(market_open_time, "Market open")
    
    # STEP 2: Wait until 09:15:40 for premium selection ✅ MOVED UP!
    live_selection_time = "09:15:40"
    current_time = datetime.now(IST).strftime("%H:%M:%S")
    
    if current_time < live_selection_time:
        self.log(f"⏳ Waiting for live premium selection at {live_selection_time}")
        self.wait_until(live_selection_time, "Live premium selection")
    
    # STEP 3: Fetch live premiums and select strikes FIRST ✅ CRITICAL FIX!
    self.log(f"🔍 Fetching live premiums and selecting strikes...")
    if not self.prepare_session():
        self.log(f"❌ Live premium selection failed, exiting")
        return
    
    # STEP 4: NOW start streaming with CORRECT strikes ✅ FIXED ORDER!
    self.log(f"🚀 Starting streaming with selected strikes...")
    self.start_streaming()
    
    # Give WebSocket time to connect and subscribe
    await asyncio.sleep(2)
    
    # STEP 5: Wait until 09:16:00 to start strategy
    strategy_start_time = "09:16:00"
    current_time = datetime.now(IST).strftime("%H:%M:%S")
    
    if current_time < strategy_start_time:
        self.log(f"⏳ Waiting for strategy start at {strategy_start_time}")
        self.wait_until(strategy_start_time, "Strategy start")
    
    self.log(f"📈 Strategy starting! Trading active...")
    
    # STEP 6: Wait until market end (silent wait)
    while self.is_running and self.get_current_time_str() < MARKET_END:
        time.sleep(60)
    self.stop_streaming()
    self.log(f"✅ Done for today")
    self.is_running = False
```

---

## 🔍 KEY CHANGES EXPLAINED

### Change 1: Order Swap
```python
# OLD ORDER (BROKEN):
start_streaming()        # Loads STALE option_keys.txt
prepare_session()        # Writes FRESH option_keys.txt (too late!)

# NEW ORDER (FIXED):
prepare_session()        # Writes FRESH option_keys.txt
start_streaming()        # Loads FRESH option_keys.txt ✅
```

### Change 2: Logging Improvements
```python
# Added clear log before prepare_session
self.log(f"🔍 Fetching live premiums and selecting strikes...")

# Added clear log before start_streaming
self.log(f"🚀 Starting streaming with selected strikes...")
```

### Change 3: Connection Buffer
```python
# Added 2-second sleep after start_streaming
await asyncio.sleep(2)
# Ensures WebSocket fully connects before strategy starts
```

---

## 🧪 TESTING & VALIDATION

### Pre-Deployment Testing:

1. **Delete option_keys.txt** before running
2. **Run the bot** and watch logs carefully
3. **Verify the sequence:**
   ```
   [09:15:40.xxx] 🔍 Fetching live premiums and selecting strikes...
   [09:15:40.xxx] Expiry: 2026-02-10
   [09:15:40.xxx] Fetching chain for 2026-02-10...
   [09:15:40.xxx] Chain fetched – XX strikes
   [09:15:40.xxx] Scanning ≥ ₹100 ...
   [09:15:40.xxx] ✅ Live CE: XXXXX (XXX.XX), PE: XXXXX (XXX.XX)
   [09:15:41.xxx] 🚀 Starting streaming with selected strikes...
   [09:15:41.xxx] ✅ Loaded: CE=NSE_FO|..., PE=NSE_FO|...
   [09:15:43.xxx] ✅ WebSocket connected
   [09:15:45.xxx] 📡 Subscribed to instruments
   ```

4. **Verify strikes match:**
   - Check "Live CE: XXXXX" from prepare_session()
   - Check "Loaded: CE=..." from DataStreamer
   - **They MUST be identical!**

5. **Verify first entry:**
   - When first entry happens, check the entry price
   - It should align with the premium of the selected strike
   - Example: If CE selected with ₹112 premium, first entry should be around ₹112-₹120 range

---

## 📊 EXPECTED LOG OUTPUT (Correct Flow)

```
[09:15:00.000] 🚀 Bot Started
[09:15:00.000] 📊 Trading: CE, PE
[09:15:00.000] ⏳ Waiting for market open at 09:15
[09:15:00.000] ⏳ Market open in 14m
[09:15:00.000] ⏳ Waiting for live premium selection at 09:15:40
[09:15:40.000] ⏳ Live premium selection in 0s
[09:15:40.100] 🔍 Fetching live premiums and selecting strikes...
[09:15:40.150] 🔧 Preparing session with live premiums...
[09:15:40.350] Expiry: 2026-02-10
[09:15:40.550] Fetching chain for 2026-02-10...
[09:15:40.750] Chain fetched – 98 strikes
[09:15:40.751] Scanning ≥ ₹100 ...
[09:15:40.752] ✅ Live CE: 25950 (112.05), PE: 25550 (105.00)
[09:15:40.850] 🚀 Starting streaming with selected strikes...
[09:15:40.900] 🚀 Starting streaming...
[09:15:40.950] ✅ Loaded: CE=NSE_FO|NIFTY25DEC1625950CE, PE=NSE_FO|NIFTY25DEC1625550PE
                       ↑ MATCHES the strikes selected above! ✅
[09:15:40.951] 📊 Trading: CE, PE
[09:15:41.000] ✅ Streaming started
[09:15:41.100] 🔌 Connecting to market data...
[09:15:43.000] ✅ WebSocket connected
[09:15:45.000] 📡 Subscribed to instruments
[09:15:45.100] 📡 Live data streaming started
[09:15:45.200] ⏳ Waiting for strategy start at 09:16:00
[09:16:00.000] 📈 Strategy starting! Trading active...
[09:16:07.000] [CE] 🚀 ENTRY at 112.50 | SL: 107.50
                             ↑ Entry price matches selected premium range! ✅
```

---

## ⚠️ CRITICAL VALIDATION POINTS

### ✅ CORRECT Behavior:
- Strike selected at 09:15:40: **25950 CE (₹112)**
- Strike loaded by DataStreamer: **25950 CE** ✅ MATCH!
- First entry price: **~₹112-₹120** ✅ MATCHES PREMIUM!

### ❌ WRONG Behavior (Current Bug):
- Strike selected at 09:15:40: **25950 CE (₹112)**
- Strike loaded by DataStreamer: **25900 CE** ❌ MISMATCH!
- First entry price: **~₹315** ❌ DOESN'T MATCH!

---

## 🛡️ ADDITIONAL SAFEGUARDS (Optional but Recommended)

### Add Validation in DataStreamer.__init__():

**File:** `upstox/data_streamer.py` (around line 30-43)

```python
# After loading option_keys.txt
self.CE_KEY = keys["CE_SYMBOL"]
self.CE_SYMBOL = keys["CE_KEY"]
self.PE_KEY = keys["PE_SYMBOL"]
self.PE_SYMBOL = keys["PE_KEY"]

print(f"[{self.now()}] ✅ Loaded: CE={self.CE_SYMBOL}, PE={self.PE_SYMBOL}")

# ADD THIS VALIDATION:
try:
    ce_premium = float(keys.get("CE_PREMIUM_FROZEN", 0))
    pe_premium = float(keys.get("PE_PREMIUM_FROZEN", 0))
    
    # Validate premiums are in expected range
    if ce_premium < 80 or ce_premium > 150:
        print(f"[{self.now()}] ⚠️  WARNING: CE premium {ce_premium} outside expected range (80-150)")
    if pe_premium < 80 or pe_premium > 150:
        print(f"[{self.now()}] ⚠️  WARNING: PE premium {pe_premium} outside expected range (80-150)")
    
    print(f"[{self.now()}] 📊 Selected premiums: CE=₹{ce_premium:.2f}, PE=₹{pe_premium:.2f}")
except:
    print(f"[{self.now()}] ⚠️  WARNING: Could not validate premium values from option_keys.txt")
```

This will help catch if old/wrong strikes are loaded.

---

## 🔄 ROLLBACK PLAN (If Issues Occur)

If the fix causes unexpected issues, you can quickly revert:

1. **Keep a backup of the original `scheduler.py`**
2. **If needed, revert by:**
   ```bash
   cp scheduler.py.backup scheduler.py
   ```

---

## 📞 SUPPORT & QUESTIONS

### If you encounter issues:

1. **Check the logs** - Look for the exact sequence
2. **Verify option_keys.txt** - Check if it has fresh strikes
3. **Check timestamps** - Ensure prepare_session runs BEFORE start_streaming
4. **Validate premiums** - Entry prices should match selected premiums

### Common Issues:

**Issue:** Bot still trading wrong strikes  
**Solution:** Ensure prepare_session() is called BEFORE start_streaming()

**Issue:** WebSocket connection fails  
**Solution:** Check if there's enough buffer time (current 2-second sleep)

**Issue:** API rate limiting  
**Solution:** Ensure you're not fetching option chain multiple times

---

## ✅ DEPLOYMENT CHECKLIST

- [ ] Backup current `scheduler.py`
- [ ] Implement the code changes
- [ ] Test in paper trading mode first
- [ ] Verify log sequence matches expected output
- [ ] Confirm strikes selected = strikes traded
- [ ] Confirm entry prices match premium range
- [ ] Monitor first live trading day closely
- [ ] Keep backup ready for quick rollback

---

## 📝 CONCLUSION

This fix resolves a critical race condition where the bot was subscribing to stale strikes instead of the live premium-selected strikes. By ensuring `prepare_session()` runs BEFORE `start_streaming()`, we guarantee that:

1. ✅ Fresh strikes are selected based on LIVE premiums at 09:15:40
2. ✅ DataStreamer loads the CORRECT strikes from option_keys.txt
3. ✅ WebSocket subscribes to the RIGHT instruments
4. ✅ Strategy trades on instruments with premiums close to ₹100

**Estimated Impact:** Should see entry prices in ₹100-₹120 range instead of ₹200-₹300 range.

---

**Document Version:** 1.0  
**Date:** February 5, 2026  
**Author:** Claude AI  
**Priority:** CRITICAL - Deploy before next trading session
