import csv
import os
from datetime import datetime
from collections import defaultdict

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

def _parse_trade_log(filepath):
    trades = []
    try:
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            entry = None
            for row in reader:
                row_type = row.get("type", "").strip()
                if row_type == "entry":
                    entry = {
                        "entry_time": row.get("time", ""),
                        "symbol": row.get("symbol", ""),
                        "entry_price": _safe_float(row.get("price")),
                        "stop_loss": _safe_float(row.get("stop_loss")),
                    }
                elif row_type == "exit" and entry:
                    trade = {
                        **entry,
                        "exit_time": row.get("time", ""),
                        "exit_price": _safe_float(row.get("price")),
                        "exit_reason": row.get("exit_reason", ""),
                        "pnl": _safe_float(row.get("pnl")),
                    }
                    trades.append(trade)
                    entry = None
    except (IOError, csv.Error):
        pass
    return trades

def _safe_float(val):
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None

def _parse_date_from_time(time_str):
    try:
        return datetime.strptime(time_str[:10], "%Y-%m-%d")
    except (ValueError, IndexError):
        return None

def _scan_csvs(directory):
    results = []
    if not os.path.isdir(directory):
        return results
    for fname in os.listdir(directory):
        if fname.endswith(".csv"):
            results.append(os.path.join(directory, fname))
        elif os.path.isdir(os.path.join(directory, fname)):
            results.extend(_scan_csvs(os.path.join(directory, fname)))
    return results

def load_all_trades(year=None):
    all_trades = []
    for filepath in _scan_csvs(LOGS_DIR):
        trades = _parse_trade_log(filepath)
        if year is not None:
            trades = [t for t in trades if _parse_date_from_time(t.get("entry_time", ""))
                     and _parse_date_from_time(t["entry_time"]).year == year]
        all_trades.extend(trades)
    all_trades.sort(key=lambda t: t.get("entry_time", ""))
    return all_trades

def load_trade_pnl(year=None):
    trades = load_all_trades(year=year)
    day_map = defaultdict(lambda: {"trade_count": 0, "net_pnl": 0.0})
    for t in trades:
        dt = _parse_date_from_time(t.get("entry_time", ""))
        if not dt:
            continue
        date_str = dt.strftime("%Y-%m-%d")
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
