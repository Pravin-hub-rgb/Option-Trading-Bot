# Performance Optimization Plan — 2026-07-17

## Goal
Eliminate all unnecessary work from the trade execution hot path and UI render path. No compromise on execution latency.

---

## Phase 1 — Zero-Risk Frontend Wins

### 1.1 Remove 4 dead npm dependencies
- **Files:** `frontend/package.json`
- **Packages to uninstall:** `@mui/material`, `@emotion/react`, `@emotion/styled`, `lightweight-charts`
- **Why safe:** Grep across all 19 source files in `frontend/app/` — zero imports of any of these. `PriceDiagram.tsx` uses raw Canvas 2D, all icons use `@iconify/react` (actively used in 10 files).
- **Savings:** ~680KB gzipped from bundle.

### 1.2 Memoize `buildLevels` + remove `levels` from effect deps
- **Files:** `frontend/app/components/PriceDiagram.tsx`
- **Lines:** 52-53, 173
- **Problem:** `buildLevels()` runs every render, returns new array refs. `levels` is in the canvas effect dependency array at line 173, so every parent re-render triggers a full canvas redraw even if no data changed.
- **Fix:** Wrap `buildLevels` call in `useMemo([entryPrice, currentSl, tpLevels])`. Remove `levels` from effect deps (all constituent values are already listed separately).
- **Risk:** None. Memo is a pure optimization, behavior unchanged.

### 1.3 Consolidate 5 setStates into one tick state object
- **Files:** `frontend/app/components/TerminalQuadrant.tsx`
- **Lines:** 20-26 (state defs), 82-90 (WebSocket handler)
- **Problem:** Each WebSocket tick calls up to 5 separate `setState` calls. React 19 likely batches these, but the pattern is fragile and ties 5 state variables to the same data source.
- **Fix:** Replace `ticks`, `currentSl`, `pnl`, `entryPrice`, `tpLevels` with a single state object: `{ ticks, currentSl, pnl, entryPrice, tpLevels }`. Update in one `setTickData()` call.
- **Risk:** Low. Refactor is mechanical — spread old state, override changed fields.

### 1.4 Deduplicate lo/hi/range computation
- **Files:** `frontend/app/components/PriceDiagram.tsx`
- **Lines:** 73-82 (in effect), 183-189 (in render)
- **Problem:** Same `ticks.map(l) -> Math.min/max -> lo/hi/range -> yPos` computed twice. For 2000 ticks, ~4000 iterations per render.
- **Fix:** Compute once in `useMemo`, share between effect and JSX.
- **Risk:** None. Pure refactor.

### 1.5 Precompute log type at insertion time
- **Files:** `frontend/app/components/TerminalLogs.tsx`
- **Lines:** 107-108
- **Problem:** `detectType()` runs 4x `msg.includes()` for all 200 logs on every new log arrival (800 string searches per new log).
- **Fix:** Compute `{ label, color }` once when the log is received in the SSE handler and store as part of the `Log` object.
- **Risk:** None.

---

## Phase 2 — Tick Path Optimization (Backend)

### 2.1 Cache `get_as_dict()` with write-through invalidation
- **Files:** `backend/settings_db.py`
- **Problem:** 17 call sites across 7 files, with 2-3 reads per tick on the hot path. `settings.json` is re-parsed from disk every call. Settings only change via API (`save_setting`, `reset_settings`) — 99.9% of reads are wasted.
- **Fix:**
  1. Add `_cache = None` module-level variable.
  2. `get_as_dict()` returns `_cache` if set, otherwise loads from disk + caches.
  3. `save_setting()`, `reset_settings()` call a new `invalidate_cache()` or `reload()`.
  4. `load_settings()` does NOT cache (it's a raw read used by the API endpoints that need fresh data).
  5. Call `invalidate_cache()` at startup in `main.py` after initial `load_settings()`.
- **Impact:** Eliminates ALL disk I/O from the tick path. SL detection, trailing, entry checks all become CPU-only.
- **Risk:** Low. Settings only change via the two API endpoints, both of which will invalidate cache. The cache is a simple dict — no stale data concern.

### 2.2 Thread-safe position writes from Upstox callbacks
- **Files:** `backend/upstox/data_streamer.py`, `backend/core/bot_manager.py`
- **Problem:** `bot_manager.lock` is only acquired by the API thread (T3). The Upstox callback thread (T6+) writes `positions`, `mode`, `_exiting` flags WITHOUT any lock. API reads `positions` WITH the lock, but since the writer doesn't lock, the lock provides zero protection. T3 can observe a partially-written position dict.
- **Fix:**
  1. Pass `bot_manager.lock` to `DataStreamer` constructor.
  2. Acquire `self.bm_lock` before mutating `self.bot_manager.positions` entries in `process_tick()` (line 205-212) and `exit_position()` (lines 128-135).
  3. Also acquire before writing `comp['can_trade']`, `comp['trade_slot']`, `comp['trades_taken']` — or keep these in `components` (single-thread access) if we confirm Upstox uses one callback thread.
- **Risk:** Medium — need to verify if Upstox SDK uses a thread pool for callbacks. If single-threaded, `components` accesses are safe and only `positions` needs the lock. We should also avoid holding the lock during `requests.get()` (already done — the HTTP calls happen before the locked sections).

---

## Phase 3 — Resilience

### 3.1 Backpressure on WebSocket broadcast
- **Files:** `backend/upstox/live_feed_server.py`
- **Lines:** 52
- **Problem:** `asyncio.run_coroutine_threadsafe` is fire-and-forget. If ticks arrive faster than the event loop can process broadcasts, the internal task queue grows unboundedly.
- **Fix:** Replace with `asyncio.Queue(maxsize=100)`. `broadcast_sync` puts messages into the queue (drops oldest if full). A background coroutine drains the queue and broadcasts.
- **Risk:** Low. Dropping old ticks when backlogged is better than unbounded memory growth.

### 3.2 Parallel WebSocket sends
- **Files:** `backend/upstox/live_feed_server.py`
- **Lines:** 42-46
- **Problem:** `for ws in self.clients: await ws.send(data)` — one slow client blocks all others.
- **Fix:** Use `asyncio.gather(*(ws.send(data) for ws in self.clients), return_exceptions=True)`.
- **Risk:** Low.

---

## Phase 4 — Minor Cleanup

### 4.1 Fix drag listener leak
- **Files:** `frontend/app/components/TerminalLogs.tsx`
- **Fix:** Add `useEffect` cleanup that removes `mousemove`/`mouseup` listeners if component unmounts mid-drag.

### 4.2 Share status fetch across quadrants
- **Files:** `frontend/app/page.tsx`, `frontend/app/components/TerminalQuadrant.tsx`
- **Fix:** Lift single `/api/status` fetch to `page.tsx`, pass data down as props or context.

---

## Files Changed Summary

| Phase | File | Change |
|-------|------|--------|
| 1.1 | `frontend/package.json` | Remove 4 deps |
| 1.2 | `frontend/app/components/PriceDiagram.tsx` | Add `useMemo` for `buildLevels` + deps |
| 1.3 | `frontend/app/components/TerminalQuadrant.tsx` | Merge 5 states -> 1 |
| 1.4 | `frontend/app/components/PriceDiagram.tsx` | Deduplicate lo/hi/range |
| 1.5 | `frontend/app/components/TerminalLogs.tsx` | Precompute log type |
| 2.1 | `backend/settings_db.py` | Add cache + invalidation |
| 2.2 | `backend/upstox/data_streamer.py`, `backend/core/bot_manager.py` | Thread-safe positions |
| 3.1 | `backend/upstox/live_feed_server.py` | Backpressure queue |
| 3.2 | `backend/upstox/live_feed_server.py` | Parallel sends |
| 4.1 | `frontend/app/components/TerminalLogs.tsx` | Drag listener cleanup |
| 4.2 | `frontend/app/page.tsx` | Shared status fetch |
