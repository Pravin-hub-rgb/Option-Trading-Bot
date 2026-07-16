# Implementation Checklist — Options Trading Bot Dashboard

**Started:** 2026-07-16
**Target:** Dashboard UI (Terminal, History, Analytics, Settings) with live WebSocket + SSE + REST

---

## Phase 1: Backend Core Files

### 1.1 Settings Database
- [ ] Create `settings_db.py` — JSON file read/write with defaults from `config.py`
  - [ ] `load_settings()` → dict
  - [ ] `save_setting(key, value)` → writes single key
  - [ ] `reset_settings()` → restores defaults
  - [ ] `get_setting_meta()` → list with type, label, category, options

### 1.2 Live Feed Server (WebSocket)
- [ ] Create `live_feed_server.py`
  - [ ] `LiveFeedServer` class with `start()`, `stop()`, `broadcast()`
  - [ ] WebSocket handler (accept connections, send state on connect)
  - [ ] Message protocol: `InitMessage`, `CandleUpdateMessage`, `CandleClosedMessage`,
        `TickMessage`, `TradeMessage`, `StrategyMessage`
  - [ ] Connection tracking (set of clients)
  - [ ] Handle disconnects gracefully

### 1.3 Trade Log Reader
- [ ] Create `trade_log_reader.py`
  - [ ] `load_all_trades(year=None)` → list of TradeEntry
  - [ ] `load_trade_pnl(year)` → per-day P&L summary
  - [ ] `load_trade_stats()` → aggregate statistics
  - [ ] Handle missing/empty CSV files

### 1.4 Bot Manager
- [ ] Create `bot_manager.py`
  - [ ] `BotManager` class with `start()`, `stop()`, `get_status()`
  - [ ] Thread management (bot runs in daemon thread)
  - [ ] Position state tracking (CE trade1/2, PE trade1/2)
  - [ ] Log buffer (deque for SSE)
  - [ ] Thread safety (Lock on positions)
  - [ ] Graceful error handling (no sys.exit)
  - [ ] Market hours validation (before 09:15 or after 15:30 → reject)

### 1.5 API Server (FastAPI)
- [ ] Create `api_server.py`
  - [ ] Initialize FastAPI app with CORS (allow localhost:3002)
  - [ ] `GET /api/status` — bot status + positions + stats
  - [ ] `POST /api/start` — start bot (validate not already running, market open)
  - [ ] `POST /api/stop` — stop bot (validate running)
  - [ ] `GET /api/trades` — trade history list
  - [ ] `GET /api/trades/pnl` — per-day P&L
  - [ ] `GET /api/trades/stats` — aggregated trade stats
  - [ ] `GET /api/settings` — all settings with metadata
  - [ ] `PUT /api/settings/{key}` — update single setting
  - [ ] `POST /api/settings/reset` — reset to defaults
  - [ ] `GET /api/logs/stream` — SSE endpoint

### 1.6 Modify Existing Files
- [ ] Modify `main.py` — start BotManager, API server, WS server
- [ ] Modify `data_streamer.py` — remove signal, remove sys.exit, add price history, broadcast
- [ ] Modify `candle.py` — add listener system
- [ ] Create `config_defaults.py` (rename config.py content)
- [ ] Create `dev.js` — concurrent runner for backend + frontend

---

## Phase 2: Frontend Scaffold

### 2.1 Next.js Setup
- [ ] Run `npx create-next-app@latest frontend --typescript --tailwind --eslint`
- [ ] `package.json` — add dependencies: `lightweight-charts`, `@mui/material`, `@emotion/react`, `@emotion/styled`
- [ ] `next.config.ts` — set: `{"devIndicators": {...}, "output": "export"}`
- [ ] `globals.css` — CSS variables, fonts (Inter + JetBrains Mono), dark theme
- [ ] `layout.tsx` — root layout with `<Navbar>` + `<StatusBar>` + children
- [ ] `tsconfig.json` — path aliases `@/components/*`, `@/lib/*`

### 2.2 Shared Components
- [ ] `Navbar.tsx` — 4 tabs: Terminal (/), Analytics (/analytics), History (/history), Settings (/settings)
- [ ] `StatusBar.tsx` — connection dot, active strikes, total P&L, clock
- [ ] `lib/types.ts` — all TypeScript interfaces
- [ ] `lib/api.ts` — `fetchStatus()`, `fetchTrades()`, `fetchSettings()`, `startBot()`, `stopBot()`, `updateSetting()`

---

## Phase 3: Terminal Page (4 Quadrants)

### 3.1 Price Diagram
- [ ] `PriceDiagram.tsx` — SVG component
  - [ ] Horizontal ref lines: ENTRY (y=0), +5, +10, -5 (points → pixels)
  - [ ] Price path: left-to-right SVG polyline/curve
  - [ ] Glowing LTP marker (latest point)
  - [ ] Trailing SL markers (dashed line when moved)
  - [ ] Entry marker (circle/dot at entry price + time)
  - [ ] Frozen state: green overlay (win) / red overlay (loss)
  - [ ] Responsive width (fills card)

### 3.2 Terminal Quadrant
- [ ] `TerminalQuadrant.tsx` — card component
  - [ ] CE: indigo top border (#6366f1), PE: amber top border (#f59e0b)
  - [ ] Header: instrument name, trade slot, state badge (watching/active/exited)
  - [ ] PriceDiagram component
  - [ ] Stats row: Entry Price, Current SL, Unrealized P&L, Duration
  - [ ] Dim variant for slot 2 (opacity 0.5, full opacity when active)
  - [ ] WebSocket connection for live updates

### 3.3 Terminal Page
- [ ] `page.tsx` — 2×2 grid layout
  - [ ] CE-T1 top-left, PE-T1 top-right
  - [ ] CE-T2 bottom-left (dim), PE-T2 bottom-right (dim)
  - [ ] Full viewport height, no scroll on quadrants

### 3.4 Terminal Logs
- [ ] `TerminalLogs.tsx` — collapsible bottom panel
  - [ ] SSE connection to `/api/logs/stream`
  - [ ] Color-coded log lines: STRATEGY (blue), EXECUTION (green), RISK (red), SYSTEM (grey)
  - [ ] Auto-scroll to bottom
  - [ ] Collapse/expand toggle
  - [ ] Max 200 lines buffer

---

## Phase 4: History Page

### 4.1 Trade Calendar
- [ ] `TradeCalendar.tsx`
  - [ ] GitHub-style heatmap grid (12px squares)
  - [ ] Year navigation (left/right arrows)
  - [ ] Color: green P&L (#10b981), red P&L (#ef4444), grey no trades (#1e1e1e)
  - [ ] Tooltip on hover: date + trades count + net P&L
  - [ ] Fetches from `GET /api/trades/pnl?year=YYYY`

### 4.2 Trade Logs Table
- [ ] `TradeLogsTable.tsx`
  - [ ] Sortable columns: Date, Time, Instrument, Slot, Entry, Exit, SL, P&L, Reason, Duration
  - [ ] P&L column: green for profit, red for loss
  - [ ] Fetches from `GET /api/trades`
  - [ ] Empty state: "No trades recorded"

### 4.3 History Page
- [ ] `page.tsx` — StatsRow + TradeCalendar + TradeLogsTable
  - [ ] StatsRow: Total Trades, Profitable, Losing, Win Rate, Net P&L
  - [ ] Fetches from `GET /api/trades/stats`

---

## Phase 5: Analytics Page

### 5.1 Analytics Page
- [ ] `page.tsx` — stats overview
  - [ ] Extended stats cards (6-8 cards with border-left accent)
  - [ ] Total Trades, Wins, Losses, Win Rate, Net P&L, Avg Win, Avg Loss, Largest Win, Largest Loss
  - [ ] Capital section: Initial Capital, Available, In Use, Realized P&L
  - [ ] Fetches from `GET /api/trades/stats`

---

## Phase 6: Settings Page

### 6.1 Settings Accordion
- [ ] `SettingsAccordion.tsx`
  - [ ] Accordion section for each category
  - [ ] Input types: text, number, boolean (toggle), select (dropdown), password
  - [ ] `input-dark` styling (dark bg, white text, subtle border)
  - [ ] Save button (only enabled when dirty)
  - [ ] Reset to defaults button
  - [ ] Fetches from `GET /api/settings`
  - [ ] Saves via `PUT /api/settings/{key}`

### 6.2 Settings Page
- [ ] `page.tsx` — accordion list
  - [ ] Categories: Timing, Strategy, Risk, Limits, Logging, Credentials

---

## Phase 7: Integration & Testing

### 7.1 Wire Connections
- [ ] TerminalLogs connected to SSE endpoint
- [ ] Quadrants connected to WebSocket
- [ ] History page connected to REST trades endpoints
- [ ] Analytics page connected to REST stats endpoint
- [ ] Settings page connected to REST settings endpoints
- [ ] StatusBar polling `/api/status` every 2s

### 7.2 WebSocket Reconnect
- [ ] Exponential backoff (1s, 2s, 4s, 8s, max 30s)
- [ ] Connection status indicator in StatusBar

### 7.3 Cleanup & Polish
- [ ] Loading states for all pages
- [ ] Error states for failed API calls
- [ ] Empty states (no trades, no data)
- [ ] 404 page

---

## Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Bot + positions + stats |
| `/api/start` | POST | Start bot |
| `/api/stop` | POST | Stop bot |
| `/api/trades` | GET | Trade list |
| `/api/trades/pnl` | GET | Per-day P&L |
| `/api/trades/stats` | GET | Aggregated stats |
| `/api/settings` | GET | All settings |
| `/api/settings/{key}` | PUT | Update setting |
| `/api/settings/reset` | POST | Reset settings |
| `/api/logs/stream` | GET | SSE log stream |

| WebSocket URI | Purpose |
|---------------|---------|
| `ws://localhost:8765` | Live quadrant data |

| Command | Purpose |
|---------|---------|
| `python main.py` | Start backend (API + WS + bot) |
| `cd frontend && npm run dev` | Start frontend |
| `node dev.js` | Start both concurrently |

---

## Progress

- [ ] Phase 1: Backend Core Files
- [ ] Phase 2: Frontend Scaffold
- [ ] Phase 3: Terminal Page (4 Quadrants)
- [ ] Phase 4: History Page
- [ ] Phase 5: Analytics Page
- [ ] Phase 6: Settings Page
- [ ] Phase 7: Integration & Testing
