# Options Trading Bot — Dashboard Implementation Plan

**Date:** 2026-07-16
**Project:** `Desktop/option-trading-bot/`

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  SINGLE PYTHON PROCESS (port 8002 + 8765)                           │
│                                                                      │
│  main.py (entry point)                                               │
│  ├── api_server.py       → FastAPI :8002 (REST + SSE)               │
│  ├── live_feed_server.py → WebSocket :8765 (real-time quadrant data)│
│  ├── bot_manager.py      → controls bot lifecycle                   │
│  ├── settings_db.py      → JSON-backed settings                     │
│  ├── trade_log_reader.py → CSV trade log parser                     │
│  │                                                                   │
│  └── Bot Thread (daemon):                                            │
│       ├── scheduler.py    → time waits, strike fetching              │
│       ├── data_streamer.py → Upstox WS → ticks + OHLC               │
│       ├── candle.py       → CandleAggregator (1-min candles)        │
│       └── strategy + PM   → RedCandleHighBreak + PositionManager    │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  NEXT.JS FRONTEND (port 3002) — Pure UI layer                       │
│                                                                      │
│  /           → Terminal (4-quadrant with price diagrams)             │
│  /history    → Trade Logs (calendar heatmap + table)                │
│  /analytics  → Strategy Dashboard (stats overview)                  │
│  /settings   → Settings (accordion categories)                      │
│                                                                      │
│  REST  → http://localhost:8002/api/*                                 │
│  SSE   → http://localhost:8002/api/logs/stream                      │
│  WS    → ws://localhost:8765                                         │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow — Terminal Page (4 Quadrants)

```
Upstox Feed → DataStreamer → on_message()
  ├── process_ohlc_candles() → CandleAggregator
  │   └── candle_closed/candle_updated events
  │       └── LiveFeedServer.broadcast() → WS → Browser chart.series.update()
  │
  ├── process_tick()
  │   ├── PositionManager (entry/exit/SL checks)
  │   │   └── trade events → LiveFeedServer → WS → Browser
  │   └── LTP update (throttled 300ms) → LiveFeedServer → WS → Browser
  │
  ├── PositionManager.get_state() → status_poll → REST → Browser (every 2s)
  └── print() capture → log_buffer → SSE → Browser terminal window
```

---

## 2. File Manifest

### New Python Files (7)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `api_server.py` | FastAPI app — all REST endpoints + SSE | fastapi, uvicorn |
| `bot_manager.py` | Bot lifecycle wrapper (start/stop/status) | scheduler, data_streamer |
| `live_feed_server.py` | WebSocket broadcast server | websockets>=13.0 |
| `settings_db.py` | Read/write `settings.json` | json (stdlib) |
| `trade_log_reader.py` | Parse trade CSVs → API data | csv (stdlib) |
| `dev.js` | Run frontend + backend concurrently | concurrently |
| `frontend/` | Next.js app (scaffold) | next, react, lightweight-charts |

### Modified Python Files (5)

| File | Changes |
|------|---------|
| `main.py` | Start BotManager + API server + WS server instead of scheduler directly |
| `upstox/data_streamer.py` | Remove `signal.signal()`, remove `sys.exit()`, accept `live_feed_server` ref, add price history buffer, broadcast events |
| `core/candle.py` | Add listener/callback system for candle events |
| `config.py` | Rename to `config_defaults.py` (settings.json becomes the source of truth) |
| `requirements.txt` | Add `websockets`, `fastapi`, `uvicorn` |

### New Frontend Files

| File | Component |
|------|-----------|
| `frontend/package.json` | Dependencies |
| `frontend/next.config.ts` | Next.js config |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/src/app/layout.tsx` | Root layout with nav |
| `frontend/src/app/globals.css` | Global styles + CSS variables |
| `frontend/src/app/page.tsx` | **Terminal** — 4-quadrant dashboard |
| `frontend/src/app/history/page.tsx` | **Trade Logs** — calendar + table |
| `frontend/src/app/analytics/page.tsx` | **Analytics** — stats overview |
| `frontend/src/app/settings/page.tsx` | **Settings** — accordion form |
| `frontend/src/components/TerminalQuadrant.tsx` | Single quadrant card with price diagram |
| `frontend/src/components/PriceDiagram.tsx` | SVG price path visualization |
| `frontend/src/components/TradeLogsTable.tsx` | Trade history table |
| `frontend/src/components/TradeCalendar.tsx` | GitHub-style calendar heatmap |
| `frontend/src/components/TerminalLogs.tsx` | SSE log viewer |
| `frontend/src/components/SettingsAccordion.tsx` | Settings form section |
| `frontend/src/components/StatusBar.tsx` | Top bar (connection, strikes, P&L) |
| `frontend/src/components/Navbar.tsx` | Navigation tabs |
| `frontend/src/lib/api.ts` | API client helpers |
| `frontend/src/lib/types.ts` | TypeScript interfaces |

---

## 3. REST API Specification (FastAPI :8002)

### Bot Control

```
GET  /api/status
→ { running: bool, mode: str, connected: bool,
    instruments: string[], strikes: { ce: str, pe: str },
    positions: {
      ce: { trade1: PositionState | null, trade2: PositionState | null },
      pe: { trade1: PositionState | null, trade2: PositionState | null }
    },
    stats: { total_trades: int, wins: int, losses: int,
             win_rate: float, total_pnl: float },
    strategy: { name: str, ref_candle: ..., candles_waited: int } }

POST /api/start
body: { instruments?: ["CE","PE"] | ["CE"] | ["PE"] }
→ { status: "starting", message: str, strikes: {...} }

POST /api/stop
→ { status: "stopped", summary: {...} }
```

### Trade Logs

```
GET /api/trades
?year=2026 (optional)
→ { trades: TradeEntry[], count: int }

GET /api/trades/pnl?year=2026
→ { days: [{ date: str, trade_count: int, net_pnl: float | null }] }

GET /api/trades/stats
→ { total_trades: int, profitable: int, losing: int,
    unsettled: int, win_rate: float, total_pnl: float,
    capital: { initial: float, available: float, in_use: float, realized_pnl: float } }
```

### Settings

```
GET /api/settings
→ { settings: SettingMeta[] }

PUT /api/settings/{key}
body: { value: str }
→ { status: "saved" }

POST /api/settings/reset
→ { status: "reset" }
```

### Logs

```
GET /api/logs/stream
→ SSE stream: data: {"type":"log","timestamp":"...","message":"..."}
```

---

## 4. WebSocket Protocol (WS :8765)

All messages are JSON. Frontend connects once and listens.

### Messages Server → Client

```typescript
// On connect — full state snapshot
interface InitMessage {
  type: "init";
  status: BotStatus;  // same as GET /api/status
}

// Current candle updated (every tick — throttled 300ms)
interface CandleUpdateMessage {
  type: "candle_update";
  instrument: "CE" | "PE";
  trade_slot: 1 | 2;
  candle: Candle;  // { timestamp, open, high, low, close }
}

// Completed candle (every 1 min)
interface CandleClosedMessage {
  type: "candle_closed";
  instrument: "CE" | "PE";
  trade_slot: 1 | 2;
  candle: Candle;
}

// LTP tick (throttled 300ms) — for price diagram path
interface TickMessage {
  type: "tick";
  instrument: "CE" | "PE";
  ltp: number;
  timestamp: string;  // "HH:MM:SS.mmm"
  sl: number | null;  // current stop loss
  pnl: number | null; // current unrealized P&L
}

// Trade event (entry or exit)
interface TradeMessage {
  type: "trade";
  instrument: "CE" | "PE";
  trade_slot: 1 | 2;
  action: "entry" | "exit";
  price: number;
  timestamp: string;
  pnl?: number;      // exit only
  reason?: string;   // exit only (e.g. "Trailing SL Hit")
}

// Strategy state update (watching/entry/exit)
interface StrategyMessage {
  type: "strategy";
  instrument: "CE" | "PE";
  state: "idle" | "watching" | "in_position" | "exited_win" | "exited_loss" | "stopped";
  ref_high?: number;       // watching: red candle high
  candles_waited?: number; // watching: 1/2
  entry_price?: number;
  current_sl?: number;
  highest_price?: number;
}
```

### Messages Client → Server

None for now. Connection is read-only.

---

## 5. Key Data Structures

### PositionState (used by BotManager + API)

```python
@dataclass
class PositionState:
    trade_slot: int          # 1 or 2
    state: str               # idle | watching | in_position | exited_win | exited_loss | stopped
    instrument: str          # CE | PE
    
    # Watching state
    ref_candle_high: float | None = None
    candles_waited: int = 0
    
    # Position state
    entry_price: float | None = None
    current_sl: float | None = None
    highest_price: float | None = None
    entry_time: datetime | None = None
    
    # Price history (for diagram path)
    price_history: list[tuple[datetime, float]] = field(default_factory=list)
    
    # Exit state
    exit_price: float | None = None
    exit_time: datetime | None = None
    exit_reason: str | None = None
    pnl: float | None = None
    duration_seconds: float | None = None
```

### TradeEntry (used by API)

```python
@dataclass
class TradeEntry:
    id: int
    date: str              # "2026-07-16"
    time: str              # "09:17:05"
    instrument: str        # "CE" | "PE"
    trade_slot: int        # 1 | 2
    entry_price: float
    exit_price: float | None
    stop_loss: float | None
    pnl: float | None
    exit_reason: str | None
    duration_seconds: float | None
```

---

## 6. Threading Architecture

```
main thread (main.py):
  ├── Start LiveFeedServer (daemon thread, asyncio event loop)
  ├── Start api_server (daemon thread, uvicorn internally threaded)
  └── Wait for shutdown signal

on API call POST /api/start:
  api_server thread → bot_manager.start()
    → Creates BotThread (daemon):
        1. Load settings from settings.json
        2. Fetch strikes via scheduler.fetch_live_strikes()
        3. Wait until market open if needed
        4. Create DataStreamer with live_feed_server ref
        5. DataStreamer.run() ← this was previously in main.py
        6. Wait until market end

on API call POST /api/stop:
  api_server thread → bot_manager.stop()
    → Sets bot_manager.running = False
    → Calls scheduler.stop() → streamer.close()
    → BotThread exits cleanly
```

### Thread Safety Rules

| Resource | Access Pattern | Protection |
|----------|---------------|------------|
| `bot_manager.positions` | Read by REST, Write by bot thread | threading.Lock |
| `bot_manager.log_buffer` | Read by SSE, Write by bot thread | deque (thread-safe) |
| `DataStreamer.components` | Read by REST (via bot_manager), Write by streamer thread | threading.Lock |
| `settings.json` | Read by REST, Write by REST | file write atomicity |
| `logs/trade_log_*.csv` | Write by bot, Read by REST | flush after each write, no lock needed |

---

## 7. Settings Management

**File:** `settings.json` (in project root)

On first run, created from `config.py` defaults. On subsequent runs, reads from JSON.

```json
{
  "market_start": { "value": "09:15", "type": "time", "label": "Market Start", "category": "timing" },
  "market_end": { "value": "15:30", "type": "time", "label": "Market End", "category": "timing" },
  "strategy_start": { "value": "09:15", "type": "time", "label": "Strategy Start", "category": "timing" },
  "entry_window_end": { "value": "15:00", "type": "time", "label": "Entry Window End", "category": "timing" },
  "market_open_delay": { "value": "40", "type": "number", "label": "Market Open Delay (s)", "category": "timing" },
  "max_wait_candles": { "value": "2", "type": "number", "label": "Max Wait Candles", "category": "strategy" },
  "allow_reference_shift": { "value": "true", "type": "boolean", "label": "Allow Reference Shift", "category": "strategy" },
  "initial_sl_points": { "value": "5", "type": "number", "label": "Initial SL (points)", "category": "risk" },
  "trailing_trigger": { "value": "5", "type": "number", "label": "Trailing Trigger (points)", "category": "risk" },
  "trailing_step": { "value": "5", "type": "number", "label": "Trailing Step (points)", "category": "risk" },
  "stop_after_first_win": { "value": "true", "type": "boolean", "label": "Stop After First Win", "category": "limits" },
  "max_trades_per_side": { "value": "2", "type": "number", "label": "Max Trades Per Side", "category": "limits" },
  "log_level": { "value": "VERBOSE", "type": "select", "options": "VERBOSE,MINIMAL", "label": "Log Level", "category": "logging" },
  "log_every_tick": { "value": "false", "type": "boolean", "label": "Log Every Tick", "category": "logging" },
  "log_candle_updates": { "value": "true", "type": "boolean", "label": "Log Candle Updates", "category": "logging" },
  "access_token": { "value": "", "type": "password", "label": "Upstox Access Token", "category": "credentials" }
}
```

Bot loads settings from this file at `start()`. API saves to this file on `PUT /api/settings/{key}`.

---

## 8. Frontend Component Tree

```
<Layout>
  <Navbar />                    # Tab bar: Terminal | Analytics | History | Settings
  <StatusBar />                 # Connection dot, strikes, account P&L, clock
  {children}                    # Page content
  
  Terminal (/):
    <div.grid-2x2>
      <TerminalQuadrant instrument="CE" slot={1} />    # CE Trade 1
      <TerminalQuadrant instrument="PE" slot={1} />    # PE Trade 1
      <TerminalQuadrant instrument="CE" slot={2} dim /> # CE Trade 2 (dim)
      <TerminalQuadrant instrument="PE" slot={2} dim /> # PE Trade 2 (dim)
    </div.grid-2x2>
    <TerminalLogs />             # Collapsible SSE log viewer
  
  TerminalQuadrant:
    <div.card className={ce|pe}>
      <div.header> title + state badge </div>
      <PriceDiagram />           # SVG path + reference lines
      <div.stats> entry, SL, P&L, duration </div>
    </div.card>
  
  PriceDiagram:
    <svg> path + grid lines + markers + glow </svg>
  
  History (/history):
    <StatsRow />                 # Total, Wins, Losses, Win Rate, Net P&L
    <TradeCalendar />            # Year nav + heatmap squares
    <TradeLogsTable />           # Sortable trade table
  
  Analytics (/analytics):
    <StatsRow />                 # Extended stats
    <div.charts>                 # Win rate, P&L over time (optional)
  
  Settings (/settings):
    <SettingsAccordion category="timing" />
    <SettingsAccordion category="strategy" />
    <SettingsAccordion category="risk" />
    <SettingsAccordion category="limits" />
    <SettingsAccordion category="logging" />
    <SettingsAccordion category="credentials" />
```

---

## 9. CSS Design System

```css
:root {
  --bg: #0a0a0a;
  --surface: #111111;
  --border: rgba(255,255,255,0.06);
  --ce: #6366f1;
  --pe: #f59e0b;
  --profit: #10b981;
  --loss: #ef4444;
  --warning: #facc15;
  --text: #e5e7eb;
  --text-muted: #64748b;
}
```

All design tokens extracted from the superdesign outputs. The frontend will use these exact values.

---

## 10. Running & Development

### Installation

```bash
cd Desktop/option-trading-bot

# Python deps
pip install websockets>=13.0 fastapi uvicorn

# Frontend deps
cd frontend && npm install
```

### Running

```bash
# Terminal 1: Python backend (bot + API + WS)
python main.py

# Terminal 2: Frontend
cd frontend && npm run dev
```

Or via dev.js:

```bash
node dev.js
```

### Ports

| Service | Port | Purpose |
|---------|------|---------|
| FastAPI | 8002 | REST + SSE |
| WebSocket | 8765 | Real-time quadrant data |
| Next.js | 3002 | Frontend UI |

---

## 11. Implementation Order

| Phase | Step | Files | Est. |
|-------|------|-------|------|
| **1. Backend Core** | Create `bot_manager.py` | 1 file | 30m |
| | Create `settings_db.py` | 1 file | 15m |
| | Create `trade_log_reader.py` | 1 file | 15m |
| | Create `live_feed_server.py` | 1 file | 30m |
| | Create `api_server.py` | 1 file | 45m |
| | Modify `main.py` | 1 file | 10m |
| | Modify `data_streamer.py` | 1 file | 30m |
| | Modify `candle.py` | 1 file | 10m |
| | Modify `config.py` | 1 file | 5m |
| | Create `dev.js` | 1 file | 5m |
| **2. Frontend** | Scaffold Next.js app | 4 files | 15m |
| | Create `Navbar.tsx` + `StatusBar.tsx` | 2 files | 20m |
| | Create `TerminalQuadrant.tsx` + `PriceDiagram.tsx` | 2 files | 45m |
| | Create Terminal page (`/`) | 1 file | 15m |
| | Create `TerminalLogs.tsx` | 1 file | 15m |
| | Create `TradeLogsTable.tsx` + `TradeCalendar.tsx` | 2 files | 30m |
| | Create History page (`/history`) | 1 file | 10m |
| | Create Analytics page (`/analytics`) | 1 file | 15m |
| | Create `SettingsAccordion.tsx` | 1 file | 20m |
| | Create Settings page (`/settings`) | 1 file | 10m |
| | Create API client + types | 2 files | 15m |
| **3. Integration** | Wire SSE to TerminalLogs | 1 file | 10m |
| | Wire WebSocket to quadrants | 1 file | 20m |
| | Wire REST to History/Analytics/Settings | 3 files | 15m |
| **4. Testing** | Test bot start/stop via API | — | 15m |
| | Test trade log CSV → API → frontend | — | 15m |
| | Test settings read/write cycle | — | 10m |
| | Test WebSocket reconnect | — | 10m |
| | **Total** | | **~7-8 hours** |

---

## 12. Key Changes to Existing Files

### `data_streamer.py`

```python
# REMOVE from __init__:
signal.signal(signal.SIGINT, self.signal_handler)  # ← DELETE
sys.exit(1)  # in run() → change to raise exception

# ADD to __init__:
self.live_feed_server = live_feed_server
self.price_history = {inst: [] for inst in instruments}  # for diagram path

# ADD to process_tick():
if comp['position_manager'].is_in_position():
    self.price_history[inst_type].append((timestamp, ltp))
    # Trim to last 1000 points
    if len(self.price_history[inst_type]) > 1000:
        self.price_history[inst_type] = self.price_history[inst_type][-1000:]

# ADD methods for broadcast:
def _broadcast_tick(self, inst, ltp, timestamp):
    if not self.live_feed_server: return
    # throttle 300ms, then broadcast
```

### `candle.py`

```python
# ADD to CandleAggregator:
self.listeners = []

def add_listener(self, callback):
    self.listeners.append(callback)

def _notify(self, event_type, candle):
    for cb in self.listeners:
        cb(event_type, candle)

# In update_from_ohlc():
# after adding to history:
self._notify("candle_closed", candle)
# after updating current:
self._notify("candle_updated", self.current_candle)
```

### `main.py`

```python
from api_server import start_api_server
from live_feed_server import LiveFeedServer
from bot_manager import BotManager

def main():
    # 1. Load settings
    # 2. Start LiveFeedServer (daemon thread)
    # 3. Start FastAPI server (daemon thread, port 8002)
    # 4. Print "Dashboard: http://localhost:3002"
    # 5. Wait for Ctrl+C
    #    (bot is started/stopped via API, not directly in main)
```

---

## 13. Edge Cases & Mitigations

| # | Edge Case | Mitigation |
|---|-----------|------------|
| 1 | `signal.signal()` in DataStreamer | Remove it. BotManager handles signals. |
| 2 | `sys.exit(1)` on connection failure | Replace with exception + auto-reconnect logic |
| 3 | Two CE trades — tracking slots | BotManager maintains `positions` dict with slot tracking |
| 4 | Price history not stored | `DataStreamer.price_history[inst]` buffer (max 1000 points) |
| 5 | CSV file locking | TradeLogger flushes after each write. Reader opens read-only. |
| 6 | WS not ready when frontend connects | Frontend auto-reconnects with exponential backoff |
| 7 | Settings change mid-bot | Settings cached in memory; applied on next `start()` |
| 8 | Race: API reads while bot writes | `threading.Lock` on `bot_manager.positions` |
| 9 | Start after market close | API returns 400, message "Market closed" |
| 10 | Start while already running | API returns 400, message "Bot already running" |
| 11 | Stop while already stopped | API returns 400, message "Bot not running" |
| 12 | No strikes found | API returns error with details. User can retry. |
| 13 | WebSocket disconnects mid-session | Upstox SDK auto-reconnects. LiveFeedServer keeps broadcasting. |
| 14 | SSE client count grows | Each SSE connection is independent. Broadcast fan-out to all. |
