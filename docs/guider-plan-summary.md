# Real Trading Mode — Plan Summary for Guider

## What we're building

A Real / Paper trading switch in the existing dashboard. One UI, one toggle. Paper mode keeps doing what it does. Real mode talks to Upstox and places real SL-L orders.

---

## Our Strategy: Red Candle High Break

Not "entry on breach" — it's more specific:

1. Wait for first **red candle** (open > close) after 09:16 → becomes reference candle (high = H)
2. On next candle(s), if `LTP > H` → entry signal. Entry price in paper = H
3. `max_wait_candles` (default 2) — reference expires after this many candles
4. `allow_reference_shift` (default true) — if a newer red candle closes while waiting, shift reference to it, reset counter
5. Initial SL = H - initial_sl_points (default 4)
6. Trailing: 5-pt step (profit ≥ 5 → move SL up 5 pts, never down)
7. Manual SL drag via chart → modify SL
8. Manual close via floating panel → exit at LTP

**Key real-mode difference**: SL-L fills at `H + buffer` (≥ H). Recorded entry price = broker fill price, not H. P&L distribution will differ slightly from paper.

---

## Architecture

```
Frontend:
  AppHeader → Paper | Real toggle
    → Real switch → confirm modal (checkbox "I understand this places real orders")
    → PUT /api/mode {mode: "real", confirm: true}

Backend:
  api_server.py → /api/mode GET/PUT
  bot_manager.py → holds self.mode ("paper" | "real")
    → on start(), check confirm flag
    → build PaperExecutor or LiveExecutor
    → inject into DataStreamer

DataStreamer:
  Candle closed → executor.on_candle_closed(is_red)
    Paper: if red → strategy sets reference (in-memory)
    Live: executor.place_breakout_entry(candle['high'])
  Tick → entry signal → executor.on_entry_filled(fill_price)
    Paper: pm.open_position(entry_price=H)
    Live: pm.open_position(entry_price=fill_price), place SL-L SELL
  Tick → trailing SL moved → executor.on_trailing_sl_update(new_sl)
    Paper: no broker call
    Live: modify_order(sl_order_id, trigger=new_sl)
  Manual SL drag → executor.on_manual_sl(new_sl)
    Paper: pm.set_manual_sl(new_sl)
    Live: modify_order(sl_order_id, trigger=new_sl)
  Manual close → executor.on_manual_close()
    Paper: exit_position(ltp, now, "Manual Close")
    Live: cancel SL order, place MARKET/LIMIT SELL, record on fill via WebSocket
```

---

## Real-mode entry/exit lifecycle (per slot)

```
Candle N closes → red
  → strategy: reference_candle=N, counter=0
  → Live: place SL-L BUY (trigger=N.high, limit=N.high+buffer)
       → entry_order_id stored

Candle N+1 closes:
  - If candle N+1 is red AND allow_reference_shift:
      → strategy: reference shifts to N+1
      → Live: cancel_order(old_entry_id)
      → Live: place SL-L BUY (trigger=N+1.high, limit=+buffer)
  - Else:
      → Live: get_order_status(entry_order_id)
      → Filled:
           → pm.open_position(fill_price=broker_fill_price, ...)
           → place SL-L SELL (trigger=sl, limit=sl-buffer)
           → sl_order_id stored
      → Still pending:
           → cancel_order(entry_order_id)
      → Rejected:
           → log + skip

While in position:
  Tick LTP → pm.update_trailing_sl(ltp)
    → sl_moved → executor.on_trailing_sl_update(new_sl)
    → Live: modify_order(sl_order_id, trigger=new_sl)
  Manual SL drag → executor.on_manual_sl(new_sl)
    → Live: modify_order(sl_order_id, trigger=new_sl)
  Manual close → executor.on_manual_close()
    → Live: cancel SL order, place LIMIT SELL, on fill → exit_position(fill_price)

EOD 15:15:
  → Bot calls kill_switch()
  → cancel all open orders, market/limit exit all positions
EOD 15:25 (hard kill):
  → Force exit all positions at last known LTP
```

---

## Real-mode constraints

- A "newer red candle" can ONLY be known at candle close → reference shift logic runs in `on_candle_closed`, not on ticks
- SL order is **SELL SL-L** (opposite side of entry) with `trigger=sl, limit=sl-buffer`
- Manual SL drag goes through `modify-order` on the live SL order (same path as auto-trailing)
- Manual close places a real exit order; trade is recorded when the exit order fills via PortfolioDataStreamer
- Partial fills: accept the filled qty as position size, cancel the remainder immediately, place SL for filled qty only
- Race condition protection: always re-fetch order status immediately before any cancel or modify

---

## Answers to your Upstox BreakoutTrader integration questions

1. **Language** → Python (existing bot is Python)
2. **Intraday or delivery?** → Intraday, `product = "I"`, `validity = "DAY"`, square off by 15:00
3. **Trailing method?** → Simple 5-pt step — use `trailing_step` from settings, move SL with `max(old_sl, current_ltp - 5)` for CE long positions
4. **Auth/token?** → Reuse existing `access_token` from settings. "Confirm Real Trading" UI checkbox gates the mode switch
5. **Instrument?** → Nifty options, CE + PE, `NSE_FO` segment. `instrument_token` format: `"NSE_FO|<exchange_token>"`

---

## Answers to the 6 follow-up questions

1. **PortfolioDataStreamer vs polling** → **WebSocket + candle-close backup.** Run the order-update WebSocket the whole day. On fill event, immediately set position + place initial SL + cancel remainder if partial. Keep candle-close check as safety net for disconnects.

2. **Partial fills policy** → **Accept partial + cancel remainder.** Treat the filled qty as the real position size. Cancel the unfilled remainder right away. Place the SL only for the filled qty.

3. **Gap risk on entry** → **Wider buffer (2–3 pts) + optional 10s re-price.** Hierarchy:
   - Best: increase `buffer_pts` so the SL-L limit is more likely to fill
   - Good: after trigger, if still unfilled after 10–12s → cancel SL, place a fresh LIMIT closer to current LTP
   - Avoid pure "convert to market after N seconds" — market orders are heavily restricted under SEBI rules

4. **EOD square-off** → **Bot must force exit at 15:15–15:20.** Do not rely on the broker's auto square-off. Hard kill-switch at 15:25 as a final safety net.

5. **GTT trailing vs Manual Modify** → **Manual Modify (Option A).** GTT `trailing_gap` is gap-based, less flexible for candle-based 5-pt step. Manual Modify gives full control and works perfectly with WebSocket fill events. GTT can be added later as an alternative mode.

6. **Manual SL direction protection** → **Hard "never widen SL" rule.** In `trail_sl` and `set_manual_sl`:
   - Long position → `new_trigger = max(old_trigger, calculated_new)`
   - Short position → `new_trigger = min(old_trigger, calculated_new)`
   - This is non-negotiable. A separate "emergency widen" function (with explicit flag) can exist if needed.

---

## Lot size correction

- **Nifty options lot size is 65** (not 75 as in the sample code in the doc). Our settings already have `lot_size = 65` → no change needed.

---

## Final Configuration

| Decision        | Value                                                                        |
| --------------- | ---------------------------------------------------------------------------- |
| Fill detection  | PortfolioDataStreamer (WebSocket) + candle-close backup                      |
| Partial fills   | Accept partial + cancel remainder                                            |
| Gap on entry    | Wider buffer (2–3 pts) + optional 10s re-price                               |
| EOD square-off  | Bot forces exit at 15:15 (kill-switch at 15:25)                              |
| Trailing method | Manual Modify (5-pt step, candle-close based)                                |
| SL direction    | Hard "never widen" rule                                                      |
| Lot size        | 65                                                                           |
| Product         | Intraday `"I"`                                                               |
| Validity        | `"DAY"`                                                                      |
| Buffer          | 2–3 points (configurable `buffer_pts`)                                       |
| Sandbox default | `sandbox=True` for first run                                                 |
| Static IP       | Required from April 2026                                                     |
| Confirm gate    | UI checkbox → `confirm_real_trading` setting                                 |
| Auth            | Reuse existing `access_token`                                                |
| Mode toggle     | Paper \| Real in AppHeader                                                   |
| Real dashboard  | Open orders, fills, ₹ P&L, kill switch                                       |
| Cancel rule     | Pending entry SL-L cancelled on next candle close if not filled              |
| Reference shift | Cancel old SL-L + place new at shifted candle's high (in `on_candle_closed`) |
| Manual SL drag  | `modify-order` on live SL order                                              |
| Manual close    | Cancel SL order + market/limit SELL exit                                     |
| Entry price     | Broker fill price (≥ H + buffer), not H                                      |
| Race protection | Re-fetch order status immediately before any cancel/modify                   |
| Rate limit      | Stay under 10 orders/sec (regular algo)                                      |

---

## Would you like us to ask you for:

1. **PortfolioDataStreamer integration** — exact Python snippet for the order-update WebSocket (subscribing to fills, partial fills, cancels) so we can wire it into the executor
2. **Full `UpstoxBreakoutTrader` class** with PortfolioDataStreamer, partial-fill handling, hard never-widen logic, EOD auto square-off, and the 10-second gap-protection re-price logic included
3. **Option chain helper** to pick ATM/OTM CE/PE automatically from the option chain
4. **GTT version** of trailing SL as an alternative mode (in addition to manual Modify)

Just say the word and I'll paste the exact Python into the doc.

---

## Guider's Second-Round Feedback (incorporated into plan)

### Keep-as-is

- Reference-candle + max_wait + allow_reference_shift logic cleanly in `on_candle_closed`
- Entry price = broker fill price (not H)
- Partial fill policy (accept + cancel remainder + SL for filled qty only)
- Hard "never widen SL" rule
- Race-condition protection
- EOD force exit at 15:15 + hard kill at 15:25
- Lot size 65
- Mode toggle + confirm checkbox gate

### Refinements to apply

1. **Entry buffer default → 2.5 pts.** Current plan said "2–3 pts". Set default to `buffer_pts = 2.5`. Nifty options can jump 3–5 pts/sec on fast breakouts — a 1-pt buffer often leaves the order unfilled.

2. **10–12 second re-price logic (gap on entry).** Add to entry flow:
   - After SL-L triggers, if still unfilled after ~10–12s → cancel the SL-L → place a fresh LIMIT slightly above current LTP.
   - Avoid converting to MARKET — still restricted under SEBI rules.
   - The unfilled order dying naturally on next candle close remains the fallback.

3. **PortfolioDataStreamer is primary, not backup.** WebSocket is the main path for fill detection. Candle-close polling is the safety net for disconnects only. Update the architecture to reflect this.

4. **Manual close → LIMIT exit, not MARKET.** Place LIMIT SELL at LTP – small buffer. Fall back to MARKET only if LIMIT doesn't fill within a few seconds. MARKET from API still carries SEBI restrictions.

5. **Reference shift → sequential cancel then place.** Cancel old entry SL-L first → wait for cancel confirmation → then place new SL-L at new high. Avoid two live entry orders simultaneously.

6. **Track filled_qty permanently.** After partial fill, store `filled_qty` in the position object. All subsequent SL and exit orders use `filled_qty`, never the original requested quantity.

7. **Second "Really go live?" confirmation on first trade each day.** Even after sandbox toggle + confirm checkbox, the first time real mode places an order each trading day should require one extra click.

8. **State machine per slot:** `IDLE → WAITING_ENTRY → IN_POSITION → EXITING`.

9. **When bot stops or mode switches to Paper → immediately cancel all pending entry SL-L orders.**

10. **Log every order_id + status transition with timestamps.** Essential for debugging real fills.

11. **Rate-limit counter.** Simple in-memory counter so we never exceed ~8 calls/sec even under bursty reference shifts.

### Final Configuration (updated)

| Decision          | Value                                                                 |
| ----------------- | --------------------------------------------------------------------- |
| Entry buffer      | **2.5 pts** (default, configurable)                                   |
| Re-price timeout  | **10–12 seconds** after trigger, then LIMIT re-price                  |
| Fill detection    | **PortfolioDataStreamer (primary) + candle-close backup**             |
| Manual close exit | **LIMIT** (at LTP – buffer), fallback to MARKET after a few seconds   |
| Reference shift   | **Sequential**: cancel first → confirm → then place new               |
| Position size     | Track `filled_qty` permanently, use for all subsequent orders         |
| Daily live gate   | Extra "Really go live?" confirmation on first real order each day     |
| State machine     | `IDLE → WAITING_ENTRY → IN_POSITION → EXITING` per slot               |
| Bot stop action   | **Cancel all pending entry SL-L orders** when bot stops or mode flips |
| Order logging     | Every order_id + status transition with timestamps                    |
| Rate limit        | In-memory counter, max ~8 calls/sec                                   |

---

## Partial Fill Handling — Detailed Spec (from guider, round 3)

### Goal

When an SL-L entry order receives a **partial fill**, treat the filled quantity as the real position size, immediately cancel the unfilled remainder, and place the protective SL only for the filled quantity. Never leave a dangling partial order.

### Exact Behaviour

1. **Detection**
   - Primary: PortfolioDataStreamer `order_update` event where `status == "complete"` or `"partially filled"` and `filled_quantity > 0`.
   - Backup: on candle close, call `get_order_details(entry_order_id)` and inspect `filled_quantity` vs `quantity`.

2. **On Partial Fill (or full fill)**

   ```python
   filled_qty = order.filled_quantity          # e.g. 65, 130, 45, etc.
   remaining_qty = order.quantity - filled_qty
   if remaining_qty > 0:
       cancel_order(entry_order_id)            # cancel the unfilled portion
       # Wait for cancel confirmation (or fire-and-forget with log)
   ```

3. **Position Opening**

   ```python
   pm.open_position(
       instrument_token=...,
       side="BUY",                             # or SELL for PE
       quantity=filled_qty,                    # ← use filled_qty, never original
       entry_price=order.average_price,        # broker fill price
       ...
   )
   position.filled_qty = filled_qty            # store permanently
   ```

4. **Initial SL Placement**
   - Place SELL SL-L **only for `filled_qty`**.
   - `trigger = current_sl`
   - `limit = trigger - buffer_pts`
   - Store the new `sl_order_id`.

5. **All Subsequent Orders Use `filled_qty`**
   - Trailing SL modify
   - Manual SL drag
   - Manual close / EOD exit
   - Any re-price logic
     → Always pass `quantity=position.filled_qty`

6. **Edge Cases**
   - **Multiple partials** (rare but possible): keep accumulating `filled_qty` until the order reaches terminal state or is cancelled. Only open the position once the first fill arrives, then update quantity if more fills come in before cancel.
   - **Cancel fails**: log loudly and retry once. If still fails, treat the remaining quantity as risk and place SL for the full original size as fallback (safety).
   - **Fill arrives after we already cancelled**: WebSocket may deliver a late fill event. Ignore it if position is already open with a different order_id, or reconcile quantity if it belongs to the same order.

7. **Logging (mandatory)**
   ```
   [PARTIAL]  order_id=... requested=65 filled=45 remaining=20 average_price=248.75
   [CANCEL]   remaining qty cancelled
   [POSITION] opened with qty=45 @ 248.75
   [SL]       placed SELL SL-L for qty=45 trigger=...
   ```

### Code-level responsibilities

| Component             | Responsibility                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------- |
| PortfolioDataStreamer | Emit fill/partial events with `filled_quantity` + `average_price`                              |
| LiveExecutor          | On fill event → cancel remainder → open position with `filled_qty` → place SL for `filled_qty` |
| PositionManager       | Store and expose `filled_qty`; never use original requested qty after open                     |
| on_candle_closed      | Safety net: if entry order still shows partial + pending, force the same cancel + open logic   |

### Why this is non-negotiable

- Leaving the remainder open can produce a second fill at a much worse price.
- Using original quantity for the SL would over-hedge and create unwanted risk.
- Tracking `filled_qty` permanently keeps trailing, manual SL, and EOD exit consistent.
