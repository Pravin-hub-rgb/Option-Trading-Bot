import os
import sys
import json
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, init_db

BROKERAGE_PER_ORDER = 20.0
EXCHANGE_TXN_RATE = 0.000355
STT_RATE = 0.0015
SEBI_RATE = 0.000001
GST_RATE = 0.18


def _parse_tick_path(row):
    """
    The stored entry-to-exit tick series, as a list of floats.

    Returns None - not [] - when there is nothing stored, so callers can tell
    "this trade predates path capture" apart from "this trade had no ticks".
    Corrupt JSON also yields None rather than raising, because one bad row must
    not take down the whole history page.
    """
    try:
        raw = row["tick_path"]
    except (IndexError, KeyError):
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    out = []
    for x in data:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            return None
    return out or None


def per_point_value():
    from settings_db import get_as_dict
    cfg = get_as_dict()
    try:
        lot_size = float(cfg.get("lot_size", 65))
    except (TypeError, ValueError):
        lot_size = 65.0
    try:
        lots = float(cfg.get("lots", 1))
    except (TypeError, ValueError):
        lots = 1.0
    return lot_size * lots


def compute_charges(buy_value, sell_value):
    if buy_value is None or sell_value is None:
        return None
    turnover = buy_value + sell_value
    brokerage = BROKERAGE_PER_ORDER * 2
    exchange = turnover * EXCHANGE_TXN_RATE
    stt = sell_value * STT_RATE
    sebi = turnover * SEBI_RATE
    gst = (brokerage + exchange + sebi) * GST_RATE
    return round(brokerage + exchange + stt + sebi + gst, 2)


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
    day_map = defaultdict(lambda: {"trade_count": 0, "net_pnl": 0.0, "settled_count": 0, "net_rupees": 0.0})
    for t in trades:
        entry_time = t.get("entry_time", "")
        date_str = entry_time[:10] if len(entry_time) >= 10 else None
        if not date_str:
            continue
        day_map[date_str]["trade_count"] += 1
        if t.get("pnl") is not None:
            day_map[date_str]["net_pnl"] += t["pnl"]
            day_map[date_str]["settled_count"] += 1
            if t.get("net_pnl") is not None:
                day_map[date_str]["net_rupees"] += t["net_pnl"]
    result = []
    for date_str in sorted(day_map.keys()):
        entry = day_map[date_str]
        net_pnl = round(entry["net_pnl"], 2) if entry["settled_count"] > 0 else None
        net_rupees = round(entry["net_rupees"], 2) if entry["settled_count"] > 0 else None
        result.append({
            "date": date_str,
            "trade_count": entry["trade_count"],
            "net_pnl": net_pnl,
            "net_rupees": net_rupees,
        })
    return result


BREAKEVEN_TOLERANCE = 1.5


def load_trade_stats(year=None):
    trades = load_all_trades(year=year)
    total = len(trades)
    tol = BREAKEVEN_TOLERANCE
    profitable = sum(1 for t in trades if t.get("pnl") is not None and t["pnl"] > tol)
    losing = sum(1 for t in trades if t.get("pnl") is not None and t["pnl"] < -tol)
    breakeven = sum(1 for t in trades if t.get("pnl") is not None and -tol <= t["pnl"] <= tol)
    unsettled = sum(1 for t in trades if t.get("pnl") is None)
    total_pnl = sum(t["pnl"] for t in trades if t.get("pnl") is not None)
    win_rate = round(profitable / (profitable + losing) * 100, 1) if (profitable + losing) > 0 else 0.0
    pnls = [t["pnl"] for t in trades if t.get("pnl") is not None]
    avg_win = round(sum(p for p in pnls if p > tol) / profitable, 2) if profitable > 0 else 0.0
    avg_loss = round(sum(p for p in pnls if p < -tol) / losing, 2) if losing > 0 else 0.0
    largest_win = round(max(pnls), 2) if pnls else 0.0
    largest_loss = round(min(pnls), 2) if pnls else 0.0
    pp = per_point_value()
    gross_total_pnl = round(total_pnl * pp, 2)
    total_charges = round(sum(t["charges"] for t in trades if t.get("charges") is not None), 2)
    net_total_pnl = round(gross_total_pnl - total_charges, 2)
    days_traded = len({t["entry_time"][:10] for t in trades if t.get("entry_time")})
    return {
        "total_trades": total,
        "profitable": profitable,
        "breakeven": breakeven,
        "losing": losing,
        "unsettled": unsettled,
        "win_rate": win_rate,
        "total_pnl": round(total_pnl, 2),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "breakeven_tolerance": tol,
        "gross_total_pnl": gross_total_pnl,
        "total_charges": total_charges,
        "net_total_pnl": net_total_pnl,
        "per_point": pp,
        "days_traded": days_traded,
    }


def _row_to_dict(row):
    pp = per_point_value()
    entry_price = row["entry_price"]
    exit_price = row["exit_price"]
    pnl = row["pnl"]
    buy_value = round(entry_price * pp, 2) if entry_price is not None else None
    sell_value = round(exit_price * pp, 2) if exit_price is not None else None
    charges = compute_charges(buy_value, sell_value)
    net_pnl = round(pnl * pp - charges, 2) if pnl is not None and charges is not None else None
    return {
        "id": row["id"],
        "entry_time": row["entry_time"],
        "symbol": row["symbol"],
        "entry_price": entry_price,
        "stop_loss": row["stop_loss"],
        "exit_time": row["exit_time"] or "",
        "exit_price": exit_price,
        "exit_reason": row["exit_reason"] or "",
        "pnl": pnl,
        "gross_pnl": pnl,
        "buy_value": buy_value,
        "sell_value": sell_value,
        "charges": charges,
        "net_pnl": net_pnl,
        "mfe_points": row["mfe_points"] if "mfe_points" in row.keys() else None,
        "mae_points": row["mae_points"] if "mae_points" in row.keys() else None,
        "sl_rungs_locked": row["sl_rungs_locked"] if "sl_rungs_locked" in row.keys() else None,
        # Recorded price path. dips_below_bank is what makes the shadow engine
        # tick-wise instead of hindsight: it counts how many times the price
        # came back below +5 after touching it, i.e. exactly when a stop parked
        # at +5 would have fired. NULL means the trade predates path capture.
        "ticks_seen": row["ticks_seen"] if "ticks_seen" in row.keys() else None,
        "peak_tick": row["peak_tick"] if "peak_tick" in row.keys() else None,
        "bank_touched": row["bank_touched"] if "bank_touched" in row.keys() else None,
        "first_bank_tick": row["first_bank_tick"] if "first_bank_tick" in row.keys() else None,
        "dips_below_bank": row["dips_below_bank"] if "dips_below_bank" in row.keys() else None,
        # Raw entry-to-exit tick series, when we captured it. Parsed here so the
        # API hands the chart an array rather than a JSON string. NULL means the
        # trade predates path capture.
        "tick_path": _parse_tick_path(row),
        # What the strike selector paid for THIS option, and when. NULL on
        # every trade logged before selection capture existed. Comparing
        # sel_premium against entry_price is the only honest way to see how far
        # the option moved between being chosen and being bought.
        "sel_premium": row["sel_premium"] if "sel_premium" in row.keys() else None,
        "sel_tier": row["sel_tier"] if "sel_tier" in row.keys() else None,
        "sel_at": row["sel_at"] if "sel_at" in row.keys() else None,
    }
