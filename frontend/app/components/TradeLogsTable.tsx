"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { fetchTrades, deleteTrade, fetchSmartPnl } from "../lib/api";
import TradePathChart from "./TradePathChart";
import type { TradeEntry, SmartTrade } from "../lib/types";

type RowInfo = {
  deltaNet: number | null;
  smartNet: number | null;
  proof: SmartTrade["proof"];
  rule: string;
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
  // Which trade has its price-path chart expanded, if any.
  const [openPath, setOpenPath] = useState<number | null>(null);
  const pathTrade = trades.find((t) => t.id === openPath) ?? null;
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
            deltaNet: t.delta_net,
            smartNet: t.smart_net,
            proof: t.proof,
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

  /**
   * What the strike selector paid for this option, versus what we actually
   * filled at. The selector runs once at the open; the entry only fires on a
   * breakout, which can be minutes later, so these two drift apart. Until
   * selection was being persisted this existed only as a console line.
   */
  function selectionNote(t: TradeEntry): string | null {
    if (t.sel_premium == null || t.entry_price == null) return null;
    const drift = t.entry_price - t.sel_premium;
    const mins = t.sel_at && t.entry_time
      ? Math.round(
          (new Date(t.entry_time.replace(" ", "T")).getTime() -
            new Date(t.sel_at.replace(" ", "T")).getTime()) /
            60000,
        )
      : null;
    const tier = t.sel_tier != null ? ` (basket ≥₹${t.sel_tier})` : "";
    const when = mins != null ? ` in ${mins} min` : "";
    return `Selected at ${t.sel_at?.slice(11, 16)} for ₹${t.sel_premium.toFixed(2)}${tier}, filled ₹${t.entry_price.toFixed(2)}${when} — drifted ${drift >= 0 ? "+" : ""}${drift.toFixed(2)} points.`;
  }

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
      <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[#64748b] border-b border-[rgba(255,255,255,0.06)]">
            <th className="text-left py-2 pr-3">#</th>
            <th className="text-left py-2 pr-3">Date</th>
            <th className="text-left py-2 pr-3">Time</th>
            <th className="text-left py-2 pr-3">Symbol</th>
            <th className="text-right py-2 pr-3">Entry</th>
            <th className="text-right py-2 pr-3">Exit</th>
            <th className="text-right py-2 pr-3">P&amp;L</th>
            <th className="text-right py-2 pr-3">Net</th>
            <th className="text-right py-2 pr-3">Fees</th>
            <th
              className="text-right py-2 pr-3 border-l border-white/10"
              style={{ color: "#818cf8" }}
              title="What a trailing ladder (pehla rung +5, phir +5 steps) would have BANKED on this trade, replayed over the real recorded ticks. Compare it against the Net column. The small figure underneath is the difference against what we actually banked — red means the rule would have lost money here."
            >
              Smart&nbsp;book
            </th>
            <th className="py-2 w-8">
              <span className="sr-only">Show price path</span>
            </th>
            <th className="py-2 w-6"></th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => {
            const m = t.id != null ? info[t.id] : undefined;
            // Smart book: what the trailing ladder (first rung +5, then +5 steps) would
            // have BANKED on this trade, replayed over the real recorded ticks.
            //
            // The big number is the counterfactual's own net, not a difference,
            // so it reads directly against the Net column beside it. The small
            // figure underneath is the delta against what we actually banked -
            // that is the part that says whether switching would help or hurt.
            //
            // Rows are split by how solid the counterfactual is, because they
            // are NOT equally trustworthy:
            //   tick      replayed on real recorded ticks - trust it
            //   crossing  the stop provably fired, but WHERE it filled is an
            //             assumption (first rung less the exit buffer), so it is
            //             drawn dimmed and italic rather than as a hard number
            //   live      the rule provably changed nothing - nothing to show
            //   assumed   not provable at all - no claim is made
            const rule = m?.rule ?? "";
            const d = m?.deltaNet;
            const moved = d != null && Math.abs(d) > 0.5;
            // No rule info at all, or the rule provably changed nothing.
            const sameEffect =
              !moved &&
              (rule === "" ||
                rule === "survived" ||
                rule === "untouched" ||
                rule === "unknown-mfe" ||
                rule === "ladder_same" ||
                rule === "ladder_help" ||
                rule === "ladder_hurt" ||
                rule === "confirmed_same" ||
                rule === "confirmed_help" ||
                rule === "confirmed_hurt" ||
                rule === "current");
            const tone = !moved ? "#64748b" : d > 0 ? "#10b981" : "#ef4444";
            // A real counterfactual exists only for tick / crossing rows. For
            // the other two smartNet just mirrors actual, so printing it would
            // duplicate the Net column and read as though the rule had a view.
            const hasCounterfactual =
              m != null &&
              m.smartNet != null &&
              (m.proof === "tick" || m.proof === "crossing");
            const inferred = m?.proof === "crossing";
            const smartTone =
              m?.smartNet == null || m.smartNet === 0
                ? "#64748b"
                : m.smartNet > 0
                  ? "#10b981"
                  : "#ef4444";
            return (
            <tr
              key={t.id ?? i}
              className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] group"
            >
              <td className="py-2 pr-3 font-mono text-[#475569]">{t.id ?? "—"}</td>
              <td className="py-2 pr-3">{formatDate(t.entry_time)}</td>
              <td className="py-2 pr-3 font-mono">{t.entry_time?.slice(11, 19)}</td>
              <td className="py-2 pr-3 font-mono">{t.symbol}</td>
              <td
                className="py-2 pr-3 text-right font-mono"
                title={selectionNote(t) ?? undefined}
              >
                {t.entry_price?.toFixed(2)}
              </td>
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
              {/* ---- smart book: what the +5 ladder would have banked ---- */}
              <td
                className="py-2 pr-3 text-right font-mono font-semibold border-l border-white/10"
                style={{ color: hasCounterfactual ? smartTone : tone }}
                title={
                  hasCounterfactual
                    ? inferred
                      ? `Trailing ladder would have netted Rs ${m?.smartNet?.toFixed(2)} vs the Rs ${t.net_pnl?.toFixed(2)} we actually banked — a difference of ${d != null && d < 0 ? "-" : "+"}Rs ${Math.abs(d ?? 0).toFixed(0)}. ESTIMATED: the stop provably fired, but exactly where it filled is an assumption, so this is a close estimate, not a measurement.`
                      : `Trailing ladder would have netted Rs ${m?.smartNet?.toFixed(2)} vs the Rs ${t.net_pnl?.toFixed(2)} we actually banked — a difference of ${d != null && d < 0 ? "-" : "+"}Rs ${Math.abs(d ?? 0).toFixed(0)}. Replayed tick by tick over the prices the bot actually received.`
                    : m?.proof === "assumed"
                      ? "No counterfactual is possible for this trade: without a recorded price path there is nothing to replay, and the peak does not prove where the stop would have filled."
                      : "The trailing ladder provably would not have changed this exit."
                }
              >
                {hasCounterfactual && m?.smartNet != null ? (
                  <div className="leading-tight">
                    <div className={inferred ? "italic opacity-60" : undefined}>
                      {m.smartNet >= 0 ? "+" : "-"}₹{Math.abs(m.smartNet).toFixed(0)}
                    </div>
                    {moved && d != null && (
                      <div className="text-[9px] font-normal" style={{ color: tone }}>
                        {d >= 0 ? "+" : "-"}₹{Math.abs(d).toFixed(0)}
                      </div>
                    )}
                  </div>
                ) : m?.proof === "assumed" ? (
                  <span className="font-normal">—</span>
                ) : sameEffect ? (
                  <span className="font-normal">same</span>
                ) : (
                  <span className="font-normal">—</span>
                )}
              </td>
              <td className="py-2">
                <button
                  onClick={() => setOpenPath(openPath === t.id ? null : t.id)}
                  className="text-[#64748b] hover:text-[#818cf8] transition-colors"
                  title="Draw the real entry-to-exit tick path, with the trailing +5 ladder replayed over it"
                >
                  <Icon
                    icon={openPath === t.id ? "lucide:chevron-down" : "lucide:line-chart"}
                    width={14}
                  />
                </button>
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

        {openPath != null && pathTrade && (
          <div className="px-3 py-4 border-t border-white/10 bg-black/20">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-[#e2e8f0] flex items-center gap-2">
                <Icon icon="lucide:line-chart" width={14} className="text-[#818cf8]" />
                {pathTrade.symbol} · {pathTrade.entry_time.slice(0, 19)}
              </h3>
              <button
                onClick={() => setOpenPath(null)}
                className="text-[#64748b] hover:text-white"
                title="Close"
              >
                <Icon icon="lucide:x" width={14} />
              </button>
            </div>
            <TradePathChart tradeId={openPath} />
          </div>
        )}
      </div>
    </div>
  );
}
