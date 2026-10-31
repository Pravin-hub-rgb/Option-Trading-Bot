"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { fetchTrades, deleteTrade, fetchExitRules } from "../lib/api";
import TradePathChart from "./TradePathChart";
import type { TradeEntry, ExitRulesTrade } from "../lib/types";

type RowInfo = {
  rulePnl: number | null;
  ruleNet: number | null;
  ruleProof: ExitRulesTrade["proof"];
  mfePoints: number | null;
};

export default function TradeLogsTable({
  year,
  onDeleted,
  breakevenTolerance,
  refreshKey,
  bankAt,
}: {
  year: number;
  onDeleted: () => void;
  breakevenTolerance: number;
  refreshKey: number;
  bankAt: number;
}) {
  const [trades, setTrades] = useState<TradeEntry[]>([]);
  const [info, setInfo] = useState<Record<number, RowInfo>>({});
  const [openPath, setOpenPath] = useState<number | null>(null);
  const pathTrade = trades.find((t) => t.id === openPath) ?? null;
  useEffect(() => {
    fetchTrades(year)
      .then((res) => setTrades(res.trades))
      .catch(() => setTrades([]));
  }, [year, refreshKey]);

  useEffect(() => {
    fetchExitRules(year)
      .then((r) => {
        const map: Record<number, RowInfo> = {};
        for (const b of r.rule_book?.rows ?? []) {
          if (b.id === null) continue;
          map[b.id] = {
            rulePnl: b.rule_pnl ?? null,
            ruleNet: b.rule_net ?? null,
            ruleProof: b.proof,
            mfePoints: b.mfe_points ?? null,
          };
        }
        setInfo(map);
      })
      .catch(() => setInfo({}));
  }, [year, refreshKey]);

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
            <th className="py-2 w-8">
              <span className="sr-only">Show price path</span>
            </th>
            <th className="py-2 w-6"></th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => {
            const m = t.id != null ? info[t.id] : undefined;
            // Bank-first results: where the counterfactual is reliable (tick
            // = replayed over real ticks, crossing = stop provably fired,
            // live = rule didn't change the exit) we show the measured rule
            // P&L/Net. For "assumed" trades (no tick path) we can't replay the
            // ladder, BUT if MFE crossed the first bank rung (+bankAt) the engine
            // would have banked that band - so we show +bankAt as the conservative
            // floor. If MFE never reached the bank rung, show "—".
            const bankUnknown = m?.ruleProof === "assumed";
            const bankedFloor =
              bankUnknown && m?.mfePoints != null && m.mfePoints >= bankAt;
            const pp =
              t.pnl != null &&
              t.pnl !== 0 &&
              t.net_pnl != null &&
              t.charges != null
                ? (t.net_pnl + t.charges) / t.pnl
                : null;
            const displayPnl = bankedFloor
              ? bankAt
              : bankUnknown
                ? null
                : m?.rulePnl ?? t.pnl;
            const displayNet =
              bankedFloor && pp != null && t.charges != null
                ? bankAt * pp - t.charges
                : bankUnknown
                  ? null
                  : m?.ruleNet ?? t.net_pnl;
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
                title={
                  bankedFloor
                    ? `No tick path — MFE reached +${bankAt}, banked at first rung`
                    : bankUnknown
                      ? `No tick path — MFE ${m?.mfePoints != null ? `(${m.mfePoints} pts)` : ""} below +${bankAt}, exit unknowable`
                      : m?.ruleProof === "crossing"
                        ? "Bank stepped on the SL band — exit assumed at first rung"
                        : undefined
                }
                style={{
                  color:
                    displayPnl !== null
                      ? displayPnl > breakevenTolerance
                        ? "#10b981"
                        : displayPnl < -breakevenTolerance
                          ? "#ef4444"
                          : "#f59e0b"
                      : "#64748b",
                }}
              >
                {displayPnl !== null ? `${displayPnl >= 0 ? "+" : ""}${displayPnl.toFixed(2)}` : "—"}
              </td>
              <td
                className="py-2 pr-3 text-right font-mono"
                title={
                  bankedFloor
                    ? `No tick path — MFE reached +${bankAt}, banked at first rung`
                    : bankUnknown
                      ? `No tick path — MFE ${m?.mfePoints != null ? `(${m.mfePoints} pts)` : ""} below +${bankAt}, exit unknowable`
                      : m?.ruleProof === "crossing"
                        ? "Bank stepped on the SL band — exit assumed at first rung"
                        : undefined
                }
                style={{
                  color:
                    displayNet !== null && displayNet !== undefined
                      ? displayNet >= 0
                        ? "#10b981"
                        : "#ef4444"
                      : "#64748b",
                }}
              >
                {displayNet !== null && displayNet !== undefined
                  ? `${displayNet >= 0 ? "+" : "-"}₹${Math.abs(displayNet).toFixed(2)}`
                  : "—"}
              </td>
              <td className="py-2 pr-3 text-right font-mono text-[#64748b]">
                {t.charges !== null && t.charges !== undefined ? `₹${t.charges.toFixed(2)}` : "—"}
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
