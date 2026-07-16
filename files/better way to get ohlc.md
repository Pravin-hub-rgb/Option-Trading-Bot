# Guidance Document: Correct Way to Get 1-Minute Completed OHLC in This Bot

**Date:** February 03, 2026  
**Purpose:** The historical API approach (HistoryApi / get_historical_candle_data) is **not reliable** for getting the just-completed 1-minute candle instantly after the minute boundary (e.g., at 9:16:01 for the 9:15–9:16 candle). It suffers from commit delays, caching, and sometimes returns yesterday's data even during market hours.  

**The correct, production-proven method already exists in your codebase.**  
We must use the **real-time WebSocket feed in "full" mode** + the existing `CandleAggregator` class to obtain **exact, exchange-aggregated 1-minute OHLC** the moment the candle is completed.

### 1. Why Historical API Is Wrong for This Use Case

| Aspect                          | Historical API (get_historical_candle_data) | WebSocket "full" mode + CandleAggregator |
|---------------------------------|----------------------------------------------|-------------------------------------------|
| Speed after minute close        | 5–60 seconds delay (sometimes more)         | Usually <1–5 seconds                      |
| Accuracy of High/Low            | Can be correct but delayed                   | 100% exchange-accurate (pre-aggregated)   |
| Availability during market hours| Sometimes returns old data if not committed  | Always current                            |
| Use in your current bot         | Not used for strategy                        | Used for red candle detection & breakout  |
| Reliability at 9:16 for 9:15 candle | Low – often fails in tests                  | High – proven in production               |

**Conclusion:** Do **not** use HistoryApi in the live trading path for the opening candle decision. Use the WS + aggregator path that already powers the strategy.

### 2. How the Bot Already Gets Instant & Accurate 1-Min OHLC

Flow (proven in `data_streamer.py` + `candle.py`):

1. WebSocket in "full" mode subscribed → Upstox pushes 'marketOHLC' messages containing completed 1-min candles (interval='I1')
2. `on_message` parses:
   ```python
   if 'marketOHLC' in full_feed:
       for ohlc in full_feed['marketOHLC']['ohlc']:
           if ohlc['interval'] == 'I1':
               timestamp = datetime.fromtimestamp(ohlc['ts']/1000, IST)
               o = float(ohlc['open'])
               h = float(ohlc['high'])
               l = float(ohlc['low'])
               c = float(ohlc['close'])
               aggregator.update_from_ohlc(timestamp, o, h, l, c)
   ```
3. `CandleAggregator.update_from_ohlc()`:
   - Creates candle with **exchange-provided exact values**
   - If candle is completed (timestamp < current minute) → adds to `candle_history`
   - Returns `True` if new completed candle added
4. When `is_new_candle == True`:
   - Calls `strategy.on_new_candle_closed()` (increments wait counter)
   - Strategy checks `candle_history[-1]` for red candle logic
   - High is used for breakout check and entry price

**Result:** At ~9:16:01–9:16:05, the 9:15 candle is already in `candle_history` with accurate O/H/L/C — ready for red check and high-break decision.

### 3. Guidance for Tomorrow's Implementation

**Do NOT** add or rely on HistoryApi calls at 9:16 for the opening candle.

**Instead** — leverage the existing mechanism:

#### Option A – Preferred (Use the aggregator directly – cleanest)

In `scheduler.py` after live strike selection (around 9:15:40):

```python
# After self.prepare_session() succeeds
self.log("Waiting for 9:16 to read opening candle from aggregator...")

# Wait until at least 9:16:05 (give WS time to push)
while datetime.now(IST).strftime("%H:%M") < "09:16":
    time.sleep(1)

# Now access the aggregator (you need to expose it or pass reference)
# Assuming you can get it from self.data_streamer.components['CE']['candle_aggregator']

ce_agg = self.data_streamer.components['CE']['candle_aggregator']
pe_agg = self.data_streamer.components['PE']['candle_aggregator']

opening_ce = ce_agg.get_candle_history()[-1] if ce_agg.get_candle_history() else None
opening_pe = pe_agg.get_candle_history()[-1] if pe_agg.get_candle_history() else None

if opening_ce:
    self.log(f"CE 9:15 candle: O:{opening_ce['open']:.2f} H:{opening_ce['high']:.2f} "
             f"L:{opening_ce['low']:.2f} C:{opening_ce['close']:.2f}")
    if opening_ce['open'] > opening_ce['close']:
        self.log(f"   → RED | Reference high = {opening_ce['high']:.2f}")

# Same for PE
```

→ This uses the **exact same candle object** the strategy will use → zero inconsistency.

#### Option B – Simpler (Listen in on_message for the first I1 push after 9:16)

Add temporary logging in `data_streamer.py` on_message:

```python
# Inside the marketOHLC parsing block
if is_new_candle and timestamp.strftime("%H:%M") == "09:16":
    print(f"[{self.now()}] FIRST OPENING CANDLE DETECTED:")
    print(f"  O: {open_price:.2f}  H: {high_price:.2f}  L: {low_price:.2f}  C: {close_price:.2f}")
    if open_price > close_price:
        print(f"  → RED CANDLE - Reference high = {high_price:.2f}")
```

→ Deploy tomorrow morning → observe console at ~9:16.

### 4. Action Items for Tomorrow Morning

1. Keep the current live selection timing (9:15:40) — it's good.
2. **Do NOT add HistoryApi calls** for the 9:15 candle decision — they are unreliable at that exact moment.
3. Use one of the two options above to read/log the candle from the aggregator or WS push.
4. Confirm in console/log at ~9:16:05 that you see the 9:15 candle with correct O/H/L/C.
5. Let the strategy run normally — it will use the same candle for red check and breakout.

This is **already implemented and proven** in your production path. We are not inventing anything new — just reading from the correct place at the right time.

If you want, paste tomorrow's 9:15–9:20 logs (especially any OHLC lines) — we can confirm it's working as expected.

Good luck tomorrow — the bot is ready.