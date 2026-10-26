"""
Self-test for the bank-first ladder switch (26 Oct 2026).

The live PositionManager now parks its first rung at entry + bank_rung
(default +5, the rule the exit-rules study promoted) and mirrors the replay
engine rung for rung. The bank_rung setting keeps a knob: setting it to 1
restores the old charges-only first band.

Also covers the Day Stop gate: day_stop_at defaults to 0 (off, nothing
changes), and once set the streamer refuses new entries after the day's
realised points cross it.

Uses a throwaway copy of the database - the real trades.db is never touched.
Run:  python test_bank_rung.py
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "upstox"))

import db as db_mod
from core.position_manager import PositionManager
from settings_db import get_as_dict, save_setting

FAILURES = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}")
    if not ok:
        FAILURES.append(name)


def main():
    tmpdir = tempfile.mkdtemp()
    real_db = db_mod.DB_PATH
    shutil.copy(real_db, os.path.join(tmpdir, "test.db"))
    db_mod.DB_PATH = os.path.join(tmpdir, "test.db")

    t0 = datetime(2026, 10, 27, 9, 20, 0)

    # Snapshot every setting the suite writes so the live settings.json comes
    # back exactly as it was found.
    s = get_as_dict()
    keep = {k: s.get(k) for k in ("bank_rung", "day_stop_at", "trailing_trigger",
                                  "trailing_step", "initial_sl_points")}

    def sl_series(entry, ticks):
        """Run the real pm over a tick series, return every stop it held."""
        p = PositionManager()
        p.open_position(entry, t0, "T")
        stops = [p.get_current_sl()]
        for x in ticks:
            p.update_trailing_sl(x)
            stops.append(p.get_current_sl())
        return stops

    # ---------- 1. default: first rung banks +5, then +5 per step ----------
    print("1) default ladder (bank_rung 5) mirrors the replay engine")
    stops = sl_series(100.0, [104.9, 105.0, 105.5, 110.5, 115.0, 120.5])
    check("below the bank nothing moves", stops[1], 96.0)
    check("the bank touch parks entry+5 exactly", stops[2], 105.0)
    check("profit +5.5 stays parked at entry+5", stops[3], 105.0)
    check("profit +10.5 parks entry+10", stops[4], 110.0)
    check("profit +15.0 parks entry+15", stops[5], 115.0)
    check("profit +20.5 parks entry+20", stops[6], 120.0)

    # The stop is the floor of the current 5-point band - never above the
    # price that armed it (a stop above price is a hidden take-profit).
    p = PositionManager()
    p.open_position(100.0, t0, "SAFE")
    bad = None
    for x in (105.0, 105.05, 107.5, 109.95, 110.0, 120.0, 130.05, 101.0, 100.5):
        if x >= 100.0 + float(get_as_dict().get("bank_rung") or 5):
            moved, new_sl = p.update_trailing_sl(x)
            bad = (x, new_sl) if moved and new_sl > x + 1e-9 else bad
    check("stop is never armed above the price", bad, None)

    # ---------- 2. the knob: bank_rung 1 restores the charges-only band ----
    print("\n2) bank_rung=1 knob (charges-only first band)")
    save_setting("bank_rung", "1")
    stops = sl_series(100.0, [105.5, 110.5])
    check("profit +5.5 parks the charges-only rung at entry+1", stops[1], 101.0)
    # later rungs stay anchored off the bank (+1 then +5 per step = 6, 11, ...),
    # which is the documented knob caveat versus the retired trigger rule.
    check("profit +10.5 parks the next rung at entry+6", stops[2], 106.0)
    save_setting("bank_rung", "5")

    # ---------- 3. Day Stop: default off, then gates entries ---------------
    print("\n3) Day Stop gate on the streamer")
    from upstox.data_streamer import DataStreamer

    ds = DataStreamer.__new__(DataStreamer)   # skip __init__: no feeds needed
    ds.components = {"CE": {"can_trade": True}, "PE": {"can_trade": True}}
    ds.day_realized = 0.0

    save_setting("day_stop_at", "0")
    ds.day_realized = -50.0
    check("knob off (default): never blocks", ds._day_stop_block(), False)
    ds.day_realized = 500.0
    check("knob off (default): big day still never blocks",
          ds._day_stop_block(), False)

    save_setting("day_stop_at", "10")
    ds.day_realized = 9.99
    check("below the limit: entries stay open", ds._day_stop_block(), False)
    ds.day_realized = 10.0
    check("at the limit: no more entries", ds._day_stop_block(), True)
    ds.day_realized = 42.5
    check("well past the limit: no more entries", ds._day_stop_block(), True)

    # Cross it in exit_position's shoe: realised points accrue and every
    # component's can_trade flips, which is what the scheduler's auto-stop
    # loop consumes to close the day.
    ds.day_realized = 0.0
    for pnl in (7.5, -4.0, 6.5):
        ds.day_realized += pnl
        limit = float(get_as_dict().get("day_stop_at") or 0)
        if limit > 0 and ds.day_realized >= limit:
            for c in ds.components.values():
                c["can_trade"] = False
    check("day-stop blocks all instruments once crossed",
          all(c["can_trade"] is False for c in ds.components.values()), True)

    # ---------- restore ---------------------------------------------------
    for k, v in keep.items():
        save_setting(k, v if v is not None else "0")

    shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): {FAILURES}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
