# 🧪 Tester Report

## Project Structure
- **Language:** Python 3.x (backend) + Next.js/TypeScript (frontend)
- **Broker API:** Upstox (NSE India)
- **Instrument:** NIFTY Weekly Options (CE & PE)
- **Timeframe:** 1-minute candles
- **Trading Session:** 9:15 AM – 3:30 PM IST

## Known Issues — Status

| # | Issue | Status | File |
|---|-------|--------|------|
| 1 | Trailing SL uses tick LTP (not candle high) | ✅ **Intended Design** — OHLC candle high is only known after candle closes; can't use future data for real-time SL. Tick LTP is correct input. | `position_manager.py:66-67` |
| 2 | Frozen premium at market open | ✅ **FIXED** — Bot now uses `/v2/market-quote/ltp` batch API for live premiums instead of `market_data.ltp` from option chain. Strike selection working correctly. | `scheduler.py:fetch_live_strikes()` |
| 3 | Time format mismatch in `is_entry_window_open()` | ✅ **FIXED** — Both `STRATEGY_START` ("09:15") and `current_time` ("%H:%M") now use HH:MM format. | `data_streamer.py:69-71` |
| 4 | No WebSocket auto-reconnect | ✅ **FIXED** — `run()` loops with exponential backoff (up to 20 attempts, max 30s delay). On reconnect, resubscribes and resumes. | `data_streamer.py:376-412` |
| 5 | Hardcoded access token in `config.py` | ✅ **FIXED** — Token removed from config. Both scheduler and data streamer fetch from `settings_db.get_setting("access_token")`. | `config.py`, `scheduler.py:_get_token()` |

## Bugs Found During Review — Fixed

| # | Issue | Fix | File |
|---|-------|-----|------|
| 1 | `MARKET_OPEN_DELAY` defined twice | Duplicate line removed | `config.py` |
| 2 | `apply_settings_to_config()` no error handling | Wrapped in try/except with validation | `settings_db.py:68-85` |
| 3 | `getattr(self, ...)` fragile dependency injection | Constructor accepts explicit params | `data_streamer.py:17-29` |
| 4 | `stop()` orphans streaming thread | `stop()` now calls `stop_streaming()` | `scheduler.py:stop()` |
| 5 | Second trade slot not populated | `trade_slot` tracking added; entry/exit data written to `bot_manager.positions[trade1/trade2]`; slot transitions after loss | `data_streamer.py`, `bot_manager.py` |
| 6 | `_broadcast_tick` uses `pm.current_sl` (doesn't exist) | Changed to `pm.get_current_sl()` | `data_streamer.py:88` |

## Intended Design (Not Bugs)

| Issue | Why It's Correct |
|-------|-----------------|
| `int()` in trailing milestone calc | Trailing moves in 5-point steps only (100→105→110→115). `int((profit-5)/5)` correctly floors to whole milestones. Profit 9.9 → 0 milestones → SL at breakeven. Profit 10 → 1 milestone → SL at entry+5. This is the intended 5-point step trailing. |
| Trailing SL ignores candle high | Candle high is only known at candle close (up to 1 minute late). By then price action has moved. Tick LTP is the correct real-time input. |
| No red candle strength filter | Strategy is designed to enter on ANY red candle breakout. Adding a minimum body filter would change the strategy behavior. |

## 📊 Red Candle High Break — Strategy Overview

1. Wait for a red candle (open > close) among 1-min candles
2. Set reference — store that candle's high
3. Wait max 2 candles for price to break above reference high
4. Enter at reference high (NOT current LTP — matches backtest)
5. Initial SL: entry - 5 points
6. Trailing: on +5 profit milestone, SL moves to breakeven → on +10, SL moves to entry+5 → every +5 thereafter

## Trade Slot Tracking (Implemented 17 Jul 2026)

Before: `bot_manager.positions[CE/PE].trade1/trade2` were always `null` — never written to.

After: Trade slots are now populated:

- Slot 1 starts active
- On entry: `bot_manager.positions[inst].trade1 = { state, entry_price, current_sl, entry_time }`
- On exit: slot updated with `state, exit_price, pnl, exit_reason, duration_seconds`
- If loss and `can_trade` stays True → slot transitions to 2
- Slot 2 follows same lifecycle
- `GET /api/status` now returns real position data for both slots

## 🔧 Implementation Status

| Priority | Item | Status |
|----------|------|--------|
| **Critical** | WebSocket auto-reconnect (exponential backoff) | ✅ FIXED |
| **Critical** | Token management (removed hardcoded, uses settings) | ✅ FIXED |
| **High** | Second trade slot tracking | ✅ FIXED |
| **High** | Scheduler stop cleanup | ✅ FIXED |
| **High** | Error handling in settings apply | ✅ FIXED |
| **Medium** | Red candle strength filter | Open |
| **Medium** | ATR-based dynamic SL | Open |
| **Low** | Unit tests for strategy logic | Open |
