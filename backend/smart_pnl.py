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

# Prices are accumulated as floats, so a replayed exit can land a few times
# 1e-15 away from the real one (25.549999999999997 vs 25.55). Anything inside
# this band is arithmetic noise, not a different outcome, so comparisons that
# decide "did the rule help" must use it - otherwise an unchanged trade gets
# reported as a win.
POINTS_EPS = 0.005

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


# A hypothetical stop is armed at a level, and a stop order FILLS at or below
# that level - never exactly at it. Observed slippage on real trailing exits
# ranged from 0.05 to 1.45 points, so 1.0 is a deliberately conservative
# average. Every "would bank" figure below subtracts this.
EXIT_BUFFER_PTS = 1.0


def replay_stop_on_ticks(ticks, entry_price, stop_offset=5.0):
    """
    Walk a real tick series with a stop parked at entry+stop_offset.

    This is the tick-wise counterfactual the chart draws. Arm the stop the
    moment price first reaches it, then fire on the first tick that trades back
    through. Nothing here is estimated from the peak - it is replayed.

    Returns a dict:
      armed_at    index where the stop was armed (None if never reached)
      exit_idx    index where it fired (None if it never fired)
      exit_price  the fill price
      exit_points fill price - entry, in points
      hit_stop    True only if it fired BEFORE the last tick, i.e. the real
                  trade carried on past it
    """
    stop = entry_price + stop_offset
    armed_at = None
    exit_idx = None
    exit_price = None
    for i, px in enumerate(ticks or []):
        if exit_idx is not None:
            break
        if px >= stop:
            if armed_at is None:
                armed_at = i
        elif armed_at is not None:
            exit_idx = i
            exit_price = px
    if exit_price is None and armed_at is not None and ticks:
        # Touched the stop, never broke it, and the trade ended above it.
        exit_idx = len(ticks) - 1
        exit_price = ticks[-1]
    return {
        "stop_price": round(stop, 2),
        "armed_at": armed_at,
        "exit_idx": exit_idx,
        "exit_price": exit_price,
        "exit_points": None if exit_price is None else round(exit_price - entry_price, 2),
        "hit_stop": (armed_at is not None and exit_idx is not None
                     and len(ticks or []) > 1 and exit_idx < len(ticks) - 1),
    }


def replay_trailing_ladder(ticks, entry_price, first_rung=5.0, step=5.0):
    """
    Walk a real tick series with a stop that RATCHETS.

    This is the ladder we want to know about: the first rung sits at
    `first_rung` (not entry+1), and every further `step` points of profit
    locks another rung. A trade that runs to +10.5 parks the stop at +10, so
    a pullback banks +10 instead of the +5 a flat barrier would have given up.

    ORDER OF THE TWO CHECKS IS THE WHOLE POINT
    -----------------------------------------
    Each tick is judged in this order:
      1. does the price breach the stop as it stands RIGHT NOW? -> fire
      2. if not, and the tick is high enough, ratchet the stop up one rung

    Checking the breach before ratcheting is what lets a gap up through
    several rungs survive. Flip the order and a tick that jumps 5 -> 10.5
    would fill at the old +5 stop on the same tick that earned the +10 rung,
    which never happens in a live book - the exchange cannot retroactively
    fill a stop you had not yet placed.

    Returns the rung ladder alongside the fill, so the chart can draw the
    staircase instead of a flat line.
    """
    stop = entry_price - 5.0
    armed_at = None
    exit_idx = None
    exit_price = None
    stop_at_exit = None
    rungs = 0
    stop_path = []
    for i, px in enumerate(ticks or []):
        if exit_idx is not None:
            break
        # 1. breach the current stop?
        if armed_at is not None and px <= stop:
            exit_idx = i
            exit_price = px
            stop_at_exit = stop
            break
        # 2. safe on this tick - ratchet up
        profit = px - entry_price
        if profit >= first_rung:
            milestones = int((profit - first_rung) / step)
            new_stop = entry_price + first_rung + milestones * step
            if new_stop > stop:
                stop = new_stop
                rungs = milestones + 1
            if armed_at is None:
                armed_at = i
        stop_path.append(stop)

    if exit_price is None and armed_at is not None and ticks:
        # Touched a rung, never broke it, and the trade ended above it.
        exit_idx = len(ticks) - 1
        exit_price = ticks[-1]
        stop_at_exit = stop

    return {
        "stop_price": round(stop_at_exit if stop_at_exit is not None else stop, 2),
        "armed_at": armed_at,
        "exit_idx": exit_idx,
        "exit_price": exit_price,
        "exit_points": None if exit_price is None else round(exit_price - entry_price, 2),
        "rungs_locked": rungs,
        "stop_path": stop_path,
        "hit_stop": (armed_at is not None and exit_idx is not None
                     and len(ticks or []) > 1 and exit_idx < len(ticks) - 1),
    }


def _confirmed_crossing_points(trade, first_rung, step, buffer_pts):
    """
    No tick path, but the outcome is still PROVABLE - not a guess.

    If the peak (mfe_points, recorded exactly) reached `first_rung` and the
    real exit came in BELOW it, then price necessarily traded back down through
    that level: options move in 0.05 ticks, so it cannot jump from above the
    rung to below it without printing the cross. A stop parked at the first
    rung was therefore hit, guaranteed, on the way down.

    What we still do NOT know is the exact fill tick, because the recorded
    path has gaps - hence `buffer_pts`. The DIRECTION is measured; only the
    exact rupee is approximate, and this is not the peak-based guess the
    `hindsight` rule used to make.

    Returns None when nothing can be proven: the trade never reached the first
    rung (no rung was ever armed), or the real exit came in at or above it
    (so the price may never have traded back down through it at all).
    """
    mfe = trade.get("mfe_points")
    actual = trade.get("pnl")
    if mfe is None or actual is None:
        return None
    if mfe < first_rung:
        return None                    # never reached, no rung ever armed
    if actual >= first_rung:
        return None                    # exited above the rung - unknowable

    # Price came back down through it. The fill lands at or just under the
    # rung, so subtract the same allowance the other inferences use.
    fill = first_rung - (buffer_pts or 0.0)
    return fill if fill > 0 else 0.0


def smart_exit(trade, bank_at=5, prove_at=None, buffer_pts=EXIT_BUFFER_PTS):
    """
    SIMULATION ONLY - this is not what the bot does.

    The live bot runs the untouched original ladder in
    position_manager.update_trailing_sl(): first rung entry+1, then entry+5,
    entry+10 and so on. Nothing here changes that.

    The question: if we had parked the stop at entry+5 instead of entry+1,
    what would this trade have returned?

    WHY PEAK MINUS GIVEBACK IS NOT THE ANSWER
    ------------------------------------------
    Option prices do not travel in a straight line. A trade that peaks at +8
    typically goes 5 -> 4.5 -> 6 -> 5.2 -> 8. The moment a stop is armed at +5,
    that 4.5 tick fires it. Assuming we could sit through the wiggle and still
    bank the +8 is hindsight - it is the single biggest way this study can lie
    to us, and it is exactly the mistake that made an earlier version of this
    page look like it was worth lakhs.

    SO WE REPLAY THE REAL TICKS
    ---------------------------
    Whenever tick_path is stored, the answer is not estimated at all. We walk
    the actual prices through the ladder, ratcheting the stop up as the price
    earns each rung, and fire on the first tick that breaks it. The exit is read
    off the recorded path, tick for tick. That is a measurement, not a model.

    Sources, in order of trustworthiness:

      1. tick_path present  -> replayed on real ticks through the trailing
         ladder. Exact, including which rung filled. This is the gold standard
         and the only source strong enough to settle the question.
      2. no tick path, but mfe reached the first rung AND the real exit came
         in below it -> PROVABLE. Price was above the rung and then below it,
         so it traded back through and a stop there would have fired. Only the
         exact fill tick is unknown, so the buffer is subtracted. This is a
         measurement of direction, not a peak-based guess.
      3. neither -> genuinely unknowable without the path. No claim is made.

    The old `hindsight` rule (assume every trade that peaked high banked the
    rung nearest its peak) is deliberately gone: with a ratcheting ladder that
    guess is wrong more often than it is right, and it is what once made this
    page look worth lakhs.

    Returns (pnl_points, rule_fired).
    """
    actual = trade["pnl"]
    mfe = trade.get("mfe_points")
    first_rung = float(bank_at or 5.0)
    step = 5.0
    if actual is None:
        return None, "unsettled"
    if mfe is None:
        return actual, "unknown-mfe"
    if mfe < first_rung:
        # Never reached the first rung, so no rung was ever armed.
        return actual, "untouched"

    # --- 1. THE DEFINITIVE PATH: replay the actual recorded ticks -------------
    ticks = trade.get("tick_path")
    if ticks:
        entry = trade.get("entry_price")
        if entry is not None:
            r = replay_trailing_ladder(ticks, entry, first_rung, step)
            pts = r["exit_points"]
            if pts is None:
                # Reached the rung but the series ends without a break in either
                # direction; treat as untouched rather than invent a fill.
                return actual, "survived"
            if pts > actual + POINTS_EPS:
                return pts, "ladder_help"
            if pts < actual - POINTS_EPS:
                # The real exit beat the hypothetical ladder. The replayed number
                # is a MEASUREMENT, not a guess, so the loss is booked like any
                # other. Flooring it to `actual` here would make this branch a
                # no-op and leave delta_net structurally incapable of going
                # negative - the headline could then only ever ratchet upwards.
                return pts, "ladder_hurt"
            return actual, "ladder_same"

    # --- 2. provable without the path: it crossed the first rung --------------
    pts = _confirmed_crossing_points(trade, first_rung, step, buffer_pts)
    if pts is not None:
        if pts > actual + POINTS_EPS:
            return pts, "confirmed_help"
        if pts < actual - POINTS_EPS:
            # Book the loss. Symmetry matters: this fill is the SAME estimate
            # used by confirmed_help above, so crediting the estimate when it
            # helps while discarding it when it hurts would overstate the rule
            # by construction.
            return pts, "confirmed_hurt"
        return actual, "confirmed_same"

    # --- 3. nothing provable - say so rather than guess ----------------------
    return actual, "no_path"


# A row is a measurement only when it was replayed over real recorded ticks, or
# when the outcome is provable from what WAS recorded (never reached the rung,
# the stop was never hit, or price provably crossed the rung on the way back
# down). The exact fill tick of an inferred row is approximate - only its
# direction is measured.
MEASURED_RULES = {
    "ladder_help", "ladder_hurt", "ladder_same",       # exact, from ticks
    "confirmed_help", "confirmed_hurt", "confirmed_same",  # provable crossing
    "survived", "untouched", "unknown-mfe",           # exact, no exit change
}
# No claim at all: without the tick path and without a provable crossing, the
# trade is simply unknown. These must never be summed as if they were results.
UNVERIFIED_RULES = {"no_path"}

# Rules whose verdict comes from a full tick-by-tick replay. These are the only
# ones strong enough to decide whether the idea works.
REPLAYED_RULES = {"ladder_help", "ladder_hurt", "ladder_same"}

VERDICT_FOR = {
    "ladder_help": "helped",
    "ladder_hurt": "hurt",
    "ladder_same": "same",
    "confirmed_help": "helped",
    "confirmed_hurt": "hurt",
    "confirmed_same": "same",
    "survived": "same",
    "untouched": "same",
    "unknown-mfe": "same",
    "no_path": "unknown",
}


def is_measured(rule_fired):
    """True when the outcome came from real recorded price path, not a guess."""
    return rule_fired in MEASURED_RULES


def is_replayed(rule_fired):
    """True only when the outcome was replayed over the real tick series."""
    return rule_fired in REPLAYED_RULES


def verdict_for(rule_fired):
    """did the rule help, hurt, or make no difference - or is it unknown?"""
    return VERDICT_FOR.get(rule_fired, "unknown")


# Rules whose name alone must never be trusted as a verdict: any rule that
# returns the live result unchanged in some branch ("*_hurt", "*_same") or one
# that fires on a float compare arithmetic noise can win ("*_help"). The delta
# decides, not the label.
RULES_NEEDING_DELTA = {
    "ladder_help", "ladder_hurt",
    "confirmed_help", "confirmed_hurt",
}


def _verdict_from_delta(rule, delta_points):
    """
    The verdict that the numbers support, not the one the rule name implies.

    A rule says what the stop DID; only the delta says whether that was worth
    anything. Where a rule can fire without moving the result, the delta
    decides. Rows with no provable outcome stay "unknown" no matter what they
    moved, because a number we cannot stand behind is not evidence.
    """
    if rule == "skipped" or rule == "no_path":
        return "unknown"
    if rule not in RULES_NEEDING_DELTA:
        return verdict_for(rule)
    if delta_points is None or abs(delta_points) <= POINTS_EPS:
        return "same"
    return "helped" if delta_points > 0 else "hurt"


def simulate(trades, bank_at=None, prove_at=None, day_stop_at=None,
             buffer_pts=EXIT_BUFFER_PTS):
    """
    Replay settled trades in entry-time order, per day.

    day_stop_at is compared against the CUMULATIVE realised points for the day
    (gross, in points - not net rupees). Once reached, every later trade that
    day is skipped, which is what "done for the day" means in practice.

    Rows are tagged with `verified`: True when the outcome was derived from
    recorded tick path, False when it is the old peak-based guess. Callers must
    keep the two apart - mixing them is how this study ends up looking better
    than it is.
    """
    rows = []
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["entry_time"][:10]].append(t)

    for day in sorted(by_day):
        day_pts = 0.0
        stopped = False
        for t in sorted(by_day[day], key=lambda x: (x["entry_time"], x["id"] or 0)):
            pnl, rule = smart_exit(t, bank_at, prove_at, buffer_pts)
            skipped = stopped or t.get("pnl") is None
            if skipped:
                pnl, rule = t.get("pnl"), "skipped"
            elif pnl is not None:
                day_pts += pnl
                if day_stop_at is not None and day_pts >= day_stop_at:
                    stopped = True

            # Full replay evidence, so the verdict is auditable tick by tick
            # instead of taken on trust. Only present when ticks were recorded.
            ticks = t.get("tick_path")
            replay = None
            if ticks and t.get("entry_price") is not None:
                rp = replay_trailing_ladder(ticks, t["entry_price"],
                                            bank_at or 5.0, 5.0)
                replay = {
                    "ticks": len(ticks),
                    "armed_at_tick": rp["armed_at"],
                    "fired_at_tick": rp["exit_idx"],
                    "rungs_locked": rp["rungs_locked"],
                    "exit_price": rp["exit_price"],
                    "exit_points": rp["exit_points"],
                    "fired_early": rp["hit_stop"],
                }

            actual_net = t.get("net_pnl")
            smart_net = None if pnl is None else net_for(t, pnl)
            delta_pts = None if (skipped or pnl is None or t.get("pnl") is None) \
                            else round(pnl - t["pnl"], 2)
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
                "dips_below_bank": t.get("dips_below_bank"),
                "actual_pnl": t.get("pnl"),
                "actual_net": actual_net,
                "smart_pnl": None if skipped else pnl,
                "smart_net": None if skipped else smart_net,
                "delta_points": delta_pts,
                "delta_net": None if (skipped or smart_net is None or actual_net is None)
                              else round(smart_net - actual_net, 2),
                "rule_fired": rule,
                "verified": is_measured(rule),
                "replayed": is_replayed(rule),
                # How solid is THIS row's number? The caller must keep these
                # apart - summing them together is how an estimate gets
                # presented as a result.
                #   "tick"      exit read off real recorded ticks (gold standard)
                #   "crossing"  the crossing is PROVED, but the exact fill is not
                #                known, so it carries the allowance - a close
                #                estimate, NOT a measurement
                #   "assumed"   nothing provable; the live result is kept
                #   "live"      rule left the result untouched either way
                "proof": ("tick" if is_replayed(rule)
                          else "crossing" if rule.startswith("confirmed_")
                          else "assumed" if rule == "no_path"
                          else "live"),
                "verdict": _verdict_from_delta(rule, delta_pts),
                "evidence": replay,
                "day_stopped": stopped and not skipped,
            })
    return rows


def _summarise(rows):
    taken = [r for r in rows if r["smart_pnl"] is not None]
    verified = [r for r in taken if r.get("verified")]
    replayed = [r for r in taken if r.get("replayed")]
    # The verdict, counted only over trades replayed tick by tick. This is the
    # only tally that can settle whether the rule works: every other number on
    # this page is either a guess or a blend of guesses.
    def tally(subset):
        out = {"helped": 0, "hurt": 0, "same": 0, "unknown": 0}
        for r in subset:
            v = r.get("verdict", "unknown")
            out[v] = out.get(v, 0) + 1
        return out

    rep_tally = tally(replayed)
    return {
        "trades": len(taken),
        "trades_skipped": sum(1 for r in rows if r["rule_fired"] == "skipped"),
        "gross_points": round(sum(r["smart_pnl"] for r in taken), 2),
        "net_rupees": round(sum(r["smart_net"] for r in taken), 2),
        "actual_gross_points": round(sum(r["actual_pnl"] for r in taken if r["actual_pnl"] is not None), 2),
        "actual_net_rupees": round(sum(r["actual_net"] for r in taken if r["actual_net"] is not None), 2),
        "win_rate": round(100 * sum(1 for r in taken if r["smart_pnl"] > 0) / len(taken), 1) if taken else 0.0,
        # The honest split. `net_rupees` above blends both and will look better
        # than reality; these two do not.
        "verified_trades": len(verified),
        "unverified_trades": len(taken) - len(verified),
        "verified_net_rupees": round(sum(r["smart_net"] for r in verified), 2),
        "verified_actual_net_rupees": round(sum(r["actual_net"] for r in verified if r["actual_net"] is not None), 2),
        # Definitive, replay-only view.
        "replayed_trades": len(replayed),
        "replayed_helped": rep_tally["helped"],
        "replayed_hurt": rep_tally["hurt"],
        "replayed_same": rep_tally["same"],
        "replayed_points": round(sum(r["delta_points"] or 0 for r in replayed), 2),
        "replayed_actual_points": round(
            sum(r["actual_pnl"] for r in replayed if r["actual_pnl"] is not None), 2),
    }


def _baseline_summary(rows):
    return _summarise([dict(r, smart_pnl=r["actual_pnl"], smart_net=r["actual_net"],
                            rule_fired="current", verified=True) for r in rows])


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
        "settings": {"bank_at": bank_at, "prove_at": prove_at, "day_stop_at": day_stop_at,
                     "exit_buffer_pts": EXIT_BUFFER_PTS},
        "trades": sorted(rows, key=lambda r: r["entry_time"], reverse=True),
        "days": days,
        "summary": smart,
        "baseline": baseline,
        "delta_net": round(smart["net_rupees"] - baseline["net_rupees"], 2),
        "per_day_delta": round((smart["net_rupees"] - baseline["net_rupees"]) / max(1, len(days)), 2),
        # The number to actually trust. delta_net blends in trades where we had
        # to guess; this one only counts trades whose real tick path we recorded.
        "verified_delta_net": round(
            smart["verified_net_rupees"] - smart["verified_actual_net_rupees"], 2),
        "verified_coverage_pct": round(
            100 * smart["verified_trades"] / max(1, smart["trades"]), 1),
        # THE SPLIT THAT MATTERS. `delta_net` above blends all three strengths
        # and will read far better than the evidence supports. A "crossing" row
        # is proven to have stopped, but WHERE it filled is an assumption, so it
        # is counted separately from a row replayed on real recorded ticks.
        "evidence_split": {
            "tick_replayed": {
                "trades": smart["replayed_trades"],
                "delta_net": round(
                    sum(r["delta_net"] for r in rows
                        if r.get("proof") == "tick" and r["delta_net"] is not None), 2),
                "delta_points": smart["replayed_points"],
            },
            "crossing_estimated": {
                "trades": sum(1 for r in rows if r.get("proof") == "crossing"),
                "delta_net": round(
                    sum(r["delta_net"] for r in rows
                        if r.get("proof") == "crossing" and r["delta_net"] is not None), 2),
            },
            "not_provable": {
                "trades": sum(1 for r in rows if r.get("proof") == "assumed"),
                "delta_net": 0.0,
            },
            "unchanged": {
                "trades": sum(1 for r in rows if r.get("proof") == "live"),
                "delta_net": 0.0,
            },
        },
        # The definitive view: only trades replayed tick by tick, listed with
        # the evidence needed to check the arithmetic by hand.
        "replay_verdict": {
            "trades": smart["replayed_trades"],
            "helped": smart["replayed_helped"],
            "hurt": smart["replayed_hurt"],
            "same": smart["replayed_same"],
            "actual_points": smart["replayed_actual_points"],
            "sim_points": round(smart["replayed_actual_points"] + smart["replayed_points"], 2),
            "delta_points": smart["replayed_points"],
            "rows": [
                {
                    "id": r["id"],
                    "date": r["date"],
                    "entry_time": r["entry_time"],
                    "symbol": r["symbol"],
                    "verdict": r["verdict"],
                    "actual_points": r["actual_pnl"],
                    "sim_points": r["smart_pnl"],
                    "delta_points": r["delta_points"],
                    "mfe_points": r["mfe_points"],
                    "dips": r["dips_below_bank"],
                    "evidence": r["evidence"],
                }
                for r in sorted(rows, key=lambda x: x["entry_time"], reverse=True)
                if r.get("replayed") and r.get("evidence")
            ],
        },
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
    #
    # Both figures go through smart_exit rather than a hardcoded "+5", because
    # the ladder now ratchets: a trade that peaked inside this band locks only
    # the first rung, so the flat assumption is no longer the right counterfactual.
    # The two are kept apart so a measurement is never summed with a guess.
    leak = [t for t in known if 5 <= (t["mfe_points"] or 0) < 10]
    leak_actual = sum(net_for(t, t["pnl"]) for t in leak)
    leak_hindsight = sum(net_for(t, 5) for t in leak)

    # MEASURED: every trade in this band whose outcome is provable or replayed.
    leak_verified = []
    leak_measured_gain = 0.0
    for t in leak:
        pts, rule = smart_exit(t, 5, None)
        if pts is None or rule == "no_path":
            continue
        leak_verified.append(t)
        leak_measured_gain += net_for(t, pts) - net_for(t, t["pnl"])

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
            # HINDSIGHT: assumes every one of them banked a clean +5. This is
            # the number that made the idea look worth lakhs. It is a guess.
            "hindsight_net": round(leak_hindsight, 2),
            "hindsight_recoverable": round(leak_hindsight - leak_actual, 2),
            # MEASURED: only trades whose real tick path we captured, each run
            # through the real stop logic including the exit buffer.
            "verified_trades": len(leak_verified),
            "unverified_trades": len(leak) - len(leak_verified),
            "verified_gain": round(leak_measured_gain, 2),
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

    # The one case that decides whether this rule is safe: did the price ever come
    # back through +5 after touching it? If yes, a +5 stop would have fired and
    # the trade would have died early. Counted across every trade with real
    # recorded path, not just runners - a dipper is a dipper at any peak.
    measured = [t for t in trades if t.get("dips_below_bank") is not None]
    dippers = [t for t in measured if (t.get("dips_below_bank") or 0) > 0]
    runner_dippers = [t for t in dippers if (t.get("mfe_points") or 0) >= 10]
    # Of the trades that would actually be touched by the rule (reached +5).
    bankable = [t for t in measured if 5 <= (t.get("mfe_points") or 0) < 10]

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
        "runner_dips": {
            "measured_trades": len(measured),
            "dipped": len(dippers),
            "dipped_pct": round(100 * len(dippers) / len(measured), 1) if measured else 0.0,
            "runner_dipped": len(runner_dippers),
            "bankable_measured": len(bankable),
            "bankable_dipped": sum(1 for t in bankable if (t.get("dips_below_bank") or 0) > 0),
            "note": "Path data exists only for trades logged after capture was added. "
                    "Until measured_trades is in the dozens, treat every figure here as provisional.",
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(smart_pnl_report(bank_at=5, prove_at=10, day_stop_at=10)["summary"], indent=2))
