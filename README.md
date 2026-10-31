# Option Trading Bot - TradeStack

A Python + Next.js options trading bot for Indian index options (NIFTY/BANKNIFTY) with a smart bank-first trailing stop loss system.

## Overview

TradeStack is a paper-trading and live-trading bot designed for intraday options trading. It features:

- **Bank-first trailing SL**: Parks the stop-loss at entry + 5 points (the "bank"), then ratchets up in 5-point steps as profit increases. The stop never moves backward.
- **Red candle breakout strategy**: Identifies bullish/bearish breakouts using red candle high/low levels.
- **Real-time WebSocket data**: Connects to Upstox for live tick data and order execution.
- **Web dashboard**: Next.js frontend showing trade history, MFE/MAE analysis, and performance metrics.

## Architecture

```
.
├── backend/
│   ├── upstox/                  # Upstox API integration & data streaming
│   │   ├── data_streamer.py     # Main trading engine (entry/exit logic)
│   │   └── upstox_client.py     # API client wrapper
│   ├── core/
│   │   ├── position_manager.py  # Bank-first trailing SL logic
│   │   └── trade_logger.py      # Trade logging to SQLite
│   ├── exit_rules.py            # Backtesting & counterfactual analysis
│   ├── db.py                    # SQLite database schema
│   ├── settings_db.py           # Trading parameter configuration
│   └── api_server.py            # FastAPI backend server (port 8002)
├── frontend/
│   └── app/
│       ├── components/          # React components
│       ├── api/                 # API client functions
│       └── *.tsx               # Pages (history, mfe, dashboard)
└── trades.db                    # SQLite trade database
```

## Bank-First Trailing SL Logic

The core innovation is the **bank-first** stop-loss strategy:

1. **Initial SL**: Set at `entry - 4` points (covers charges and small downside)
2. **First rung (bank)**: When profit reaches +5, the stop parks at `entry + 5`
3. **Trailing**: Every additional 5 points of profit locks another 5-point rung
4. **Never moves backward**: The stop only rises, locking in profits

This prevents the trade from sliding back to breakeven (as the old charges-only system did) and ensures that any trade touching the bank level locks in at least +5.

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Upstox API access (for live trading)

### Backend
```bash
cd backend
pip install -r requirements.txt
python api_server.py  # Starts on port 8002
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Settings
Trading parameters are stored in `backend/settings.json`:
- `bank_rung`: First profit target where SL parks (default: 5)
- `trailing_step`: Points per additional rung (default: 5)
- `initial_sl_points`: Initial stop distance from entry (default: 4)
- `max_trades_per_side`: Max open positions per side (default: 2)
- `eod_exit_time`: Force-exit all positions at 14:59

## Key Files

- **`backend/core/position_manager.py`**: Live PositionManager with bank-first trailing SL
- **`backend/exit_rules.py`**: Read-only counterfactual analysis engine comparing live vs legacy rules
- **`backend/upstox/data_streamer.py`**: WebSocket data streamer and trade execution
- **`frontend/app/history/page.tsx`**: Trade history dashboard
- **`frontend/app/components/TradeLogsTable.tsx`**: Trade table with bank-first P&L display

## Trade Database Schema

Trade data is stored in `backend/trades.db` with columns:
- `bank_rung`: Which first-rung arithmetic governed the trade (5 = bank-first, NULL = legacy)
- `mfe_points`: Max favorable excursion recorded from ticks
- `mae_points`: Max adverse excursion recorded from ticks
- `sl_rungs_locked`: How many times the trailing SL moved up
- `tick_path`: Full tick-by-tick price series (for post-trade analysis)
- `exit_reason`: How the trade exited (Trailing SL Hit, EOD Exit, etc.)

## Development

### Run Tests
```bash
cd backend
python test_excursion_tracking.py
python test_four_slots.py
python test_bank_rung.py
```

### Verify Ladder Logic
```bash
python demo_ladder.py
python _verify_ladder.py
```

## License

This project is for educational and personal trading use only. Past performance is not indicative of future results.
