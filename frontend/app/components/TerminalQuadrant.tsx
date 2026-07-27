"use client";

import { useEffect, useState, useRef } from "react";
import { Icon } from "@iconify/react";
import PriceDiagram from "./PriceDiagram";

interface Tick {
  timestamp: string;
  ltp: number;
  sl: number | null;
  pnl: number | null;
}

interface InitialPos {
  state: string;
  entry_price: number | null;
  current_sl: number | null;
  pnl: number | null;
  exit_price?: number | null;
  exit_time?: string | null;
}

interface Props {
  instrument: "CE" | "PE";
  slot: 1 | 2;
  initialPos?: InitialPos | null;
}

interface TickData {
  ticks: Tick[];
  currentSl: number | null;
  pnl: number | null;
  entryPrice: number | null;
  entryTime: string | null;
  exitTime: string | null;
  exitPrice: number | null;
  tpLevels: number[];
}

function extractTime(iso: string): string {
  const m = iso.match(/T(\d{2}:\d{2}:\d{2})\.?(\d*)/);
  if (!m) return iso;
  const ms = (m[2] || "000").slice(0, 3).padEnd(3, "0");
  return `${m[1]}.${ms}`;
}

const INITIAL_TICK_DATA: TickData = {
  ticks: [],
  currentSl: null,
  pnl: null,
  entryPrice: null,
  entryTime: null,
  exitTime: null,
  exitPrice: null,
  tpLevels: [],
};

function fmtTime(ts: string): string {
  const m = ts.match(/^(\d{2}):(\d{2})/);
  if (m) return `${+m[1]}:${m[2]}`;
  const d = new Date(ts);
  if (!isNaN(d.getTime())) return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  return ts;
}

export default function TerminalQuadrant({ instrument, slot, initialPos }: Props) {
  const [state, setState] = useState<string>("idle");
  const [tickData, setTickData] = useState<TickData>(INITIAL_TICK_DATA);
  const [synced, setSynced] = useState(false);
  const [enteredAt, setEnteredAt] = useState<string | null>(null);
  const [exitedAt, setExitedAt] = useState<string | null>(null);
  const frozenRef = useRef(false);

  const isCe = instrument === "CE";
  const accent = isCe ? "#6366f1" : "#f59e0b";
  const glowClass = isCe ? "card-ce" : "card-pe";

  const dim = state === "idle" && tickData.entryPrice === null;

  const stateColors: Record<string, string> = {
    idle: "#64748b",
    watching: "#facc15",
    in_position: "#10b981",
    exited_win: "#10b981",
    exited_loss: "#ef4444",
    stopped: "#ef4444",
  };

  useEffect(() => {
    const pos = initialPos !== undefined ? initialPos : undefined;
    if (pos) {
      if (pos.state === "in_position") {
        frozenRef.current = false;
        setState("in_position");
        setTickData({
          ticks: [],
          currentSl: pos.current_sl ?? null,
          pnl: pos.pnl ?? null,
          entryPrice: pos.entry_price ?? null,
          entryTime: null,
          exitTime: null,
          exitPrice: null,
          tpLevels: [],
        });
      } else if (pos.state === "exited_win" || pos.state === "exited_loss") {
        frozenRef.current = true;
        setState(pos.state);
        setTickData({
          ticks: [],
          currentSl: null,
          pnl: pos.pnl ?? null,
          entryPrice: pos.entry_price ?? null,
          entryTime: null,
          exitTime: pos.exit_time ?? null,
          exitPrice: pos.exit_price ?? null,
          tpLevels: [],
        });
      }
    }
    if (initialPos !== undefined) {
      setSynced(true);
      return;
    }

    fetch("http://127.0.0.1:8002/api/status")
      .then((r) => r.json())
      .then((status) => {
        const pos = status?.positions?.[instrument]?.[`trade${slot}`];
        if (pos) {
          if (pos.state === "in_position") {
            frozenRef.current = false;
            setState("in_position");
            setTickData({
              ticks: [],
              currentSl: pos.current_sl ?? null,
              pnl: pos.pnl ?? null,
              entryPrice: pos.entry_price ?? null,
              entryTime: null,
              exitTime: null,
              exitPrice: null,
              tpLevels: [],
            });
          } else if (pos.state === "exited_win" || pos.state === "exited_loss") {
            frozenRef.current = true;
            setState(pos.state);
            setTickData({
              ticks: [],
              currentSl: null,
              pnl: pos.pnl ?? null,
              entryPrice: pos.entry_price ?? null,
              entryTime: null,
              exitTime: pos.exit_time ?? null,
              exitPrice: pos.exit_price ?? null,
              tpLevels: [],
            });
          }
        }
        setSynced(true);
      })
      .catch(() => setSynced(true));
  }, [instrument, slot, initialPos]);

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
          if (msg.type === "tick" && msg.instrument === instrument && msg.trade_slot === slot && !frozenRef.current) {
            setTickData((prev) => ({
              ticks: [...prev.ticks.slice(-2000), { timestamp: msg.timestamp, ltp: msg.ltp, sl: msg.sl, pnl: msg.pnl }],
              currentSl: msg.sl,
              pnl: msg.pnl,
              entryPrice: msg.entry ?? prev.entryPrice,
              entryTime: msg.entry_time ?? prev.entryTime,
              exitTime: prev.exitTime,
              exitPrice: prev.exitPrice,
              tpLevels: msg.tp_levels ?? prev.tpLevels,
            }));
          }
          if (msg.type === "trade" && msg.instrument === instrument && msg.trade_slot === slot) {
            if (msg.action === "entry") {
              frozenRef.current = false;
              setState("in_position");
              setEnteredAt(fmtTime(msg.timestamp));
              setTickData((prev) => ({ ...prev, entryPrice: msg.price, entryTime: extractTime(msg.timestamp) }));
            }
            if (msg.action === "exit") {
              frozenRef.current = true;
              setState(msg.pnl > 0 ? "exited_win" : "exited_loss");
              setExitedAt(fmtTime(msg.timestamp));
              setTickData((prev) => ({ ...prev, exitTime: extractTime(msg.timestamp), exitPrice: msg.price, pnl: msg.pnl }));
            }
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
    <div className={`card ${glowClass} p-2 flex flex-col ${dim ? "opacity-40" : ""}`}>
      <div className="flex items-center justify-between shrink-0">
        <h3 className="text-xs font-bold tracking-tight flex items-center gap-1.5">
          <Icon icon={isCe ? "lucide:trending-up" : "lucide:trending-down"} className={isCe ? "text-indigo-400" : "text-amber-400"} width={14} />
          {instrument} Trade {slot}
          {enteredAt && (
            <span className="text-xs font-mono font-semibold text-green-300 ml-1">entered {enteredAt}</span>
          )}
          {exitedAt && (
            <span className="text-xs font-mono font-semibold text-red-300 ml-1">exit {exitedAt}</span>
          )}
        </h3>
        <span
          className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider"
          style={{
            background: `${stateColors[state] || "#64748b"}15`,
            color: stateColors[state] || "#64748b",
            border: `1px solid ${stateColors[state] || "#64748b"}30`,
          }}
        >
          {stateLabel}
        </span>
      </div>

      <div className="flex-1 min-h-0 mt-1">
        <PriceDiagram ticks={tickData.ticks} entryPrice={tickData.entryPrice} entryTime={tickData.entryTime} exitTime={tickData.exitTime} exitPrice={tickData.exitPrice} currentSl={tickData.currentSl} tpLevels={tickData.tpLevels} color={accent} realizedPnl={tickData.pnl} />
      </div>
    </div>
  );
}
