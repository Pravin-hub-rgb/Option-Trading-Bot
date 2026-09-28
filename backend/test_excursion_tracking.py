"""
Self-test for the excursion tracking added to PositionManager.

Runs a synthetic tick sequence through the real code path and asserts that
MFE / MAE / rung counts come out right, and that the trailing SL behaviour is
UNCHANGED (the tracking must be purely observational).

Uses a throwaway copy of the database - the real trades.db is never touched.
Run:  python test_excursion_tracking.py
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "upstox"))

import db as db_mod
from core.position_manager import PositionManager
from core.trade_logger import TradeLogger
from settings_db import get_as_dict

FAILURES = []


def check(name, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}")
    if not ok:
        FAILURES.append(name)


def close(a, b, tol=0.001):
    return abs(a - b) < tol


def main():
    tmpdir = tempfile.mkdtemp()
    real_db = db_mod.DB_PATH
    shutil.copy(real_db, os.path.join(tmpdir, "test.db"))
    db_mod.DB_PATH = os.path.join(tmpdir, "test.db")

    s = get_as_dict()
    sl_pts = int(s.get("initial_sl_points", 4))
    trig = int(s.get("trailing_trigger", 5))
    step = int(s.get("trailing_step", 5))
    print(f"settings: initial_sl={sl_pts} trigger={trig} step={step}\n")

    t0 = datetime(2026, 1, 1, 9, 20, 0)

    # ---------- 1. giveback trade: peaks at +7, exits at the BE rung ----------
    print("1) peak +7 then collapse to break-even")
    pm = PositionManager()
    pm.open_position(100.0, t0, "TEST CE")
    check("initial SL", pm.get_current_sl(), 100.0 - sl_pts)
    # the 99.8 dip first, so MAE is non-zero
    for ltp in (100.5, 99.8, 103.0, 107.0, 106.0, 104.0, 102.0, 101.0):
        pm.track_price(ltp)
        pm.check_exit(ltp)
        pm.update_trailing_sl(ltp)
    check("MFE (peak 107)", pm.get_mfe(), 7.0)
    check("MAE (low 99.8)", close(pm.get_mae(), 0.2), True)
    check("SL locked to first rung (entry+5)", pm.get_current_sl(), 105.0)
    summary = pm.close_position(101.0, t0 + timedelta(minutes=6))
    check("summary mfe_points", summary["mfe_points"], 7.0)
    check("summary mae_points", summary["mae_points"], 0.2)
    check("summary pnl", summary["pnl"], 1.0)
    check("sl_initial honours settings", summary["sl_initial"], 100.0 - sl_pts)

    # ---------- 2. runner: peaks at +22, should trail to +20 rung ----------
    print("\n2) runner peaking at +22")
    pm2 = PositionManager()
    pm2.open_position(100.0, t0, "TEST PE")
    for ltp in (112.0, 117.0, 119.0, 122.0, 121.0):
        pm2.track_price(ltp)
        pm2.update_trailing_sl(ltp)
    check("MFE (peak 122)", pm2.get_mfe(), 22.0)
    # profit 22 -> milestone int((22-5)/5)=3 -> SL = entry + 3*step = 115
    check("SL = entry+15 rung", pm2.get_current_sl(), 115.0)
    s2 = pm2.close_position(120.0, t0 + timedelta(minutes=5))
    check("runner mfe_points", s2["mfe_points"], 22.0)
    check("runner rungs locked", s2["sl_rungs_locked"] >= 3, True)

    # ---------- 2b. the ladder rung formula, spelled out ----------
    print("\n2b) rung arithmetic (first rung = bank_at = +5)")
    for ltp, want_sl in ((105.0, 105.0), (110.0, 105.0), (115.0, 110.0),
                         (120.0, 115.0), (125.0, 120.0)):
        p = PositionManager()
        p.open_position(100.0, t0, "T")
        p.update_trailing_sl(ltp)
        check(f"profit {ltp - 100:.0f} -> SL {want_sl}", p.get_current_sl(), want_sl)

    # ---------- 3. never triggers: MFE must be small ----------
    print("\n3) loser, never reaches trigger")
    pm3 = PositionManager()
    pm3.open_position(100.0, t0, "TEST CE2")
    for ltp in (99.5, 98.0, 97.0, 96.0):
        pm3.track_price(ltp)
        pm3.update_trailing_sl(ltp)
    check("MFE (peak 100.0 = entry)", pm3.get_mfe(), 0.0)
    check("MAE (low 96)", close(pm3.get_mae(), 4.0), True)
    s3 = pm3.close_position(96.0, t0 + timedelta(minutes=4))
    check("loser mfe_points", s3["mfe_points"], 0.0)

    # ---------- 4. regression: tracking must not alter SL behaviour ----------
    print("\n4) regression - SL path identical with and without tracking")
    pmA = PositionManager()
    pmA.open_position(100.0, t0, "X")
    pmB = PositionManager()
    pmB.open_position(100.0, t0, "X")
    ticks = [100.0, 101.2, 103.4, 105.1, 106.0, 104.5, 102.0, 106.5, 111.0, 109.0, 105.0]
    for ltp in ticks:
        pmA.update_trailing_sl(ltp)
        pmB.track_price(ltp)
        pmB.update_trailing_sl(ltp)
        if pmA.get_current_sl() != pmB.get_current_sl():
            check("SL divergence at ltp=%s" % ltp, pmB.get_current_sl(), pmA.get_current_sl())
            break
    else:
        check("SL identical across %d ticks" % len(ticks), True, True)

    # ---------- 5. DB round-trip ----------
    print("\n5) database round-trip")
    init = db_mod.get_conn()
    cols = {r["name"] for r in init.execute("PRAGMA table_info(trades)")}
    check("mfe_points column exists", "mfe_points" in cols, True)
    check("mae_points column exists", "mae_points" in cols, True)
    check("sl_rungs_locked column exists", "sl_rungs_locked" in cols, True)
    init.close()

    logger = TradeLogger("test", "TEST CE")
    logger.log_entry("TEST CE", 100.0, 100.0 - sl_pts, t0)
    logger.log_exit("TEST CE", 101.0, 101.0, t0 + timedelta(minutes=6),
                    "Trailing SL Hit", 1.0, mfe_points=7.0, mae_points=0.5, sl_rungs_locked=1)
    conn = db_mod.get_conn()
    row = conn.execute("SELECT mfe_points, mae_points, sl_rungs_locked FROM trades WHERE symbol='TEST CE'").fetchone()
    conn.close()
    check("persisted mfe", row["mfe_points"], 7.0)
    check("persisted mae", row["mae_points"], 0.5)
    check("persisted rungs", row["sl_rungs_locked"], 1)

    # ---------- 6. first-rung bank: the giveback fix ----------
    print("\n6) first SL rung = +5 (was +1)")
    from settings_db import save_setting
    old_bank = get_as_dict().get("bank_at_points")
    save_setting("bank_at_points", "5")

    # 6a. giveback trade: peaks at +7, must now exit at +5 instead of +1
    b = PositionManager()
    b.open_position(100.0, t0, "BANK CE")
    for ltp in (101.0, 103.0, 107.0, 104.0, 103.0, 102.0):
        b.track_price(ltp)
        b.update_trailing_sl(ltp)
    check("giveback trade locks stop at +5", b.get_current_sl(), 105.0)
    check("...and never lets it drop below", b.get_current_sl() >= 105.0, True)
    sb = b.close_position(105.0, t0 + timedelta(minutes=3))
    check("giveback trade banks +5 (was +1)", sb["pnl"], 5.0)

    # 6b. runner: reaches +10 and keeps its full run
    r = PositionManager()
    r.open_position(100.0, t0, "BANK PE")
    for ltp in (105.0, 104.0, 110.0, 115.0, 120.0, 118.0):
        r.track_price(ltp)
        r.update_trailing_sl(ltp)
    check("runner trails normally to +15 rung", r.get_current_sl(), 115.0)
    sr = r.close_position(115.0, t0 + timedelta(minutes=4))
    check("runner keeps full +15 (untouched)", sr["pnl"], 15.0)
    check("runner MFE preserved", sr["mfe_points"], 20.0)

    # 6c. loser is unaffected
    l = PositionManager()
    l.open_position(100.0, t0, "BANK CE2")
    for ltp in (99.0, 97.0, 96.0):
        l.track_price(ltp)
        l.update_trailing_sl(ltp)
    check("loser stop stays at initial -4", l.get_current_sl(), 96.0)
    check("loser exits at -4", l.close_position(96.0, t0)["pnl"], -4.0)

    # 6d. setting 0 restores the legacy +1 first rung
    save_setting("bank_at_points", "0")
    z = PositionManager()
    z.open_position(100.0, t0, "LEGACY")
    z.update_trailing_sl(107.0)
    check("bank_at=0 restores +1 first rung", z.get_current_sl(), 101.0)
    save_setting("bank_at_points", old_bank if old_bank is not None else "5")

    # 6e. every rung value under the new ladder
    save_setting("bank_at_points", "5")
    for ltp, want in ((105.0, 105.0), (110.0, 105.0), (115.0, 110.0),
                      (120.0, 115.0), (125.0, 120.0)):
        p = PositionManager()
        p.open_position(100.0, t0, "T")
        p.update_trailing_sl(ltp)
        check(f"profit {ltp - 100:.0f} -> SL {want}", p.get_current_sl(), want)

    # ---------- 7. hostile settings must never break the ladder ----------
    print("\n7) hostile / misconfigured settings")
    from settings_db import save_setting
    st = get_as_dict()
    keep = {k: st.get(k) for k in ("bank_at_points", "trailing_trigger", "trailing_step")}

    def sl_after(ticks, **over):
        for k, v in over.items():
            save_setting(k, str(v))
        p = PositionManager()
        p.open_position(100.0, t0, "EDGE")
        for x in ticks:
            p.track_price(x)
            p.update_trailing_sl(x)
        return p.get_current_sl()

    # 7a. bank_at above the trigger must NOT become an instant take-profit
    check("bank_at=8 > trigger=5 does not arm a stop above price",
          sl_after([105.2], bank_at_points=8), 105.0)

    # 7b. bank_at above the step must not freeze the ladder
    save_setting("trailing_trigger", "5"); save_setting("trailing_step", "3")
    p = PositionManager(); p.open_position(100.0, t0, "S3")
    rungs = []
    for x in (105.0, 108.0, 111.0, 114.0):
        p.update_trailing_sl(x)
        rungs.append(p.get_current_sl())
    check("ladder stays monotonic with step=3, bank=5",
          all(rungs[i] <= rungs[i + 1] for i in range(len(rungs) - 1)), True)
    check("...and keeps trailing past the first rung", rungs[-1] > rungs[0], True)

    # 7c. negative / junk values fall back to the legacy +1 rung
    for junk in (-5, "abc", ""):
        check(f"bank_at={junk!r} falls back to +1",
              sl_after([107.0], bank_at_points=junk), 101.0)

    # 7d. whenever the stop moves up it must never be placed above the price
    #     that just armed it (otherwise it would fire an instant exit)
    save_setting("trailing_step", "5"); save_setting("trailing_trigger", "5")
    for bank in (1, 3, 5, 7, 12):
        save_setting("bank_at_points", str(bank))
        p = PositionManager(); p.open_position(100.0, t0, "SAFE")
        bad = None
        for x in (105.0, 105.1, 106.0, 107.0, 110.0, 120.0, 101.0, 100.5, 100.0, 99.0):
            p.track_price(x)
            moved, new_sl = p.update_trailing_sl(x)
            if moved and new_sl > x + 1e-9:
                bad = (x, new_sl)
        check(f"bank_at={bank}: stop never armed above price", bad, None)

    for k, v in keep.items():
        save_setting(k, v if v is not None else "5")

    # ---------- 8. stop() must not deadlock when a position is open ----------
    print("\n8) stop() with an open position (regression: RLock fix)")
    from bot_manager import BotManager

    check("lock is reentrant", type(BotManager().lock).__name__, "RLock")

    # Mimic the exact re-entrancy path:
    #   stop() -> _force_exit_live_positions() -> streamer.exit_position()
    #         -> `with bot_manager.lock`   (same thread, must not deadlock)
    class _PM:
        def is_in_position(self):
            return True

        @property
        def position(self):
            return {"entry_price": 100.0, "last_ltp": 104.0}

    class _FakeStreamer:
        def __init__(self, mgr):
            self.mgr = mgr
            self.closed = False
            self.exited = []
            self.components = {i: {"position_manager": _PM()} for i in ("CE", "PE")}

        def exit_position(self, inst_type, ltp, now, reason):
            with self.mgr.lock:          # <- exactly what the real streamer does
                self.exited.append(inst_type)

        def close(self):
            self.closed = True

    mgr = BotManager()
    fake = _FakeStreamer(mgr)
    mgr.running = True
    mgr._data_streamer = fake
    mgr._scheduler = None
    mgr.emit_log = lambda m: None

    import threading as _th
    outcome = {}

    def _do_stop():
        try:
            outcome["res"] = mgr.stop()
        except Exception as e:
            outcome["err"] = repr(e)

    t = _th.Thread(target=_do_stop, daemon=True)
    t.start()
    t.join(timeout=8)
    check("stop() did not deadlock", t.is_alive(), False)
    check("stop() raised no exception", "err" in outcome, False)
    if "err" in outcome:
        print(f"      -> {outcome['err']}")
    check("stop() returned cleanly",
          outcome.get("res", {}).get("status"), "stopped")
    check("open positions were force-exited", len(fake.exited), 2)
    check("streamer was closed", fake.closed, True)
    check("running flag cleared", mgr.running, False)
    check("get_status() still works after stop", isinstance(mgr.get_status(), dict), True)

    # ---------- 9. path tracking (answers the MFE-only questions) ----------
    print("\n9) path capture - did it dip back below the first rung?")
    from settings_db import save_setting
    keep_bank = get_as_dict().get("bank_at_points")
    save_setting("bank_at_points", "5")

    # 9a. clean runner: touches +5 once and never comes back -> survives
    r1 = PositionManager(); r1.open_position(100.0, t0, "CLEAN")
    for x in (100.5, 105.2, 108.0, 115.0, 118.0, 114.0):
        r1.track_price(x)
    s1 = r1.close_position(114.0, t0)
    check("clean runner touched the rung", s1["bank_touched"], True)
    check("clean runner dipped back below it", s1["dips_below_bank"], 0)
    check("clean runner peak tick is recorded", isinstance(s1["peak_tick"], int), True)
    check("clean runner ticks counted", s1["ticks_seen"] >= 6, True)

    # 9b. the DANGEROUS path: +5 -> +2 -> +12. The new rule kills this at +5.
    r2 = PositionManager(); r2.open_position(100.0, t0, "DIPPER")
    for x in (100.5, 105.2, 102.0, 101.0, 106.0, 112.0, 109.0):
        r2.track_price(x)
    s2 = r2.close_position(109.0, t0)
    check("dipping runner touched the rung", s2["bank_touched"], True)
    check("dipping runner counted the dip", s2["dips_below_bank"] >= 1, True)
    print(f"      -> peak {s2['mfe_points']:.2f} pts, dipped {s2['dips_below_bank']}x "
          f"below +5, first rung at tick {s2['first_bank_tick']}")
    check("dips happened after the first touch", (s2["first_bank_tick"] or 0) > 0, True)

    # 9c. never reached the rung -> no dip to count
    r3 = PositionManager(); r3.open_position(100.0, t0, "LOSER")
    for x in (99.0, 97.0, 96.0):
        r3.track_price(x)
    s3 = r3.close_position(96.0, t0)
    check("loser never touched the rung", s3["bank_touched"], False)
    check("loser has no dips", s3["dips_below_bank"], 0)

    save_setting("bank_at_points", keep_bank if keep_bank is not None else "5")

    db_mod.DB_PATH = real_db
    shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): {FAILURES}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
