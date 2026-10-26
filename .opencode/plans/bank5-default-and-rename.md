# Make bank+5 the live baseline (replace entry+1 first rung) + full Smart-vocabulary retirement

Approved decisions (26 Oct 2026, after data analysis):
- Switch the live exit rule to bank the first rung at +5 (what the shadow study called "Smart"). Data: last 4 sessions all losers under base (-34.10 total); post-fix 15 tick-recorded trades show +18.70 convert with helped 5 / hurt 0; all-2026 delta +31.95 (17/7).
- `day_stop_at` setting ships but defaults to 0 (off). Two-click enable later.
- Effective next session (27 Oct), before the Diwali stretch (Nov 8-10).
- Full rename: no "smart" wording survives in live vocab; DB/API keys and frontend types renamed, old-rule becomes the counterfactual the study measures.

## A. Live rule switch

1. `backend/settings_db.py` DEFAULTS: add
   - `bank_rung`: {"value": "5", type number, label "Bank Rung (points)", category risk}
   - `day_stop_at`: {"value": "0", type number, label "Day Stop At (cumulative points, 0 = off)", category risk}
2. `backend/core/position_manager.py` `update_trailing_sl()` (~:171-179): first
   milestone parks at `entry + bank_rung` (settings read, default 5) instead of the
   hardcoded `1.0`; later rungs unchanged (`milestones * trailing_step`). Update the
   docstring which currently documents entry+1 (:142-146). This one change IS the switch.
3. `backend/settings.json` — note only: values stay as-is (5/5 trigger/step + bank 5).
   Token-hold-back rule continues; never stage this file.
4. Day-stop plumbing (kept inert by default):
   - `backend/upstox/data_streamer.py`: init `self.day_realized = 0.0` near other
     streamer state; on every position exit add realised points (same place the
     trade summary is persisted, ~:328 context).
   - Gate new entries where `comp['can_trade'] and self.is_entry_window_open()`
     (~:450): also require day-stop pass; when crossed, set `can_trade=False` on
     components so the scheduler auto-stop loop (:508-514) closes the day naturally.

## B. Audit trail

5. `backend/db.py` MIGRATION_COLUMNS: add `bank_rung INTEGER`. Run migration (170+ rows NULL-safe).
6. `backend/core/trade_logger.py` `log_entry`: persist bank_rung from settings at entry time.
7. `backend/trade_log_reader.py` `_row_to_dict`: expose `bank_rung`.

## C. Full rename (backend)

8. `backend/smart_pnl.py` → **`exit_rules.py`** (git mv). Inside:
   - `smart_pnl_report` → `exit_rules_report`; keys `smart_pnl`→`legacy_pnl`,
     `smart_net`→`legacy_net` (counterfactual = OLD entry+1 rule; delta = legacy - actual,
     same polarity as before so "positive delta = old rule would have been better").
   - Counterfactual mode: post-switch the study answers "would the legacy rule have
     been better?" — `STRATEGIES` relabels: `new` (bank+5), `legacy` (entry+1),
     plus day-stop variants by threshold.
   - Legacy replay: `replay_trailing_ladder(ticks, entry, first_rung=1.0, step=5.0)`
     mirrors old pm arithmetic (arm at +1 when profit ≥ trigger; document that
     approximation in a docstring).
9. `backend/api_server.py`: `/api/report/smart-pnl` → `/api/report/exit-rules`
   (imports/func names updated); threshold-sweep keys `smart_pnl_total` → `legacy_pnl_total`.
10. `backend/test_factory_arguments.py`, holiday test, server imports: update module name.

## D. Full rename (frontend)

11. `frontend/app/lib/types.ts`: TradeEntry `smart_pnl`/`smart_net` removed →
    `legacy_pnl`/`legacy_net` (+ `bank_rung`, optional).
12. `frontend/app/lib/api.ts` :62: endpoint → `/api/report/exit-rules`.
13. `frontend/app/components/TradeLogsTable.tsx`: "Smart book" column → "Legacy book";
    smartNet → legacyNet mapping; tooltip copy ("the old rule would have netted...").
14. `frontend/app/mfe/page.tsx` (and any analytics consumer surfaced by grep during build):
    wording + footers updated (they currently describe the old direction).
15. `frontend/app/lib/*` any other 'smart' references caught via build/typecheck.

## E. Tests + verification

16. `backend/test_excursion_tracking.py`: first-rung expectations flip — giveback
    trade exits at entry+5 (was entry+1); runner still trails to +20; sl_rungs counts
    updated; settings DB writes bank_rung 5 then restores.
17. New `backend/test_bank_rung.py`: pm moves to entry+5 (default), entry+1 when set
    to 1 (old behaviour preserved via knob); day-stop gates entries and baker stops
    the day via scheduler auto-stop path (stub streamer).
18. Existing suites: `test_market_holiday.py`, `test_four_slots.py`,
    `test_excursion_tracking.py` — all green.
19. `tsc --noEmit` + `next build` clean; backend import smoke of server chain.

## F. Execution notes

- Out of plan mode: implement in the order A→B→C→D→E, run tests after each chunk,
  then `tsc`/build. Commit + push on user's word (pattern: label "feat(rules): bank +5 is
  the baseline now..." + separate data commit if trades.db changed).
- `backend/settings.json` never staged (live token).
- Today (26 Oct) session already ran under old rule; new rule takes effect next start.
