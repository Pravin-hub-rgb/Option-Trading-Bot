"""
Four-slot replay harness.

Runs four independent trades through the REAL PositionManager, using the exact
call order the live bot uses on every tick:

    track_price()  ->  check_exit()  ->  update_trailing_sl()

Each trade is fully independent (there is no day-stop in the live rule), so this
shows precisely what a full 4-slot day looks like under the old first rung
(+1) versus the new one (+5).

Run:  ..\.venv\Scripts\python.exe test_four_slots.py
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from core.position_manager import PositionManager
from settings_db import save_setting, get_as_dict

GREEN = ""
RED = ""
DIM = ""
BOLD = ""
OFF = ""

# Four price paths, each shaped like a pattern actually seen in the trade log.
# (entry, [ticks], label)
SLOTS = [
    ("SLOT 1 - runner: ran to +20, gave back to +14",
     100.0, [100.4, 102.0, 105.3, 108.0, 112.0, 116.0, 121.0, 119.0, 117.0, 115.4, 114.9]),
    ("SLOT 2 - giveback: touched +7, collapsed to scratch",
     100.0, [100.5, 102.5, 105.4, 107.0, 105.5, 103.0, 101.2, 100.7]),
    ("SLOT 3 - loser: never reached the trigger",
     100.0, [99.6, 98.2, 97.0, 96.1, 95.9]),
    ("SLOT 4 - marginal: just grazed +5 then failed",
     100.0, [100.3, 101.8, 105.1, 104.2, 102.0, 100.4, 100.1]),
]


def run_slot(entry, ticks, bank_at, start):
    """Replay one slot through the real position manager. Returns exit pnl."""
    p = PositionManager()
    p.open_position(entry, start, "REPLAY")
    for i, x in enumerate(ticks):
        p.track_price(x)
        # exact live order: stop is checked BEFORE it is moved
        if p.check_exit(x):
            return x - entry, i, p
        p.update_trailing_sl(x)
    return None, len(ticks), p


def main():
    keep = get_as_dict().get("bank_at_points")
    results = {}
    for label, bank in (("OLD  first rung +1", 1), ("NEW  first rung +5", 5)):
        save_setting("bank_at_points", str(bank))
        rows = []
        for name, entry, ticks in SLOTS:
            start = datetime(2026, 1, 1, 9, 20)
            pnl, tick_no, _ = run_slot(entry, ticks, bank, start)
            rows.append((name, pnl, tick_no))
        results[label] = rows

    save_setting("bank_at_points", keep if keep is not None else "5")

    old = results["OLD  first rung +1"]
    new = results["NEW  first rung +5"]

    print()
    print("=" * 96)
    print("  FOUR-SLOT DAY - same price ticks, old rule vs new rule")
    print("=" * 96)
    print()
    for (name, opnl, _), (_, npnl, _) in zip(old, new):
        delta = (npnl - opnl) if (opnl is not None and npnl is not None) else None
        o = f"{opnl:+6.2f}" if opnl is not None else "  open"
        n = f"{npnl:+6.2f}" if npnl is not None else "  open"
        if delta is None:
            d = "   -  "
        elif delta > 0.001:
            d = f"{delta:+6.2f}  <- better"
        elif delta < -0.001:
            d = f"{delta:+6.2f}  <- WORSE"
        else:
            d = f"{delta:+6.2f}  (same)"
        print(f"  {name}")
        print(f"       old {o}      new {n}      {d}")

    ot = sum(p for _, p, _ in old if p is not None)
    nt = sum(p for _, p, _ in new if p is not None)
    print()
    print("-" * 96)
    print(f"  DAY TOTAL   old {ot:+7.2f} pts      new {nt:+7.2f} pts      change {nt - ot:+7.2f} pts")
    print(f"               in rupees (65/lot)   old {ot * 65:+7.0f}       new {nt * 65:+7.0f}       change {(nt - ot) * 65:+7.0f}")
    print("=" * 96)
    print()
    print("  Note: slots are independent - no trade changes another trade's outcome.")
    print("        The only shared thing is your capital at risk at any moment.")
    print()


if __name__ == "__main__":
    main()
