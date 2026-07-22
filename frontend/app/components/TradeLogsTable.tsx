"use client";

import { useEffect, useState } from "react";
import { fetchTrades } from "../lib/api";
import type { TradeEntry } from "../lib/types";

export default function TradeLogsTable() {
  const [trades, setTrades] = useState<TradeEntry[]>([]);

  useEffect(() => {
    fetchTrades().then((res) => setTrades(res.trades));
  }, []);

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function formatDate(iso: string | undefined) {
    if (!iso) return "—";
    const d = new Date(iso);
    return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
  }

  if (trades.length === 0) {
    return <div className="text-sm text-[#64748b] py-4">No trades recorded</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[#64748b] border-b border-[rgba(255,255,255,0.06)]">
            <th className="text-left py-2 pr-3">Date</th>
            <th className="text-left py-2 pr-3">Time</th>
            <th className="text-left py-2 pr-3">Symbol</th>
            <th className="text-right py-2 pr-3">Entry</th>
            <th className="text-right py-2 pr-3">Exit</th>
            <th className="text-right py-2 pr-3">P&L</th>
            <th className="text-left py-2 pr-3">Reason</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={i} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)]">
              <td className="py-2 pr-3">{formatDate(t.entry_time)}</td>
              <td className="py-2 pr-3 font-mono">{t.entry_time?.slice(11, 19)}</td>
              <td className="py-2 pr-3 font-mono">{t.symbol}</td>
              <td className="py-2 pr-3 text-right font-mono">{t.entry_price?.toFixed(2)}</td>
              <td className="py-2 pr-3 text-right font-mono">{t.exit_price?.toFixed(2) ?? "—"}</td>
              <td
                className="py-2 pr-3 text-right font-mono"
                style={{ color: t.pnl !== null ? (t.pnl >= 0 ? "#10b981" : "#ef4444") : "#64748b" }}
              >
                {t.pnl !== null ? `${t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}` : "—"}
              </td>
              <td className="py-2 pr-3 text-[#64748b]">{t.exit_reason || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
