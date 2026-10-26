"use client";

import { useCallback, useEffect, useState } from "react";
import TradeCalendar from "../components/TradeCalendar";
import TradeLogsTable from "../components/TradeLogsTable";
import { fetchTradeStats, fetchExitRules } from "../lib/api";
import type { TradeStats, RuleBook } from "../lib/types";

export default function HistoryPage() {
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [refreshKey, setRefreshKey] = useState(0);
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [book, setBook] = useState<RuleBook | null>(null);

  useEffect(() => {
    fetchTradeStats(year)
      .then(setStats)
      .catch(() => setStats(null));
    fetchExitRules(year)
      .then((r) => setBook(r.rule_book))
      .catch(() => setBook(null));
  }, [year, refreshKey]);

  const handleTradeDeleted = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold">Trade History</h1>

      {/* Rule book strip: the live bank-first ladder's own ledger, replayed
          over every settled trade. On archive rows this is the would-have
          study the rule switch rested on; once post-switch trades accrue it
          doubles as the live mirror. The comparison against the as-traded
          book sits in the sub line. */}
      <div
        className="card p-4 border-l-4"
        style={{ borderLeftColor: book && book.net_rupees >= 0 ? "#10b981" : "#ef4444" }}
      >
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-xs text-[#64748b] uppercase tracking-wider">
              Rule book · first rung banks +{book?.bank_at ?? "—"}, then every +5
            </div>
            <div
              className="text-3xl font-mono font-semibold mt-1"
              style={{ color: book && book.net_rupees >= 0 ? "#10b981" : "#ef4444" }}
            >
              {book ? formatRs(book.net_rupees) : "—"}
            </div>
            <div className="text-[0.65rem] text-[#64748b] mt-1">
              {book
                ? `bank-first replay over ${book.trades} trades vs actual ${formatRs(book.actual_net_rupees)} · gap ${formatRs(book.delta_net)} on ${book.delta_points >= 0 ? "+" : ""}${book.delta_points} pts`
                : "…"}
            </div>
          </div>
        </div>
      </div>

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
