# Bug #2 Family — Feed Disconnect / Reconnect / Queue Handling

Guidance doc for fixing the reconnect and delivery issues found in `data_streamer.py`,
`scheduler.py`, and `live_feed_server.py`. Every claim below was verified line-by-line
against the actual uploaded files before being written down here.

---

## Summary table

| # | Issue | File / Lines | Severity | Status |
|---|-------|--------------|----------|--------|
| 2a | `on_close` kills `run()` — reconnect logic never fires for mid-session drops | `data_streamer.py:442`, `:455-483` | 🔴 Critical | Confirmed, fix below |
| 2b | No tick-gap / slippage handling on reconnect | `data_streamer.py:177-191` (`process_tick`) | 🟠 High | Confirmed, fix below |
| 2c | No health watchdog — scheduler doesn't detect a dead streamer | `scheduler.py:326` | 🟠 High | Confirmed, fix below |
| 2d | `live_feed_server.py` treats ticks and trade events identically — both silently dropped on `QueueFull` | `live_feed_server.py:77-81` | 🟠 High | Confirmed, fix pending (separate from this doc's scope — see note at end) |

---

## 2a — `on_close` silently kills the reconnect loop

### Root cause
`close()` (intentional stop) and `on_close()` (library callback fired on any disconnect)
both do the exact same thing: `self.running = False`. `run()` has no way to distinguish
"user pressed stop" from "connection dropped." Either way the inner `while self.running:`
loop exits *without raising an exception*, so the `except Exception:` block that contains
all the actual reconnect/backoff logic (`reconnect_attempts`, `base_delay`, `max_reconnect`)
never runs. The thread just dies.

### Fix
Introduce a second, explicit flag that means "the user actually asked to stop" — separate
from `self.running`, which now only means "the socket is currently connected."

```python
# __init__
self.running = True
self._stop_requested = False   # NEW

def on_close(self, *args):
    print(f"WebSocket closed")
    self.running = False   # unchanged — "socket is down right now"

def close(self):
    self._stop_requested = True   # NEW — the only place this gets set
    self.running = False
    if self.streamer:
        self.streamer.disconnect()
    for inst in self.active_instruments:
        self.components[inst]['trade_logger'].close()

def run(self):
    configuration = upstox_client.Configuration()
    configuration.access_token = self._access_token

    reconnect_attempts = 0
    max_reconnect = 20
    base_delay = 2

    while not self._stop_requested and reconnect_attempts < max_reconnect:
        try:
            self.running = True
            self._connect_ws(configuration)

            while self.running and not self._stop_requested:
                time.sleep(1)

            if self._stop_requested:
                break  # intentional stop — exit cleanly, no reconnect attempt

            # loop exited because on_close fired — this is a real disconnect
            reconnect_attempts += 1
            delay = min(base_delay * reconnect_attempts, 30)
            print(f"Disconnected — reconnecting in {delay}s (attempt {reconnect_attempts}/{max_reconnect})")
            time.sleep(delay)

        except Exception as e:
            reconnect_attempts += 1
            delay = min(base_delay * reconnect_attempts, 30)
            print(f"Connection failed (attempt {reconnect_attempts}/{max_reconnect}): {e}")
            time.sleep(delay)

    if reconnect_attempts >= max_reconnect and not self._stop_requested:
        print("Max reconnection attempts reached — giving up")
        for inst in self.active_instruments:
            self.components[inst]['trade_logger'].close()
        self.running = False  # so 2c's watchdog can see the streamer is dead
```

**Net effect:** a mid-session drop now actually goes through the same backoff/retry path
as an initial connection failure, instead of quietly returning and leaving the thread dead.

---

## 2b — No gap/slippage handling on reconnect

### The industry standard (not a fixed number)
There's no single universal "gap threshold" — it depends on asset class and feed type.
The general pattern real systems use:

- **Threshold should be relative to your normal tick interval**, not a hardcoded constant.
  If ticks normally arrive every ~200-500ms, a gap is usually "no tick for 3-10x that
  interval" — derive this from your own feed's real tick-gap distribution rather than
  guessing.
- **Options tick data is naturally sparse** — LTP only updates on an actual trade print,
  so a quiet illiquid strike can go seconds between ticks even on a perfectly healthy
  connection. A time-only threshold will produce false positives.
- **Time + price-distance together is the robust signal**, not time alone. A 3-second gap
  that moved 0.10 past SL isn't a real slippage event. A 3-second gap that jumped 5 points
  past SL is.
- **Prefer ground-truth connection state over inferred gaps where possible.** Since
  `self.running` already flips false/true around actual disconnects (via `on_close`/
  `on_open`), that's a cleaner signal for "this was a real outage" than inferring purely
  from a timestamp delta.
- **How a real broker fills a stop order**: a stop-loss isn't a promise of "you get exactly
  your SL price." It's dormant until price touches the trigger, then converts to a market
  order and fills at the next available price. If price gaps straight through your SL
  (exactly what a disconnect causes), you get filled at the gapped price — worse than SL.
  That difference is **slippage**, and it should be recorded, not hidden by silently
  substituting the "clean" SL price.

### Fix
Do **not** override the exit price. Keep it as the real tick price (`ltp`) — exactly like
a live fill would be. Only add: gap detection + slippage annotation in the exit reason, so
you can tell "clean SL hit" apart from "gap slippage" during review.

```python
# __init__ — per-instrument last tick timestamp (also feeds 2c's watchdog)
self.last_tick_time = {inst: None for inst in self.active_instruments}

GAP_THRESHOLD_SECONDS = 5  # placeholder — derive from your real tick-gap distribution first

def process_tick(self, inst_type, ltp, timestamp):
    comp = self.components[inst_type]
    self.tick_count[inst_type] += 1

    prev_tick_time = self.last_tick_time[inst_type]
    self.last_tick_time[inst_type] = timestamp
    gap_seconds = (timestamp - prev_tick_time).total_seconds() if prev_tick_time else 0

    candle_history = comp['candle_aggregator'].get_candle_history()

    if comp['position_manager'].is_in_position():
        if comp['position_manager'].check_exit(ltp) and not comp.get('_exiting', False):
            comp['_exiting'] = True
            try:
                is_gap = gap_seconds > GAP_THRESHOLD_SECONDS
                if is_gap:
                    sl_price = comp['position_manager'].get_current_sl()
                    slippage = sl_price - ltp  # positive = worse fill than SL
                    reason = f"Trailing SL Hit — gap {gap_seconds:.0f}s, slippage {slippage:.2f}"
                    print(f"[{inst_type}] GAP EXIT: SL was {sl_price:.2f}, filled at {ltp:.2f} "
                          f"(slippage {slippage:.2f}) after {gap_seconds:.0f}s gap")
                else:
                    reason = "Trailing SL Hit"
                self.exit_position(inst_type, ltp, timestamp, reason)
                self._broadcast_tick(inst_type, ltp, timestamp)
            finally:
                comp['_exiting'] = False
            return

            # ... rest of process_tick unchanged (trailing SL update / entry check) ...
```

No changes needed in `position_manager.py` — `close_position(exit_price, exit_time)`
already just takes whatever price it's given.

**Before deploying:** log `gap_seconds` for a normal session first and look at the
distribution before picking `GAP_THRESHOLD_SECONDS` — don't ship the placeholder value.

---

## 2c — No health watchdog in `scheduler.py`

### Root cause
The market-end wait loop (`scheduler.py:326-327`) only checks `self.is_running` and the
clock. It never looks at whether the streamer thread is actually alive or still receiving
data:

```python
while self.is_running and self.get_current_time_str() < market_end:
    time.sleep(60)  # Check every minute without logging
```

If `data_streamer.run()` dies silently (pre-2a-fix) or exhausts reconnect attempts
(post-2a-fix), this loop has no way to know — it just sleeps until market close.

### Fix
Uses the `last_tick_time` dict added in the 2b fix — no extra plumbing needed.

```python
STALE_THRESHOLD = timedelta(seconds=90)  # tune to your normal tick cadence

while self.is_running and self.get_current_time_str() < market_end:
    time.sleep(30)
    ds = self.data_streamer
    if ds:
        tick_times = [t for t in ds.last_tick_time.values() if t is not None]
        if tick_times:
            newest = max(tick_times)
            gap = datetime.now(IST) - newest
            if gap > STALE_THRESHOLD:
                self.log(f"🔴 No ticks for {gap.seconds}s — streamer may be dead")
                if not ds.running:
                    self.log("🔴 Streamer confirmed dead — stopping session")
                    break  # falls through to stop_streaming() below
```

This bounds the "zombie position" window to `STALE_THRESHOLD` instead of "until market
close," and gives you an early, deliberate shutdown path instead of a silent one.

---

## 2d — `live_feed_server.py` queue (noted for completeness, separate fix)

Confirmed earlier: `_put_message()` (lines 77-81) drops both raw ticks and trade
entry/exit events identically on `QueueFull`. Tick drops are harmless (UI-only); a
dropped trade-exit event leaves the frontend stale for that slot until refresh.

This is a **separate, self-contained fix** (two queues or a priority/guaranteed-delivery
path for trade events vs. best-effort for ticks) and doesn't depend on 2a/2b/2c. Flagging
it here so it isn't lost, but it's out of scope for this reconnect-focused doc.

---

## Suggested order of implementation

1. **2a** first — everything else (2b, 2c) assumes `run()` actually attempts to reconnect
   instead of dying silently.
2. **2b** next — cheap to add once 2a is in, and it also produces the `last_tick_time`
   data that 2c needs.
3. **2c** — watchdog, depends on 2b's timestamp tracking.
4. **2d** — independent, can be done any time, ideally before going live with real capital.

Test 2a specifically by killing your network mid-session (not just at startup) and
confirming the bot reconnects and resumes rather than dying quietly.

## Verification

`✅ Verified Jul 28 — live market test passed`

| Test | Result |
|------|--------|
| Mid-session disconnect #1 (09:22:48) | Reconnected in 2s ✅ |
| Mid-session disconnect #2 (09:45:18) | Reconnected in 3s ✅ |
| Stop button (10:03:19) | Clean exit, no reconnect attempt ✅ |
| Watchdog false trigger | None — 90s threshold not hit ✅ |
| Gap tracking | Exit reasons logged correctly ✅ |

All three fixes (2a/2b/2c) merged to `main` on Jul 28.