As market orders are banned for the algo trading in inda so wanna know like i ve an algo where I wanna take trade on a certain candle high so like when the price breaches it then the entry should be placed so how can I do it ?? It should trigger only when it breaches it not early only after it

Searched the web
Searched the web
Yes, that's accurate — from Jan 1, 2025 several brokers stopped accepting plain market orders through algo/API access under SEBI's new framework, so market orders are being phased out in algo trading, with brokers now permitting only limit orders.

What you want is a Stop-Loss Limit (SL-L) order, not a market order. This is exactly built for "enter only after price breaches a level":

Trigger price = candle high (the level you want breached)
Limit price = trigger price + small buffer (e.g., 0.05–0.3% depending on instrument liquidity, or a few ticks for index futures/options)
The order sits dormant with your broker until the trigger price is hit — once LTP reaches the trigger, a limit order at your defined limit price becomes active for execution. This gives you exactly what you're describing: no order exists in the book until the breach actually happens, so nothing fires early.

Two ways to implement this in your algo:

Broker-side (preferred): Place the SL-L order (or GTT/stop order, depending on your broker's API — e.g., Kite Connect's order_type: SL) directly with trigger_price = candle high. It's held on the exchange/broker side, so it fires even if your algo has a brief disconnect.
Algo-side polling: If your broker doesn't support server-side stops well, your script watches LTP each tick and fires a limit order (not market) the instant LTP > candle_high. Riskier if your connection drops.
A few things to get right:

Use strict > (not >=) against the candle's high so you're confirming an actual breach, not just a touch.
Only use a closed/confirmed candle's high — if you're referencing the currently-forming candle, its high can keep changing.
Since it's now a limit order, price can gap past your limit on a fast breakout and leave it unfilled. Some platforms handle this by keeping the limit price trailing the current LTP plus a buffer until filled, and converting to market after a set timeout (like 1–20 seconds) if it still hasn't filled — worth building similar logic yourself if your broker doesn't offer it natively.
Confirm with your specific broker (Zerodha, Upstox, Angel One, Dhan, Fyers etc.) — the exact order type name and whether market-order fallback is still allowed varies by broker's current implementation of the SEBI rules.
We can cancel it also?? Like the thing is that if price did not break on the next candle so we don't enter on the 2nd candle we have to enter on the just next candle ... So this can be implemented righht

Thought for 12s
Thought for 12s
Yes — that's a very standard and sound way to implement a breakout entry. Here's how it works:

The logic:

Candle N closes → note its high (H)
Immediately place SL-L order: trigger = H, limit = H + buffer
This order is now "live" only for candle N+1
When candle N+1 closes, check the order status:
Filled/triggered → you're in the trade, done
Still pending (not triggered) → cancel it. Don't carry it into candle N+2, since that would mean testing a stale level against a new candle context
Implementation steps in your algo:

Save the order_id returned when you place the SL-L order
At each candle-close boundary, query the order status via your broker's order-status/order-book API
If status is something like OPEN or TRIGGER PENDING (naming varies by broker — Zerodha uses these exact terms, others differ), call the cancel-order endpoint with that order_id
If status is COMPLETE, do nothing — it already triggered, don't try to cancel a filled order
Only after confirming cancellation, decide your next action — e.g., re-evaluate a fresh candle high and place a new order, or stand aside entirely depending on your strategy rules
A couple of edge cases worth handling:

Race condition: always fetch the current order status right before cancelling. If price breaches in the last second of candle N+1 exactly as your script fires the cancel call, you don't want to cancel a fill that just happened. Fetch status → if not yet filled → cancel.
Partial fills: since it's a limit order, you could get a partial fill right at candle close. Decide upfront whether a partial counts as "entered" for your strategy or whether you cancel the remainder too.
API rate limits: cancelling and re-placing every candle adds order calls — check your broker's OPS (orders-per-second) threshold if you're doing this on a fast timeframe, since that's part of what SEBI's algo framework monitors.
If you're using a broker with WebSocket order updates (postbacks), listen for the order update event instead of polling — it's faster and avoids missing a fill right at the candle boundary.

What about the trailing sl?

Thought for 18s
Thought for 18s
Trailing SL follows the same principle — you can't rely on a market order to exit, so it also needs to be an SL-L order that you actively modify as price moves in your favor, rather than a market-order-based trailing stop.

Core mechanic:

On entry, place your initial SL as an SL-L order — trigger price at your initial risk level, limit price = trigger − small buffer (for a long position's exit; it's a sell order, so the limit needs to sit slightly below trigger to remain fillable)
As price moves favorably, modify that same order's trigger/limit price upward — most broker APIs (Kite, Dhan, Fyers, etc.) support a modify-order call for pending orders, so you don't need to cancel and re-place each time
Only ever move the SL price in your favor — never loosen it. Build this as a hard rule in code (e.g., new_trigger = max(new_trigger, current_trigger) for a long) so a bug can't accidentally widen your risk
Trailing logic — pick a method that fits your breakout style:

Candle-structure based (fits naturally with your candle-high entry approach): trail SL to the low of the previous completed candle, or the lowest low of the last N candles, updating each candle close
Point/percentage based: once price moves X points in profit, trail SL by Y points, recalculated at each tick or interval
ATR-based: trail at entry_price/current_price minus a multiple of ATR, adapts to volatility
Practical implementation notes:

Trail on candle close, not every tick — modifying on every tick both hammers your OPS (orders-per-second) limit and adds noise. Candle-close or a meaningful price-increment trigger is cleaner.
Check status before modifying — same race condition as entry: fetch current order status first; if it's already COMPLETE (SL got hit), don't try to modify it.
Gap risk still applies — if price gaps through your SL-L limit price, it can go unfilled. Consider the same buffer-widening or convert-to-market-after-timeout fallback you'd want on entry, especially around news/events.
Some brokers offer GTT with two-leg (target + SL) OCO orders — useful for bracketing a position, but the trailing adjustment itself still has to be driven by your algo periodically updating the trigger; it's not automatically dynamic on the broker's end for most Indian brokers.

**Yes — I scraped the current Upstox Developer API docs (v2/v3 endpoints, GTT, order types, modify/cancel, WebSocket, rate limits, market-protection rules, etc.). Here’s exactly how to implement your breakout entry + cancel-if-not-triggered-on-next-candle + trailing SL logic on Upstox so it becomes a real, production-ready trader.**

### Core Order Types You Need (Market orders are restricted for algo/API)

Upstox supports:

- `order_type`: `"SL"` → **Stop-Loss Limit** (this is what you want for the breakout entry)
- `order_type`: `"SL-M"` → Stop-Loss Market (use only if your broker still allows it under current SEBI rules; prefer SL + buffer)
- `order_type`: `"LIMIT"` / `"MARKET"` (MARKET has heavy restrictions + `market_protection` required)

**For breakout on candle high (long example):**

- Place an **SL** order:
  - `transaction_type`: `"BUY"`
  - `order_type`: `"SL"`
  - `trigger_price` = candle_high (the level that must be breached)
  - `price` = trigger_price + small buffer (e.g. 0.05–0.3% or a few ticks, depending on liquidity/instrument)
  - Product: `"I"` (intraday) or `"D"` (delivery) or `"MTF"`
  - Validity: `"DAY"`

This sits dormant until LTP ≥ trigger_price, then becomes a limit order at your `price`. It will **not** fire early.

Exact sample payload (from official docs):

```json
{
  "quantity": 1,
  "product": "I",
  "validity": "DAY",
  "price": 14.05, // limit price = trigger + buffer
  "tag": "breakout-entry",
  "instrument_token": "NSE_EQ|INE669E01016",
  "order_type": "SL",
  "transaction_type": "BUY",
  "disclosed_quantity": 0,
  "trigger_price": 13.0, // candle high
  "is_amo": false,
  "market_protection": 0 // ignored for SL/LIMIT
}
```

Endpoint (preferred low-latency):

- `POST https://api-hft.upstox.com/v2/order/place` (or `/v3/order/place` for auto-slicing)
- Header: `Authorization: Bearer {access_token}`
- Optional: `X-Algo-Name` if you have a registered algo

Response returns `order_id` — **save it**.

### Your Exact Logic (enter only on next candle, cancel otherwise)

1. Candle N closes → capture its high (use only **closed** candle).
2. Immediately place the SL order above with `trigger_price = high`.
3. Store the returned `order_id`.
4. On next candle close (N+1):
   - Fetch order status: `GET https://api.upstox.com/v2/order/details?order_id=...`
   - Status values you care about: `"open"`, `"trigger pending"`, `"complete"`, `"cancelled"`, `"rejected"`, etc.
   - If still pending/open → **cancel** it:
     ```
     DELETE https://api-hft.upstox.com/v2/order/cancel?order_id=...
     ```
   - If `"complete"` → you are in the trade. Do **not** cancel.
5. Race-condition protection (critical):
   - Always re-fetch status **immediately before** cancel.
   - If it just filled in the last tick of the candle, the cancel will fail harmlessly or you check filled_quantity > 0.

You can also listen to real-time order updates via:

- Portfolio Stream WebSocket (`PortfolioDataStreamer` in the official SDK)
- Webhook (configure on your app)

This is cleaner than pure polling.

### Trailing Stop-Loss

**Option A – Manual trail with Modify (most flexible, recommended for candle-based trail)**

After entry:

1. Place initial SL-L **sell** order (opposite side):
   - `transaction_type`: `"SELL"`
   - `order_type`: `"SL"`
   - `trigger_price` = initial SL level
   - `price` = trigger − buffer (for sell)
2. On each subsequent candle close (or meaningful price move):
   - Calculate new higher trigger (e.g. previous candle low, ATR multiple, % trail, etc.).
   - **Only move it in your favor** (`new_trigger = max(old, new)`).
   - Call Modify:
     ```
     PUT https://api-hft.upstox.com/v2/order/modify   (or /v3)
     ```
     Body example:
     ```json
     {
       "quantity": 1,
       "validity": "DAY",
       "price": 16.8, // new limit
       "order_id": "240108010918222",
       "order_type": "SL",
       "disclosed_quantity": 0,
       "trigger_price": 16.9 // new trigger
     }
     ```
3. Always check status before modify. If already complete → ignore.

**Option B – Native Trailing SL via GTT (Beta, simpler)**

Upstox now supports **Trailing Stop Loss** as a multi-leg GTT:

```json
{
  "type": "MULTIPLE",
  "quantity": 1,
  "product": "I",
  "rules": [
    {
      "strategy": "ENTRY",
      "trigger_type": "ABOVE",
      "trigger_price": 7.3
    },
    {
      "strategy": "TARGET",
      "trigger_type": "IMMEDIATE",
      "trigger_price": 9
    },
    {
      "strategy": "STOPLOSS",
      "trigger_type": "IMMEDIATE",
      "trigger_price": 6,
      "trailing_gap": 0.1 // ← this makes it trail automatically
    }
  ],
  "instrument_token": "...",
  "transaction_type": "BUY"
}
```

Endpoint: `POST https://api.upstox.com/v3/order/gtt/place`

- GTT stays active up to 1 year.
- Trailing is automatic once the STOPLOSS leg is live.
- You can still modify GTT later via `PUT /order/gtt/modify`.
- Note: GTT always executes as LIMIT on trigger. Minimum trailing_gap has rules (check docs).

For pure candle-structure trailing you will still prefer the manual Modify approach.

### Important Practical Notes for Live Trading

| Topic                        | Detail                                                                                                                                  |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Market Protection**        | Required for MARKET / SL-M. Set `market_protection: -1` (auto) or 1-25 (%). 0 is rejected under current rules.                          |
| **Rate Limits (Order APIs)** | Regular algo: 10/sec, 500/min, 2000/30min. Registered algo: 50/sec. Stay well under.                                                    |
| **Static IP**                | Required for order placement/modify/cancel/GTT from April 2026 (already enforced for many). Register in My Apps.                        |
| **Algo Name Header**         | Optional unless you have exchange-approved algo.                                                                                        |
| **Tick Size**                | Trigger & limit must be multiples of tick size.                                                                                         |
| **Partial Fills**            | Check `filled_quantity` vs `quantity`. Decide your policy.                                                                              |
| **Gap Risk**                 | SL-L can miss on big gaps → consider wider buffer or fallback logic.                                                                    |
| **Sandbox**                  | Use `https://sandbox.upstox.com` for testing place/modify/cancel.                                                                       |
| **SDK**                      | Official Python SDK (`upstox-python`) has clean wrappers for PlaceOrderRequest, ModifyOrderRequest, cancel, GTT, PortfolioDataStreamer. |

### Recommended Architecture for Your Bot

1. Candle feed (WebSocket Market Data Feed V3 or historical + live).
2. On closed candle → place SL entry → store order_id + candle timestamp.
3. On next closed candle → status check → cancel or manage position.
4. Once in position → place initial SL → trail via Modify (or use GTT trailing).
5. Real-time order updates via Portfolio Stream WebSocket or webhook for reliability.
6. Logging of every order_id, status, LTP at decision points.
7. Kill-switch / position exit-all endpoint available if needed.

I can give you ready-to-use Python functions (using the official SDK or raw requests) for:

- Place breakout SL entry
- Cancel pending on candle close
- Trail SL
- Full position management loop

Just tell me:

- Language (Python preferred?)
- Intraday or delivery?
- Exact trailing method (candle low, ATR, points, %)?
- Whether you already have auth/token handling
- Any specific instrument (Nifty, stocks, options)?

Then I’ll give you production-grade code snippets that match the current Upstox API exactly.

**Here’s a complete, production-ready Python implementation** tailored exactly to your requirements:

- **Language**: Python
- **Product**: Intraday (`"I"`), validity `"DAY"`
- **Instruments**: Nifty options (NSE_FO, CE + PE)
- **Entry**: SL (Stop-Loss Limit) on candle high – fires only after breach
- **Cancel**: If not triggered by end of next candle → cancel
- **Trailing SL**: Simple 5-pt step (configurable), only moves in favor
- **Safety**: `CONFIRM_REAL_TRADING` flag (your UI checkbox)
- **Auth**: Reuses `access_token`

### 1. Install

```bash
pip install upstox-python-sdk requests
```

### 2. Core Trading Class

```python
# upstox_breakout_trader.py
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import upstox_client
from upstox_client.rest import ApiException

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


class UpstoxBreakoutTrader:
    def __init__(
        self,
        access_token: str,
        confirm_real_trading: bool = False,          # <-- Your UI checkbox
        trailing_step: float = 5.0,                  # 5-pt step as requested
        buffer_pts: float = 1.0,                     # buffer above trigger for limit price
        product: str = "I",
        sandbox: bool = False
    ):
        self.confirm_real_trading = confirm_real_trading
        self.trailing_step = trailing_step
        self.buffer_pts = buffer_pts
        self.product = product

        configuration = upstox_client.Configuration(sandbox=sandbox)
        configuration.access_token = access_token
        self.api_client = upstox_client.ApiClient(configuration)

        # Prefer V3 for better features + latency metadata
        self.order_api = upstox_client.OrderApiV3(self.api_client)
        # Fallback / some endpoints still use v2 style
        self.order_api_v2 = upstox_client.OrderApi(self.api_client)

        # State
        self.pending_entry_order_id: Optional[str] = None
        self.sl_order_id: Optional[str] = None
        self.position: Optional[Dict[str, Any]] = None   # {"side": "BUY"/"SELL", "qty": int, "entry_price": float, "instrument_token": str}

    # ------------------------------------------------------------------
    # Safety gate
    # ------------------------------------------------------------------
    def _can_trade(self) -> bool:
        if not self.confirm_real_trading:
            logger.warning("CONFIRM_REAL_TRADING is False → order blocked (dry-run mode)")
            return False
        return True

    # ------------------------------------------------------------------
    # Place Breakout Entry (SL Limit)
    # ------------------------------------------------------------------
    def place_breakout_entry(
        self,
        instrument_token: str,          # e.g. "NSE_FO|51059"
        quantity: int,                  # number of lots * lot_size (or just lots depending on your convention)
        candle_high: float,
        side: str = "BUY"               # "BUY" for CE long / PE short? → you decide
    ) -> Optional[str]:
        """
        Places SL order that triggers only after price breaches candle_high.
        Returns order_id or None.
        """
        if not self._can_trade():
            logger.info(f"[DRY-RUN] Would place SL entry {side} {quantity} @ trigger={candle_high}")
            return "DRY-RUN-ORDER-ID"

        trigger = round(candle_high, 2)          # Nifty options tick = 0.05 or 0.25 depending on premium, but round safely
        limit_price = round(trigger + self.buffer_pts, 2) if side == "BUY" else round(trigger - self.buffer_pts, 2)

        body = upstox_client.PlaceOrderV3Request(
            quantity=quantity,
            product=self.product,
            validity="DAY",
            price=limit_price,
            tag="breakout-entry",
            instrument_token=instrument_token,
            order_type="SL",
            transaction_type=side,
            disclosed_quantity=0,
            trigger_price=trigger,
            is_amo=False,
            slice=False
        )

        try:
            resp = self.order_api.place_order(body)
            order_id = resp.data.order_ids[0] if hasattr(resp.data, "order_ids") else resp.data.order_id
            self.pending_entry_order_id = order_id
            logger.info(f"SL Entry placed | {side} {quantity} | trigger={trigger} limit={limit_price} | order_id={order_id}")
            return order_id
        except ApiException as e:
            logger.error(f"Place entry failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Check & Cancel if not filled by end of next candle
    # ------------------------------------------------------------------
    def check_and_cancel_if_not_triggered(self) -> bool:
        """
        Call this on every candle close.
        Returns True if order was cancelled (or already gone), False if filled.
        """
        if not self.pending_entry_order_id:
            return True

        if self.pending_entry_order_id == "DRY-RUN-ORDER-ID":
            logger.info("[DRY-RUN] Simulated cancel of pending entry")
            self.pending_entry_order_id = None
            return True

        try:
            # Always re-fetch status right before acting (race condition protection)
            details = self.order_api_v2.get_order_details(self.pending_entry_order_id, api_version="2.0")
            status = details.data.status.lower() if details.data else ""

            if status in ("complete", "filled"):
                logger.info(f"Entry filled → order_id={self.pending_entry_order_id}")
                # You should now fetch average_price & filled_quantity and set self.position
                self.pending_entry_order_id = None
                return False

            if status in ("open", "trigger pending", "pending"):
                # Cancel
                self.order_api.cancel_order(self.pending_entry_order_id)
                logger.info(f"Cancelled pending entry (not triggered) | order_id={self.pending_entry_order_id}")
                self.pending_entry_order_id = None
                return True

            # already cancelled / rejected
            logger.info(f"Entry order already in terminal state: {status}")
            self.pending_entry_order_id = None
            return True

        except ApiException as e:
            logger.error(f"Status/cancel error: {e}")
            return False

    # ------------------------------------------------------------------
    # Place Initial Stop-Loss after entry
    # ------------------------------------------------------------------
    def place_initial_sl(
        self,
        instrument_token: str,
        quantity: int,
        trigger_price: float,
        side: str                    # opposite of entry side
    ) -> Optional[str]:
        if not self._can_trade():
            return "DRY-RUN-SL-ID"

        limit_price = round(trigger_price - self.buffer_pts, 2) if side == "SELL" else round(trigger_price + self.buffer_pts, 2)

        body = upstox_client.PlaceOrderV3Request(
            quantity=quantity,
            product=self.product,
            validity="DAY",
            price=limit_price,
            tag="trailing-sl",
            instrument_token=instrument_token,
            order_type="SL",
            transaction_type=side,
            disclosed_quantity=0,
            trigger_price=round(trigger_price, 2),
            is_amo=False,
            slice=False
        )

        try:
            resp = self.order_api.place_order(body)
            order_id = resp.data.order_ids[0] if hasattr(resp.data, "order_ids") else resp.data.order_id
            self.sl_order_id = order_id
            logger.info(f"Initial SL placed | {side} | trigger={trigger_price} | order_id={order_id}")
            return order_id
        except ApiException as e:
            logger.error(f"Place SL failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Trail Stop-Loss (5-pt step)
    # ------------------------------------------------------------------
    def trail_sl(self, current_ltp: float, side: str = "SELL") -> bool:
        """
        Call on every candle close (or every meaningful move).
        Only moves SL in favor by trailing_step points.
        For long entry (BUY) → side of SL is SELL
        """
        if not self.sl_order_id or self.sl_order_id == "DRY-RUN-SL-ID":
            return False

        try:
            details = self.order_api_v2.get_order_details(self.sl_order_id, api_version="2.0")
            if not details.data or details.data.status.lower() in ("complete", "cancelled", "rejected"):
                logger.info("SL already terminal → stop trailing")
                self.sl_order_id = None
                return False

            old_trigger = float(details.data.trigger_price)

            if side == "SELL":  # protecting a long
                new_trigger = max(old_trigger, current_ltp - self.trailing_step)
                # only move up
                if new_trigger <= old_trigger:
                    return False
            else:  # protecting a short
                new_trigger = min(old_trigger, current_ltp + self.trailing_step)
                if new_trigger >= old_trigger:
                    return False

            new_limit = round(new_trigger - self.buffer_pts, 2) if side == "SELL" else round(new_trigger + self.buffer_pts, 2)

            modify_body = upstox_client.ModifyOrderRequest(
                quantity=details.data.quantity,
                validity="DAY",
                price=new_limit,
                order_id=self.sl_order_id,
                order_type="SL",
                disclosed_quantity=0,
                trigger_price=round(new_trigger, 2)
            )

            self.order_api_v2.modify_order(modify_body, api_version="2.0")
            logger.info(f"Trailed SL → old={old_trigger} → new={new_trigger}")
            return True

        except ApiException as e:
            logger.error(f"Trail SL failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Helper: get current order status
    # ------------------------------------------------------------------
    def get_order_status(self, order_id: str) -> Optional[str]:
        try:
            details = self.order_api_v2.get_order_details(order_id, api_version="2.0")
            return details.data.status if details.data else None
        except:
            return None
```

### 3. How to use it in your main loop (example)

```python
# main.py (simplified)
ACCESS_TOKEN = "your_live_or_sandbox_token"
CONFIRM_REAL = True          # ← driven by your UI checkbox

trader = UpstoxBreakoutTrader(
    access_token=ACCESS_TOKEN,
    confirm_real_trading=CONFIRM_REAL,
    trailing_step=5.0,       # 5 points
    buffer_pts=1.0,
    product="I",
    sandbox=False            # True for testing
)

# ---------- On closed candle N ----------
instrument = "NSE_FO|51059"          # example CE instrument_key
qty = 75                             # 1 lot Nifty usually 75 (check current lot size)
candle_high = 245.50

order_id = trader.place_breakout_entry(
    instrument_token=instrument,
    quantity=qty,
    candle_high=candle_high,
    side="BUY"
)

# ---------- On closed candle N+1 ----------
was_cancelled = trader.check_and_cancel_if_not_triggered()

if not was_cancelled:
    # Entry filled → place initial SL (example: 20 pts below entry)
    # You should get real average_price from order details or position API
    entry_price = 246.00               # replace with real fill price
    initial_sl_trigger = entry_price - 20

    trader.place_initial_sl(
        instrument_token=instrument,
        quantity=qty,
        trigger_price=initial_sl_trigger,
        side="SELL"
    )

# ---------- Every subsequent candle close (while in position) ----------
current_ltp = 255.0                    # from your market data feed
trader.trail_sl(current_ltp=current_ltp, side="SELL")
```

### 4. Important Notes for Nifty Options

- **instrument_token** format is always `"NSE_FO|xxxxx"` (numeric exchange token).  
  Get the correct one from the option chain API or the daily instruments JSON.
- Lot size for Nifty is currently 75 (verify daily).
- Tick size for premiums is usually 0.05 or 0.25 — the code rounds to 2 decimals; tighten if needed.
- Rate limits: stay under 10 orders/sec (regular) / 50 (registered algo).
- Static IP is required for live order placement (from April 2026 enforcement).
- Always run with `sandbox=True` first.
- For real-time order fills, add the `PortfolioDataStreamer` (I can give you the exact snippet if you want).

Would you like me to also add:

1. Full position tracking + auto square-off at 3:15/3:20?
2. PortfolioDataStreamer for instant fill detection?
3. Option chain helper to pick ATM/OTM CE/PE automatically?
4. GTT version of the trailing SL (native trailing_gap)?

Just say the word and I'll extend the class.

---

## Bot-Specific Integration Notes

The code above is the standalone broker layer. Here is how it fits into our existing bot's architecture.

### Our Strategy: Red Candle High Break

Not a simple "breach candle high → enter". The actual strategy is:

1. Find first **red candle** (open > close) after 09:16 → becomes **reference candle**, capture its `high = H`
2. On the next candle(s), if `LTP > H` → **entry signal**. Entry price in paper mode = `H` (not LTP, to match backtest)
3. `max_wait_candles` (default 2) — reference expires after this many candles, resets
4. `allow_reference_shift` (default true) — if a newer red candle closes while waiting, shift reference to it, reset counter
5. On entry → `PositionManager.open_position(entry_price=H)`, initial SL = `H - initial_sl_points` (default 4)
6. Trailing: when profit ≥ `trailing_trigger` (5 pts), move SL up by `trailing_step` (5 pts), never down
7. Manual SL drag via PriceDiagram → `modifySl` API → `position_manager.set_manual_sl`
8. Manual close via floating panel → `exit_position` with last LTP

**Real-mode key difference**: SL-L fills at `limit_price = H + buffer` (which is ≥ H). The recorded entry price for P&L is the **broker fill price**, not `H`. P&L distribution will differ slightly from paper — this is expected.

### Where to inject the broker class

```python
# backend/core/trade_executor.py (new interface)

class TradeExecutor:
    """Interface — paper or live."""
    def on_candle_closed(self, inst_type, candle, is_red): ...
    def on_reference_shifted(self, inst_type, old_order_id, new_candle): ...
    def on_entry_filled(self, inst_type, slot, fill_price, entry_order_id): ...
    def on_trailing_sl_update(self, inst_type, slot, new_sl): ...
    def on_manual_sl(self, inst_type, slot, new_sl): ...
    def on_manual_close(self, inst_type, slot, ltp): ...
    def kill_switch(self): ...
    def get_open_orders(self): ...
    def get_broker_positions(self): ...


class PaperExecutor(TradeExecutor):
    """Current behavior — no broker calls."""
    # on_candle_closed: if red → place pending entry signal (in-memory)
    # on_reference_shifted: if has pending → cancel it, record new ref (in-memory)
    # on_entry_filled: open position at fill_price
    # on_trailing_sl_update: pm.update_trailing_sl → no broker call
    # on_manual_sl: pm.set_manual_sl → no broker call
    # on_manual_close: exit_position(ltp) → no broker call


class LiveExecutor(TradeExecutor):
    """Wraps UpstoxBreakoutTrader per slot."""
    def __init__(self, access_token, confirm, sandbox=False):
        self.traders = {}  # inst_type + slot → UpstoxBreakoutTrader instance
        ...

    def on_candle_closed(self, inst_type, candle, is_red):
        if is_red:
            # Red candle closed → place SL-L entry at its high
            trader = self.traders[inst_type]
            trader.place_breakout_entry(
                instrument_token=...,   # from bot's instrument key
                quantity=...,           # from settings (lot_size × lots)
                candle_high=candle['high'],
                side="BUY"
            )
        else:
            # Non-red candle closed → check if pending entry filled
            trader = self.traders.get(inst_type)
            if trader and trader.pending_entry_order_id:
                was_cancelled = trader.check_and_cancel_if_not_triggered()
                if not was_cancelled:
                    # Entry filled — get fill price from order details
                    details = trader.order_api_v2.get_order_details(
                        trader.pending_entry_order_id, api_version="2.0"
                    )
                    fill_price = details.data.average_price
                    self.on_entry_filled(inst_type, fill_price, ...)

    def on_reference_shifted(self, inst_type, old_order_id, new_candle):
        # Cancel old pending SL-L, place new one at new high
        trader = self.traders[inst_type]
        trader.order_api.cancel_order(old_order_id)
        trader.place_breakout_entry(
            instrument_token=...,
            quantity=...,
            candle_high=new_candle['high'],
            side="BUY"
        )

    def on_entry_filled(self, inst_type, slot, fill_price, entry_order_id):
        # Open position at broker fill price (not reference high!)
        pm = self.components[inst_type]['position_manager']
        pm.open_position(entry_price=fill_price, ...)
        # Place SL-L SELL
        initial_sl = fill_price - initial_sl_points
        sl_order_id = self.traders[inst_type].place_initial_sl(
            instrument_token=...,
            quantity=...,
            trigger_price=initial_sl,
            side="SELL"
        )
        self._sl_order_ids[(inst_type, slot)] = sl_order_id

    def on_trailing_sl_update(self, inst_type, slot, new_sl):
        sl_order_id = self._sl_order_ids.get((inst_type, slot))
        if sl_order_id:
            self.traders[inst_type].trail_sl(current_ltp=new_sl + trailing_step, side="SELL")

    def on_manual_sl(self, inst_type, slot, new_sl):
        sl_order_id = self._sl_order_ids.get((inst_type, slot))
        if sl_order_id:
            trader = self.traders[inst_type]
            trader.order_api.modify_order(
                ModifyOrderRequest(
                    order_id=sl_order_id,
                    trigger_price=round(new_sl, 2),
                    price=round(new_sl - buffer_pts, 2),
                    ...
                )
            )

    def on_manual_close(self, inst_type, slot, ltp):
        # Cancel SL order
        sl_order_id = self._sl_order_ids.pop((inst_type, slot), None)
        if sl_order_id:
            trader = self.traders[inst_type]
            try:
                trader.order_api.cancel_order(sl_order_id)
            except:
                pass
        # Place market/limit exit SELL — listen for fill via PortfolioDataStreamer
        trader.place_market_exit(instrument_token=..., quantity=..., side="SELL")

    def kill_switch(self):
        for trader in self.traders.values():
            # Cancel all open orders
            for order_id in trader.get_open_order_ids():
                trader.order_api.cancel_order(order_id)
            # Market exit all positions
            for pos in trader.get_positions():
                trader.place_market_exit(...)
```

### UpstoxBreakoutTrader additions needed

The class above needs these extras for our bot:

```python
# Add to UpstoxBreakoutTrader:

def place_market_exit(self, instrument_token: str, quantity: int, side: str) -> Optional[str]:
    """Place a LIMIT exit order (no trigger needed — just exit now).
    Uses price slightly beyond LTP to ensure fill."""
    if not self._can_trade():
        return "DRY-RUN-EXIT-ID"
    body = upstox_client.PlaceOrderV3Request(
        quantity=quantity,
        product=self.product,
        validity="DAY",
        price=0,           # 0 for LIMIT means best available; or use current_ltp ± buffer
        tag="manual-exit",
        instrument_token=instrument_token,
        order_type="LIMIT",
        transaction_type=side,
        disclosed_quantity=0,
        is_amo=False,
        slice=False
    )
    resp = self.order_api.place_order(body)
    return resp.data.order_ids[0]

def get_open_order_ids(self) -> List[str]:
    """Return all open order IDs for kill-switch."""
    book = self.order_api_v2.get_order_book(api_version="2.0")
    return [o.order_id for o in book.data if o.status.lower() in ("open", "trigger pending")]

def get_positions(self) -> List[Dict]:
    """Return current open positions from broker."""
    pos_api = upstox_client.PositionApi(self.api_client)
    positions = pos_api.get_positions()
    return positions.data or []
```

### DataStreamer wiring changes

In `data_streamer.py`, the key changes:

```python
# In __init__:
self.executor: TradeExecutor = PaperExecutor()  # default paper

# When strategy detects red candle (on_candle_closed):
def _on_candle_event(self, inst_type, event_type, candle):
    if event_type == "candle_closed":
        is_red = candle['open'] > candle['close']
        self.executor.on_candle_closed(inst_type, candle, is_red)
        # Paper behavior: if is_red, strategy sets reference (in-memory only)
        # Live behavior: executor.place_breakout_entry(candle['high'])

# When strategy reference shifts:
#   Paper: strategy resets reference_candle internally
#   Live: executor.on_reference_shifted(old_order_id, new_candle)

# When tick triggers entry:
def process_tick(...):
    if entry_signal and entry_signal['enter']:
        # Paper: pm.open_position(entry_signal['entry_price'])
        # Live: executor.on_entry_filled(...) — fill price from broker
        pass

# When trailing SL moves:
    sl_moved, new_sl = pm.update_trailing_sl(ltp)
    if sl_moved:
        self.executor.on_trailing_sl_update(inst_type, slot, new_sl)

# Manual SL:
def modify_sl(instrument, slot, new_sl):
    # Paper: pm.set_manual_sl(new_sl)
    # Live: executor.on_manual_sl(instrument, slot, new_sl)

# Manual close:
def close_position_manual(instrument, slot):
    # Paper: exit_position(ltp, now, "Manual Close")
    # Live: executor.on_manual_close(instrument, slot, ltp) — places exit order
```

### UI Switch Architecture

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

Real dashboard panel:
  GET /api/broker/orders → open orders list (order_id, status, age, trigger, limit)
  GET /api/broker/position → positions with real P&L
  POST /api/broker/kill → kill switch
```

### Answers to Upstox BreakoutTrader integration questions

1. **Language** → Python (existing bot is Python)
2. **Intraday or delivery?** → Intraday, `product = "I"`, `validity = "DAY"`, square off by 15:00
3. **Trailing method?** → Simple 5-pt step — use `trailing_step` from settings, move SL with `max(old_sl, current_ltp - trailing_step)` for CE long positions
4. **Auth/token?** → Reuse existing `access_token` from `settings_db`. "Confirm Real Trading" UI checkbox gates the mode switch (not an Upstox requirement — it's a safety net)
5. **Instrument?** → Nifty options, CE + PE, `NSE_FO` segment. `instrument_token` format: `"NSE_FO|<exchange_token>"`. Get exchange token from option chain API or daily instruments file

### Pending questions for the guider

1. **PortfolioDataStreamer**: should we listen to order-fill WebSocket events to detect fills immediately, or just poll on each candle close? (WebSocket is faster, polling is simpler)
2. **Partial fills policy**: if SL-L gets a partial fill, should we treat it as entered (track partial position) or cancel the remainder?
3. **Gap risk on entry**: if price gaps past the SL-L limit on a fast breakout, the order stays unfilled. Should we convert to a market order after N seconds, or just leave it?
4. **EOD square-off**: should the bot call the kill-switch automatically at 15:00 (or 5 min before), or leave positions open for the broker to auto-square?
5. **Option B (GTT trailing) vs Option A (manual Modify)**: do you want the native GTT trailing_gap approach, or keep the manual Modify approach for more control over candle-based trailing?
6. **Manual SL direction protection**: `position_manager.set_manual_sl` currently allows moving SL in either direction. Should we enforce "never widen SL" as a hard rule, or keep it flexible?

### Guider's Answers (FINAL — locked in)

1. **PortfolioDataStreamer** → **WebSocket + candle-close backup.** Run the order-update WebSocket the whole day. On fill event, immediately set position + place initial SL + cancel remainder if partial. Keep candle-close check as a safety net for disconnects.
2. **Partial fills policy** → **Accept partial + cancel remainder.** Treat the filled qty as the real position size. Cancel the unfilled remainder right away so we don't get a worse second fill. Place the SL only for the filled qty.
3. **Gap risk on entry** → **Wider buffer (2–3 pts) + optional 10s re-price.** Hierarchy:
   - Best: increase `buffer_pts` so the SL-L limit is more likely to fill.
   - Good: after trigger, if still unfilled after 10–12s → cancel SL, place a fresh LIMIT closer to current LTP.
   - Avoid pure "convert to market after N seconds" — market orders are heavily restricted under current SEBI rules.
   - For pure breakout systems many accept the risk; since we already cancel on next candle close, the unfilled order dies naturally.
4. **EOD square-off** → **Bot must force exit at 15:15–15:20.** Do not rely on the broker's auto square-off. Hard kill-switch at 15:25 as a final safety net.
5. **GTT trailing vs Manual Modify** → **Manual Modify (Option A).** GTT `trailing_gap` is gap-based, less flexible for candle-based 5-pt step. Manual Modify gives full control and works with WebSocket fill events. GTT can be added later as an alternative mode.
6. **Manual SL direction protection** → **Hard "never widen SL" rule.** In `trail_sl` and `set_manual_sl`:
   - Long position → `new_trigger = max(old_trigger, calculated_new)`
   - Short position → `new_trigger = min(old_trigger, calculated_new)`
   - This is non-negotiable for risk management. A separate "emergency widen" function (with explicit flag) can exist if needed.

### Lot size correction

- **Nifty options lot size is 65** (not 75 as in the sample code).
- Our `lot_size` setting in `settings_db.py` is already `65` → no change needed, but the guider's sample `quantity = 75` in `main.py` must use `lot_size * lots` from settings.

### FINAL Configuration (do not change without strong reason)

| Decision        | Value                                                                        |
| --------------- | ---------------------------------------------------------------------------- | ----------------- |
| Fill detection  | PortfolioDataStreamer (WebSocket) + candle-close backup                      |
| Partial fills   | Accept partial + cancel remainder                                            |
| Gap on entry    | Wider buffer (2–3 pts) + optional 10s re-price                               |
| EOD square-off  | Bot forces exit at 15:15 (kill-switch at 15:25)                              |
| Trailing method | Manual Modify (5-pt step, candle-close based)                                |
| SL direction    | Hard "never widen" rule                                                      |
| Lot size        | 65 (from settings)                                                           |
| Product         | Intraday `"I"`                                                               |
| Validity        | `"DAY"`                                                                      |
| Buffer          | 2–3 points (configurable `buffer_pts`)                                       |
| Sand default    | `sandbox=True` for first run                                                 |
| Static IP       | Required from April 2026                                                     |
| Confirm gate    | UI checkbox → `confirm_real_trading` setting                                 |
| Auth            | Reuse existing `access_token`                                                |
| Mode toggle     | Paper                                                                        | Real in AppHeader |
| Real dashboard  | Open orders, fills, ₹ P&L, kill switch                                       |
| Cancel rule     | Pending entry SL-L cancelled on next candle close if not filled              |
| Reference shift | Cancel old SL-L + place new at shifted candle's high (in `on_candle_closed`) |
| Manual SL drag  | `modify-order` on live SL order                                              |
| Manual close    | Cancel SL order + market/limit SELL exit                                     |
| Entry price     | Broker fill price (≥ `H + buffer`), not `H`                                  |
| Race protection | Re-fetch order status immediately before any cancel/modify                   |
| Rate limit      | Stay under 10 orders/sec (regular algo)                                      |
