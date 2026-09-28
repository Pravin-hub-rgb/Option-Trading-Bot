"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { fetchTrades, deleteTrade, fetchSmartPnl } from "../lib/api";
import type { TradeEntry, SmartTrade } from "../lib/types";

type RowInfo = {
  mfe: number | null;
  giveback: number | null;
  source: string | null;
  smartPnl: number | null;
  smartNet: number | null;
  deltaNet: number | null;
  rule: string;
};

const RULE_TEXT: Record<string, { label: string; tone: string; help: string }> = {
  banked: { label: "stop at +5", tone: "#10b981", help: "This trade reached +5 but never got past +10, so it slid back down. With the new first rung the stop would have been parked at +5, so the exit would have happened in profit instead of at scratch." },
  trailed: { label: "no change", tone: "#64748b", help: "The trade ran past +10, where the ladder rungs are unchanged - the new rule does not touch it." },
  untouched: { label: "no change", tone: "#64748b", help: "Price never got near +5, so the first rung was never reached. The initial stop would have hit either way - no exit rule can help here." },
  skipped: { label: "not taken", tone: "#6366f1", help: "Day-stop simulation: an earlier trade had already hit the day's target, so this one would never have been opened." },
  "unknown-mfe": { label: "unknown", tone: "#475569", help: "Manual exit - we never tracked how far this trade went, so no comparison is possible." },
  current: { label: "no change", tone: "#64748b", help: "Baseline row." },
  unsettled: { label: "open", tone: "#475569", help: "Trade has not closed yet." },
};

export default function TradeLogsTable({
  year,
  onDeleted,
  breakevenTolerance,
}: {
  year: number;
  onDeleted: () => void;
  breakevenTolerance: number;
}) {
  const [trades, setTrades] = useState<TradeEntry[]>([]);
  const [info, setInfo] = useState<Record<number, RowInfo>>({});
  const [showHelp, setShowHelp] = useState(true);
  useEffect(() => {
    fetchTrades(year)
      .then((res) => setTrades(res.trades))
      .catch(() => setTrades([]));
  }, [year]);

  useEffect(() => {
    fetchSmartPnl(year)
      .then((r) => {
        const map: Record<number, RowInfo> = {};
        for (const t of r.trades as SmartTrade[]) {
          if (t.id === null) continue;
          map[t.id] = {
            mfe: t.mfe_points,
            giveback: t.giveback_points,
            source: t.mfe_source,
            smartPnl: t.smart_pnl,
            smartNet: t.smart_net,
            deltaNet: t.delta_net,
            rule: t.rule_fired,
          };
        }
        setInfo(map);
      })
      .catch(() => setInfo({}));
  }, [year]);

  async function handleDelete(id: number) {
    try {
      const res = await deleteTrade(id);
      if (res.status === "deleted") {
        setTrades((prev) => prev.filter((t) => t.id !== id));
        onDeleted();
      }
    } catch {
      // silently ignore
    }
  }

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const legend = (
    <div className="mb-3 border border-white/10 rounded bg-[rgba(255,255,255,0.02)]">
      <button
        onClick={() => setShowHelp((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left"
      >
        <span className="text-xs font-semibold text-[#e2e8f0] flex items-center gap-2">
          <Icon icon="lucide:circle-help" width={14} className="text-indigo-400" />
          What do these columns mean?
        </span>
        <Icon icon={showHelp ? "lucide:chevron-up" : "lucide:chevron-down"} width={14} className="text-[#64748b]" />
      </button>
      {showHelp && (
        <div className="px-3 pb-3 text-[11px] text-[#94a3b8] leading-relaxed space-y-2">
          <p>
            <b className="text-white">Peak (MFE)</b> = the highest price this trade ever reached while it was
            open, measured in points above entry. It answers: <i>&quot;how good did this trade get before it
            ended?&quot;</i> Every trade has one, whether it ended in profit or loss.
          </p>
          <p>
            <b className="text-white">Gave back</b> = Peak minus what we actually banked. If a trade peaked at
            +9 but closed at +0.9, it gave back 8.1 points — that is recoverable profit we left on the table.
          </p>
          <p>
            <b className="text-white">The rule</b> columns are a simulation, not live behaviour. The rule
            under test is: <i>when a trade first reaches +5, move the stop-loss up to +5 instead of +1.</i>{" "}
            Higher rungs are unchanged, so a trade that runs past +10 is left completely alone. It is a
            stop-loss change, not a take-profit — a trade can still be stopped out at -4. The bot&apos;s real
            setting is <span className="font-mono text-white">First SL Rung / Bank At</span> in Settings → Risk.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 pt-1">
            {Object.entries(RULE_TEXT).filter(([k]) => k !== "current" && k !== "unsettled").map(([k, v]) => (
              <div key={k} className="flex gap-1.5">
                <span className="font-mono font-bold shrink-0" style={{ color: v.tone }}>{v.label}</span>
                <span className="text-[#64748b]">— {v.help}</span>
              </div>
            ))}
          </div>
          <p className="text-[#475569] pt-1">
            Trades logged before today show a <span className="font-mono">~</span> before the peak: for those the
            exact peak was never recorded, so it is estimated from which stop-loss level was locked. Newer
            trades are exact.
          </p>
        </div>
      )}
    </div>
  );

  function formatDate(iso: string | undefined) {
    if (!iso) return "—";
    const [y, m, d] = iso.slice(0, 10).split("-");
    return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
  }

  if (trades.length === 0) {
    return <div className="text-sm text-[#64748b] py-4">No trades recorded</div>;
  }

  return (
    <div>
      {legend}
      <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[#475569] text-[9px] uppercase tracking-wider">
            <th colSpan={8} className="text-left py-1 pl-1 pr-3">What actually happened</th>
            <th colSpan={2} className="text-center py-1 px-3 border-l border-white/10" style={{ color: "#a78bfa" }}>
              How good did it get?
            </th>
            <th colSpan={3} className="text-center py-1 px-3 border-l border-white/10" style={{ color: "#818cf8" }}>
              The rule would have
            </th>
            <th className="py-1"></th>
          </tr>
          <tr className="text-[#64748b] border-b border-[rgba(255,255,255,0.06)]">
            <th className="text-left py-2 pr-3">Date</th>
            <th className="text-left py-2 pr-3">Time</th>
            <th className="text-left py-2 pr-3">Symbol</th>
            <th className="text-right py-2 pr-3">Entry</th>
            <th className="text-right py-2 pr-3">Exit</th>
            <th className="text-right py-2 pr-3">P&amp;L</th>
            <th className="text-right py-2 pr-3">Net</th>
            <th className="text-right py-2 pr-3">Fees</th>
            <th
              className="text-center py-2 px-3 border-l border-white/10"
              style={{ color: "#a78bfa" }}
              title="Highest price this trade ever reached, in points above entry"
            >
              Peak
            </th>
            <th
              className="text-right py-2 px-3"
              style={{ color: "#a78bfa" }}
              title="Peak minus what we actually banked — recoverable profit left on the table"
            >
              Gave&nbsp;back
            </th>
            <th className="text-center py-2 px-3 border-l border-white/10" style={{ color: "#818cf8" }}>Do</th>
            <th className="text-right py-2 px-3" style={{ color: "#818cf8" }} title="Exit price in points">Exit at</th>
            <th className="text-right py-2 pr-3" style={{ color: "#818cf8" }} title="Difference in net rupees">Worth</th>
            <th className="py-2"></th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => {
            const m = t.id != null ? info[t.id] : undefined;
            const inferred = m?.source === "rung";
            const rule = RULE_TEXT[m?.rule ?? "current"] ?? { label: m?.rule ?? "—", tone: "#64748b", help: "" };
            const banked = m?.rule === "banked";
            const skipped = m?.rule === "skipped";
            return (
            <tr
              key={t.id ?? i}
              className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] group"
              style={skipped ? { opacity: 0.55 } : undefined}
              title={rule.help}
            >
              <td className="py-2 pr-3">{formatDate(t.entry_time)}</td>
              <td className="py-2 pr-3 font-mono">{t.entry_time?.slice(11, 19)}</td>
              <td className="py-2 pr-3 font-mono">{t.symbol}</td>
              <td className="py-2 pr-3 text-right font-mono">{t.entry_price?.toFixed(2)}</td>
              <td className="py-2 pr-3 text-right font-mono">{t.exit_price?.toFixed(2) ?? "—"}</td>
              <td
                className="py-2 pr-3 text-right font-mono"
                style={{
                  color:
                    t.pnl !== null
                      ? t.pnl > breakevenTolerance
                        ? "#10b981"
                        : t.pnl < -breakevenTolerance
                          ? "#ef4444"
                          : "#f59e0b"
                      : "#64748b",
                }}
              >
                {t.pnl !== null ? `${t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}` : "—"}
              </td>
              <td
                className="py-2 pr-3 text-right font-mono"
                style={{
                  color:
                    t.net_pnl !== null && t.net_pnl !== undefined
                      ? t.net_pnl >= 0
                        ? "#10b981"
                        : "#ef4444"
                      : "#64748b",
                }}
              >
                {t.net_pnl !== null && t.net_pnl !== undefined
                  ? `${t.net_pnl >= 0 ? "+" : "-"}₹${Math.abs(t.net_pnl).toFixed(2)}`
                  : "—"}
              </td>
              <td className="py-2 pr-3 text-right font-mono text-[#64748b]">
                {t.charges !== null && t.charges !== undefined ? `₹${t.charges.toFixed(2)}` : "—"}
              </td>
              {/* ---- how good did it get ---- */}
              <td
                className="py-2 px-3 text-center font-mono border-l border-white/10"
                style={{ color: m?.mfe != null ? "#c084fc" : "#475569" }}
                title={
                  m?.source === "exact" && m.mfe != null
                    ? `Exact: this trade's highest price was ${m.mfe.toFixed(2)} points above entry`
                    : inferred
                      ? `Estimated: this trade reached at least ${m?.mfe ?? "?"} points, then fell back to here. Exact peak was not recorded for older trades.`
                      : "Not tracked - this was a manual exit, so we do not know how far it went"
                }
              >
                {m?.mfe != null ? `${inferred ? "~" : ""}${m.mfe.toFixed(m.mfe < 10 ? 2 : 1)}` : "—"}
              </td>
              <td
                className="py-2 px-3 text-right font-mono"
                style={{ color: m?.giveback != null && m.giveback >= 4 ? "#f59e0b" : "#64748b" }}
                title={
                  m?.giveback != null && m?.mfe != null
                    ? `It was ${m.mfe.toFixed(1)} up at best, but we closed with ${(t.pnl ?? 0).toFixed(2)}. That ${m.giveback.toFixed(1)} point difference was left on the table.`
                    : "No excursion data"
                }
              >
                {m?.giveback != null ? m.giveback.toFixed(1) : "—"}
              </td>

              {/* ---- what the rule would have done ---- */}
              <td className="py-2 px-3 text-center border-l border-white/10">
                <span
                  className="text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded"
                  style={{ color: rule.tone, background: `${rule.tone}1a` }}
                >
                  {rule.label}
                </span>
              </td>
              <td className="py-2 px-3 text-right font-mono" style={{ color: banked ? "#10b981" : "#475569" }}>
                {banked ? (
                  <span className="font-semibold">+{(m?.smartPnl ?? 0).toFixed(2)}</span>
                ) : skipped ? (
                  <span className="text-[#6366f1]">—</span>
                ) : (
                  <span className="text-[#475569]">—</span>
                )}
              </td>
              <td
                className="py-2 pr-3 text-right font-mono font-semibold"
                style={{
                  color:
                    m?.deltaNet == null
                      ? "#475569"
                      : m.deltaNet > 0.5
                        ? "#10b981"
                        : m.deltaNet < -0.5
                          ? "#ef4444"
                          : "#64748b",
                }}
              >
                {m?.deltaNet == null
                  ? "—"
                  : Math.abs(m.deltaNet) < 0.5
                    ? "same"
                    : `${m.deltaNet > 0 ? "+" : "-"}₹${Math.abs(m.deltaNet).toFixed(0)}`}
              </td>
              <td className="py-2">
                <button
                  onClick={() => handleDelete(t.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-[#64748b] hover:text-[#ef4444]"
                >
                  <Icon icon="lucide:trash-2" width={13} />
                </button>
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </div>
  );
}
