"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { fetchTradeStats, fetchTradePnl, fetchStatus } from "../lib/api";
import type { TradeStats, DayPnl, BotStatus } from "../lib/types";
import TerminalLogs from "../components/TerminalLogs";

export default function AnalyticsPage() {
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [days, setDays] = useState<DayPnl[]>([]);
  const [status, setStatus] = useState<BotStatus | null>(null);

  useEffect(() => {
    fetchTradeStats().then(setStats).catch(() => {});
    fetchTradePnl().then((r) => setDays(r.days)).catch(() => {});
    fetchStatus().then(setStatus).catch(() => {});
  }, []);

  const profitFactor = stats && stats.losing > 0 ? (stats.total_pnl > 0 ? (stats.avg_win * stats.profitable) / Math.abs(stats.avg_loss * stats.losing) : 0) : 0;

  const kpis = [
    { label: "Total Trades", value: stats?.total_trades ?? 0, icon: "lucide:bar-chart-3", color: "" },
    { label: "Winning", value: stats?.profitable ?? 0, icon: "lucide:trending-up", color: "#10b981", border: true },
    { label: "Losing", value: stats?.losing ?? 0, icon: "lucide:trending-down", color: "#ef4444", border: true },
    { label: "Net P&L", value: `₹${(stats?.total_pnl ?? 0).toFixed(2)}`, icon: "lucide:dollar-sign", color: (stats?.total_pnl ?? 0) >= 0 ? "#10b981" : "#ef4444", border: true },
  ];

  const extendedStats = [
    { label: "Win Rate", value: stats ? `${stats.win_rate}%` : "—" },
    { label: "Avg Win", value: stats ? `₹${stats.avg_win.toFixed(2)}` : "—" },
    { label: "Avg Loss", value: stats ? `₹${stats.avg_loss.toFixed(2)}` : "—" },
    { label: "Profit Factor", value: stats ? profitFactor.toFixed(2) : "—" },
    { label: "Largest Win", value: stats ? `₹${stats.largest_win.toFixed(2)}` : "—" },
    { label: "Largest Loss", value: stats ? `₹${stats.largest_loss.toFixed(2)}` : "—" },
  ];

  const positions = status?.positions;
  const activePositions = [];
  if (positions?.CE?.trade1?.state === "in_position") activePositions.push({ inst: "CE", slot: 1, p: positions.CE.trade1 });
  if (positions?.CE?.trade2?.state === "in_position") activePositions.push({ inst: "CE", slot: 2, p: positions.CE.trade2 });
  if (positions?.PE?.trade1?.state === "in_position") activePositions.push({ inst: "PE", slot: 1, p: positions.PE.trade1 });
  if (positions?.PE?.trade2?.state === "in_position") activePositions.push({ inst: "PE", slot: 2, p: positions.PE.trade2 });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold">Strategy Dashboard</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {kpis.map((k) => (
          <div
            key={k.label}
            className="bg-[#111] border border-white/5 p-4 rounded-xl flex flex-col"
            style={k.border ? { borderLeft: `4px solid ${k.color}` } : {}}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">{k.label}</span>
              <Icon icon={k.icon} className="text-gray-600 text-sm" />
            </div>
            <span
              className="font-['JetBrains_Mono',monospace] text-2xl font-bold"
              style={k.color ? { color: k.color } : {}}
            >
              {typeof k.value === "number" ? k.value.toString().padStart(2, "0") : k.value}
            </span>
          </div>
        ))}
      </div>

      {/* Positions Table */}
      <div className="bg-[#111] border border-white/5 rounded-xl overflow-hidden">
        <div className="px-4 py-3 bg-white/[0.02] border-b border-white/5">
          <h2 className="text-xs font-bold uppercase tracking-widest text-gray-400 flex items-center gap-2">
            <Icon icon="lucide:layout-list" className="text-indigo-400" />
            Active Positions
          </h2>
        </div>
        <div className="overflow-x-auto">
          {activePositions.length === 0 ? (
            <div className="text-center text-gray-600 text-sm py-8">No active positions</div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/5 text-gray-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-2 font-bold">Symbol</th>
                  <th className="text-left px-4 py-2 font-bold">Type</th>
                  <th className="text-right px-4 py-2 font-bold">Entry</th>
                  <th className="text-right px-4 py-2 font-bold">LTP</th>
                  <th className="text-right px-4 py-2 font-bold">P&L</th>
                  <th className="text-center px-4 py-2 font-bold">Status</th>
                </tr>
              </thead>
              <tbody>
                {activePositions.map((ap) => {
                  const pnl = ap.p?.pnl ?? 0;
                  return (
                    <tr key={`${ap.inst}-${ap.slot}`} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-3 font-mono font-bold">{ap.inst} Trade {ap.slot}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${ap.inst === "CE" ? "bg-indigo-500/10 text-indigo-400" : "bg-amber-500/10 text-amber-400"}`}>
                          {ap.inst}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono">₹{ap.p?.entry_price?.toFixed(2) ?? "—"}</td>
                      <td className="px-4 py-3 text-right font-mono" style={{ color: ap.inst === "CE" ? "#6366f1" : "#f59e0b" }}>
                        ₹{(ap.p?.entry_price ?? 0) + pnl > 0 ? ((ap.p?.entry_price ?? 0) + pnl).toFixed(2) : "—"}
                      </td>
                      <td className={`px-4 py-3 text-right font-mono font-bold ${pnl >= 0 ? "text-[#10b981]" : "text-[#ef4444]"}`}>
                        {pnl >= 0 ? "+" : ""}₹{pnl.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/20 uppercase">
                          Active
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Extended Stats */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
        {extendedStats.map((s) => (
          <div key={s.label} className="bg-[#111] border border-white/5 p-3 rounded-xl text-center">
            <div className="text-[9px] text-gray-500 uppercase tracking-widest font-bold mb-1">{s.label}</div>
            <div className="font-['JetBrains_Mono',monospace] text-sm font-bold">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Mini equity curve and donut placeholder */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-[#111] border border-white/5 p-4 rounded-xl">
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">P&L Distribution</h3>
          <div className="flex flex-col gap-2">
            {days.slice(-10).map((d) => {
              const maxPnl = Math.max(...days.map((x) => Math.abs(x.net_pnl ?? 0)), 1);
              const pct = d.net_pnl ? (Math.abs(d.net_pnl) / maxPnl) * 100 : 0;
              return (
                <div key={d.date} className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-600 w-16 shrink-0 font-mono">{d.date.slice(5)}</span>
                  <div className="flex-1 h-4 bg-[#222] rounded overflow-hidden">
                    <div
                      className="h-full rounded transition-all"
                      style={{
                        width: `${pct}%`,
                        background: (d.net_pnl ?? 0) >= 0 ? "#10b981" : "#ef4444",
                        float: d.net_pnl && d.net_pnl >= 0 ? "left" : "right",
                      }}
                    />
                  </div>
                  <span className={`text-[10px] w-16 text-right font-mono ${(d.net_pnl ?? 0) >= 0 ? "text-[#10b981]" : "text-[#ef4444]"}`}>
                    ₹{d.net_pnl?.toFixed(0) ?? "0"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="bg-[#111] border border-white/5 p-4 rounded-xl flex flex-col items-center justify-center">
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3 self-start">Win / Loss Ratio</h3>
          {stats && (stats.profitable > 0 || stats.losing > 0) ? (
            <div className="relative w-32 h-32">
              <svg viewBox="0 0 32 32" className="w-full h-full -rotate-90">
                <circle r="14" cx="16" cy="16" fill="none" stroke="#222" strokeWidth="4" />
                {stats.profitable > 0 && (
                  <circle
                    r="14"
                    cx="16"
                    cy="16"
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="4"
                    strokeDasharray={`${(stats.profitable / (stats.profitable + stats.losing)) * 87.96} 87.96`}
                    strokeLinecap="round"
                  />
                )}
              </svg>
              <div className="absolute inset-0 flex items-center justify-center flex-col">
                <span className="text-lg font-bold font-mono">{stats.win_rate}%</span>
                <span className="text-[9px] text-gray-500">Win Rate</span>
              </div>
            </div>
          ) : (
            <div className="text-gray-600 text-sm py-8">No trade data</div>
          )}
          <div className="flex gap-4 mt-2 text-[10px]">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#10b981]" /> Wins: {stats?.profitable ?? 0}</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#ef4444]" /> Losses: {stats?.losing ?? 0}</span>
          </div>
        </div>
      </div>

      <TerminalLogs />
    </div>
  );
}