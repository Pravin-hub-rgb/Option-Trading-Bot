"use client";

import { useEffect, useState } from "react";
import { fetchTradePnl } from "../lib/api";
import type { DayPnl } from "../lib/types";

export default function TradeCalendar() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [days, setDays] = useState<DayPnl[]>([]);

  useEffect(() => {
    fetchTradePnl(year).then((res) => setDays(res.days));
  }, [year]);

  const dayMap = new Map(days.map((d) => [d.date, d]));

  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];

  const colorForPnl = (pnl: number | null) => {
    if (pnl === null) return "#1a1a1a";
    if (pnl > 0) return "#10b981";
    return "#ef4444";
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <button
          className="text-sm text-[#64748b] hover:text-[#e5e7eb]"
          onClick={() => setYear((y) => y - 1)}
        >
          ◀
        </button>
        <span className="text-sm font-semibold">{year}</span>
        <button
          className="text-sm text-[#64748b] hover:text-[#e5e7eb]"
          onClick={() => setYear((y) => y + 1)}
        >
          ▶
        </button>
      </div>

      <div className="flex gap-3 flex-wrap">
        {months.map((month, mi) => {
          const monthDays = days.filter((d) => {
            const [y, m] = d.date.split("-");
            return parseInt(y) === year && parseInt(m) === mi + 1;
          });

          return (
            <div key={month} className="text-center">
              <div className="text-[10px] text-[#64748b] mb-1">{month}</div>
              <div className="grid grid-cols-7 gap-0.5">
                {monthDays.map((d) => (
                  <div
                    key={d.date}
                    className="w-3 h-3 rounded-sm cursor-pointer"
                    style={{ background: colorForPnl(d.net_pnl) }}
                    title={`${d.date}: ${d.trade_count} trades, P&L ${d.net_pnl ?? 0}`}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
