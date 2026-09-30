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
  const maxHist = Math.max(...m.histogram.map((h) => h.count), 1);
  const maxSweep = Math.max(...sweep.map((s) => Math.abs(s.net_rupees)), 1);
  const bestDay = Math.max(...report.days.map((d) => Math.abs(d.delta_net)), 1);
  const recentDays = [...report.days].reverse().slice(0, 14);
  const bestNet = Math.max(...strategies.map((s) => s.net_rupees));

  return (
    <div className="max-w-6xl mx-auto space-y-5 pb-24">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">MFE &amp; Smart P&amp;L Report</h1>
          <p className="text-xs text-[#64748b] mt-1">
            Shadow analysis — how each day would have looked with different exit rules.
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
        <Card label="Improvement" value={rs(report.delta_net)} sub={`${rs(report.per_day_delta)} per day`} color={report.delta_net >= 0 ? GREEN : RED} />
        <Card label="Win rate" value={`${report.summary.win_rate}%`} sub={`was ${report.baseline.win_rate}%`} color={INDIGO} />
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
            Reached +5, gave it all back to scratch. This is what the staged rule targets.
          </p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <Mini label="Trades" value={String(m.leak.count)} />
            <Mini label="Actual" value={rs(m.leak.actual_net)} color={m.leak.actual_net >= 0 ? GREEN : RED} />
            <Mini label="Recoverable" value={rs(m.leak.recoverable)} color={m.leak.recoverable >= 0 ? GREEN : RED} />
          </div>
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

function Mini({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-[rgba(255,255,255,0.03)] rounded p-2">
      <div className="text-[9px] uppercase text-[#64748b] font-bold">{label}</div>
      <div className="text-sm font-bold font-mono mt-0.5" style={{ color: color ?? "#e2e8f0" }}>{value}</div>
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
