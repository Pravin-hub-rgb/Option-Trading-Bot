"""
Four-slot replay harness.

Runs four independent trades through the REAL PositionManager, using the exact
call order the live bot uses on every tick:

    track_price()  ->  check_exit()  ->  update_trailing_sl()

The live rule is the ORIGINAL ladder (first rung entry+1, then +5, +10, ...).
That is what column "LIVE (baseline)" shows.

The second column, "SIMULATED", is a pure offline study of the idea that the
stop could be parked on the highest whole rung reached. It is computed here in
the harness only - the bot itself never runs it.

Each trade is fully independent (there is no day-stop in the live rule), so this
shows precisely what a full 4-slot day looks like.

Run:  ..\\.venv\\Scripts\\python.exe test_four_slots.py
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


def run_slot(entry, ticks, start, step=5, trigger=5):
    """
    Replay one slot through the real, unmodified PositionManager.

    Returns (exit_pnl, tick_number_exit_fired). This is the LIVE path.
    """
    p = PositionManager()
    p.open_position(entry, start, "REPLAY")
    for i, x in enumerate(ticks):
        p.track_price(x)
        # exact live order: stop is checked BEFORE it is moved
        if p.check_exit(x):
            return x - entry, i
        p.update_trailing_sl(x)
    return None, len(ticks)


def run_slot_simulated(entry, ticks, start, step=5):
    """
    OFFLINE STUDY ONLY. The stop is parked on the highest whole rung the price
    has reached (5.5 -> entry+5, 10.5 -> entry+10). Written here with plain
    arithmetic, in its own local variable, so it can never leak into the bot.
    """
    p = PositionManager()
    p.open_position(entry, start, "SIM")
    # local stop, absolute price, starts at the initial SL
    sim_sl = p.get_current_sl()
    for i, x in enumerate(ticks):
        p.track_price(x)
        # exit check happens BEFORE the stop is raised, same as live
        if x <= sim_sl:
            return x - entry, i
        # raise the stop to the highest whole rung the price has reached
        rung = entry + int((x - entry) // step) * step
        # never arm above the price that just set it
        sim_sl = max(sim_sl, min(rung, x))
    return None, len(ticks)


def main():
    rows = []
    for name, entry, ticks in SLOTS:
        start = datetime(2026, 1, 1, 9, 20)
        live_pnl, live_tick = run_slot(entry, ticks, start)
        sim_pnl, sim_tick = run_slot_simulated(entry, ticks, start)
        rows.append((name, live_pnl, live_tick, sim_pnl, sim_tick))

    print()
    print("=" * 96)
    print("  FOUR-SLOT REPLAY   LIVE (baseline ladder)  vs  SIMULATED (study only)")
    print("=" * 96)
    print()
    for (name, lpnl, _, spnl, _) in rows:
        delta = (spnl - lpnl) if (lpnl is not None and spnl is not None) else None
        l = f"{lpnl:+6.2f}" if lpnl is not None else "  open"
        s = f"{spnl:+6.2f}" if spnl is not None else "  open"
        if delta is None:
            d = "   -  "
        elif delta > 0.001:
            d = f"{delta:+6.2f}  <- would be better"
        elif delta < -0.001:
            d = f"{delta:+6.2f}  <- would be WORSE"
        else:
            d = f"{delta:+6.2f}  (same)"
        print(f"  {name}")
        print(f"       live {l}      sim {s}      {d}")

    lt = sum(p for _, p, _, _, _ in rows if p is not None)
    st = sum(p for _, _, _, p, _ in rows if p is not None)
    print()
    print("-" * 96)
    print(f"  DAY TOTAL   live {lt:+7.2f} pts      sim {st:+7.2f} pts      change {st - lt:+7.2f} pts")
    print(f"               in rupees (65/lot)   live {lt * 65:+7.0f}       sim {st * 65:+7.0f}       change {(st - lt) * 65:+7.0f}")
    print("=" * 96)
    print()
    print("  LIVE is what the bot actually does. The SIM column is arithmetic done")
    print("  here in the harness - the bot has no code path that can produce it.")
    print("  Four synthetic paths prove nothing either way; this is why we now")
    print("  collect dips_below_bank on real trades and wait for 50-100 of them.")
    print()
    print("  Slots are independent - no trade changes another trade's outcome.")
    print("  The only shared thing is your capital at risk at any moment.")
    print()


if __name__ == "__main__":
    main()
