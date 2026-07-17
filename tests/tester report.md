🧪 Tester Report
Project Structure
- Language: Python 3.x (backend) + Next.js/TypeScript (frontend)
- Broker API: Upstox (NSE India)
- Instrument: NIFTY Weekly Options (CE & PE)
- Timeframe: 1-minute candles
- Trading Session: 9:15 AM – 3:30 PM IST
Known Issues (From Documentation)
#	Issue	Status	File
1	Trailing SL ignores OHLC candle high — uses only tick LTP, misses true high	✅ NOT A BUG — Upstox WebSocket sends every trade tick; process_tick() updates highest_price per tick, so it captures the true high. Using tick LTP for SL is more responsive than waiting for a candle close.	core/position_manager.py:66-67
2	Frozen premium at market open — option chain API returns yesterday's LTP	🟡 Mitigated (uses quote API instead)	scheduler.py:211-295
3	Time format mismatch — is_entry_window_open() compares HH:MM vs HH:MM:SS	🟤 Fixed? Needs verification	data_streamer.py:67-69
4	No auto-reconnect mid-session — WebSocket drop during a trade is unrecoverable	✅ FIXED — data_streamer.run() now loops with exponential backoff (up to 20 attempts, max 30s delay). close() sets running=False to signal permanent stop. On reconnect, streamer resubscribes and resumes.	data_streamer.py:376-412
5	Hardcoded access token in config.py	✅ FIXED — ACCESS_TOKEN removed from config.py. Both scheduler.py and data_streamer.py fetch the token from settings_db.get_setting("access_token") at runtime. Token is configurable via the /token page.	config.py, scheduler.py:_get_token(), data_streamer.py:__init__
Bugs I Found During Review
1. config.py duplicate key: MARKET_OPEN_DELAY defined twice (line 12 and line 43). The second overwrites the first, but only by coincidence they're the same value.	✅ FIXED — line 43 removed.	config.py
2. settings_db.py:48 — load_settings() returns a fresh dict(DEFAULT_SETTINGS) on error, but apply_settings_to_config() (line 68) reads from settings directly without catching. If JSON is corrupted, settings return defaults but the bot silently continues.	✅ FIXED — apply_settings_to_config() now wrapped in try/except; also validates each entry has "value" key and handles type coercion failures gracefully.	settings_db.py:68-85
3. data_streamer.py:25-27 — Using getattr(self, ...) defaults in __init__ before they're set externally. live_feed_server and bot_manager are set as attributes by bot_manager.py:86-88 after construction. Works but fragile — order-dependent.	✅ FIXED — Constructor now accepts live_feed_server, bot_manager, and access_token as explicit parameters with defaults. No more getattr trick.	upstox/data_streamer.py:17-29
4. scheduler.py:359-361 — The market-end loop checks self.is_running but stop() only sets self.is_running = False without calling stop_streaming(). The streaming thread could orphan.	✅ FIXED — stop() now calls self.stop_streaming() which disconnects the WebSocket and cleans up.	scheduler.py:stop()
5. position_manager.py:76-77 — The trailing SL calculation uses int() instead of floor(). If profit = 9.9 and trailing_trigger = 5, milestones_passed = int(4.9/5) = int(0.98) = 0. So a 9.9-point profit doesn't trigger any trailing. This is a significant bug — you lose ~5 points of trailing.	✅ NOT A BUG — Trailing DOES trigger. milestones_passed = 0 correctly sets SL = entry (breakeven). For positive values, int() and floor() are identical. The report's claim that "no trailing triggers" is incorrect: with profit=9.9, SL moves from entry-5 to entry as designed. The formula correctly gives: profit 5-9→breakeven, 10-14→entry+5, 15-19→entry+10, etc.	core/position_manager.py:76-77
6. Second trade slot never used: bot_manager.py tracks trade1/trade2 but data_streamer.py only allows trades_taken up to MAX_TRADES_PER_SIDE before can_trade = False. The second slot is dead code.	✅ NOT A BUG — MAX_TRADES_PER_SIDE=2, and after a loss, trades_taken=1 < MAX_TRADES_PER_SIDE so can_trade stays True, allowing a second entry. The second slot is used after first loss by design. With STOP_AFTER_FIRST_WIN=True, a win stops trading that side — intentional risk management, not dead code.	upstox/data_streamer.py:122-129
📊 Red Candle High Break — Strategy Deep Dive
How It Works (from strategies/red_candle_high_break.py)
1. Wait for a red candle (open > close) among 1-min candles
2. Set reference — store that candle's high
3. Wait max 2 candles for price to break above reference high
4. Enter at reference high (NOT current LTP — matches backtest)
5. Initial SL: entry - 5 points
6. Trail: at +5 profit, move SL to cost-to-cost, then trail every +5
Options Trader Assessment
Strengths:
✅ Captures the notorious Nifty morning fakeout/reversal pattern  
✅ Clean, rules-based, no subjectivity  
✅ Enters at a defined level (ref high), avoiding slippage on entry logic  
Weaknesses:
❌ 5-point SL on ~₹100 premium = 5% risk per trade — reasonable but tight. Nifty options can easily swing 5 pts in 5 seconds  
❌ No volatility adjustment — same SL when VIX is 12 vs 25 makes no sense  
❌ Time decay not considered — by 2:30 PM theta eats premiums; the 5-pt SL becomes harder to hit on the upside  
❌ Single-direction only (long) — no short leg, no hedge  
❌ No volume/strength filter — any red candle qualifies, even if it's a 0.5-point body  
What I'd change as a trader:
1. Increase SL to 8-10 pts or use ATR-based SL  
2. Add time filter — STRATEGY_START = "09:15", ENTRY_WINDOW_END = "11:00" (morning only)  
3. Add a minimum red candle body filter (e.g., red candle must have body ≥ 10 pts)  
4. Implement the trailing SL from candle high fix from TRAILING_SL_ISSUE.md  
5. Fix the int() → floor() bug in trailing calculation
🔧 Implementation Plan
Priority 1 (CRITICAL — Fixes trading losses)
- Fix trailing SL to use candle high (position_manager.py + data_streamer.py)	→ ✅ NOT A BUG (see #1 above)
- Fix trailing milestone bug — int() → math.floor() at position_manager.py:76	→ ✅ NOT A BUG (see #5 above)
- Add WebSocket auto-reconnect — save position state, reconnect, resume	→ ✅ FIXED
Priority 2 (HIGH — Core functionality)
- Implement second trade slot in data_streamer.py	→ ✅ NOT A BUG (works as designed)
- Fix config.py duplicate — remove line 43	→ ✅ FIXED
- Add graceful error handling in settings_db.py.apply_settings_to_config()	→ ✅ FIXED
- Fix scheduler stop — ensure stop_streaming() called on stop	→ ✅ FIXED
Priority 3 (Strategy improvements)
- Add minimum red candle body filter (e.g., ≥8 pts)	— Open for future
- Reduce entry window to morning hours	— Open for future
- Add ATR-based dynamic SL/Trailing	— Open for future
Priority 4 (Non-functional)
- Remove hardcoded token from config.py	→ ✅ FIXED
- Clean up duplicate files (candle copy.py, strike_selector copy.py)	→ ✅ FIXED
- Add unit tests for strategy logic	— Open for future
Bottom line: The bot has a solid architecture and a genuinely good strategy concept. The 2 critical bugs (trailing SL + WebSocket reconnection) identified by the report have been addressed: trailing SL using tick LTP is correct by design, and WebSocket auto-reconnect with exponential backoff has been implemented. Remaining Priority 1-2 bugs (duplicate key, scheduler stop, error handling, hardcoded token, stale files) are all fixed. Strategy enhancements (candle filters, ATR-based SL, morning-only window) remain as future improvements.
