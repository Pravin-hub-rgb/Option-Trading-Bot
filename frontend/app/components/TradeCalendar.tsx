"use client";

import { useEffect, useState, useMemo } from "react";
import { Icon } from "@iconify/react";
import { fetchTradePnl } from "../lib/api";
import type { DayPnl } from "../lib/types";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function getHeatmapColor(day: DayPnl | undefined, tol: number): string {
  if (!day || day.trade_count === 0) return "#1e293b";
  if (day.net_pnl === null) return "#e2e8f0";
  if (day.net_pnl > tol) return "#10b981";
  if (day.net_pnl < -tol) return "#ef4444";
  return "#64748b";
}

function getHeatmapTooltip(day: DayPnl | undefined, dateStr: string, tol: number): string {
  if (!day || day.trade_count === 0) return `${dateStr}: No trades`;
  const rupees = day.net_rupees;
  if (rupees === null || rupees === undefined) return `${dateStr}: ${day.trade_count} trade(s), P&L not set`;
  const sign = rupees >= 0 ? "+" : "";
  const be = day.net_pnl !== null && day.net_pnl >= -tol && day.net_pnl <= tol ? " (breakeven)" : "";
  return `${dateStr}: ${day.trade_count} trade(s), ${sign}₹${rupees.toFixed(2)}${be}`;
}

export default function TradeCalendar({
  year,
  onYearChange,
  refreshKey,
  breakevenTolerance,
}: {
  year: number;
  onYearChange: (year: number) => void;
  refreshKey: number;
  breakevenTolerance: number;
}) {
  const [days, setDays] = useState<Record<string, DayPnl>>({});

  useEffect(() => {
    fetchTradePnl(year)
      .then((res) => {
        const m: Record<string, DayPnl> = {};
        for (const day of res.days || []) m[day.date] = day;
        setDays(m);
      })
      .catch(() => setDays({}));
  }, [year, refreshKey]);

  const { weeks, monthGroups, monthEndCols } = useMemo(() => {
    const first = new Date(year, 0, 1);
    const last = new Date(year, 11, 31);
    const startDow = first.getDay();
    const startPad = new Date(first);
    startPad.setDate(startPad.getDate() - startDow);

    const allDates: Date[] = [];
    const cursor = new Date(startPad);
    while (cursor <= last) {
      allDates.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }

    const w: Date[][] = [];
    for (let i = 0; i < allDates.length; i += 7) w.push(allDates.slice(i, i + 7));

    const mg: { label: string; startCol: number; span: number }[] = [];
    let cm = -1, ms = -1;
    w.forEach((week, wi) => {
      if (!week.length) return;
      const counts: Record<number, number> = {};
      for (const date of week) {
        if (date.getFullYear() !== year) continue;
        counts[date.getMonth()] = (counts[date.getMonth()] || 0) + 1;
      }
      if (Object.keys(counts).length === 0) return;
      const bestMonth = Number(Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]);
      if (bestMonth !== cm) {
        if (cm !== -1) mg.push({ label: MONTHS[cm], startCol: ms, span: wi - ms });
        cm = bestMonth;
        ms = wi;
      }
    });
    if (cm !== -1) mg.push({ label: MONTHS[cm], startCol: ms, span: w.length - ms });

    const mec = new Set(mg.map((g) => g.startCol + g.span - 1));
    return { weeks: w, monthGroups: mg, monthEndCols: mec };
  }, [year]);

  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[#94a3b8] text-[0.75rem] font-semibold uppercase tracking-[0.5px]">
          Trade Logs — {year}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onYearChange(year - 1)}
            className="text-[#64748b] hover:text-[#e5e7eb] transition-colors"
          >
            <Icon icon="lucide:chevron-left" width="18" />
          </button>
          <span className="text-sm font-bold text-[#f1f5f9] font-mono">{year}</span>
          <button
            onClick={() => onYearChange(year + 1)}
            className="text-[#64748b] hover:text-[#e5e7eb] transition-colors"
          >
            <Icon icon="lucide:chevron-right" width="18" />
          </button>
        </div>
      </div>

      <div className="flex gap-1 items-start overflow-x-auto pb-1">
        <div className="flex flex-col gap-[2px] mr-[2px] pt-[24px]">
          {DAYS.map((d, i) => (
            <div key={i} className="flex items-center h-[14px]">
              <span className="text-[#64748b] text-[0.6rem] leading-none">{d}</span>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-0">
          <div className="flex gap-[2px] mb-[2px] ml-0">
            {monthGroups.map((m, gi) => (
              <div
                key={`${m.label}-${m.startCol}`}
                className="flex-shrink-0 text-left"
                style={{ width: m.span * 14 + (m.span - 1) * 4, marginRight: "6px" }}
              >
                <span className="text-[#94a3b8] text-[0.6rem] font-semibold">{m.label}</span>
              </div>
            ))}
          </div>

          <div className="flex gap-[2px]">
            {weeks.map((week, wi) => (
              <div
                key={wi}
                className="flex flex-col gap-[2px]"
                style={{ marginRight: monthEndCols.has(wi) ? "6px" : 0 }}
              >
                {week.map((date, di) => {
                  const key = fmt(date);
                  const day = days[key];
                  const inYear = date.getFullYear() === year;
                  const color = inYear ? getHeatmapColor(day, breakevenTolerance) : "transparent";
                  return (
                    <div
                      key={di}
                      title={inYear ? getHeatmapTooltip(day, date.toDateString(), breakevenTolerance) : ""}
                      className="rounded-[3px] transition-all duration-200"
                      style={{
                        width: 14,
                        height: 14,
                        backgroundColor: color,
                        cursor: inYear ? "pointer" : "default",
                      }}
                      onMouseEnter={(e) => {
                        if (inYear) {
                          e.currentTarget.style.opacity = "0.8";
                          e.currentTarget.style.transform = "scale(1.3)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.opacity = "1";
                        e.currentTarget.style.transform = "scale(1)";
                      }}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1.5 mt-2">
        <span className="text-[#64748b] text-[0.65rem]">No trade</span>
        <div className="w-3 h-3 rounded-[2px]" style={{ backgroundColor: "#1e293b" }} />
        <span className="text-[#64748b] text-[0.65rem]">Unsettled</span>
        <div className="w-3 h-3 rounded-[2px]" style={{ backgroundColor: "#e2e8f0" }} />
        <span className="text-[#64748b] text-[0.65rem]">Breakeven</span>
        <div className="w-3 h-3 rounded-[2px]" style={{ backgroundColor: "#64748b" }} />
        <span className="text-[#64748b] text-[0.65rem]">Profit</span>
        <div className="w-3 h-3 rounded-[2px]" style={{ backgroundColor: "#10b981" }} />
        <span className="text-[#64748b] text-[0.65rem]">Loss</span>
        <div className="w-3 h-3 rounded-[2px]" style={{ backgroundColor: "#ef4444" }} />
      </div>
    </div>
  );
}
