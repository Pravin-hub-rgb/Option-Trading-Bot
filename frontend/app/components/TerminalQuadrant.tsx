"use client";

import { useEffect, useState } from "react";
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

  const accent = instrument === "CE" ? "#6366f1" : "#f59e0b";
  const headerClass = instrument === "CE" ? "card-ce" : "card-pe";

  const stateColors: Record<string, string> = {
    idle: "#64748b",
    watching: "#facc15",
    in_position: "#10b981",
    exited_win: "#10b981",
    exited_loss: "#ef4444",
    stopped: "#ef4444",
  };

  const stateLabels: Record<string, string> = {
    idle: "Idle",
    watching: "Watching",
    in_position: "Active",
    exited_win: "Win",
    exited_loss: "Loss",
    stopped: "Stopped",
  };

  useEffect(() => {
    if (typeof window === "undefined") return;

    const wsUrl = "ws://localhost:8765";
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

  return (
    <div
      className={`card ${headerClass} p-3 flex flex-col ${dim ? "opacity-40" : ""}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold">
          {instrument} T{slot}
        </span>
        <span
          className="text-[10px] px-2 py-0.5 rounded-full font-medium"
          style={{ background: `${stateColors[state] || "#64748b"}22`, color: stateColors[state] || "#64748b" }}
        >
          {stateLabels[state] || state}
        </span>
      </div>

      <PriceDiagram ticks={ticks} entryPrice={entryPrice} currentSl={currentSl} />

      <div className="grid grid-cols-2 gap-2 mt-2 text-[10px]">
        <div>
          <span className="text-[#64748b]">Entry</span>
          <div className="font-mono">{entryPrice !== null ? entryPrice.toFixed(2) : "—"}</div>
        </div>
        <div>
          <span className="text-[#64748b]">SL</span>
          <div className="font-mono">{currentSl !== null ? currentSl.toFixed(2) : "—"}</div>
        </div>
        <div>
          <span className="text-[#64748b]">P&L</span>
          <div
            className="font-mono"
            style={{ color: pnl !== null ? (pnl >= 0 ? "#10b981" : "#ef4444") : "#64748b" }}
          >
            {pnl !== null ? `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}` : "—"}
          </div>
        </div>
        <div>
          <span className="text-[#64748b]">Ticks</span>
          <div className="font-mono">{ticks.length}</div>
        </div>
      </div>
    </div>
  );
}
