"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { fetchTrades, deleteTrade, fetchSmartPnl } from "../lib/api";
import TradePathChart from "./TradePathChart";
import type { TradeEntry, SmartTrade } from "../lib/types";

type RowInfo = {
  smartNet: number | null;
  deltaNet: number | null;
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
              title="Is trade me stop +5 pe park hota to kya net book hota. Real recorded ticks pe replay kiya hua."
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
            // Smart book: what net would this trade have booked with a stop
            // parked at +5, replayed over real recorded ticks.
            // - helped/hurt rules have a real smart_net -> show it
            // - same-effect rules -> "same" (rule changed nothing)
            // - guess rows (no tick path) -> dash, never a guess
            const rule = m?.rule ?? "";
            const changed =
              rule === "stopped_at_rung" ||
              rule === "replayed_help" ||
              rule === "replayed_hurt";
            const sameEffect =
              rule === "survived" ||
              rule === "untouched" ||
              rule === "trailed" ||
              rule === "replayed_same" ||
              rule === "current";
            const smartVal = changed ? m?.smartNet ?? null : null;
            const d = m?.deltaNet;
            const tone =
              smartVal == null || d == null
                ? "#64748b"
                : d > 0.5
                  ? "#10b981"
                  : d < -0.5
                    ? "#ef4444"
                    : "#64748b";
            return (
            <tr
              key={t.id ?? i}
              className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] group"
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
              {/* ---- smart book: bas ek number ---- */}
              <td
                className="py-2 pr-3 text-right font-mono font-semibold border-l border-white/10"
                style={{ color: tone }}
                title="Stop +5 pe park hota to ye net book hota. Real ticks pe replay kiya hua."
              >
                {smartVal != null ? (
                  `${smartVal >= 0 ? "+" : "-"}₹${Math.abs(smartVal).toFixed(0)}`
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
                  title="Draw the real entry-to-exit tick path, with a stop parked at +5 replayed over it"
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
