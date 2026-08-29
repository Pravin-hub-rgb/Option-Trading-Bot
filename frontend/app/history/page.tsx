"use client";

import { useCallback, useEffect, useState } from "react";
import TradeCalendar from "../components/TradeCalendar";
import TradeLogsTable from "../components/TradeLogsTable";
import { fetchTradeStats } from "../lib/api";
import type { TradeStats } from "../lib/types";

export default function HistoryPage() {
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [refreshKey, setRefreshKey] = useState(0);
  const [stats, setStats] = useState<TradeStats | null>(null);

  useEffect(() => {
    fetchTradeStats(year)
      .then(setStats)
      .catch(() => setStats(null));
  }, [year, refreshKey]);

  const handleTradeDeleted = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold">Trade History</h1>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-4 gap-3">
        <StatCard label="Total Trades" value={stats?.total_trades ?? "—"} />
        <StatCard label="Profitable" value={stats?.profitable ?? "—"} color="#10b981" />
        <StatCard label="Breakeven" value={stats?.breakeven ?? "—"} color="#f59e0b" />
        <StatCard label="Losing" value={stats?.losing ?? "—"} color="#ef4444" />
        <StatCard label="Win Rate" value={stats ? `${stats.win_rate}%` : "—"} color="#facc15" />
        <StatCard
          label="Net P&L"
          value={formatRs(stats?.net_total_pnl)}
          color={stats && stats.net_total_pnl !== undefined ? (stats.net_total_pnl >= 0 ? "#10b981" : "#ef4444") : "#64748b"}
          sub={stats?.gross_total_pnl !== undefined ? `gross ${formatRs(stats.gross_total_pnl, false)}` : undefined}
        />
        <StatCard label="Fees" value={formatRs(stats?.total_charges, false)} color="#94a3b8" />
        <StatCard label="Days Traded" value={stats?.days_traded ?? "—"} color="#6366f1" />
      </div>

      {/* Calendar */}
      <div className="card p-4">
        <TradeCalendar
          year={year}
          onYearChange={setYear}
          refreshKey={refreshKey}
          breakevenTolerance={stats?.breakeven_tolerance ?? 1}
        />
      </div>

      {/* Trade table */}
      <div className="card p-4">
        <TradeLogsTable
          year={year}
          onDeleted={handleTradeDeleted}
          breakevenTolerance={stats?.breakeven_tolerance ?? 1}
        />
      </div>
    </div>
  );
}

function formatRs(value?: number, signed = true) {
  if (value === undefined || value === null) return "—";
  const v = Math.abs(value);
  const sign = signed ? (value >= 0 ? "+" : "-") : "";
  return `${sign}₹${v.toFixed(2)}`;
}

function StatCard({
  label,
  value,
  color,
  sub,
}: {
  label: string;
  value: string | number;
  color?: string;
  sub?: string;
}) {
  return (
    <div className="card p-3 border-l-4" style={{ borderLeftColor: color || "#64748b" }}>
      <div className="text-xs text-[#64748b]">{label}</div>
      <div className="text-lg font-semibold font-mono mt-1" style={{ color: color || "#e5e7eb" }}>
        {value}
      </div>
      {sub && <div className="text-[0.6rem] text-[#64748b] mt-0.5">{sub}</div>}
    </div>
  );
}
