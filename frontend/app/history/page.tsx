"use client";

import { useEffect, useState } from "react";
import TradeCalendar from "../components/TradeCalendar";
import TradeLogsTable from "../components/TradeLogsTable";
import { fetchTradeStats } from "../lib/api";
import type { TradeStats } from "../lib/types";

export default function HistoryPage() {
  const [stats, setStats] = useState<TradeStats | null>(null);

  useEffect(() => {
    fetchTradeStats().then(setStats);
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold">Trade History</h1>

      {/* Stats row */}
      <div className="grid grid-cols-5 gap-3">
        <StatCard label="Total Trades" value={stats?.total_trades ?? "—"} />
        <StatCard label="Profitable" value={stats?.profitable ?? "—"} color="#10b981" />
        <StatCard label="Losing" value={stats?.losing ?? "—"} color="#ef4444" />
        <StatCard label="Win Rate" value={stats ? `${stats.win_rate}%` : "—"} color="#facc15" />
        <StatCard
          label="Net P&L"
          value={stats ? `${stats.total_pnl >= 0 ? "+" : ""}${stats.total_pnl}` : "—"}
          color={stats ? (stats.total_pnl >= 0 ? "#10b981" : "#ef4444") : "#64748b"}
        />
      </div>

      {/* Calendar */}
      <div className="card p-4">
        <TradeCalendar />
      </div>

      {/* Trade table */}
      <div className="card p-4">
        <TradeLogsTable />
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="card p-3 border-l-4" style={{ borderLeftColor: color || "#64748b" }}>
      <div className="text-xs text-[#64748b]">{label}</div>
      <div className="text-lg font-semibold font-mono mt-1" style={{ color: color || "#e5e7eb" }}>
        {value}
      </div>
    </div>
  );
}
