"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import PriceDiagram from "./PriceDiagram";

interface Tick {
  timestamp: string;
  ltp: number;
  sl: number | null;
  pnl: number | null;
}

interface Props {
  instrument: "CE" | "PE";
  slot: 1 | 2;
  dim?: boolean;
}

export default function TerminalQuadrant({ instrument, slot, dim }: Props) {
  const [state, setState] = useState<string>("idle");
  const [entryPrice, setEntryPrice] = useState<number | null>(null);
  const [currentSl, setCurrentSl] = useState<number | null>(null);
  const [pnl, setPnl] = useState<number | null>(null);
  const [ticks, setTicks] = useState<Tick[]>([]);

  const isCe = instrument === "CE";
  const accent = isCe ? "#6366f1" : "#f59e0b";
  const glowClass = isCe ? "card-ce" : "card-pe";

  const stateColors: Record<string, string> = {
    idle: "#64748b",
    watching: "#facc15",
    in_position: "#10b981",
    exited_win: "#10b981",
    exited_loss: "#ef4444",
    stopped: "#ef4444",
  };

  useEffect(() => {
    if (typeof window === "undefined") return;

    const wsUrl = "ws://127.0.0.1:8765";
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "tick" && msg.instrument === instrument) {
            setTicks((prev) => [...prev.slice(-200), { timestamp: msg.timestamp, ltp: msg.ltp, sl: msg.sl, pnl: msg.pnl }]);
            setCurrentSl(msg.sl);
            setPnl(msg.pnl);
          }
          if (msg.type === "trade" && msg.instrument === instrument) {
            if (msg.action === "entry") {
              setState("in_position");
              setEntryPrice(msg.price);
            }
            if (msg.action === "exit") {
              setState(msg.pnl > 0 ? "exited_win" : "exited_loss");
            }
          }
          if (msg.type === "strategy" && msg.instrument === instrument) {
            setState(msg.state);
          }
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 2000);
      };
    }

    connect();
    return () => {
      if (ws) ws.close();
      clearTimeout(reconnectTimer);
    };
  }, [instrument]);

  const stateLabel = state === "in_position" ? "In Position"
    : state === "exited_win" ? "Exited Win"
    : state === "exited_loss" ? "Exited Loss"
    : state === "watching" ? "Watching"
    : state === "stopped" ? "Stopped"
    : "Idle";

  return (
    <div className={`card ${glowClass} p-3 flex flex-col ${dim ? "opacity-40" : ""}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-bold tracking-tight flex items-center gap-2">
          <Icon icon={isCe ? "lucide:trending-up" : "lucide:trending-down"} className={isCe ? "text-indigo-400" : "text-amber-400"} />
          {instrument} Trade {slot}
        </h3>
        <span
          className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider"
          style={{
            background: `${stateColors[state] || "#64748b"}15`,
            color: stateColors[state] || "#64748b",
            border: `1px solid ${stateColors[state] || "#64748b"}30`,
          }}
        >
          {stateLabel}
        </span>
      </div>

      <PriceDiagram ticks={ticks} entryPrice={entryPrice} currentSl={currentSl} />

      <div className="grid grid-cols-4 gap-2 mt-3 text-[10px]">
        <div>
          <span className="text-[#64748b] text-[9px] uppercase tracking-wider">Bid</span>
          <div className="font-mono" style={{ color: accent }}>{entryPrice !== null ? (entryPrice - 0.5).toFixed(2) : "—"}</div>
        </div>
        <div>
          <span className="text-[#64748b] text-[9px] uppercase tracking-wider">Ask</span>
          <div className="font-mono" style={{ color: accent }}>{entryPrice !== null ? (entryPrice + 0.5).toFixed(2) : "—"}</div>
        </div>
        <div>
          <span className="text-[#64748b] text-[9px] uppercase tracking-wider">LTP</span>
          <div className="font-mono" style={{ color: accent }}>
            {ticks.length > 0 ? ticks[ticks.length - 1].ltp.toFixed(2) : "—"}
          </div>
        </div>
        <div>
          <span className="text-[#64748b] text-[9px] uppercase tracking-wider">P&L</span>
          <div
            className="font-mono"
            style={{ color: pnl !== null ? (pnl >= 0 ? "#10b981" : "#ef4444") : "#64748b" }}
          >
            {pnl !== null ? `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}` : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}