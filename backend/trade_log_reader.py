import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, init_db


def load_all_trades(year=None):
    init_db()
    conn = get_conn()
    if year is not None:
        rows = conn.execute(
            "SELECT * FROM trades WHERE substr(entry_time, 1, 4) = ? ORDER BY entry_time DESC",
            (str(year),)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM trades ORDER BY entry_time DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def load_trade_pnl(year=None):
    trades = load_all_trades(year=year)
    day_map = defaultdict(lambda: {"trade_count": 0, "net_pnl": 0.0})
    for t in trades:
        entry_time = t.get("entry_time", "")
        date_str = entry_time[:10] if len(entry_time) >= 10 else None
        if not date_str:
            continue
        day_map[date_str]["trade_count"] += 1
        if t.get("pnl") is not None:
            day_map[date_str]["net_pnl"] += t["pnl"]
    result = []
    for date_str in sorted(day_map.keys()):
        entry = day_map[date_str]
        result.append({
            "date": date_str,
            "trade_count": entry["trade_count"],
            "net_pnl": round(entry["net_pnl"], 2) if entry["trade_count"] > 0 else None,
        })
    return result


def load_trade_stats():
    trades = load_all_trades()
    total = len(trades)
    profitable = sum(1 for t in trades if t.get("pnl") is not None and t["pnl"] > 0)
    losing = sum(1 for t in trades if t.get("pnl") is not None and t["pnl"] < 0)
    unsettled = sum(1 for t in trades if t.get("pnl") is None)
    total_pnl = sum(t["pnl"] for t in trades if t.get("pnl") is not None)
    win_rate = round(profitable / (profitable + losing) * 100, 1) if (profitable + losing) > 0 else 0.0
    pnls = [t["pnl"] for t in trades if t.get("pnl") is not None]
    avg_win = round(sum(p for p in pnls if p > 0) / profitable, 2) if profitable > 0 else 0.0
    avg_loss = round(sum(p for p in pnls if p < 0) / losing, 2) if losing > 0 else 0.0
    largest_win = round(max(pnls), 2) if pnls else 0.0
    largest_loss = round(min(pnls), 2) if pnls else 0.0
    return {
        "total_trades": total,
        "profitable": profitable,
        "losing": losing,
        "unsettled": unsettled,
        "win_rate": win_rate,
        "total_pnl": round(total_pnl, 2),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
    }


def _row_to_dict(row):
    return {
        "id": row["id"],
        "entry_time": row["entry_time"],
        "symbol": row["symbol"],
        "entry_price": row["entry_price"],
        "stop_loss": row["stop_loss"],
        "exit_time": row["exit_time"] or "",
        "exit_price": row["exit_price"],
        "exit_reason": row["exit_reason"] or "",
        "pnl": row["pnl"],
    }
