"use client";

import { useCallback, useEffect, useState } from "react";
import TradeCalendar from "../components/TradeCalendar";
import TradeLogsTable from "../components/TradeLogsTable";
import { fetchExitRules } from "../lib/api";
import type { RuleBook } from "../lib/types";

export default function HistoryPage() {
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [refreshKey, setRefreshKey] = useState(0);
  const [book, setBook] = useState<RuleBook | null>(null);
  useEffect(() => {
    fetchExitRules(year)
      .then((r) => setBook(r.rule_book))
      .catch(() => setBook(null));
  }, [year, refreshKey]);

  const handleTradeDeleted = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const tol = 1.5;
  // Bucket the rule book rows with the backend's breakeven tolerance, so the
  // grid below matches what the counterfactual engine reports.
  const bookRows = book?.rows ?? [];
  const bookProfitable = bookRows.filter((r) => (r.rule_pnl ?? 9) > tol).length;
  const bookBreakeven = bookRows.filter(
    (r) => Math.abs(r.rule_pnl ?? 9) <= tol,
  ).length;
  const bookLosing = bookRows.filter((r) => (r.rule_pnl ?? -9) < -tol).length;
  const bookWinRate = bookRows.length
    ? (Math.round((100 * bookProfitable) / bookRows.length * 10) / 10)
    : null;
  const bookDays = new Set(bookRows.map((r) => r.date)).size;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold">Trade History</h1>

      {/* Bank-first section: the headline. */}
      <div className="card p-4">
        <div className="text-xs text-[#64748b] uppercase tracking-wider mb-3">
          Bank-first
        </div>
        <div
          className="card p-3 border-l-4"
          style={{ borderLeftColor: book && book.net_rupees >= 0 ? "#10b981" : "#ef4444" }}
        >
          <div className="text-xs text-[#10b981] font-semibold">Banked</div>
          <div
            className="text-3xl font-mono font-semibold mt-1"
            style={{ color: book && book.net_rupees >= 0 ? "#10b981" : "#ef4444" }}
          >
            {book ? formatRs(book.net_rupees) : "—"}
          </div>
          <div className="text-[0.65rem] text-[#64748b] mt-1">
            {book
              ? `first rung +${book.bank_at}, then every +5 · ${bookProfitable} profitable / ${bookBreakeven} BE / ${bookLosing} L · ${bookWinRate ?? "—"}% win · ${book.gross_points >= 0 ? "+" : ""}${book.gross_points} pts`
              : "…"}
          </div>
        </div>
      </div>

      {/* Stats grid: bank-first results. */}
      <div>
        <div className="text-xs font-semibold text-[#10b981] mb-2">
          Summary
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
          <StatCard label="Days Traded" value={bookDays ?? "—"} color="#6366f1" />
        </div>
      </div>

      {/* Calendar */}
      <div className="card p-4">
        <TradeCalendar
          year={year}
          onYearChange={setYear}
          refreshKey={refreshKey}
          breakevenTolerance={tol}
        />
      </div>

      {/* Trade table */}
      <div className="card p-4">
        <TradeLogsTable
          year={year}
          onDeleted={handleTradeDeleted}
          breakevenTolerance={tol}
          refreshKey={refreshKey}
          bankAt={book?.bank_at ?? 5}
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
