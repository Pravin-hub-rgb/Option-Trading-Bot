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

  const tol = stats?.breakeven_tolerance ?? 1;
  // The books, bucketed with the same tolerance the stats row uses, so the
  // two engines can be read against each other without any tolerance drift.
  const bookRows = book?.rows ?? [];
  const bookProfitable = bookRows.filter((r) => (r.rule_pnl ?? 9) > tol).length;
  const bookBreakeven = bookRows.filter(
    (r) => Math.abs(r.rule_pnl ?? 9) <= tol,
  ).length;
  const bookLosing = bookRows.filter((r) => (r.rule_pnl ?? -9) < -tol).length;
  const bookWinRate = bookRows.length
    ? (Math.round((100 * bookProfitable) / bookRows.length * 10) / 10)
    : null;
  // The exact phenomenon the switch was for: breakeven exits that the ratchet
  // would have wrung a +5-band fill out of.
  const beConverted = bookRows.filter(
    (r) => Math.abs(r.actual_pnl ?? 9) <= tol && (r.rule_pnl ?? 0) > tol,
  ).length;
  const beTotal = bookRows.filter((r) => Math.abs(r.actual_pnl ?? 9) <= tol).length;
  const bookDays = new Set(bookRows.map((r) => r.date)).size;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold">Trade History</h1>

      {/* THE BOOKS. Same trades, two exit rules, side by side. The rule book
          (today's bank-first engine) is the default view; the retired engine's
          as-traded record sits beside it because those lost breakeven exits
          still happened and the comparison is the whole point. On archive rows
          the rule book is the would-have; once post-switch trades accrue it
          doubles as the live mirror and actual converges to it. */}
      <div className="card p-4">
        <div className="text-xs text-[#64748b] uppercase tracking-wider mb-3">
          The books · {book ? `${book.trades} trades, two exit rules` : "…"}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div
            className="card p-3 border-l-4"
            style={{ borderLeftColor: book && book.net_rupees >= 0 ? "#10b981" : "#ef4444" }}
          >
            <div className="text-xs text-[#10b981] font-semibold">Rule book · today&apos;s engine</div>
            <div
              className="text-3xl font-mono font-semibold mt-1"
              style={{ color: book && book.net_rupees >= 0 ? "#10b981" : "#ef4444" }}
            >
              {book ? formatRs(book.net_rupees) : "—"}
            </div>
            <div className="text-[0.65rem] text-[#64748b] mt-1">
              {book
                ? `bank-first · first rung banks +${book.bank_at}, then every +5 · ${bookProfitable} profitable / ${bookBreakeven} BE / ${bookLosing} L · ${bookWinRate ?? "—"}% win · ${book.gross_points >= 0 ? "+" : ""}${book.gross_points} pts`
                : "…"}
            </div>
          </div>
          <div className="card p-3 border-l-4" style={{ borderLeftColor: "#64748b" }}>
            <div className="text-xs text-[#64748b] font-semibold">Retired engine · as-traded</div>
            <div className="text-3xl font-mono font-semibold mt-1 text-[#94a3b8]">
              {book ? formatRs(book.actual_net_rupees) : "—"}
            </div>
            <div className="text-[0.65rem] text-[#64748b] mt-1">
              {book
                ? `first rung +1 · ${stats?.profitable ?? "—"} profitable / ${stats?.breakeven ?? "—"} BE / ${stats?.losing ?? "—"} L · ${stats?.win_rate ?? "—"}% win · ${book.actual_gross_points >= 0 ? "+" : ""}${book.actual_gross_points} pts`
                : "…"}
            </div>
          </div>
        </div>
        <div className="mt-3 text-[0.65rem] text-[#64748b]">
          {book
            ? `the gap the switch closes: ${formatRs(book.delta_net)} on ${book.delta_points >= 0 ? "+" : ""}${book.delta_points} pts${beTotal ? ` · ${beConverted} of the ${beTotal} breakeven exits bank the +5 ratchet instead` : ""}`
            : "…"}
        </div>
      </div>

      {/* Rule book stats: the engine the bot runs from tomorrow onward. Same
          buckets and tolerance as the retired engine's grid below, so the two
          rows read against each other factor for factor. */}
      <div>
        <div className="text-xs font-semibold text-[#10b981] mb-2">
          Rule book · today&apos;s engine (bank-first) — the default
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-4 gap-3">
          <StatCard label="Total Trades" value={book?.trades ?? "—"} />
          <StatCard label="Profitable" value={bookProfitable ?? "—"} color="#10b981" />
          <StatCard label="Breakeven" value={bookBreakeven ?? "—"} color="#f59e0b" />
          <StatCard label="Losing" value={bookLosing ?? "—"} color="#ef4444" />
          <StatCard label="Win Rate" value={bookWinRate != null ? `${bookWinRate}%` : "—"} color="#facc15" />
          <StatCard
            label="Net P&L"
            value={book ? formatRs(book.net_rupees) : "—"}
            color={book && book.net_rupees >= 0 ? "#10b981" : "#ef4444"}
            sub={book ? `gross ${book.gross_points >= 0 ? "+" : ""}${book.gross_points} pts` : undefined}
          />
          <StatCard
            label="Gap vs retired"
            value={book ? formatRs(book.delta_net) : "—"}
            color={book && book.delta_net >= 0 ? "#10b981" : "#ef4444"}
            sub={book ? `${book.delta_points >= 0 ? "+" : ""}${book.delta_points} pts` : undefined}
          />
          <StatCard label="Days Traded" value={bookDays ?? "—"} color="#6366f1" />
        </div>
      </div>

      {/* As-traded stats row: real cash under the RETIRED engine. Fees are
          money actually paid; the net is what the old ladder actually left on
          the table. Read it against the rule book above, not as the default. */}
      <div>
        <div className="text-xs text-[#64748b] mb-2">
          Actual money record · retired engine (what really hit the account)
        </div>
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
