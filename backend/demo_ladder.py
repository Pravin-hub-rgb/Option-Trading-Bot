"""
Shows the trailing ladder tick by tick: exactly when the stop moves, and that
it only ever ratchets upward (never down).

Then replays several DIFFERENT price paths that all peak in the same +5..+10
band, to show the outcome does not depend on the shape of the path.

Run:  ..\.venv\Scripts\python.exe demo_ladder.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from core.position_manager import PositionManager

T0 = datetime(2026, 1, 1, 9, 20)
ENTRY = 100.0


def ladder():
    print()
    print("=" * 86)
    print("  LADDER - exactly when the stop moves (entry 100.0)")
    print("=" * 86)
    p = PositionManager()
    p.open_position(ENTRY, T0, "LADDER")
    for x in (99.0, 103.0, 105.2, 108.0, 112.0, 115.0, 118.0, 121.0, 124.0, 127.0):
        p.track_price(x)
        if p.check_exit(x):
            print(f"  price {x:6.1f} ({x - ENTRY:+5.1f})    STOP HIT -> exit {x - ENTRY:+.2f}")
            break
        moved, sl = p.update_trailing_sl(x)
        tag = "    <== STOP MOVES" if moved else ""
        print(f"  price {x:6.1f} ({x - ENTRY:+5.1f} pts)    SL {sl:6.1f} ({sl - ENTRY:+5.1f} pts){tag}")


def path(ticks):
    p = PositionManager()
    p.open_position(ENTRY, T0, "P")
    for x in ticks:
        p.track_price(x)
        if p.check_exit(x):
            return x - ENTRY, p.get_mfe(), p.position["dips_below_bank"]
        p.update_trailing_sl(x)
    return None, p.get_mfe(), p.position["dips_below_bank"]


def ramp(a, b, step=0.25):
    """A realistic-ish price path from a to b in small ticks."""
    out, x = [], a
    while (x < b if b > a else x > b):
        x += step if b > a else -step
        out.append(round(x, 2))
    return out or [a]


def same_band():
    print()
    print("=" * 92)
    print("  ALL PATHS PEAKING IN +5..+10  ->  outcome set by TICK GRAIN, not by shape")
    print("=" * 92)
    print("  (options move in small ticks, so the fill lands close to the stop)")
    print()
    cases = [
        ("straight up, then drop",
         ramp(100.5, 109.0) + [108.5, 107.0, 105.2, 104.9, 104.6]),
        ("deep swing to +1, then recovered to +9",
         ramp(100.4, 105.5) + ramp(105.5, 101.0) + ramp(101.0, 109.0) + [106.0, 105.2, 104.8]),
        ("grazed +5, instant collapse",
         ramp(100.2, 105.05) + [104.0, 102.0, 100.5, 100.1]),
        ("slow grind up, then fade",
         ramp(100.1, 108.0, 0.15) + [106.0, 105.1, 104.7]),
        ("choppy, 6 swings",
         ramp(100.3, 105.4) + ramp(105.4, 103.2) + ramp(103.2, 106.8)
         + ramp(106.8, 104.5) + ramp(104.5, 108.1) + [105.2, 104.9]),
    ]
    print(f"  {'path':40s} {'exit pts':>9s} {'peak':>7s} {'dips':>5s}")
    for name, ticks in cases:
        pnl, mfe, dips = path(ticks)
        print(f"  {name:40s} {pnl:+9.2f} {mfe:+7.2f} {dips:5d}")
    print()
    print("  Every one of these exits at +5 MINUS the tick gap. The shape of the")
    print("  path does not change the result - only the tick size does.")


def runner_paths():
    print()
    print("=" * 92)
    print("  RUNNERS (peak above +10) - HERE the path genuinely changes the result")
    print("=" * 92)
    cases = [
        ("never dipped back after +5",
         ramp(100.5, 121.0) + [118.0, 116.0, 115.2, 114.8]),
        ("dipped to +3 mid-way, then ran to +20",
         ramp(100.5, 105.2) + ramp(105.2, 103.0) + ramp(103.0, 120.0) + [116.0, 115.4]),
        ("shallow dip to +4.5, then ran to +19",
         ramp(100.5, 105.2) + ramp(105.2, 104.5) + ramp(104.5, 119.0) + [116.0, 114.9]),
    ]
    print(f"  {'path':40s} {'exit pts':>9s} {'peak':>7s} {'dips':>5s}  note")
    for name, ticks in cases:
        pnl, mfe, dips = path(ticks)
        note = "survives" if dips == 0 else f"new rule would have exited at +5"
        print(f"  {name:40s} {pnl:+9.2f} {mfe:+7.2f} {dips:5d}  {note}")
    print()
    print("  This is the one case where the new rule can cost points, and it is")
    print("  exactly what dips_below_bank now records on every trade.")


if __name__ == "__main__":
    ladder()
    same_band()
    runner_paths()
    print()