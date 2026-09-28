"""
Prints the exact stop-loss ladder for three representative trades, so the
behaviour of the first-rung change can be eyeballed without running the bot.

Run:  ..\.venv\Scripts\python.exe demo_ladder.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from core.position_manager import PositionManager

T0 = datetime(2026, 1, 1, 9, 20)


def show(name, ticks, entry=100.0):
    p = PositionManager()
    p.open_position(entry, T0, "DEMO")
    print(f"--- {name}  (entry {entry:.2f}) ---")
    for x in ticks:
        # The real bot checks the stop BEFORE moving it. That order matters:
        # checking first is what lets a runner survive the very tick that first
        # touches +5, instead of being killed at the freshly-armed stop price.
        p.track_price(x)
        if p.check_exit(x):
            sl = p.get_current_sl()
            print(f"   price {x:7.2f} ({x - entry:+5.2f} pts)   SL {sl:7.2f} ({sl - entry:+5.2f} pts)")
            print(f"   >>> EXIT at {x:.2f}  =  {x - entry:+.2f} points\n")
            return
        moved, _ = p.update_trailing_sl(x)
        sl = p.get_current_sl()
        tag = "   <== SL SHIFTED" if moved else ""
        print(f"   price {x:7.2f} ({x - entry:+5.2f} pts)   SL {sl:7.2f} ({sl - entry:+5.2f} pts){tag}")
    print()


if __name__ == "__main__":
    show("GIVEBACK trade (aaj wala pattern: +9.85 tha, +0.90 pe nikla)",
         [100.5, 103.0, 105.2, 106.0, 104.0, 102.5, 100.8])
    show("RUNNER trade (aaj wala: +20 tak gaya, +14.20 pe nikla)",
         [105.0, 107.0, 112.0, 116.0, 121.0, 118.0, 115.5, 114.8])
    show("LOSER trade (trigger tak nahi pahuncha)",
         [99.0, 97.0, 96.5])
