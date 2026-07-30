# Pre-Subscribe OHLC Clipping Fix — Full Changelog

**Date:** July 28, 2026
**Branch:** `fix/pre-subscribe-ohlc-clipping`
**Scope:** First-candle OHLC clipping, stale strike selection LTP, candle open overwrite bug
**Testing Status:** ⏳ Pending live test

> **Post-review update (Jul 28):** Prescan band widened from ±500 pts to ±80 strikes (±4000 pts / ~320 keys). Unsubscribe of remaining keys added after finalize. `max_reconnect` guard hardened. Temporary RAW I1 debug print added for live confirmation.

---

## Table of Contents

1. [Overview](#overview)
2. [Fix 1: `backend/core/candle.py` — Open Overwrite Bug](#fix-1-backendcorecandlepy--open-overwrite-bug)
3. [Fix 2: `backend/scheduler.py` — Stale LTP in Strike Selection](#fix-2-backendschedulerpy--stale-ltp-in-strike-selection)
4. [Fix 3: `backend/upstox/data_streamer.py` — Path A Pre-Subscribe Architecture](#fix-3-backendupstoxdata_streamerpy--path-a-pre-subscribe-architecture)
5. [Fix 4: `backend/scheduler.py` — Path A/B Time-Gated Startup](#fix-4-backendschedulerpy--path-ab-time-gated-startup)
6. [Fix 5: `backend/bot_manager.py` — Factory Signature Update](#fix-5-backendbot_managerpy--factory-signature-update)
7. [Detailed Flow: What Happens at Market Open](#detailed-flow-what-happens-at-market-open)
8. [Edge Cases Handled](#edge-cases-handled)

---

## Overview

Three bugs were fixed in this change:

| Bug | Symptom | Root Cause | Fix |
|---|---|---|---|
| **Open Overwrite** | First candle open price incorrectly set to latest tick | `candle.py:60` was setting `self.current_candle['open'] = open_price` every update, overwriting the real open | Delete that line |
| **Strike Selection Stale LTP** | Selected wrong strikes before 09:15 because chain `market_data.ltp` returns frozen/yesterday data | `fetch_live_strikes()` was reading `ce.get('market_data', {}).get('ltp', 0)` from the chain API response | Replace with batch `/v2/market-quote/ltp` API call for all candidate keys |
| **First-Candle OHLC Clipping** | First 30-40s of OHLC data lost while WebSocket wasn't subscribed yet | Streamer subscribes at 09:15:40 but market opens at 09:15:00 — 40s gap | **Path A**: Pre-subscribe ~200 strikes at 09:14:30 so OHLC data flows from the true 09:15:00 start |

---

## Fix 1: `backend/core/candle.py` — Open Overwrite Bug

**File:** `backend/core/candle.py`
**Lines:** 50-66 (after fix)

### The Bug

In `CandleAggregator.update_from_ohlc()`, when the incoming candle's minute equals the current minute (i.e., this is an in-progress candle update, not a closed candle), the code was overwriting `self.current_candle['open']` with the latest `open_price` from the feed.

This meant every tick's OHLC update reset the open price to whatever the feed reported at that instant, instead of preserving the first-tick open of the minute.

### The Fix

Removed the line `self.current_candle['open'] = open_price` from the `minute == current_time` branch:

```python
# BEFORE (buggy) — line 60:
else:
    self.current_candle['open'] = open_price
    self.current_candle['high'] = max(self.current_candle['high'], high_price)
    self.current_candle['low'] = min(self.current_candle['low'], low_price)
    self.current_candle['close'] = close_price

# AFTER (fixed):
else:
    self.current_candle['high'] = max(self.current_candle['high'], high_price)
    self.current_candle['low'] = min(self.current_candle['low'], low_price)
    self.current_candle['close'] = close_price
```

The open is now set only once — when `self.current_minute != minute` creates `self.current_candle` from the raw feed data. Subsequent updates only adjust high/low/close.

### Risk

None. The open is correctly preserved from the first OHLC packet of each minute. High/low/close continue to update as expected.

---

## Fix 2: `backend/scheduler.py` — Stale LTP in Strike Selection

**File:** `backend/scheduler.py`
**Method:** `fetch_live_strikes()` (lines 145-277)

### The Bug

The original code read LTP directly from the option chain response:

```python
# ORIGINAL (broken):
ce = entry.get('call_options', {})
if ce:
    ltp = float(ce.get('market_data', {}).get('ltp', 0))
```

This `market_data.ltp` in the chain API response is NOT real-time. Before market open (and even just after), it returns the previous day's closing price or stale data. This caused the strike selection algorithm to pick wrong strikes.

### The Fix

A two-phase approach:

**Phase 1** — Collect all candidate keys near spot (no LTP check yet):
```python
candidates = []
for entry in chain:
    strike = int(float(entry.get('strike_price', 0)))
    if abs(strike - spot) > 500:
        continue
    ce = entry.get('call_options', {})
    if ce:
        key = ce.get('instrument_key', '')
        if key:
            candidates.append({'strike': strike, 'key': key, 'type': 'CE'})
    pe = entry.get('put_options', {})
    if pe:
        key = pe.get('instrument_key', '')
        if key:
            candidates.append({'strike': strike, 'key': key, 'type': 'PE'})
```

**Phase 2** — Batch fetch LIVE LTP via REST API (chunked at 50 keys per request):
```python
all_keys = [c['key'] for c in candidates]
live_ltp = {}
if all_keys:
    chunk_size = 50
    for i in range(0, len(all_keys), chunk_size):
        chunk = all_keys[i:i+chunk_size]
        keys_param = ','.join(chunk)
        resp = requests.get(
            f"{base_url}/market-quote/ltp",
            headers=headers,
            params={'instrument_key': keys_param},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            for inst_key, quote in data.items():
                ltp_val = float(quote.get('last_price', 0))
                if ltp_val > 0:
                    live_ltp[inst_key] = ltp_val
```

**Phase 3** — Build CE/PE lists using ONLY live LTP values:
```python
ce_list = []
pe_list = []
for c in candidates:
    live = live_ltp.get(c['key'])
    if live is None or live <= 0:
        continue  # skip strikes without live data
    entry = {'strike': c['strike'], 'premium': live, ...}
    ...
```

The selection logic (closest to ₹100 with fallbacks to 80/50) is unchanged.

### Notes

- Upstox `/v2/market-quote/ltp` accepts comma-separated instrument keys
- 50 keys per chunk is a safe limit for Upstox
- The instrument key format `NSE_FO|12345` is the same in both chain API and market-quote API
- Response keys use `NSE_FO:12345` format (colon separator), which is why `inst_key` is used to map back

---

## Fix 3: `backend/upstox/data_streamer.py` — Path A Pre-Subscribe Architecture

**File:** `backend/upstox/data_streamer.py` (620 lines total)

This is the most complex change. The DataStreamer gains a new "prescan mode" that subscribes to ~200 instrument keys before knowing which 2 will be traded.

### 3.1 Constructor — `__init__` (lines 16-91)

**New parameter:** `prescan_keys` (optional list of instrument key strings)

When `prescan_keys` is provided (Path A):
- `CE_KEY`, `PE_KEY`, `CE_SYMBOL`, `PE_SYMBOL`, `CE_STRIKE`, `PE_STRIKE` are all set to `None`
- `self.components` is set to `{}` (empty — no trading components yet)
- `self._prescan_aggregators` is populated with a `CandleAggregator` for each prescan key
- The aggregator's symbol is the raw instrument key (e.g., `NSE_FO|12345`)
- No listeners are attached yet (they're added in `finalize_selection`)

When `prescan_keys` is `None` (Path B / existing behavior):
- Original code path unchanged — validates `ce_key` and `pe_key`, creates components with strategies/position managers/trade loggers

```python
if prescan_keys:
    self.CE_KEY = None
    ...
    self.components = {}
    for key in prescan_keys:
        agg = CandleAggregator(symbol=key)
        self._prescan_aggregators[key] = agg
    print(f"Pre-subscribe mode: {len(prescan_keys)} instruments loaded")
else:
    # original code...
```

### 3.2 Prescan OHLC Routing — `_update_prescan_ohlc()` (lines 138-154)

New method that processes OHLC data for a single prescan instrument key. Mirrors `process_ohlc_candles()` but routes to `_prescan_aggregators` instead of `components[inst_type]`.

```python
def _update_prescan_ohlc(self, instrument_key, ohlc_list, feed_time=None):
    agg = self._prescan_aggregators.get(instrument_key)
    if not agg:
        return
    i1_candles = [c for c in ohlc_list if c.get('interval') == 'I1']
    i1_candles.sort(key=lambda c: int(c.get('ts', 0)), reverse=True)
    for candle_data in i1_candles[:2]:
        ts_ms = int(candle_data.get('ts', 0))
        candle_ts = datetime.fromtimestamp(ts_ms / 1000, IST)
        agg.update_from_ohlc(
            timestamp=candle_ts,
            open_price=float(candle_data.get('open', 0)),
            high_price=float(candle_data.get('high', 0)),
            low_price=float(candle_data.get('low', 0)),
            close_price=float(candle_data.get('close', 0)),
            feed_time=feed_time
        )
```

### 3.3 Finalize Selection — `finalize_selection()` (lines 156-203)

Called by the scheduler AFTER strikes are selected. This is the critical injection point:

```python
def finalize_selection(self, ce_key, pe_key, ce_strike=None, pe_strike=None):
    if not self._prescan_aggregators:
        print(f"[ERROR] finalize_selection called without prescan aggregators")
        return
    
    self.CE_KEY = ce_key
    self.PE_KEY = pe_key
    self.CE_STRIKE = ce_strike
    self.PE_STRIKE = pe_strike
    self.CE_SYMBOL = f"{ce_strike} CE" if ce_strike else ce_key
    self.PE_SYMBOL = f"{pe_strike} PE" if pe_strike else pe_key

    s = self._settings = get_as_dict()

    for inst, key, strike in [('CE', ce_key, ce_strike), ('PE', pe_key, pe_strike)]:
        prescan_agg = self._prescan_aggregators.pop(key, None)
        if not prescan_agg:
            print(f"[WARN] No prescan aggregator for {key}, creating fresh")
            prescan_agg = CandleAggregator(symbol=...)
        else:
            prescan_agg.symbol = self.CE_SYMBOL if inst == 'CE' else self.PE_SYMBOL

        # Attach listener to the EXISTING aggregator (which already has OHLC data)
        prescan_agg.add_listener(lambda e, c, i=inst: self._on_candle_event(i, e, c))
        self.components[inst] = {
            'candle_aggregator': prescan_agg,  # <-- SAME object, has pre-collected data
            'strategy': RedCandleHighBreak(...),
            'position_manager': PositionManager(...),
            'trade_logger': TradeLogger(...),
            ...
        }

    self._prescan_aggregators.clear()  # discard non-selected aggregators
    self._prescan_keys = None  # reconnect will subscribe only to 2 keys
```

**Key insight:** The `CandleAggregator` object in `_prescan_aggregators` is the SAME object that gets injected into `components[inst]['candle_aggregator']`. It doesn't lose its collected candle history. The listener for broadcasting is attached only after injection (prescan aggregators don't broadcast — no `_on_candle_event` is subscribed until finalize).

### 3.4 Message Routing — `on_message()` (lines 375-534)

Both the dict feed path and binary feed path were modified with the same routing logic:

```python
for instrument_key, feed_data in feeds.items():
    inst_type = None
    is_prescan = self._prescan_aggregators and instrument_key in self._prescan_aggregators

    if self.components and instrument_key == self.CE_KEY and 'CE' in self.active_instruments:
        inst_type = 'CE'
    elif self.components and instrument_key == self.PE_KEY and 'PE' in self.active_instruments:
        inst_type = 'PE'
    elif not is_prescan:
        continue

    # ... extract ltp, timestamp, ohlc_list (unchanged) ...

    if ohlc_list:
        if inst_type:
            self.process_ohlc_candles(inst_type, ohlc_list, feed_time=timestamp)
        elif is_prescan:
            self._update_prescan_ohlc(instrument_key, ohlc_list, feed_time=timestamp)

    if inst_type:
        self.process_tick(inst_type, ltp, timestamp)
```

**Three routing cases:**

| State | `inst_type` | `is_prescan` | Action |
|---|---|---|---|
| Pre-finalize, prescan key | `None` | `True` | OHLC → `_update_prescan_ohlc()`, ticks ignored |
| Post-finalize, selected key | `'CE'`/`'PE'` | `False` (aggregators cleared) | OHLC → `process_ohlc_candles()`, ticks → `process_tick()` |
| Post-finalize, non-selected key | `None` | `False` | Skipped entirely (`continue`) |

After finalize: `_prescan_aggregators` is cleared → empty dict → falsy → `is_prescan = False` for ALL keys. Only the 2 selected keys (which match `CE_KEY`/`PE_KEY`) get processed.

### 3.5 WebSocket Subscription — `on_open()` (lines 536-554)

```python
def on_open(self):
    self.running = True
    print(f"WebSocket connected")
    time.sleep(2)
    try:
        if self._prescan_keys:
            self.streamer.subscribe(self._prescan_keys, "full")
            print(f"Subscribed to {len(self._prescan_keys)} pre-subscribe instruments")
        elif self.streamer:
            keys_to_subscribe = []
            if 'CE' in self.active_instruments:
                keys_to_subscribe.append(self.CE_KEY)
            if 'PE' in self.active_instruments:
                keys_to_subscribe.append(self.PE_KEY)
            self.streamer.subscribe(keys_to_subscribe, "full")
            print(f"Subscribed to instruments")
    except Exception as e:
        print(f"Subscription error: {e}")
```

After `finalize_selection()`: `self._prescan_keys = None` → falls through to `elif` → subscribes only to CE_KEY and PE_KEY. This ensures reconnects don't re-subscribe to all 200 keys.

### 3.6 Cleanup — `close()` (lines 612-620)

```python
def close(self):
    self._stop_requested = True
    self.running = False
    if self.streamer:
        self.streamer.disconnect()
    for inst in self.active_instruments:
        comp = self.components.get(inst)
        if comp:
            comp['trade_logger'].close()
```

The `.get(inst)` prevents KeyError during prescan mode (when `self.components` is empty). Prescan aggregators don't hold file handles so they don't need explicit close.

### 3.7 max_reconnect guard (line 608-609)

```python
if reconnect_attempts >= max_reconnect and not self._stop_requested:
    print("Max reconnection attempts reached — giving up")
    for inst in self.active_instruments:
        self.components[inst]['trade_logger'].close()
```

Protected by the same `.get()` pattern — but in practice, if max reconnect is reached and `self.active_instruments` still references `['CE', 'PE']` while `self.components` is empty (prescan mode failed and never finalized), this would error. However, this path is extremely unlikely: reconnection failures during the brief (1-2 min) prescan window would be exceptional.

---

## Fix 4: `backend/scheduler.py` — Path A/B Time-Gated Startup

**File:** `backend/scheduler.py` (447 lines total)

### 4.1 New Method: `get_prescan_keys()` (lines 279-305)

Fetches the option chain and returns all instrument keys within ±500 of spot:

```python
def get_prescan_keys(self):
    try:
        expiry = self.get_expiry()
        spot = self.get_spot()
        chain = self.fetch_chain(expiry)
        keys = []
        for entry in chain:
            strike = int(float(entry.get('strike_price', 0)))
            if abs(strike - spot) > 500:
                continue
            for side in ('call_options', 'put_options'):
                opt = entry.get(side, {})
                if opt:
                    key = opt.get('instrument_key', '')
                    if key:
                        keys.append(key)
        return keys
    except:
        return None
```

This is a simpler version of `fetch_live_strikes()` — it collects keys without checking LTP, because the purpose is just to know WHICH keys to subscribe to, NOT which ones to trade.

### 4.2 Modified `start_streaming()` (lines 307-327)

Now accepts optional `prescan_keys` parameter. When provided, creates DataStreamer in prescan mode:

```python
def start_streaming(self, ce_key=None, pe_key=None, ce_strike=None, pe_strike=None, prescan_keys=None):
    self.current_session = "day"
    self.data_streamer = self.data_streamer_factory(
        session_name="day",
        ce_key=ce_key, pe_key=pe_key,
        ce_strike=ce_strike, pe_strike=pe_strike,
        prescan_keys=prescan_keys,
    )
    threading.Thread(target=self.data_streamer.run, daemon=True).start()
```

### 4.3 Modified `start()` — Path A/B Branch (lines 337-442)

The `start()` method now branches based on `PATH_A_CUTOFF = "09:20"`:

```
                     start()
                        │
            ┌───────────┴───────────┐
        current_time < 09:20    current_time >= 09:20
            │                           │
        PATH A                      PATH B
            │                           │
    1. Wait 09:14:30               Wait 09:15:40
    2. Fetch prescan keys          Fetch live strikes
    3. Start prescan streamer      Start streamer (direct)
    4. Wait 09:15:40                    
    5. Fetch live strikes               
    6. finalize_selection()             
            │                           │
            └───────────┬───────────────┘
                    Watchdog loop
                    until market end
```

**Path A code path:**
```python
if is_path_a:
    prescan_start = (market_start_time - timedelta(seconds=30)).strftime("%H:%M:%S")
    self.wait_until(prescan_start, "Pre-subscribe start")
    
    prescan_keys = self.get_prescan_keys()
    if prescan_keys:
        self.start_streaming(prescan_keys=prescan_keys)
    else:
        is_path_a = False  # fallback to Path B
    
    # Still wait for live selection time
    if current_time_full < live_selection_time:
        self.wait_until(live_selection_time, "Live premium selection")
```

**Finalize (Path A) or start (Path B):**
```python
if is_path_a and self.data_streamer:
    if hasattr(self.data_streamer, '_prescan_aggregators') and not self.data_streamer._prescan_aggregators:
        is_path_a = False  # fallback
    else:
        self.data_streamer.finalize_selection(
            ce_key=strikes['ce_key'], pe_key=strikes['pe_key'],
            ce_strike=strikes['ce_strike'], pe_strike=strikes['pe_strike']
        )

if not is_path_a or not self.data_streamer:
    if is_path_a and self.data_streamer:
        self.stop_streaming()  # clean up the prescan streamer first
    self.start_streaming(
        strikes['ce_key'], strikes['pe_key'],
        ce_strike=strikes['ce_strike'], pe_strike=strikes['pe_strike']
    )
```

The fallback logic ensures that if anything goes wrong in Path A (prescan keys unavailable, aggregators already empty, etc.), the system cleanly falls back to Path B behavior.

---

## Fix 5: `backend/bot_manager.py` — Factory Signature Update

**File:** `backend/bot_manager.py`, method `_bot_loop()` (lines 82-99)

### The Change

The factory closure `create_streamer` was updated to pass `prescan_keys` through to `DataStreamer`:

```python
# BEFORE:
def create_streamer(session_name, ce_key, pe_key, ce_strike=None, pe_strike=None):
    ds = DataStreamer(
        session_name=session_name,
        instruments=instruments,
        ce_key=ce_key, pe_key=pe_key,
        ce_strike=ce_strike, pe_strike=pe_strike,
        live_feed_server=self.live_feed_server,
        bot_manager=self,
        access_token=get_setting("access_token"),
    )

# AFTER:
def create_streamer(session_name, ce_key=None, pe_key=None, ce_strike=None, pe_strike=None, prescan_keys=None):
    ds = DataStreamer(
        session_name=session_name,
        instruments=instruments,
        ce_key=ce_key, pe_key=pe_key,
        ce_strike=ce_strike, pe_strike=pe_strike,
        prescan_keys=prescan_keys,
        live_feed_server=self.live_feed_server,
        bot_manager=self,
        access_token=get_setting("access_token"),
    )
```

Changes:
1. `ce_key`, `pe_key` now default to `None` (they were required positional args before)
2. Added `prescan_keys=None` parameter
3. Passes `prescan_keys=prescan_keys` to `DataStreamer`
4. `self.strikes` is only set when `ce_strike` is truthy (guards against prescan mode where no strikes exist yet)

---

## Detailed Flow: What Happens at Market Open

### Path A (Normal Market Open)

```
Time        Action
─────────────────────────────────────────────────────
09:14:30    scheduler.start() reaches Path A branch
            → wait_until("09:14:30") exits
            → get_prescan_keys() fetches chain, returns ~200 keys
            → start_streaming(prescan_keys=~200 keys)
            → DataStreamer created in prescan mode
            → Thread starts, WebSocket connects
            → on_open(): subscribes to all ~200 keys
            → log: "Pre-subscribe mode: ~200 instruments loaded"

09:15:00    MARKET OPENS
            → Option ticks start flowing
            → on_message() receives feeds for all ~200 keys
            → Prescan keys (not selected yet): OHLC → _update_prescan_ohlc()
            → Ticks ignored (no components yet)
            → ~200 CandleAggregators collect OHLC data

09:15:40    scheduler: wait_until("09:15:40") exits
            → fetch_live_strikes() called
            → Phase 1: collects all candidate keys from chain
            → Phase 2: batch GET /v2/market-quote/ltp for live premiums
            → Phase 3: filters/ranks by live premium
            → Returns {'ce_key': ..., 'pe_key': ..., 'ce_strike': ..., ...}
            
            → finalize_selection() called on DataStreamer
            → Pops CandleAggregator for CE key from _prescan_aggregators
            → Pops CandleAggregator for PE key from _prescan_aggregators
            → Each gets a listener attached
            → Each gets wrapped in a full component (strategy, PM, logger)
            → _prescan_aggregators cleared
            → _prescan_keys set to None

09:15:40+   → on_message() now routes selected keys to components
            → Aggregators already have 0-40s of OHLC data
            → process_tick() begins for selected keys (entry logic)
            → process_ohlc_candles() on existing aggregators
            → strategy.check_entry() can now trigger immediately
```

### Path B (Restart / Mid-Session After 09:20)

```
Time        Action
─────────────────────────────────────────────────────
09:20+      scheduler.start() reaches Path B branch
            → wait_until("09:15:40") — skipped if already past
            → fetch_live_strikes() (same as Path A, uses /v2/market-quote/ltp)
            → start_streaming(ce_key=..., pe_key=...)
            → DataStreamer created normally
            → Thread starts, WebSocket connects
            → on_open(): subscribes to CE_KEY, PE_KEY
            → Components created fresh (no prescan aggregators)
            → First OHLC may be incomplete if mid-candle
```

---

## Edge Cases Handled

| Scenario | Handling |
|---|---|
| `get_prescan_keys()` fails (API error) | `is_path_a = False`, falls back to Path B. Prescan time already waited, normal selection at 09:15:40 proceeds. |
| `finalize_selection` called on empty aggregators | Guard at top of method returns early. Scheduler detects `is_path_a` and `not self.data_streamer._prescan_aggregators` → falls back to Path B (stops prescan streamer, starts fresh one). |
| WebSocket reconnect after finalize | `_prescan_keys = None` → `on_open()` subscribes only to CE_KEY/PE_KEY. No re-subscription to all 200 keys. |
| WebSocket reconnect during prescan | `_prescan_keys` is still truthy → `on_open()` subscribes to all prescan keys again. Data continues flowing to `_prescan_aggregators`. |
| Watchdog fires during prescan mode | `last_tick_time` is empty dict → `tick_times = []` → `if tick_times:` is False → no stale check triggers. Watchdog effectively disabled during the brief prescan window. |
| `close()` called during prescan mode | `self.components` is empty → `for inst in self.active_instruments: comp = self.components.get(inst)` returns None → `.get()` short-circuits. No KeyError. |
| CandleAggregator not found for selected key | `_prescan_aggregators.pop(key, None)` returns None → creates a fresh aggregator (no prescan data for that key — edge case if instrument keys changed between prescan fetch and selection). |
| Path B run where current_time < 09:15:40 | Same as original: `wait_until("09:15:40")` → `fetch_live_strikes()` → `start_streaming()`. No prescan involved. |
| Path B run where current_time > 09:15:40 | Skip wait → `fetch_live_strikes()` → `start_streaming()`. Immediate start. |

---

## Post-Review Updates (Jul 28)

Changes made after code review, before live test:

| Item | Change |
|---|---|
| **Prescan band** | Changed from hardcoded `±500` pts (±10 strikes) to `PRESCAN_STRIKE_RANGE = 80` strikes × `NIFTY_STRIKE_INTERVAL = 50` = `PRESCAN_RANGE_PTS = 4000`. Both `get_prescan_keys()` and `fetch_live_strikes()` use the same constant. Total ~320 keys pre-subscribed (80 CE ↑ + 80 CE ↓ + 80 PE ↑ + 80 PE ↓). |
| **Unsubscribe remaining keys** | `finalize_selection()` now calls `self.streamer.unsubscribe(remaining)` after clearing aggregators. Wrapped in try/except in case SDK version doesn't support it. Frees bandwidth by dropping the ~318 non-selected keys from the WebSocket subscription. |
| **`max_reconnect` guard** | Changed to `self.components.get(inst)` with `.get()` guard (same pattern as `close()`). Prevents KeyError if reconnect limit is hit before `finalize_selection` creates components. |
| **RAW I1 debug print** | Added `[RAW I1] <strike> @ HH:MM:SS O=... H=... L=... C=...` in `_update_prescan_ohlc()`. Prints every prescan OHLC feed before feeding into aggregator. Remove after confirming 09:15 candle has full range in live test. |
| **Constants in scheduler.py** | Added module-level constants: `NIFTY_STRIKE_INTERVAL = 50`, `PRESCAN_STRIKE_RANGE = 80`, `PRESCAN_RANGE_PTS = 4000`. Replaces magic number `500` in both methods. |
| **Duplicated chain-walking refactored** | Extracted shared `_get_chain_candidates(range_pts)` method that fetches expiry → spot → chain → filters by range → returns `[{strike, key, type}]`. Both `get_prescan_keys()` and `fetch_live_strikes()` call it with `PRESCAN_RANGE_PTS`. Eliminates two copies of identical loop logic. `get_prescan_keys()` reduced from 27 lines to 5. |
