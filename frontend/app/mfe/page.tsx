"use client";

import { useCallback, useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { fetchSmartPnl, fetchStrategies, fetchThresholdSweep, fetchRiskReport, fetchSettings } from "../lib/api";
import type { SmartPnlReport, StrategyRow, SweepRow, RiskReport } from "../lib/types";

const GREEN = "#10b981";
const RED = "#ef4444";
const SLATE = "#64748b";
const AMBER = "#f59e0b";
const INDIGO = "#6366f1";

const rs = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `${v < 0 ? "-" : "+"}₹${Math.abs(v).toFixed(0)}`;

export default function MfeReportPage() {
  const [report, setReport] = useState<SmartPnlReport | null>(null);
  const [strategies, setStrategies] = useState<StrategyRow[]>([]);
  const [sweep, setSweep] = useState<SweepRow[]>([]);
  const [risk, setRisk] = useState<RiskReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [bankAt, setBankAt] = useState(5);
  const [proveAt, setProveAt] = useState(10);
  // Day-stop is OFF by default because the live bot does not have it enabled.
  // The report must mirror the live setting, not a hypothetical rule.
  const [dayStopAt, setDayStopAt] = useState(0);
  const [trailingTriggerShown, setTrailingTriggerShown] = useState(5);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const year = new Date().getFullYear();
      const [r, s, w, rk] = await Promise.all([
        fetchSmartPnl(year, bankAt, proveAt, dayStopAt),
        fetchStrategies(year),
        fetchThresholdSweep(year),
        fetchRiskReport(year),
      ]);
      setReport(r);
      setStrategies(s);
      setSweep(w);
      setRisk(rk);
      fetchSettings()
        .then((r) => {
          const t = r.settings.find((x) => x.key === "trailing_trigger");
          if (t) setTrailingTriggerShown(Number(t.value));
        })
        .catch(() => {});
    } catch {
      setErr("Could not reach the backend API (port 8002). Is the bot running?");
    } finally {
      setLoading(false);
    }
  }, [bankAt, proveAt, dayStopAt]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <div className="text-sm text-[#64748b]">Loading report…</div>;
  if (err) return <div className="text-sm text-[#ef4444]">{err}</div>;
  if (!report) return null;

  const m = report.mfe_coverage;
  const rv = report.replay_verdict;
  const es = report.evidence_split;
  const maxHist = Math.max(...m.histogram.map((h) => h.count), 1);
  const maxSweep = Math.max(...sweep.map((s) => Math.abs(s.net_rupees)), 1);
  const bestDay = Math.max(...report.days.map((d) => Math.abs(d.delta_net)), 1);
  const recentDays = [...report.days].reverse().slice(0, 14);
  const bestNet = Math.max(...strategies.map((s) => s.net_rupees));

  return (
    <div className="max-w-6xl mx-auto space-y-5 pb-24">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Smart P&amp;L</h1>
          <p className="text-xs text-[#64748b] mt-1">
            Trailing ladder (pehla rung +5, phir +5 steps) — replayed on real recorded ticks, against
            what the live bot actually banked.
            <span className="text-[#f59e0b] font-semibold"> This does not change live trading.</span>
          </p>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 text-xs text-[#94a3b8] hover:text-white transition-colors">
          <Icon icon="lucide:refresh-cw" width={13} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card label="Actual net" value={rs(report.baseline.net_rupees)} sub={`${report.baseline.trades} trades`} color={report.baseline.net_rupees >= 0 ? GREEN : RED} />
        <Card label="Smart net" value={rs(report.summary.net_rupees)} sub={`${report.summary.trades} taken · ${report.summary.trades_skipped} skipped`} color={report.summary.net_rupees >= 0 ? GREEN : RED} />
        <Card
          label="Headline gain"
          value={rs(report.delta_net)}
          sub="blends measured + estimated — see below"
          color={INDIGO}
        />
        <Card label="Win rate" value={`${report.summary.win_rate}%`} sub={`was ${report.baseline.win_rate}%`} color={INDIGO} />
      </div>

      {/* ---------- HOW MUCH OF THAT GAIN IS ACTUALLY EVIDENCE ---------- */}
      <div className="card p-4 border-l-2" style={{ borderLeftColor: AMBER }}>
        <div className="flex items-center gap-2 mb-1">
          <Icon icon="lucide:scale" width={15} className="text-[#f59e0b]" />
          <h2 className="text-sm font-semibold text-[#f59e0b]">
            The Rs{rs(report.delta_net)} headline is NOT all measured
          </h2>
        </div>
        <p className="text-[11px] text-[#64748b] mb-3 leading-relaxed">
          Fees are already deducted from every figure here. But the gains are not all the same
          quality, and adding them up hides it. Split by what each trade can actually prove:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-center mb-3">
          <Mini
            label="MEASURED — real ticks"
            value={rs(es.tick_replayed.delta_net)}
            sub={`${es.tick_replayed.trades} trades · ${es.tick_replayed.delta_points} pts`}
            color={es.tick_replayed.delta_net >= 0 ? GREEN : RED}
          />
          <Mini
            label="ESTIMATED — crossing proven"
            value={rs(es.crossing_estimated.delta_net)}
            sub={`${es.crossing_estimated.trades} trades · exit price assumed`}
            color={AMBER}
          />
          <Mini
            label="NOT PROVABLE"
            value="—"
            sub={`${es.not_provable.trades} trades · no path, no claim`}
            color={SLATE}
          />
        </div>

        <p className="text-[11px] text-[#94a3b8] leading-relaxed">
          Only <b className="text-white">₹{rs(Math.abs(es.tick_replayed.delta_net))}</b> of the{" "}
          <b className="text-white">₹{rs(report.delta_net)}</b> headline rests on real recorded ticks. The
          rest is trades where we <i>know</i> price crossed the stop (peak was above it, exit came in
          below it) but <b>where exactly it filled is an assumption</b> — those carry a small allowance
          and are marked ESTIMATED, not measured.
          <span className="text-[#64748b]">
            {" "}This is why the number moves as new trades arrive: a replayed trade needs real ticks,
            and those only exist from 4 Oct onward. Decide on the measured row, not the headline.
          </span>
        </p>
      </div>

      {/* ---------- THE DEFINITIVE ANSWER ---------- */}
      <div className="card p-4 border-l-2" style={{ borderLeftColor: GREEN }}>
        <div className="flex items-center gap-2 mb-1">
          <Icon icon="lucide:check-check" width={15} className="text-[#10b981]" />
          <h2 className="text-sm font-semibold text-[#10b981]">
            Did it actually work? — replayed on real recorded ticks
          </h2>
        </div>
        <p className="text-[11px] text-[#64748b] mb-3 leading-relaxed">
          Every number here is replayed tick by tick over the price path the bot actually received. The
          stop is armed at <b className="text-white">entry+5</b> the moment price gets there, and fires
          on the first tick back through. No peak-based guessing anywhere. This is the only figure on
          the page built from measurement — but it is also the smallest sample, so read it with the
          trade count next to it.
        </p>
        {rv.trades > 0 && rv.trades < 50 && (
          <p className="text-[11px] text-[#f59e0b] mb-3 leading-relaxed">
            <b>Not enough trades to call this a win.</b> {rv.trades} replayed trades is a thin sample:
            a single unlucky trade here moves the total by more than the whole edge. Treat this as
            provisional and leave the live bot on its current rules until the count is in the dozens.
          </p>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center">
          <Mini label="Trades replayed" value={String(rv.trades)} color={rv.trades ? GREEN : SLATE} />
          <Mini label="HELPED" value={String(rv.helped)} color={rv.helped ? GREEN : SLATE} />
          <Mini label="HURT" value={String(rv.hurt)} color={rv.hurt ? RED : SLATE} />
          <Mini label="No change" value={String(rv.same)} color={SLATE} />
          <Mini
            label="Delta (points)"
            value={`${rv.delta_points >= 0 ? "+" : ""}${rv.delta_points.toFixed(2)}`}
            color={rv.delta_points >= 0 ? GREEN : RED}
          />
        </div>

        {rv.rows.length === 0 ? (
          <div className="mt-3 pt-3 border-t border-white/5">
            <p className="text-[11px] text-[#f59e0b] leading-relaxed">
              <b>No trades have recorded tick paths yet.</b> Path capture went live just now, so the
              first replayable trade will be the next one the bot takes. Until then this reads zero —
              which is the honest number, not a missing one.
            </p>
            <p className="text-[11px] text-[#64748b] mt-1.5">
              The {report.summary.unverified_trades} older trades can never be replayed: their prices
              were never recorded, so any figure for them would be an assumption.
            </p>
          </div>
        ) : (
          <div className="mt-3 pt-3 border-t border-white/5 overflow-x-auto">
            <ReplayTable rows={rv.rows} />
          </div>
        )}
      </div>

      <div className="card p-4 border-l-2" style={{ borderLeftColor: AMBER }}>
        <div className="flex items-start gap-2">
          <Icon icon="lucide:triangle-alert" width={15} className="text-[#f59e0b] mt-0.5 shrink-0" />
          <div className="text-[11px] text-[#94a3b8] leading-relaxed">
            <p>
              <b className="text-[#f59e0b]">Read the split card above, not the headline.</b>{" "}
              <b>Smart net</b> adds up three very different kinds of trade:{" "}
              {es.tick_replayed.trades} replayed on real recorded ticks,{" "}
              {es.crossing_estimated.trades} where the crossing is proven but the fill is assumed, and{" "}
              {es.not_provable.trades} that genuinely cannot be determined at all. Only the first group is
              a measurement.
            </p>
            <p className="mt-1.5">
              Only <b className="text-white">{es.tick_replayed.trades} of {report.summary.trades}</b>{" "}
              trades have real recorded ticks. Until that count is in the dozens, treat every figure here
              as provisional and keep the live bot on its current rules.
            </p>
          </div>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex flex-wrap items-end gap-4">
          <NumField label="SIM: bank at (pts)" value={bankAt} onChange={setBankAt} />
          <NumField label="SIM: trail past (pts)" value={proveAt} onChange={setProveAt} />
          <NumField label="SIM: stop day at (pts, 0 = off)" value={dayStopAt} onChange={setDayStopAt} />
          <div className="text-xs text-[#64748b] flex-1 min-w-[240px] leading-relaxed">
            <b className="text-amber-400">Simulation only.</b> The live bot runs its original stop ladder
            (first rung entry+1, then +5, +10) and nothing on this page changes that. This study asks: if
            we had parked the stop at <b className="text-white">+{bankAt}</b> once a trade reached{" "}
            <b className="text-white">+{trailingTriggerShown}</b>, would it have returned more? It is a
            stop-loss change, not a take-profit — a trade can still be stopped out at the initial loss.{" "}
            {dayStopAt ? (
              <>
                Day-stop is <b className="text-white">ON at +{dayStopAt}</b> — once the day&apos;s cumulative
                P&amp;L hits that, later trades are skipped.{" "}
                <b className="text-[#f59e0b]">The live bot has no day stop, so this is a simulation only.</b>
              </>
            ) : (
              <b className="text-[#10b981]">No day stop — this mirrors what the live bot actually does.</b>
            )}
          </div>
        </div>
      </div>
      {risk && (
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-1">
            <Icon icon="lucide:shield-alert" width={15} className="text-[#f59e0b]" />
            <h2 className="text-sm font-semibold text-[#f59e0b]">What could go wrong</h2>
          </div>
          <p className="text-xs text-[#64748b] mb-3">
            Every rule is scored against the same fixed baseline: {risk.total_trades} trades that actually
            happened, at their actual result ={" "}
            <b className="text-white">{risk.baseline_points >= 0 ? "+" : ""}{risk.baseline_points} points</b> over{" "}
            {risk.total_days} days. The question is not &quot;does it help on average&quot; but{" "}
            <i>&quot;on how many days does it make things worse?&quot;</i>
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#64748b] border-b border-[rgba(255,255,255,0.06)]">
                  <th className="text-left py-2 pr-3">Rule</th>
                  <th className="text-right py-2 pr-3">Trades taken</th>
                  <th className="text-right py-2 pr-3">Points</th>
                  <th className="text-right py-2 pr-3">vs baseline</th>
                  <th className="text-right py-2 pr-3" style={{ color: GREEN }}>Better</th>
                  <th className="text-right py-2 pr-3">No change</th>
                  <th className="text-right py-2" style={{ color: RED }}>Worse</th>
                </tr>
              </thead>
              <tbody>
                {risk.scenarios.map((s) => (
                  <tr key={s.key} className="border-b border-[rgba(255,255,255,0.04)]">
                    <td className="py-2 pr-3">
                      {s.label}
                      {s.days_worse > 0 && (
                        <span className="ml-2 text-[9px] text-[#ef4444] font-bold">RISKY</span>
                      )}
                      {s.days_worse === 0 && (
                        <span className="ml-2 text-[9px] text-[#10b981] font-bold">NO DOWNSIDE</span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono text-[#94a3b8]">{s.trades_taken}</td>
                    <td className="py-2 pr-3 text-right font-mono" style={{ color: s.points >= 0 ? GREEN : RED }}>
                      {s.points >= 0 ? "+" : ""}{s.points.toFixed(2)}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono font-semibold" style={{ color: s.vs_baseline >= 0 ? GREEN : RED }}>
                      {s.vs_baseline >= 0 ? "+" : ""}{s.vs_baseline.toFixed(2)}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono" style={{ color: GREEN }}>{s.days_better}</td>
                    <td className="py-2 pr-3 text-right font-mono text-[#64748b]">{s.days_same}</td>
                    <td className="py-2 text-right font-mono font-semibold" style={{ color: s.days_worse > 0 ? RED : "#334155" }}>
                      {s.days_worse}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {risk.scenarios.some((s) => s.worst_days.length > 0) && (
            <div className="mt-3 text-[10px] text-[#64748b] leading-relaxed">
              <b className="text-[#ef4444]">Days that got worse:</b>{" "}
              {risk.scenarios
                .filter((s) => s.worst_days.length > 0)
                .map((s) => (
                  <span key={s.key} className="mr-4 inline-block">
                    {s.label}:{" "}
                    {s.worst_days.map((w, i) => (
                      <span key={w.date}>
                        {i > 0 && ", "}
                        <span className="font-mono">{w.date}</span> ({w.delta > 0 ? "+" : ""}{w.delta} pts)
                      </span>
                    ))}
                  </span>
                ))}
            </div>
          )}

          <div className="mt-3 pt-3 border-t border-[rgba(255,255,255,0.06)]">
            <h3 className="text-xs font-semibold text-[#e2e8f0] mb-1">How much can the rule even reach?</h3>
            <div className="flex h-4 rounded overflow-hidden">
              <div style={{ width: `${(risk.coverage.bankable / risk.total_trades) * 100}%`, background: GREEN }} />
              <div style={{ width: `${(risk.coverage.never_reached / risk.total_trades) * 100}%`, background: RED }} />
              <div style={{ width: `${(risk.coverage.runner / risk.total_trades) * 100}%`, background: INDIGO }} />
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[10px]">
              <span style={{ color: GREEN }}>
                {risk.coverage.bankable} reached +5 to +10 &rarr; rule acts ({(100 * risk.coverage.bankable / risk.total_trades).toFixed(0)}%)
              </span>
              <span style={{ color: RED }}>
                {risk.coverage.never_reached} never reached +5 &rarr; rule cannot help ({(100 * risk.coverage.never_reached / risk.total_trades).toFixed(0)}%)
              </span>
              <span style={{ color: INDIGO }}>
                {risk.coverage.runner} ran past +10 &rarr; left alone ({(100 * risk.coverage.runner / risk.total_trades).toFixed(0)}%)
              </span>
            </div>
            <p className="text-[10px] text-[#475569] mt-2 leading-relaxed">
              This is the honest limit: the exit rule only touches about a fifth of the book. The red block is
              an entry problem — those trades never moved in our favour at all, so no exit rule can save them.
            </p>
            {risk.runner_dips && risk.runner_dips.measured_trades > 0 && (
              <div className="mt-3 pt-3 border-t border-[rgba(255,255,255,0.06)]">
                <h3 className="text-xs font-semibold text-[#e2e8f0] mb-1">
                  Measured: did the price break +5 after touching it?
                </h3>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <Mini label="Trades measured" value={String(risk.runner_dips.measured_trades)} />
                  <Mini
                    label="Dipped below +5"
                    value={`${risk.runner_dips.dipped} (${risk.runner_dips.dipped_pct}%)`}
                    color={risk.runner_dips.dipped > 0 ? AMBER : GREEN}
                  />
                  <Mini
                    label="Would be stopped"
                    value={`${risk.runner_dips.bankable_dipped} / ${risk.runner_dips.bankable_measured}`}
                    color={risk.runner_dips.bankable_dipped > 0 ? AMBER : GREEN}
                  />
                </div>
                <p className="text-[10px] text-[#64748b] mt-2 leading-relaxed">
                  This is the number that decides whether parking the stop at +5 is safe. Of the{" "}
                  {risk.runner_dips.bankable_measured} measured trades that reached +5 (where the rule would
                  act), <b className="text-[#f59e0b]">{risk.runner_dips.bankable_dipped}</b> traded back
                  through +5 at least once — those would have been stopped before reaching their peak, not
                  after. Only {risk.runner_dips.measured_trades} trades have path data so far, so treat this
                  as an early read, not a conclusion.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="card p-4 border-l-2" style={{ borderLeftColor: AMBER }}>
          <div className="flex items-center gap-2 mb-1">
            <Icon icon="lucide:triangle-alert" width={14} className="text-[#f59e0b]" />
            <h2 className="text-sm font-semibold text-[#f59e0b]">Exit problem — recoverable</h2>
          </div>
          <p className="text-xs text-[#64748b] mb-3">
            Reached +5, gave it all back to scratch. This is what the study targets.
          </p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <Mini label="Trades" value={String(m.leak.count)} />
            <Mini label="Actual" value={rs(m.leak.actual_net)} color={m.leak.actual_net >= 0 ? GREEN : RED} />
            <Mini
              label="If all held +5"
              value={rs(m.leak.hindsight_recoverable)}
              color={m.leak.hindsight_recoverable >= 0 ? GREEN : RED}
            />
          </div>
          <p className="text-[11px] text-[#f59e0b] mt-3 leading-relaxed">
            <b>That last number is a guess.</b> It assumes every one of those{" "}
            {m.leak.count} trades sat through the wiggle and banked a clean +5. Option prices
            go 5 → 4.5 → 6, so a +5 stop would have fired on the 4.5.
          </p>
          <div className="grid grid-cols-2 gap-2 text-center mt-2 pt-3 border-t border-white/5">
            <Mini
              label="Measured gain"
              value={rs(m.leak.verified_gain)}
              color={m.leak.verified_gain >= 0 ? GREEN : RED}
            />
            <Mini
              label="Trades measured"
              value={`${m.leak.verified_trades} / ${m.leak.count}`}
              color={m.leak.verified_trades > 0 ? GREEN : "#64748b"}
            />
          </div>
          <p className="text-[11px] text-[#64748b] mt-2 leading-relaxed">
            Measured gain uses only the {m.leak.verified_trades} trades whose real tick path we
            captured, each run through the actual stop logic. The other{" "}
            {m.leak.unverified_trades} predate path capture and are excluded rather than guessed.
          </p>
        </div>

        <div className="card p-4 border-l-2" style={{ borderLeftColor: RED }}>
          <div className="flex items-center gap-2 mb-1">
            <Icon icon="lucide:octagon-alert" width={14} className="text-[#ef4444]" />
            <h2 className="text-sm font-semibold text-[#ef4444]">Entry problem — separate</h2>
          </div>
          <p className="text-xs text-[#64748b] mb-3">
            Never reached +5 at all. Exit rules cannot fix this; it needs a different setup.
          </p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <Mini label="Trades" value={`${m.never_reached_5.count} (${m.never_reached_5.pct}%)`} />
            <Mini label="Avg pts" value={m.never_reached_5.avg_pnl.toFixed(2)} color={RED} />
            <Mini label="Total net" value={rs(m.never_reached_5.total_net)} color={RED} />
          </div>
        </div>
      </div>

      <div className="card p-4">
        <h2 className="text-sm font-semibold mb-1">How far each trade travelled in our favour</h2>
        <p className="text-xs text-[#64748b] mb-4">
          MFE = highest price reached before exit. {m.exact_count} trades measured exactly,{" "}
          {m.rung_count} inferred from the locked stop-loss rung, {m.mfe_unknown} unknown (manual
          exits) and excluded.
        </p>
        <div className="space-y-2">
          {m.histogram.map((h) => (
            <div key={h.bucket} className="flex items-center gap-3">
              <div className="w-28 text-xs text-[#94a3b8] shrink-0">{h.label}</div>
              <div className="flex-1 flex items-center gap-2">
                <div
                  className="h-5 rounded-sm"
                  style={{ width: `${(h.count / maxHist) * 100}%`, background: h.total_net >= 0 ? GREEN : RED, opacity: 0.75, minWidth: 4 }}
                />
                <span className="text-xs font-mono text-[#e2e8f0]">{h.count}</span>
                <span className="text-[10px] text-[#64748b]">({h.pct}%)</span>
              </div>
              <div className="w-44 text-right text-[10px] font-mono text-[#64748b] shrink-0">
                avg {h.avg_pnl.toFixed(2)} pts · giveback {h.avg_giveback.toFixed(1)} · {rs(h.total_net)}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="card p-4">
        <h2 className="text-sm font-semibold mb-3">Strategy comparison — same trades, different rules</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748b] border-b border-[rgba(255,255,255,0.06)]">
                <th className="text-left py-2 pr-3">Strategy</th>
                <th className="text-right py-2 pr-3">Trades</th>
                <th className="text-right py-2 pr-3">Skipped</th>
                <th className="text-right py-2 pr-3">Net ₹</th>
                <th className="text-right py-2 pr-3">Per day</th>
                <th className="text-right py-2">Win %</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((s) => {
                const isCurrent = s.key === "current";
                const best = !isCurrent && s.net_rupees === bestNet;
                return (
                  <tr key={s.key} className="border-b border-[rgba(255,255,255,0.04)]" style={{ background: best ? "rgba(16,185,129,0.07)" : undefined }}>
                    <td className="py-2 pr-3">
                      {s.label}
                      {best && <span className="ml-2 text-[9px] text-[#10b981] font-bold">BEST</span>}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono">{s.trades}</td>
                    <td className="py-2 pr-3 text-right font-mono text-[#64748b]">{s.skipped}</td>
                    <td className="py-2 pr-3 text-right font-mono" style={{ color: s.net_rupees >= 0 ? GREEN : RED }}>{rs(s.net_rupees)}</td>
                    <td className="py-2 pr-3 text-right font-mono text-[#94a3b8]">{rs(s.per_day)}</td>
                    <td className="py-2 text-right font-mono text-[#94a3b8]">{s.win_rate}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="text-[10px] text-[#64748b] mt-3 leading-relaxed">
          Note: &quot;Hard TP +5 on every trade&quot; is the trap. It looks safe but wipes out the
          runners that reached +10 to +30, which is most of the profit. The staged rule keeps them.
        </p>
      </div>

      <div className="card p-4">
        <h2 className="text-sm font-semibold mb-1">Day-stop threshold sweep</h2>
        <p className="text-xs text-[#64748b] mb-4">
          If the result jumps around between neighbouring thresholds, the exact number is noise —
          trust the shape, not the peak.
        </p>
        <div className="flex items-end gap-1.5 h-32">
          {sweep.map((s) => {
            const label = s.day_stop_at === null ? "none" : `+${s.day_stop_at}`;
            const h = (Math.abs(s.net_rupees) / maxSweep) * 100;
            return (
              <div key={label} className="flex-1 flex flex-col items-center justify-end gap-1">
                <span className="text-[9px] font-mono text-[#94a3b8]">{rs(s.net_rupees)}</span>
                <div className="w-full rounded-t-sm" style={{ height: `${h}%`, minHeight: 3, background: s.net_rupees >= 0 ? INDIGO : RED, opacity: 0.8 }} />
                <span className="text-[9px] text-[#64748b]">{label}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div className="card p-4">
        <h2 className="text-sm font-semibold mb-3">Out-of-sample check — month by month</h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[#64748b] border-b border-[rgba(255,255,255,0.06)]">
              <th className="text-left py-2 pr-3">Month</th>
              <th className="text-right py-2 pr-3">Trades</th>
              <th className="text-right py-2 pr-3">Actual</th>
              <th className="text-right py-2 pr-3">Smart</th>
              <th className="text-right py-2">Δ</th>
            </tr>
          </thead>
          <tbody>
            {report.monthly.map((x) => (
              <tr key={x.month} className="border-b border-[rgba(255,255,255,0.04)]">
                <td className="py-2 pr-3 font-mono">{x.month}</td>
                <td className="py-2 pr-3 text-right font-mono text-[#94a3b8]">{x.trades}</td>
                <td className="py-2 pr-3 text-right font-mono" style={{ color: x.actual_net >= 0 ? GREEN : RED }}>{rs(x.actual_net)}</td>
                <td className="py-2 pr-3 text-right font-mono" style={{ color: x.smart_net >= 0 ? GREEN : RED }}>{rs(x.smart_net)}</td>
                <td className="py-2 text-right font-mono font-semibold" style={{ color: x.delta_net >= 0 ? GREEN : RED }}>{rs(x.delta_net)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card p-4">
        <h2 className="text-sm font-semibold mb-1">Day by day (most recent 14)</h2>
        <p className="text-xs text-[#64748b] mb-4">Actual day result vs what the smarter rules would have produced.</p>
        <div className="space-y-1.5">
          {recentDays.map((d) => (
            <div key={d.date} className="flex items-center gap-3 text-xs">
              <div className="w-20 font-mono text-[#94a3b8] shrink-0">{d.date}</div>
              <div className="w-14 text-[#64748b] shrink-0">{d.trades_taken}/{d.trades_actual} trades</div>
              <div className="w-16 text-right font-mono shrink-0" style={{ color: (d.actual_net ?? 0) >= 0 ? GREEN : RED }}>{rs(d.actual_net)}</div>
              <Icon icon="lucide:arrow-right" width={11} className="text-[#475569] shrink-0" />
              <div className="w-16 text-right font-mono shrink-0" style={{ color: (d.smart_net ?? 0) >= 0 ? GREEN : RED }}>{rs(d.smart_net)}</div>
              <div className="flex-1 flex items-center gap-2">
                <div
                  className="h-1.5 rounded-sm"
                  style={{ width: `${(Math.abs(d.delta_net) / bestDay) * 100}%`, background: d.delta_net >= 0 ? GREEN : RED, opacity: 0.8, minWidth: d.delta_net === 0 ? 0 : 3 }}
                />
                <span className="text-[10px] font-mono shrink-0" style={{ color: d.delta_net >= 0 ? GREEN : RED }}>{rs(d.delta_net)}</span>
                {d.stopped_early && <span className="text-[9px] text-[#6366f1] font-bold shrink-0">STOPPED EARLY</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Card({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="card p-3">
      <div className="text-[9px] uppercase tracking-widest text-[#64748b] font-bold">{label}</div>
      <div className="text-xl font-bold font-mono mt-1" style={{ color: color ?? "#e2e8f0" }}>{value}</div>
      {sub && <div className="text-[10px] text-[#64748b] mt-0.5">{sub}</div>}
    </div>
  );
}

function Mini({
  label,
  value,
  color,
  sub,
}: {
  label: string;
  value: string;
  color?: string;
  /** Small qualifier under the value - e.g. how many trades it covers. */
  sub?: string;
}) {
  return (
    <div className="bg-[rgba(255,255,255,0.03)] rounded p-2">
      <div className="text-[9px] uppercase text-[#64748b] font-bold">{label}</div>
      <div className="text-sm font-bold font-mono mt-0.5" style={{ color: color ?? "#e2e8f0" }}>{value}</div>
      {sub && <div className="text-[9px] text-[#64748b] mt-0.5 leading-tight">{sub}</div>}
    </div>
  );
}

function NumField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label className="block">
      <span className="text-[9px] uppercase tracking-widest text-[#64748b] font-bold block mb-1">{label}</span>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="bg-[#0a0a0a] border border-white/10 rounded px-2 py-1 text-sm font-mono text-white w-24 focus:outline-none focus:border-indigo-500"
      />
    </label>
  );
}

/**
 * Per-trade evidence for the replayed verdict. Deliberately plain data, no
 * chart: the point is that every number here can be re-checked by hand against
 * the tick indices shown in the last column.
 */
function ReplayTable({ rows }: { rows: SmartPnlReport["replay_verdict"]["rows"] }) {
  return (
    <>
      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-[#64748b]">
            <th className="text-left py-1 pr-2 font-medium">date</th>
            <th className="text-left py-1 pr-2 font-medium">symbol</th>
            <th className="text-right py-1 pr-2 font-medium">peak</th>
            <th className="text-right py-1 pr-2 font-medium">dips</th>
            <th className="text-right py-1 pr-2 font-medium">live</th>
            <th className="text-right py-1 pr-2 font-medium">sim</th>
            <th className="text-right py-1 pr-2 font-medium">&Delta;</th>
            <th className="text-left py-1 pr-2 font-medium">verdict</th>
            <th className="text-left py-1 font-medium">replay evidence</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {rows.map((r) => {
            const e = r.evidence;
            const tone =
              r.verdict === "helped" ? GREEN : r.verdict === "hurt" ? RED : SLATE;
            return (
              <tr key={r.id ?? r.entry_time} className="border-t border-white/5">
                <td className="py-1 pr-2 text-[#94a3b8]">{r.date}</td>
                <td className="py-1 pr-2 text-[#e2e8f0]">{r.symbol}</td>
                <td className="py-1 pr-2 text-right text-[#94a3b8]">
                  +{(r.mfe_points ?? 0).toFixed(1)}
                </td>
                <td
                  className="py-1 pr-2 text-right"
                  style={{ color: (r.dips ?? 0) > 0 ? AMBER : SLATE }}
                >
                  {r.dips ?? "—"}
                </td>
                <td className="py-1 pr-2 text-right text-[#e2e8f0]">
                  {r.actual_points != null ? r.actual_points.toFixed(2) : "—"}
                </td>
                <td className="py-1 pr-2 text-right text-[#e2e8f0]">
                  {r.sim_points != null ? r.sim_points.toFixed(2) : "—"}
                </td>
                <td
                  className="py-1 pr-2 text-right font-semibold"
                  style={{ color: (r.delta_points ?? 0) >= 0 ? GREEN : RED }}
                >
                  {r.delta_points != null
                    ? `${r.delta_points >= 0 ? "+" : ""}${r.delta_points.toFixed(2)}`
                    : "—"}
                </td>
                <td className="py-1 pr-2" style={{ color: tone }}>
                  {r.verdict.toUpperCase()}
                </td>
                <td className="py-1 text-[9px] text-[#64748b]">
                  {e
                    ? `${e.ticks} ticks · armed @${e.armed_at_tick} · fired @${
                        e.fired_at_tick
                      } @${e.exit_price ?? "—"}`
                    : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[10px] text-[#64748b] mt-2 leading-relaxed">
        Evidence column: how many ticks were recorded, which tick armed the +5 stop, and which tick it
        fired on. A row marked <b style={{ color: RED }}>HURT</b> means the real exit beat the
        hypothetical stop — the replayed loss is booked in full, exactly like a win is. Both sides count,
        so the total below is a real net rather than a best case.
      </p>
    </>
  );
}
