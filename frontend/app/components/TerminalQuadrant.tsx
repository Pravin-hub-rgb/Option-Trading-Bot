"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Icon } from "@iconify/react";
import PriceDiagram from "./PriceDiagram";
import { fetchTickHistory, modifySl, closePosition } from "../lib/api";

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

  const [panelOpen, setPanelOpen] = useState(false);
  const [panelPos, setPanelPos] = useState({ x: 0, y: 0 });
  const [panelInited, setPanelInited] = useState(false);
  const [closing, setClosing] = useState(false);
  const [closeError, setCloseError] = useState(false);
  const panelDragRef = useRef({ active: false, startX: 0, startY: 0, origX: 0, origY: 0 });

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
    exited_breakeven: "#a3a3a3",
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
        fetchTickHistory(instrument, slot).then((ticks) => {
          setTickData((prev) => ({ ...prev, ticks }));
        }).catch(() => {});
      } else if (pos.state === "exited_win" || pos.state === "exited_loss" || pos.state === "exited_breakeven") {
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
            fetchTickHistory(instrument, slot).then((ticks) => {
              setTickData((prev) => ({ ...prev, ticks }));
            }).catch(() => {});
          } else if (pos.state === "exited_win" || pos.state === "exited_loss" || pos.state === "exited_breakeven") {
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
              const outcome = msg.outcome === "breakeven" ? "exited_breakeven" : msg.pnl > 0 ? "exited_win" : "exited_loss";
              setState(outcome);
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
    : state === "exited_breakeven" ? "Breakeven"
    : state === "exited_win" ? "Exited Win"
    : state === "exited_loss" ? "Exited Loss"
    : state === "watching" ? "Watching"
    : state === "stopped" ? "Stopped"
    : "Idle";

  const handleSlChange = (newSl: number) => {
    modifySl(instrument, slot, newSl).then(() => {
      setTickData((prev) => ({ ...prev, currentSl: newSl }));
    }).catch(() => {});
  };

  const handlePanelDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    panelDragRef.current = { active: true, startX: e.clientX, startY: e.clientY, origX: panelPos.x, origY: panelPos.y };
    document.body.style.cursor = "move";
    document.body.style.userSelect = "none";

    const onMove = (ev: MouseEvent) => {
      if (!panelDragRef.current.active) return;
      const dx = ev.clientX - panelDragRef.current.startX;
      const dy = ev.clientY - panelDragRef.current.startY;
      setPanelPos({ x: panelDragRef.current.origX + dx, y: panelDragRef.current.origY + dy });
    };

    const onUp = () => {
      panelDragRef.current.active = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [panelPos]);

  const openPanel = useCallback(() => {
    if (!panelInited) {
      setPanelPos({ x: window.innerWidth / 2 - 140, y: window.innerHeight / 2 - 100 });
      setPanelInited(true);
    }
    setPanelOpen(true);
  }, [panelInited]);

  const handleClose = useCallback(() => {
    setClosing(true);
    setCloseError(false);
    closePosition(instrument, slot)
      .then(() => setClosing(false))
      .catch(() => {
        setClosing(false);
        setCloseError(true);
        setTimeout(() => setCloseError(false), 2000);
      });
  }, [instrument, slot]);

  useEffect(() => {
    if (state !== "in_position") {
      setPanelOpen(false);
      setClosing(false);
      setCloseError(false);
    }
  }, [state]);

  const lastTick = tickData.ticks[tickData.ticks.length - 1];
  const displayLtp = lastTick?.ltp ?? tickData.exitPrice ?? null;
  const displayPnl = tickData.pnl ?? lastTick?.pnl ?? null;
  const lockedPnl = tickData.currentSl !== null && tickData.entryPrice !== null
    ? tickData.currentSl - tickData.entryPrice
    : null;

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
        <div className="flex items-center gap-2">
          {displayLtp != null && (
            <span className="text-[10px] font-mono font-bold" style={{ color: accent }}>
              LTP {displayLtp.toFixed(2)}
            </span>
          )}
          {displayPnl != null && (
            <span className="text-[10px] font-mono font-bold" style={{ color: displayPnl >= 0 ? "#10b981" : "#ef4444" }}>
              P&L {displayPnl >= 0 ? "+" : ""}{displayPnl.toFixed(2)}
            </span>
          )}
          {lockedPnl != null && (
            <span className="text-[10px] font-mono font-bold" style={{ color: lockedPnl >= 0 ? "#10b981" : "#ef4444" }}>
              Locked {lockedPnl >= 0 ? "+" : ""}{lockedPnl.toFixed(2)}
            </span>
          )}
          {state === "in_position" && (
            <button
              onClick={openPanel}
              className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider cursor-pointer transition-all hover:brightness-125"
              style={{
                background: "#ef444420",
                color: "#ef4444",
                border: "1px solid #ef444440",
              }}
            >
              ✕ Close
            </button>
          )}
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
      </div>

      <div className="flex-1 min-h-0 mt-1">
        <PriceDiagram ticks={tickData.ticks} entryPrice={tickData.entryPrice} entryTime={tickData.entryTime} exitTime={tickData.exitTime} exitPrice={tickData.exitPrice} currentSl={tickData.currentSl} tpLevels={tickData.tpLevels} color={accent} realizedPnl={tickData.pnl} onSlChange={handleSlChange} isTrading={state === "in_position"} />
      </div>

      {panelOpen && (
        <div
          className="fixed z-50 pointer-events-auto"
          style={{ transform: `translate(${panelPos.x}px, ${panelPos.y}px)` }}
        >
          <div className="w-[280px] bg-[#111] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
            <div
              className="flex items-center justify-between px-3 py-2 bg-white/[0.04] cursor-move select-none"
              onMouseDown={handlePanelDragStart}
            >
              <div className="flex items-center gap-1.5">
                <Icon icon={isCe ? "lucide:trending-up" : "lucide:trending-down"} className={isCe ? "text-indigo-400" : "text-amber-400"} width={12} />
                <span className="text-[11px] font-bold text-white">{instrument} — Trade {slot}</span>
              </div>
              <button
                onClick={() => setPanelOpen(false)}
                className="text-gray-500 hover:text-white text-xs cursor-pointer leading-none"
              >
                ✕
              </button>
            </div>

            <div className="px-3 py-3 space-y-2">
              <div className="flex justify-between text-[10px]">
                <span className="text-gray-500">Entry</span>
                <span className="text-white font-mono font-bold">{tickData.entryPrice?.toFixed(2) ?? "—"}</span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-gray-500">LTP</span>
                <span className="font-mono font-bold text-sm" style={{ color: accent }}>{displayLtp?.toFixed(2) ?? "—"}</span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-gray-500">P&L</span>
                <span className="font-mono font-bold text-sm" style={{ color: (displayPnl ?? 0) >= 0 ? "#10b981" : "#ef4444" }}>
                  {(displayPnl ?? 0) >= 0 ? "+" : ""}{displayPnl?.toFixed(2) ?? "—"}
                </span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-gray-500">SL</span>
                <span className="text-red-400 font-mono font-bold">{tickData.currentSl?.toFixed(2) ?? "—"}</span>
              </div>
            </div>

            <div className="px-3 pb-3">
              <button
                onClick={handleClose}
                disabled={closing}
                className="w-full py-2 rounded-lg text-xs font-bold uppercase tracking-wider cursor-pointer transition-all hover:brightness-125 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  background: closeError ? "#f59e0b25" : closing ? "#64748b30" : "#ef444425",
                  color: closeError ? "#f59e0b" : "#ef4444",
                  border: `1px solid ${closeError ? "#f59e0b40" : "#ef444440"}`,
                }}
              >
                {closeError ? "Failed — try again" : closing ? "Closing..." : "Close at CMP"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
