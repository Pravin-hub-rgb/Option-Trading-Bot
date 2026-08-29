# Guide: Fix First-Candle OHLC Clipping via Time-Aware Pre-Subscribe

## Context / problem being fixed

At market open, the bot currently:
1. Waits until ~09:15:40 to fetch spot, scan the option chain, and pick CE/PE strikes near ₹100 premium.
2. Subscribes to those two instrument keys for the first time at that point.
3. Because the bot is very likely the **first subscriber of the day** to those specific far-OTM instrument keys, the 09:15 candle it receives is a strict subset of the true full-minute range (bot: H=124.60/L=90.25 vs chart: H=133.00/L=85.60, identical close). This matches the signature of a clipped observation window that starts at subscribe time, not at 09:15:00.

A controlled test subscribing mid-candle at 12:10:30 got a correct full candle — but that instrument almost certainly already had other subscribers earlier in the day, so that test does not rule out first-subscriber clipping specifically at market open.

**This bug is time-dependent.** It only applies to the *first* candle after a *first* subscription of the day for that instrument. It is not expected to occur when the bot is started mid-session (e.g. 2pm for a manual restart/bugfix run), because by then any liquid-enough strike has almost certainly already had other subscribers all day.

**Therefore the fix must also be time-dependent.** Do not change behavior for mid-session starts — that path already works. Only add the new logic for open-time starts.

---

## Decision tree to implement

At bot start (`BotManager.start()` → `_bot_loop()` → scheduler kickoff), determine which path to take **once**, based on current IST time:

```
now = current IST time

if now < MARKET_OPEN_TIME (09:15:00):
    → PATH A: Pre-open wide pre-subscribe flow (new)

elif MARKET_OPEN_TIME <= now < PATH_A_CUTOFF (e.g. 09:20:00):
    → still PATH A, but skip the "wait until 09:14:30" step — pre-subscribe immediately, then
      proceed straight to the existing 09:15:40-style selection logic (or immediately if already past it)

else:  # now >= PATH_A_CUTOFF, e.g. started at 2pm
    → PATH B: existing/current behavior, unchanged. Fetch spot, scan chain, subscribe directly
      to the 2 selected keys immediately (no artificial delay, no wide pre-subscribe — not needed,
      and would just waste an unsubscribe step for no benefit).
```

`PATH_A_CUTOFF` exists as a safety margin — e.g. if the bot is started at 09:17 due to a slow restart, it's arguably still close enough to open that pre-subscribing wide is cheap insurance and worth doing. Pick a value like 09:20:00 or 09:25:00; anything past that, just use Path B. This constant should live next to the existing `MARKET_OPEN_DELAY` constant — find where that's defined (agent: confirm exact file, likely `scheduler.py`) and add `PRE_SUBSCRIBE_CUTOFF` alongside it.

**Do not touch Path B's logic at all.** It is already proven correct by the 12:10:30 test. The only job here is to add Path A as a new branch and route to it only when justified by time.

---

## Path A: Pre-open wide pre-subscribe flow

### Step 1 — ~09:14:30 (or immediately, if already past that but before cutoff)

1. Fetch previous day's close for NIFTY (or current spot if pre-market close isn't available — check what data is actually available from Upstox before 09:15; if previous close isn't fetchable that early, use whatever the existing strike-selection code already uses as its spot reference and widen from there).
2. Compute a strike band: spot ± 50 strikes (50 × 50pt interval = ±2500 points). This is deliberately generous; the cost of extra subscriptions is negligible (~200 instruments total, well under Upstox's 1500–2000 full-mode subscription limit).
3. Build the list of ~100 CE + ~100 PE instrument keys in that band (reuse whatever chain-fetching function already exists for the 09:15:40 scan — do not duplicate it).
4. Subscribe to all ~200 keys via the WebSocket in full mode, **before** market open if possible, so the first tick each of these instruments ever sees on this connection is at/near 09:15:00.
5. For each of these ~200 keys, create **only a `CandleAggregator`** — not a full component (no `RedCandleHighBreak` strategy, no `PositionManager`, no `TradeLogger`). We don't know yet which 2 will be traded, so don't waste per-instrument state on all 200. Keep these aggregators in a dict keyed by instrument key, e.g. `self._prescan_aggregators = {key: CandleAggregator(...), ...}`.
6. Route incoming ticks/OHLC packets for all subscribed keys into `process_ohlc_candles`-equivalent logic that only feeds the matching `CandleAggregator`. (This likely means a lightweight parallel path in `on_message`/`process_ohlc_candles` during the pre-scan phase — or extend the existing dispatch to check `self._prescan_aggregators` in addition to `self.components` until final selection happens.)

### Step 2 — 09:15:40 (unchanged timing, unchanged selection logic)

1. Run the existing premium-scan logic exactly as today to pick CE and PE strikes near ₹100.
2. Look up the selected CE key and PE key in `self._prescan_aggregators`.

   **Case 1 — found (expected, common case):**
   - Reuse the *existing* `CandleAggregator` object for that key (it has already been collecting the full 09:15 candle since before open). Do **not** construct a fresh one.
   - Wrap it into a full component: create `RedCandleHighBreak`, `PositionManager`, `TradeLogger` for it, and assign into `self.components[inst_type]` exactly as `DataStreamer.__init__` does today — but pass in the pre-existing aggregator instead of building a new one.
   - This is the critical step Grok flagged: **the CandleAggregator that collected the correct 09:15 candle must be the same object the strategy reads from.** If a new aggregator is constructed at selection time, all the pre-collected candle history is lost and you're back to square one.

   **Case 2 — not found (rare edge case: selected strike fell outside the ±2500pt band):**
   - Log a warning (e.g. `"[WARN] Selected strike outside pre-subscribed band, falling back to late-subscribe for this key"`).
   - Fall back to exactly today's current behavior for that one key: create a fresh `CandleAggregator` + full component at selection time, same as Path B. This is a known, accepted degradation for a scenario that should be extremely rare given the wide band — not worse than current behavior, just not improved for that one instrument.

3. Unsubscribe from the other ~198 keys (cleanup — not required for correctness since `on_message` already ignores non-matching keys, but keeps bandwidth/logs/tick-counters clean). If unsubscribe adds meaningful complexity, it's fine to leave as a follow-up rather than blocking on it.
4. From this point on, everything proceeds exactly as it does today — `process_tick`, `process_ohlc_candles`, strategy, position manager, all unchanged.

---

## Path B: unchanged existing behavior (for late/mid-session starts)

No changes. Confirm via the time check above that this path is taken whenever `now >= PRE_SUBSCRIBE_CUTOFF`, and leave all existing code in this path untouched.

---

## Files likely touched

| File | Change |
|---|---|
| `scheduler.py` | Add the time-check branch point; add `PRE_SUBSCRIBE_CUTOFF` constant; route to Path A or Path B |
| `upstox/data_streamer.py` | Support constructing `DataStreamer` with a pre-existing `CandleAggregator` per key rather than always building fresh ones in `__init__`; add pre-scan aggregator dispatch in the tick-handling path |
| `core/candle.py` | Unrelated but still-pending fix: remove the `self.current_candle['open'] = open_price` line in the live-candle-update branch (defensive fix, does not affect this bug but is a real bug) |

Agent: confirm the exact structure of `scheduler.py` before implementing — its current contents (specifically where `MARKET_OPEN_DELAY` is defined and how `TradingScheduler.start()` currently sequences strike selection vs. streaming start) haven't been reviewed yet in this conversation, so don't assume field/method names; inspect the file first and adapt the above to its real shape.

---

## Testing / validation checklist

Do **not** treat this as done just because it compiles and runs. Confirm the hypothesis and the fix together:

1. **Keep the raw I1 debug log** (from earlier discussion) active for the first real morning this runs:
   ```python
   for c in i1_candles:
       ts = datetime.fromtimestamp(int(c.get('ts', 0)) / 1000, IST)
       print(f"[RAW I1][{inst_type}] minute_ts={ts.strftime('%H:%M:%S')} "
             f"O={c.get('open')} H={c.get('high')} L={c.get('low')} C={c.get('close')} "
             f"feed_time={feed_time.strftime('%H:%M:%S.%f')[:-3] if feed_time else 'N/A'}")
   ```
2. On the next live morning run: confirm the logged 09:15 candle for the finally-selected CE/PE now matches (or is much closer to) the reference chart, instead of showing the nested-range clipping pattern.
3. Confirm Case 2 (fallback) path does **not** trigger under normal conditions — if it fires often, the ±2500pt band may need reconsideration (unlikely, but verify at least once).
4. Separately, on a manual 2pm test run: confirm Path B still behaves identically to before this change — no regressions to the already-working mid-session path.
5. Confirm unsubscribe (if implemented) doesn't accidentally unsubscribe the 2 selected keys themselves — test with a deliberate log of exactly which keys get unsubscribed vs retained.

---

## Explicit non-goals for this change

- Do not alter `RedCandleHighBreak` strategy logic.
- Do not alter `PositionManager` or trailing SL logic.
- Do not change the 09:15:40 selection timing or premium-scan criteria — those are separately documented as deliberately tuned (see `files/strike selection new logic.md`, `11feb issue.md`).
- Do not apply Path A logic when starting mid-session — this must be strictly time-gated as described above.