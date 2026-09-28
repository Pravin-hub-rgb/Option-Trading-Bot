"""
SMART P&L SHADOW ENGINE
======================

Read-only. Answers: "what would the day have looked like if we had traded it
with smarter exit rules?" WITHOUT touching the live bot.

Two things it measures per trade:
  * MFE  - how far the trade travelled in our favour before it exited
  * the giveback - MFE minus what we actually banked

Why MFE matters: with the current ladder (trigger +5, step +5) a trade that
touches +5 locks the SL at entry+1 to cover charges. Roughly half the trades
reach that trigger and then slide all the way back to scratch. That band is
recoverable profit, and this module prices it.

MFE SOURCES
-----------
  * "exact"   - mfe_points was recorded in the DB (trades logged after the
                excursion tracking was added). Precise.
  * "rung"    - older trades. We infer the MFE band from which SL rung was
                locked at exit time, which is exact for band purposes.
  * "unknown" - manual / bot-stopped exits, where we cannot know the peak.
                These are excluded from counterfactuals rather than guessed.

All rupee figures reuse trade_log_reader.compute_charges so they match the
dashboard exactly.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trade_log_reader import load_all_trades, compute_charges, per_point_value

# A trailing SL fill happens at or below the locked rung. Options tick is 0.05,
# so allow a tick of tolerance when matching a fill back to its rung.
TICK_TOLERANCE = 0.06

# rung -> MFE band it implies. rung N locks when profit reaches 5 + 5*(N-1).
RUNGS = [
    (1.0, 5),    # SL=entry+1   => MFE was in [5, 10)
    (5.0, 10),   # SL=entry+5   => MFE was in [10, 15)
    (10.0, 15),
    (15.0, 20),
    (20.0, 25),
    (25.0, 30),
]

BUCKET_LABELS = {
    0: "Never reached +5",
    5: "MFE 5-10",
    10: "MFE 10-15",
    15: "MFE 15-20",
    20: "MFE 20-25",
    25: "MFE 25-30",
    30: "MFE 30+",
}

# Named strategies evaluated side by side. bank_at=None disables banking.
STRATEGIES = [
    {"key": "current", "label": "Current (trailing as-is)",
     "bank_at": None, "prove_at": None, "day_stop_at": None},
    {"key": "bank5", "label": "Bank +5 (staged: trail past +10)",
     "bank_at": 5, "prove_at": 10, "day_stop_at": None},
    {"key": "bank5_stop10", "label": "Bank +5 + stop day at +10",
     "bank_at": 5, "prove_at": 10, "day_stop_at": 10},
    {"key": "bank5_stop8", "label": "Bank +5 + stop day at +8",
     "bank_at": 5, "prove_at": 10, "day_stop_at": 8},
    {"key": "bank5_stop5", "label": "Bank +5 + stop day at +5",
     "bank_at": 5, "prove_at": 10, "day_stop_at": 5},
    {"key": "hard5", "label": "Hard TP +5 on every trade",
     "bank_at": 5, "prove_at": None, "day_stop_at": None},
    {"key": "hard10", "label": "Hard TP +10 on every trade",
     "bank_at": 10, "prove_at": None, "day_stop_at": None},
]


def _rung_mfe(pnl):
    """
    Infer the MFE band a trailing fill implies.

    A non-gap fill happens AT or BELOW the locked rung, so the smallest rung
    that can hold the fill tells us which milestone the trade had reached.
    Returns 0 for a losing exit (the trigger was never armed) and None only
    when we genuinely cannot tell.
    """
    if pnl is None:
        return None
    if pnl <= 0:
        # Initial SL was hit, so profit never reached the +5 trigger.
        return 0
    for rung, mfe in RUNGS:
        if pnl <= rung + TICK_TOLERANCE:
            return mfe
    return 30


def _bucket_of(mfe):
    if mfe is None or mfe < 5:
        return 0
    for b in (5, 10, 15, 20, 25):
        if mfe < b + 5:
            return b
    return 30


def resolve_mfe(trade):
    """Return (mfe_points, source) for a trade."""
    stored = trade.get("mfe_points")
    if stored is not None:
        return float(stored), "exact"
    reason = (trade.get("exit_reason") or "").lower()
    if "trailing" in reason:
        return _rung_mfe(trade.get("pnl")), "rung"
    return None, "unknown"


def enrich(trade):
    """Attach MFE / bucket / giveback to a raw trade dict."""
    t = dict(trade)
    mfe, source = resolve_mfe(t)
    t["mfe_points"] = mfe
    t["mfe_source"] = source
    t["mfe_bucket"] = _bucket_of(mfe)
    t["mfe_bucket_label"] = BUCKET_LABELS[t["mfe_bucket"]]
    if mfe is not None and t.get("pnl") is not None:
        t["giveback_points"] = round(mfe - t["pnl"], 2)
    else:
        t["giveback_points"] = None
    return t


def net_for(trade, pnl_points):
    """Net rupees for a hypothetical exit at pnl_points, using real charges."""
    pp = per_point_value()
    entry = trade["entry_price"]
    buy = round(entry * pp, 2)
    sell = round((entry + pnl_points) * pp, 2)
    charges = compute_charges(buy, sell)
    if charges is None:
        return None
    return round(pnl_points * pp - charges, 2)


def smart_exit(trade, bank_at, prove_at):
    """
    Staged exit: hold a hard target at `bank_at` until the trade proves itself
    by reaching `prove_at`, then hand it back to the trailing ladder.

    Returns (pnl_points, rule_fired).
    """
    actual = trade["pnl"]
    mfe = trade.get("mfe_points")
    if actual is None:
        return None, "unsettled"
    if bank_at is None:
        return actual, "current"
    if mfe is None:
        return actual, "unknown-mfe"
    if mfe < bank_at:
        # Never reached the target, so the initial SL is what would have hit.
        return actual, "untouched"
    if prove_at is not None and mfe >= prove_at:
        return actual, "trailed"
    return float(bank_at), "banked"


def simulate(trades, bank_at=None, prove_at=None, day_stop_at=None):
    """
    Replay settled trades in entry-time order, per day.

    day_stop_at is compared against the CUMULATIVE realised points for the day
    (gross, in points - not net rupees). Once reached, every later trade that
    day is skipped, which is what "done for the day" means in practice.
    """
    rows = []
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["entry_time"][:10]].append(t)

    for day in sorted(by_day):
        day_pts = 0.0
        stopped = False
        for t in sorted(by_day[day], key=lambda x: (x["entry_time"], x["id"] or 0)):
            pnl, rule = smart_exit(t, bank_at, prove_at)
            skipped = stopped or t.get("pnl") is None
            if skipped:
                pnl, rule = t.get("pnl"), "skipped"
            elif pnl is not None:
                day_pts += pnl
                if day_stop_at is not None and day_pts >= day_stop_at:
                    stopped = True

            actual_net = t.get("net_pnl")
            smart_net = None if pnl is None else net_for(t, pnl)
            rows.append({
                "id": t.get("id"),
                "date": day,
                "entry_time": t.get("entry_time"),
                "symbol": t.get("symbol"),
                "entry_price": t.get("entry_price"),
                "exit_price": t.get("exit_price"),
                "exit_reason": t.get("exit_reason"),
                "mfe_points": t.get("mfe_points"),
                "mfe_source": t.get("mfe_source"),
                "mfe_bucket": t.get("mfe_bucket"),
                "mfe_bucket_label": t.get("mfe_bucket_label"),
                "giveback_points": t.get("giveback_points"),
                "actual_pnl": t.get("pnl"),
                "actual_net": actual_net,
                "smart_pnl": None if skipped else pnl,
                "smart_net": None if skipped else smart_net,
                "delta_points": None if (skipped or pnl is None or t.get("pnl") is None)
                                else round(pnl - t["pnl"], 2),
                "delta_net": None if (skipped or smart_net is None or actual_net is None)
                              else round(smart_net - actual_net, 2),
                "rule_fired": rule,
                "day_stopped": stopped and not skipped,
            })
    return rows


def _summarise(rows):
    taken = [r for r in rows if r["smart_pnl"] is not None]
    return {
        "trades": len(taken),
        "trades_skipped": sum(1 for r in rows if r["rule_fired"] == "skipped"),
        "gross_points": round(sum(r["smart_pnl"] for r in taken), 2),
        "net_rupees": round(sum(r["smart_net"] for r in taken), 2),
        "actual_gross_points": round(sum(r["actual_pnl"] for r in taken if r["actual_pnl"] is not None), 2),
        "actual_net_rupees": round(sum(r["actual_net"] for r in taken if r["actual_net"] is not None), 2),
        "win_rate": round(100 * sum(1 for r in taken if r["smart_pnl"] > 0) / len(taken), 1) if taken else 0.0,
    }


def _baseline_summary(rows):
    return _summarise([dict(r, smart_pnl=r["actual_pnl"], smart_net=r["actual_net"],
                            rule_fired="current") for r in rows])


def smart_pnl_report(year=None, bank_at=5, prove_at=10, day_stop_at=0):
    """Full side-by-side report.

    day_stop_at of 0 (or None) means "no day stop", which mirrors the live bot.
    Normalised here so no caller can accidentally pass a threshold of 0, which
    would read as "stop as soon as the day is not losing".
    """
    day_stop_at = day_stop_at or None
    trades = [enrich(t) for t in load_all_trades(year=year) if t.get("pnl") is not None]
    trades = [t for t in trades if t.get("entry_time")]
    rows = simulate(trades, bank_at, prove_at, day_stop_at)
    baseline = _baseline_summary(rows)

    by_day = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r)

    days = []
    for day in sorted(by_day):
        rs = by_day[day]
        actual_net = sum(x["actual_net"] for x in rs if x["actual_net"] is not None)
        smart_net = sum(x["smart_net"] for x in rs if x["smart_net"] is not None)
        days.append({
            "date": day,
            "trades_actual": len(rs),
            "trades_taken": sum(1 for x in rs if x["smart_net"] is not None),
            "actual_net": round(actual_net, 2),
            "smart_net": round(smart_net, 2),
            "delta_net": round(smart_net - actual_net, 2),
            "stopped_early": any(x["day_stopped"] for x in rs),
            "first_trade_pnl": rs[0]["actual_pnl"],
        })

    smart = _summarise(rows)
    by_month = defaultdict(lambda: [0, 0.0, 0.0])
    for r in rows:
        if r["smart_net"] is None:
            continue
        m = r["date"][:7]
        by_month[m][0] += 1
        by_month[m][1] += r["actual_net"] or 0
        by_month[m][2] += r["smart_net"]
    monthly = [{"month": m, "trades": v[0], "actual_net": round(v[1], 2),
                "smart_net": round(v[2], 2), "delta_net": round(v[2] - v[1], 2)}
               for m, v in sorted(by_month.items())]

    return {
        "settings": {"bank_at": bank_at, "prove_at": prove_at, "day_stop_at": day_stop_at},
        "trades": sorted(rows, key=lambda r: r["entry_time"], reverse=True),
        "days": days,
        "summary": smart,
        "baseline": baseline,
        "delta_net": round(smart["net_rupees"] - baseline["net_rupees"], 2),
        "per_day_delta": round((smart["net_rupees"] - baseline["net_rupees"]) / max(1, len(days)), 2),
        "monthly": monthly,
        "mfe_coverage": mfe_report(year=year),
    }


def mfe_report(year=None):
    """MFE distribution, the giveback leak, and the never-reached band."""
    trades = [enrich(t) for t in load_all_trades(year=year) if t.get("pnl") is not None]
    known = [t for t in trades if t.get("mfe_points") is not None]
    unknown = [t for t in trades if t.get("mfe_points") is None]

    hist = []
    for b in sorted(BUCKET_LABELS):
        grp = [t for t in known if t["mfe_bucket"] == b]
        if not grp:
            continue
        hist.append({
            "bucket": b,
            "label": BUCKET_LABELS[b],
            "count": len(grp),
            "pct": round(100 * len(grp) / max(1, len(known)), 1),
            "avg_pnl": round(sum(t["pnl"] for t in grp) / len(grp), 2),
            "avg_net": round(sum(net_for(t, t["pnl"]) for t in grp) / len(grp), 2),
            "avg_giveback": round(sum(t["giveback_points"] for t in grp) / len(grp), 2),
            "total_net": round(sum(net_for(t, t["pnl"]) for t in grp), 2),
        })

    # The recoverable leak: reached +5, exited at or below the BE rung (+1).
    leak = [t for t in known if 5 <= (t["mfe_points"] or 0) < 10]
    leak_actual = sum(net_for(t, t["pnl"]) for t in leak)
    leak_banked = sum(net_for(t, 5) for t in leak)

    never = [t for t in known if t["mfe_points"] is not None and t["mfe_points"] < 5]
    runner = [t for t in known if (t["mfe_points"] or 0) >= 10]

    return {
        "total_trades": len(trades),
        "mfe_known": len(known),
        "mfe_unknown": len(unknown),
        "exact_count": sum(1 for t in trades if t.get("mfe_source") == "exact"),
        "rung_count": sum(1 for t in trades if t.get("mfe_source") == "rung"),
        "histogram": hist,
        "leak": {
            "count": len(leak),
            "actual_net": round(leak_actual, 2),
            "banked_at_5_net": round(leak_banked, 2),
            "recoverable": round(leak_banked - leak_actual, 2),
        },
        "never_reached_5": {
            "count": len(never),
            "pct": round(100 * len(never) / max(1, len(known)), 1),
            "avg_pnl": round(sum(t["pnl"] for t in never) / len(never), 2) if never else 0,
            "total_net": round(sum(net_for(t, t["pnl"]) for t in never), 2),
        },
        "reached_10": {
            "count": len(runner),
            "pct": round(100 * len(runner) / max(1, len(known)), 1),
        },
    }


def strategy_comparison(year=None):
    """Every named strategy scored on the same settled trades."""
    trades = [enrich(t) for t in load_all_trades(year=year) if t.get("pnl") is not None]
    trades = [t for t in trades if t.get("entry_time")]
    days = {t["entry_time"][:10] for t in trades}
    out = []
    for s in STRATEGIES:
        rows = simulate(trades, s["bank_at"], s["prove_at"], s["day_stop_at"])
        summ = _summarise(rows)
        out.append({
            "key": s["key"],
            "label": s["label"],
            "bank_at": s["bank_at"],
            "prove_at": s["prove_at"],
            "day_stop_at": s["day_stop_at"],
            "trades": summ["trades"],
            "skipped": summ["trades_skipped"],
            "gross_points": summ["gross_points"],
            "net_rupees": summ["net_rupees"],
            "win_rate": summ["win_rate"],
            "per_day": round(summ["net_rupees"] / max(1, len(days)), 2),
        })
    return out


def threshold_sweep(year=None, bank_at=5, prove_at=10):
    """Day-stop threshold sweep, to see whether the optimum is a plateau or noise."""
    trades = [enrich(t) for t in load_all_trades(year=year) if t.get("pnl") is not None]
    trades = [t for t in trades if t.get("entry_time")]
    days = {t["entry_time"][:10] for t in trades}
    out = []
    for stop in (None, 5, 6, 7, 8, 9, 10, 11, 12, 15, 20):
        rows = simulate(trades, bank_at, prove_at, stop)
        summ = _summarise(rows)
        out.append({
            "day_stop_at": stop,
            "trades": summ["trades"],
            "net_rupees": summ["net_rupees"],
            "per_day": round(summ["net_rupees"] / max(1, len(days)), 2),
        })
    return out


def risk_analysis(year=None):
    """
    Downside analysis. Answers the question "what if the rule makes things
    WORSE?" by scoring each scenario against a fixed baseline (every trade that
    actually happened, at its actual result) and counting the days each rule
    improved, left alone, or damaged.
    """
    trades = [enrich(t) for t in load_all_trades(year=year) if t.get("pnl") is not None]
    trades = [t for t in trades if t.get("entry_time")]
    base = defaultdict(float)
    for t in trades:
        base[t["entry_time"][:10]] += t["pnl"]
    baseline_points = round(sum(base.values()), 2)

    scenarios = [
        ("bank_only", "Bank +5 only", 5, 10, None),
        ("stop10_only", "Day-stop +10 only", None, None, 10),
        ("stop5_only", "Day-stop +5 only", None, None, 5),
        ("both", "Bank +5 + day-stop +10", 5, 10, 10),
    ]

    out = []
    for key, label, b, p, d in scenarios:
        rows = simulate(trades, b, p, d)
        smart = defaultdict(float)
        taken = 0
        for r in rows:
            if r["smart_pnl"] is None:
                continue
            smart[r["date"]] += r["smart_pnl"]
            taken += 1
        better = [day for day in base if smart[day] > base[day] + 0.01]
        same = [day for day in base if abs(smart[day] - base[day]) <= 0.01]
        worse = sorted(
            ((day, round(smart[day] - base[day], 2)) for day in base if smart[day] < base[day] - 0.01),
            key=lambda x: x[1],
        )
        total = round(sum(smart.values()), 2)
        out.append({
            "key": key,
            "label": label,
            "trades_taken": taken,
            "points": total,
            "vs_baseline": round(total - baseline_points, 2),
            "days_better": len(better),
            "days_same": len(same),
            "days_worse": len(worse),
            "worst_days": [{"date": d, "delta": v} for d, v in worse[:5]],
        })

    # How much of the book can each rule even touch?
    buckets = defaultdict(int)
    for t in trades:
        if t["mfe_points"] is None:
            buckets["unknown"] += 1
        elif t["mfe_points"] >= 10:
            buckets["runner"] += 1
        elif t["mfe_points"] >= 5:
            buckets["bankable"] += 1
        else:
            buckets["never_reached"] += 1

    return {
        "baseline_points": baseline_points,
        "total_days": len(base),
        "total_trades": len(trades),
        "scenarios": out,
        "coverage": {
            "bankable": buckets["bankable"],
            "never_reached": buckets["never_reached"],
            "runner": buckets["runner"],
            "unknown": buckets["unknown"],
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(smart_pnl_report(bank_at=5, prove_at=10, day_stop_at=10)["summary"], indent=2))
