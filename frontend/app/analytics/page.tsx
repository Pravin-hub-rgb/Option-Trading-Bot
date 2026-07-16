"use client";

import { useEffect, useState } from "react";
import { fetchTradeStats } from "../lib/api";
import type { TradeStats } from "../lib/types";

export default function AnalyticsPage() {
  const [stats, setStats] = useState<TradeStats | null>(null);

  useEffect(() => {
    fetchTradeStats().then(setStats);
  }, []);

  const cards = [
    { label: "Total Trades", value: stats?.total_trades, color: "#64748b" },
    { label: "Win Rate", value: stats ? `${stats.win_rate}%` : "—", color: "#facc15" },
    { label: "Net P&L", value: stats ? fmtPnl(stats.total_pnl) : "—", color: stats ? (stats.total_pnl >= 0 ? "#10b981" : "#ef4444") : "#64748b" },
    { label: "Avg Win", value: stats ? fmtPnl(stats.avg_win) : "—", color: "#10b981" },
    { label: "Avg Loss", value: stats ? fmtPnl(stats.avg_loss) : "—", color: "#ef4444" },
    { label: "Largest Win", value: stats ? fmtPnl(stats.largest_win) : "—", color: "#10b981" },
    { label: "Largest Loss", value: stats ? fmtPnl(stats.largest_loss) : "—", color: "#ef4444" },
    { label: "Profitable", value: stats?.profitable, color: "#10b981" },
    { label: "Losing", value: stats?.losing, color: "#ef4444" },
    { label: "Unsettled", value: stats?.unsettled, color: "#64748b" },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold">Strategy Analytics</h1>

      <div className="grid grid-cols-5 gap-3">
        {cards.map((card) => (
          <div
            key={card.label}
            className="card p-3 border-l-4"
            style={{ borderLeftColor: card.color }}
          >
            <div className="text-xs text-[#64748b]">{card.label}</div>
            <div className="text-lg font-semibold font-mono mt-1" style={{ color: card.color }}>
              {card.value ?? "—"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function fmtPnl(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
}
