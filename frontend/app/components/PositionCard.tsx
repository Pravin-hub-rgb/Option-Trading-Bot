"use client";

import { useState } from "react";
import { Icon } from "@iconify/react";
import type { PositionState } from "../lib/types";

interface Props {
  instrument: "CE" | "PE";
  slot: 1 | 2;
  position: PositionState | null;
}

export default function PositionCard({ instrument, slot, position }: Props) {
  const isCe = instrument === "CE";
  const accent = isCe ? "#6366f1" : "#f59e0b";
  const [slValue, setSlValue] = useState(position?.current_sl ?? position?.entry_price ?? 0);

  const inPosition = position?.state === "in_position";
  const entryPrice = position?.entry_price ?? 0;
  const ltp = position?.pnl != null ? entryPrice + position.pnl : entryPrice;
  const pnl = position?.pnl ?? 0;
  const pnlPct = entryPrice > 0 ? (pnl / entryPrice) * 100 : 0;
  const isProfit = pnl >= 0;

  return (
    <div
      className={`bg-[#111] border border-white/5 rounded-2xl flex flex-col relative overflow-hidden ${
        isCe ? "card-glow-indigo border-t-4 border-t-[#6366f1]" : "card-glow-amber border-t-4 border-t-[#f59e0b]"
      }`}
    >
      <div className="p-5 flex items-center justify-between bg-white/[0.02] border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isCe ? "bg-indigo-500/10 border border-indigo-500/20" : "bg-amber-500/10 border border-amber-500/20"}`}>
            <Icon icon={isCe ? "lucide:trending-up" : "lucide:trending-down"} className={`text-xl ${isCe ? "text-indigo-400" : "text-amber-400"}`} />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-tight">
              {instrument} Trade {slot}
              {position?.exit_price && <span className="text-gray-500 font-normal ml-1">(Closed)</span>}
            </h3>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">
              {inPosition ? "Active Position" : position?.state === "exited_win" ? "Closed - Win" : position?.state === "exited_loss" ? "Closed - Loss" : "No Position"}
            </p>
          </div>
        </div>
        {inPosition && (
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${isCe ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" : "bg-amber-500/10 text-amber-400 border border-amber-500/20"}`}>
            LIVE
          </span>
        )}
      </div>

      <div className="p-5 flex flex-col gap-5">
        {/* Entry / LTP / P&L */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold">Entry</span>
            <div className="font-['JetBrains_Mono',monospace] text-lg font-bold">₹{entryPrice.toFixed(2)}</div>
          </div>
          <div>
            <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold">LTP</span>
            <div className="font-['JetBrains_Mono',monospace] text-lg font-bold" style={{ color: accent }}>₹{ltp.toFixed(2)}</div>
          </div>
          <div>
            <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold">P&L</span>
            <div className={`font-['JetBrains_Mono',monospace] text-lg font-bold ${isProfit ? "text-[#10b981]" : "text-[#ef4444]"}`}>
              {isProfit ? "+" : ""}₹{pnl.toFixed(2)}
            </div>
          </div>
        </div>

        {/* P&L Progress Bar */}
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500 font-mono">{pnlPct.toFixed(1)}%</span>
            <span className="text-gray-500 font-mono">100%</span>
          </div>
          <div className="h-2 bg-[#333] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(Math.abs(pnlPct), 100)}%`,
                background: isProfit ? "#10b981" : "#ef4444",
              }}
            />
          </div>
        </div>

        {/* Mini equity curve */}
        <div className="h-16 bg-black/30 rounded-lg border border-white/5 flex items-center justify-center text-[10px] text-gray-600">
          {inPosition ? "Chart loading..." : "No data"}
        </div>

        {/* Risk Metrics */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-black/30 rounded-lg p-3">
            <span className="text-[9px] uppercase tracking-widest text-gray-500 font-bold">Current SL</span>
            <div className="font-['JetBrains_Mono',monospace] text-sm font-bold mt-1">
              {position?.current_sl ? `₹${position.current_sl.toFixed(2)}` : "—"}
            </div>
          </div>
          <div className="bg-black/30 rounded-lg p-3">
            <span className="text-[9px] uppercase tracking-widest text-gray-500 font-bold">Trail SL</span>
            <div className="font-['JetBrains_Mono',monospace] text-sm font-bold mt-1">
              {position?.highest_price ? `₹${position.highest_price.toFixed(2)}` : "—"}
            </div>
          </div>
          <div className="bg-black/30 rounded-lg p-3">
            <span className="text-[9px] uppercase tracking-widest text-gray-500 font-bold">Risk %</span>
            <div className="font-['JetBrains_Mono',monospace] text-sm font-bold mt-1">
              {entryPrice > 0 ? `${((entryPrice - (position?.current_sl ?? entryPrice)) / entryPrice * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
        </div>

        {/* SL Range Slider */}
        {inPosition && (
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-gray-500">SL: ₹{slValue.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min={(entryPrice * 0.8).toFixed(2)}
              max={(entryPrice * 1.2).toFixed(2)}
              step="0.05"
              value={slValue.toFixed(2)}
              onChange={(e) => setSlValue(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#333] rounded-full appearance-none cursor-pointer"
              style={{
                accentColor: accent,
              }}
            />
          </div>
        )}

        {/* Trade Controls */}
        {inPosition && (
          <div className="flex gap-3">
            <button className="flex-1 px-4 py-2 bg-indigo-500/10 border border-indigo-500/30 rounded-lg text-sm font-semibold text-indigo-400 hover:bg-indigo-500/20 transition-all">
              <Icon icon="lucide:edit" className="inline mr-1.5" />
              Modify SL
            </button>
            <button className="flex-1 px-4 py-2 bg-[#10b981]/10 border border-[#10b981]/30 rounded-lg text-sm font-semibold text-[#10b981] hover:bg-[#10b981]/20 transition-all">
              <Icon icon="lucide:dollar-sign" className="inline mr-1.5" />
              Book Profit
            </button>
          </div>
        )}

        {/* Order Details */}
        {position?.exit_price && (
          <div className="text-[10px] text-gray-500 border-t border-white/5 pt-3 mt-1">
            <div className="grid grid-cols-2 gap-2">
              <div><span className="text-gray-600">Exit Price:</span> ₹{position.exit_price.toFixed(2)}</div>
              <div><span className="text-gray-600">Exit Reason:</span> {position.exit_reason || "—"}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}