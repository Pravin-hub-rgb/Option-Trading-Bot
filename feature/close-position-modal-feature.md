# Close Position Floating Panel — Feature Plan

## Overview
Add a "Close Position" button to each trading slot (TerminalQuadrant). Clicking it opens a draggable floating panel that shows live PnL and lets the user exit the trade instantly at CMP. No backdrop — charts remain fully interactive behind it.

## Backend

### 1. `data_streamer.py` — `close_position_manual(instrument, slot)`
- New method on `DataStreamer`
- Gets last LTP from `pm.position['last_ltp']`
- Calls existing `exit_position(instrument, last_ltp, now, "Manual Close")`
- Returns `{pnl, exit_price}` on success, `None` if no position

### 2. `api_server.py` — `POST /api/position/{instrument}/{slot}/close`
- Calls `bot_manager._data_streamer.close_position_manual(instrument, slot)`
- Returns `{status, pnl, exit_price}`
- 400 if bot not running or no active position

## Frontend

### 3. `api.ts` — `closePosition(instrument, slot)`
- `POST http://127.0.0.1:8002/api/position/{instrument}/{slot}/close`
- Returns `{status, pnl, exit_price}`

### 4. `TerminalQuadrant.tsx` — Close Button
- Red "✕ Close" button in the card header
- Only visible when `state === "in_position"`
- On click → toggles floating panel open

### 5. `TerminalQuadrant.tsx` — Floating Panel (NOT a modal)
- **No overlay/backdrop** — charts stay 100% interactive (zoom, pan, drag, SL drag)
- `pointer-events: none` on wrapper, `pointer-events: auto` on the panel — clicks pass through to chart
- Positioned with `fixed` + `transform: translate(x, y)` for dragging
- **Drag handle** = the panel header bar (`onMouseDown` → track offset → update transform)
- Dark card style matching app theme (`bg-[#111]`, border `white/10`, rounded-xl)
- Content:
  - Header: instrument label (e.g. "BANKNIFTY PE — Trade 1")
  - Entry price
  - **Live LTP** (large font, updates via tick data)
  - **Live PnL** (large font, green if positive, red if negative)
  - Current SL level
- Buttons:
  - **"Close at CMP"** (red) — calls `closePosition()` API, disables on click, shows loading
  - **"✕"** (tiny, top-right) — closes the floating panel
- **Auto-closes** when `state` changes from `in_position` (trade exited via SL hit, auto-trail, or manual close)
- Appears centered by default, user drags it anywhere

## Drag Implementation
Same pattern as `PriceDiagram.tsx` SL drag and `TerminalLogs.tsx` resize:
- `onMouseDown` on header → store start position
- `onMouseMove` on document → calculate delta, update `transform`
- `onMouseUp` on document → stop drag
- State: `{ x: number, y: number }` for panel position
- Initial position: centered `(window.innerWidth/2 - panelWidth/2, window.innerHeight/2 - panelHeight/2)`

## No New Dependencies
Pure React + mouse events + Tailwind CSS. Same patterns already in the codebase.

## Files to Modify
1. `backend/upstox/data_streamer.py` — add `close_position_manual()`
2. `backend/api_server.py` — add `POST /api/position/{instrument}/{slot}/close`
3. `frontend/app/lib/api.ts` — add `closePosition()`
4. `frontend/app/components/TerminalQuadrant.tsx` — close button + floating panel
