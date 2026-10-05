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
    check("SL moves only to entry+1 at peak +7 (baseline)", pm.get_current_sl(), 101.0)
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
    # profit 22 -> milestones_passed = int((22-5)/5) = 3 -> entry + 15
    check("SL = entry+15 rung at profit 22", pm2.get_current_sl(), 115.0)
    s2 = pm2.close_position(115.0, t0 + timedelta(minutes=5))
    check("runner mfe_points", s2["mfe_points"], 22.0)
    check("runner rungs locked", s2["sl_rungs_locked"] >= 3, True)

    # ---------- 2b. the baseline ladder, spelled out ----------
    print("\n2b) baseline rung arithmetic (first rung is +1, then every +5)")
    for ltp, want_sl in ((105.5, 101.0), (110.5, 105.0), (115.0, 110.0),
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

    # ---------- 6. BASELINE LADDER REGRESSION (live exit logic) ----------
    # The live stop ladder is the ORIGINAL rule and must stay that way.
    # This is the money path: it decides when real money leaves the account.
    print("\n6) baseline trailing ladder (live exit logic)")
    from settings_db import save_setting
    save_setting("trailing_trigger", "5")
    save_setting("trailing_step", "5")
    save_setting("observe_dip_level", "5")

    def sl_only(ltp, entry=100.0):
        """Feed one price, return the live stop. No settings touched."""
        p = PositionManager()
        p.open_position(entry, t0, "LADDER")
        p.update_trailing_sl(ltp)
        return p.get_current_sl()

    # 6a. THE key regression: +5.5 must NOT park the stop at +5.
    # A design experiment briefly did this and it broke the strategy. If this
    # assertion ever fails again, the live exit logic has been changed without
    # approval.
    check("+5.5 -> entry+1  (NOT entry+5)", sl_only(105.5), 101.0)
    check("+5.0 -> entry+1", sl_only(105.0), 101.0)

    # 6b. the rest of the ladder
    check("+10.5 -> entry+5", sl_only(110.5), 105.0)
    check("+10.0 -> entry+5", sl_only(110.0), 105.0)
    check("+15.5 -> entry+10", sl_only(115.5), 110.0)
    check("+20.5 -> entry+15", sl_only(120.5), 115.0)

    # 6c. below the trigger nothing ever moves
    check("+4.9 -> initial stop untouched", sl_only(104.9), 96.0)
    check("+0.0 -> initial stop untouched", sl_only(100.0), 96.0)

    # 6d. full giveback path: runner that reached +20 then slid back.
    g = PositionManager()
    g.open_position(100.0, t0, "GIVEBACK")
    for ltp in (101.0, 105.5, 110.5, 115.5, 120.5, 118.0, 116.0, 115.0):
        g.update_trailing_sl(ltp)
    check("giveback path trails to +15", g.get_current_sl(), 115.0)
    check("giveback exits at +15", g.close_position(115.0, t0)["pnl"], 15.0)

    # 6e. a loser is completely unaffected
    l = PositionManager()
    l.open_position(100.0, t0, "LOSER")
    for ltp in (99.0, 97.0, 96.0):
        l.track_price(ltp)
        l.update_trailing_sl(ltp)
    check("loser stop stays at initial -4", l.get_current_sl(), 96.0)
    check("loser exits at -4", l.close_position(96.0, t0)["pnl"], -4.0)

    # ---------- 7. observation must NEVER influence the live ladder ----------
    # dips_below_bank / MFE tracking is passive. Whatever the observation level
    # is set to, the stop ladder has to produce identical results.
    print("\n7) observation is strictly passive (regression)")
    path = (105.5, 110.5, 115.5, 104.0, 102.0, 120.5, 121.0, 99.0)

    def ladder_rungs(do_track, level):
        save_setting("observe_dip_level", str(level))
        p = PositionManager()
        p.open_position(100.0, t0, "PASSIVE")
        out = []
        for x in path:
            if do_track:
                p.track_price(x)
            p.update_trailing_sl(x)
            out.append(p.get_current_sl())
        return out

    control = ladder_rungs(False, 0)
    for level in (0, 1, 3, 5, 8, 50, -5, "abc", ""):
        check(f"observe_dip_level={level!r}: ladder with tracking = ladder without",
              ladder_rungs(True, level), control)

    # The path ends at 99.0 after peaking at 121.0, so the stop parks at +15
    # (milestones_passed = int((21-5)/5) = 3) and stays there.
    check("ladder parks at +15 after peaking at +21", control[-1], 115.0)

    save_setting("observe_dip_level", "5")

    # track_price() on its own must not move the stop, but MUST record.
    t = PositionManager()
    t.open_position(100.0, t0, "TRACKONLY")
    for x in (105.5, 110.5, 115.5, 120.5, 104.0):
        t.track_price(x)
    check("track_price alone never moves the stop", t.get_current_sl(), 96.0)
    r2 = t.close_position(100.0, t0)
    check("MFE recorded while observing", r2["mfe_points"], 20.5)
    check("dips counted while observing", (r2["dips_below_bank"] or 0) > 0, True)

    save_setting("observe_dip_level", "0")
    t2 = PositionManager()
    t2.open_position(100.0, t0, "TRACKOFF")
    for x in (105.5, 110.5, 104.0):
        t2.track_price(x)
    r3 = t2.close_position(100.0, t0)
    check("MFE recorded even when observation is off", r3["mfe_points"], 10.5)
    check("dips not counted when observation is off", r3["dips_below_bank"], 0)
    save_setting("observe_dip_level", "5")

    # ---------- 7e. safety invariants of the live ladder ----------
    print("\n7e) live ladder safety invariants")
    st = get_as_dict()
    keep = {k: st.get(k) for k in ("trailing_trigger", "trailing_step")}
    save_setting("trailing_trigger", "5"); save_setting("trailing_step", "5")

    # The stop must never be armed above the price that just set it, otherwise
    # it fires an instant exit (a hidden take-profit).
    p = PositionManager(); p.open_position(100.0, t0, "SAFE")
    bad = None
    for x in (105.0, 105.1, 106.0, 107.0, 110.0, 120.0, 101.0, 100.5, 100.0, 99.0):
        p.track_price(x)
        moved, new_sl = p.update_trailing_sl(x)
        if moved and new_sl > x + 1e-9:
            bad = (x, new_sl)
    check("stop is never armed above the price", bad, None)

    # And it must never move backwards.
    p2 = PositionManager(); p2.open_position(100.0, t0, "MONO")
    back = []
    prev = p2.get_current_sl()
    for x in (105.5, 104.0, 110.5, 106.0, 99.0, 120.5, 115.0, 100.0):
        p2.update_trailing_sl(x)
        s = p2.get_current_sl()
        if s < prev:
            back.append((x, s, prev))
        prev = s
    check("stop never moves backwards", back, [])

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
    keep_bank = get_as_dict().get("observe_dip_level")
    save_setting("observe_dip_level", "5")

    # 9a. clean runner: touches +5 once and never comes back -> survives
    r1 = PositionManager(); r1.open_position(100.0, t0, "CLEAN")
    for x in (100.5, 105.2, 108.0, 115.0, 118.0, 114.0):
        r1.track_price(x)
    s1 = r1.close_position(114.0, t0)
    check("clean runner touched the rung", s1["bank_touched"], True)
    check("clean runner dipped back below it", s1["dips_below_bank"], 0)
    check("clean runner peak tick is recorded", isinstance(s1["peak_tick"], int), True)
    check("clean runner ticks counted", s1["ticks_seen"] >= 6, True)

    # 9b. the DIPPER path: +5 -> +2 -> +12. A stop parked at +5 would have been
    #     stopped out here. That is exactly the risk the study has to measure
    #     before anyone promotes it to the live bot.
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

    save_setting("observe_dip_level", keep_bank if keep_bank is not None else "5")

    # ---------- 10. the smart engine must not use hindsight ----------
    # A peak-only counterfactual ("MFE was 8, so it banked 8") is the trap that
    # made this study look worth lakhs. Option prices go 5 -> 4.5 -> 6 -> 8, so a
    # stop parked at +5 fires on the 4.5 tick. dips_below_bank is what tells us
    # that happened, and the engine has to honour it.
    print("\n10) shadow engine is tick-wise, not peak-wise")
    from smart_pnl import smart_exit, is_measured, EXIT_BUFFER_PTS
    check("exit buffer is 1 point", EXIT_BUFFER_PTS, 1.0)

    def sim(mfe, actual, dips, prove=10):
        pnl, rule = smart_exit({"pnl": actual, "mfe_points": mfe,
                                "dips_below_bank": dips}, 5, prove)
        return pnl, rule

    # 10a. the exact shape that fooled us: peaked at 8 but broke +5 on the way
    check("dipped trade exits at +5 - buffer, NOT at its peak",
          sim(8.8, -0.45, 1), (4.0, "stopped_at_rung"))
    check("...even with a big peak", sim(18.0, 3.0, 1), (4.0, "stopped_at_rung"))

    # 10b. no dip + proved it => the +5 stop never fired, keep the real result
    check("clean runner keeps its real result", sim(22.1, 14.85, 0), (14.85, "survived"))

    # 10c. touched +5, never broke it, but never proved it -> stop was armed
    check("touched but unproven exits at +5 - buffer", sim(7.0, 0.9, 0), (4.0, "stopped_at_rung"))

    # 10d. never reached the rung at all -> untouched
    check("never reached +5 is untouched", sim(1.0, -4.45, 0), (-4.45, "untouched"))

    # 10e. no path data => must be flagged unverified, never presented as measured
    pnl, rule = smart_exit({"pnl": 0.9, "mfe_points": 8.0, "dips_below_bank": None}, 5, 10)
    check("no path data is labelled hindsight", rule, "hindsight")
    check("...and is_measured() says so", is_measured(rule), False)
    check("...and it still subtracts the buffer", pnl, 4.0)

    # 10f. measured rows must always be flagged verified
    for args, want in (((8.8, -0.45, 1), True), ((22.1, 14.85, 0), True),
                       ((1.0, -4.45, 0), True)):
        _p, r = sim(*args)
        check(f"{args} verified={want}", is_measured(r), want)

    # 10g. the simulation must never beat a trade that already did better
    for mfe in (5.0, 6.0, 9.9, 12.0, 30.0):
        for actual in (0.5, 4.0, 9.0, 25.0):
            for dips in (0, 1, 2):
                p, _r = sim(mfe, actual, dips)
                check(f"mfe={mfe} actual={actual} dips={dips}: never worse than reality",
                      p >= actual, True)

    # 10h. a buffer of 0 must be honoured exactly
    p, r = smart_exit({"pnl": -0.45, "mfe_points": 8.8, "dips_below_bank": 1}, 5, 10, 0)
    check("zero buffer exits exactly at the rung", p, 5.0)

    # ---------- 11. tick_path is recorded but never acted on ----------
    # The chart needs the real entry-to-exit series. Storing it must not change
    # a single exit decision, and it must survive the round trip to the DB.
    print("\n11) tick path capture (feeds the study chart)")
    from db import get_conn as _gc
    save_setting("trailing_trigger", "5"); save_setting("trailing_step", "5")

    ticks = [100.5, 103.0, 105.2, 107.0, 104.5, 102.0, 106.0, 110.0, 108.0, 109.0]
    # Control runs the exact live tick order; the other captures the path too.
    # The two stops must be identical - capture cannot influence an exit.
    a = PositionManager(); a.open_position(100.0, t0, "PATH_A")
    b = PositionManager(); b.open_position(100.0, t0, "PATH_B")
    for px in ticks:
        a.track_price(px)
        a.update_trailing_sl(px)
        b.update_trailing_sl(px)
    check("tick_path captures every price", a.position["tick_path"], ticks)
    check("no capture without track_price", b.position["tick_path"], [])
    check("capturing did not move the stop", a.get_current_sl(), b.get_current_sl())

    # and the persisted copy round-trips
    sa = a.close_position(109.0, t0)
    sb = b.close_position(109.0, t0)
    check("summary carries the path", sa["tick_path"], ticks)
    check("same exit with and without capture", sa["pnl"], sb["pnl"])
    conn2 = _gc()
    cols = {r["name"] for r in conn2.execute("PRAGMA table_info(trades)")}
    check("tick_path column exists", "tick_path" in cols, True)
    conn2.close()

    # 11a. full round trip: manager -> logger -> DB -> reader -> replay.
    # This is what the chart depends on, so prove the whole chain rather than
    # just that the column exists.
    # Aliased: `TradeLogger` is already bound as a local further up in main(), and
    # a second plain import would make Python treat it as local-only everywhere.
    from core.trade_logger import TradeLogger as PathLogger
    from trade_log_reader import load_all_trades, _parse_tick_path
    from smart_pnl import replay_stop_on_ticks
    tl = PathLogger("test", "PATHSYM")
    tl.log_entry("PATHSYM", 100.0, 96.0, t0)
    wig = [100.0, 102.0, 104.0, 105.3, 104.4, 106.0, 110.0, 112.0, 108.0, 109.5]
    mgr = PositionManager()
    mgr.open_position(100.0, t0, "PATHSYM")
    for px in wig:
        mgr.track_price(px)
    summary = mgr.close_position(109.5, t0)
    tl.log_exit("PATHSYM", 109.5, summary["sl_final"], t0, "Trailing SL Hit",
                summary["pnl"], tick_path=summary["tick_path"])

    row = next((t for t in load_all_trades() if t["symbol"] == "PATHSYM"), None)
    check("trade round-tripped through the DB", row is not None, True)
    check("tick_path survived the DB write", row.get("tick_path"), wig)
    check("tick_path parsed as floats", all(isinstance(x, float) for x in row["tick_path"]), True)
    check("_parse_tick_path(None) is None, not []", _parse_tick_path({"tick_path": None}), None)
    check("_parse_tick_path(garbage) is None", _parse_tick_path({"tick_path": "{oops"}), None)

    rr = replay_stop_on_ticks(row["tick_path"], row["entry_price"])
    check("round-tripped path replays to the dip, not the peak",
          (rr["armed_at"], rr["exit_idx"]), (3, 4))
    check("...and the fill is at the dipped price", rr["exit_points"], 4.4)

    print("\n11b) chart replay: stop parked at +5 over real ticks")
    # 5 -> 4.5 -> 6 -> 8: the dip at 4.5 must fire the stop, even though the
    # trade went on to reach 8. A peak-based engine would wrongly say "+8".
    wiggle = [100.0, 102.0, 105.2, 104.5, 106.0, 108.0]
    r = replay_stop_on_ticks(wiggle, 100.0)
    check("stop armed at tick 2", r["armed_at"], 2)
    check("stop fired at tick 3 (the 4.5 dip)", r["exit_idx"], 3)
    check("filled at the dipped price, not the peak", r["exit_points"], 4.5)
    check("flagged as a genuine early stop", r["hit_stop"], True)

    # never reached +5 -> never armed
    r2 = replay_stop_on_ticks([100.0, 101.0, 99.0], 100.0)
    check("never reached +5 => never armed", r2["armed_at"], None)
    check("...and no exit", r2["exit_idx"], None)

    # reached +5 and held to the end -> not an early stop
    r3 = replay_stop_on_ticks([100.0, 106.0, 110.0, 108.0], 100.0)
    check("held +5 to the end => armed", r3["armed_at"], 1)
    check("...exits on the last tick", r3["exit_idx"], 3)
    check("...and is NOT an early stop", r3["hit_stop"], False)

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
