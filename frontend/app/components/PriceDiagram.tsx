"use client";

import { useEffect, useRef, useState, useMemo } from "react";

interface Tick {
  timestamp: string;
  ltp: number;
  sl: number | null;
  pnl: number | null;
}

interface Props {
  ticks: Tick[];
  entryPrice: number | null;
  entryTime?: string | null;
  exitTime?: string | null;
  exitPrice?: number | null;
  currentSl: number | null;
  tpLevels?: number[];
  belowSlCount?: number;
  slStep?: number;
  color?: string;
}

const PX_PER_TICK = 2.5;

type Level = { label: string; price: number; color: string };

function buildLevels(entryPrice: number | null, currentSl: number | null, tpLevels: number[], belowSlCount: number, slStep: number): { left: Level[]; right: Level | null; below: Level[] } {
  const left: Level[] = [];
  const below: Level[] = [];
  let right: Level | null = null;
  if (currentSl !== null)
    right = { label: `SL ${currentSl.toFixed(2)}`, price: currentSl, color: "#ef4444" };
  if (entryPrice !== null) {
    left.push({ label: `Entry ${entryPrice.toFixed(2)}`, price: entryPrice, color: "#94a3b8" });
    tpLevels.forEach((tp, i) => {
      const diff = tp - entryPrice;
      left.push({ label: tp.toFixed(2), price: tp, color: "#10b981" });
    });
  }
  if (currentSl !== null) {
    for (let i = 1; i <= belowSlCount; i++) {
      const price = currentSl - i * slStep;
      below.push({ label: price.toFixed(2), price, color: "#94a3b8" });
    }
  }
  left.sort((a, b) => a.price - b.price);
  return { left, right, below };
}

export default function PriceDiagram({
  ticks, entryPrice, entryTime, exitTime, exitPrice, currentSl,
  tpLevels = [], belowSlCount = 3, slStep = 5, color = "#6366f1"
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const outerRef = useRef<HTMLDivElement>(null);
  const [chartH, setChartH] = useState(200);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, offsetX: 0, offsetY: 0 });
  const atEndRef = useRef(true);
  const offsetRef = useRef({ x: 0, y: 0 });
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);
  const entryPosRef = useRef<{ x: number; y: number } | null>(null);
  const entryLabelRef = useRef<string>("");
  const exitPosRef = useRef<{ x: number; y: number } | null>(null);
  const exitLabelRef = useRef<string>("");

  const { left: leftLevels, right: slLevel, below: belowLevels } = useMemo(
    () => buildLevels(entryPrice, currentSl, tpLevels, belowSlCount, slStep),
    [entryPrice, currentSl, tpLevels, belowSlCount, slStep]
  );
  const levels = useMemo(
    () => slLevel ? [...leftLevels, slLevel] : leftLevels,
    [leftLevels, slLevel]
  );
  const allLevels = useMemo(
    () => belowLevels.length > 0 ? [...levels, ...belowLevels] : levels,
    [levels, belowLevels]
  );

  useEffect(() => {
    const el = outerRef.current;
    if (!el || entryPrice === null) return;
    setChartH(el.clientHeight);
    const ro = new ResizeObserver(([entry]) => setChartH(entry.contentRect.height));
    ro.observe(el);
    return () => ro.disconnect();
  }, [entryPrice !== null]);

  const { lo, hi, range } = useMemo(() => {
    const prices = ticks.map(t => t.ltp);
    const allVals = [...prices, ...levels.map(l => l.price)];
    const lo = Math.min(...allVals) - 0.4;
    const hi = Math.max(...allVals) + 0.4;
    return { lo, hi, range: hi - lo || 1 };
  }, [ticks, levels]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || entryPrice === null || ticks.length === 0) return;

    const dpr = window.devicePixelRatio || 1;
    const containerH = outerRef.current?.clientHeight || chartH;
    const containerW = outerRef.current?.clientWidth || 800;
    if (containerH === 0) return;

    const T = 4;
    const B = 4;
    const ch = containerH - T - B;
    const yPos = (p: number) => T + ch - ((p - lo) / range) * ch + offset.y;

    const totalPathW = (ticks.length - 1) * PX_PER_TICK;
    const canvasW = Math.max(containerW, totalPathW + 280);

    canvas.width = canvasW * dpr;
    canvas.height = containerH * dpr;
    canvas.style.width = `${canvasW}px`;
    canvas.style.height = `${containerH}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, canvasW, containerH);

    const xPos = (i: number) => 120 + i * PX_PER_TICK + offset.x;

    // reference lines
    ctx.textBaseline = "middle";
    allLevels.forEach(lvl => {
      const y = yPos(lvl.price);
      ctx.strokeStyle = lvl.color;
      ctx.globalAlpha = 0.6;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvasW, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    });

    // price path
    if (ticks.length > 1) {
      const pts = ticks.map((t, i) => ({
        x: xPos(i),
        y: yPos(t.ltp),
      }));

      const grad = ctx.createLinearGradient(0, T, 0, T + ch);
      grad.addColorStop(0, color + "20");
      grad.addColorStop(1, color + "02");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(pts[0].x, T + ch);
      pts.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.lineTo(pts[pts.length - 1].x, T + ch);
      ctx.closePath();
      ctx.fill();

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.beginPath();
      pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
      ctx.stroke();

      const last = pts[pts.length - 1];
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.15;
      ctx.beginPath();
      ctx.arc(last.x, last.y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(last.x, last.y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // entry marker
    entryPosRef.current = null;
    if (entryTime && ticks.length > 0) {
      const entryIdx = ticks.findIndex(t => t.timestamp >= entryTime);
      if (entryIdx >= 0) {
        const et = ticks[entryIdx].timestamp;
        const short = `${+et.slice(0, 2)}:${et.slice(3, 5)}`;
        const ex = xPos(entryIdx);
        const ey = yPos(entryPrice);
        entryPosRef.current = { x: ex, y: ey };
        entryLabelRef.current = `Entry ${short}`;
        ctx.save();
        ctx.fillStyle = "#22c55e";
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(ex, ey - 7);
        ctx.lineTo(ex + 7, ey);
        ctx.lineTo(ex, ey + 7);
        ctx.lineTo(ex - 7, ey);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.restore();
      }
    }

    // exit marker
    exitPosRef.current = null;
    if (exitTime && exitPrice != null && ticks.length > 0) {
      let exitIdx = ticks.findIndex(t => t.timestamp >= exitTime);
      if (exitIdx < 0) {
        // Fallback: use last tick if no matching tick found
        // (this happens when exit occurs after the last tick was received)
        exitIdx = ticks.length - 1;
      }
      const xt = ticks[exitIdx].timestamp;
      const short = `${+xt.slice(0, 2)}:${xt.slice(3, 5)}`;
      const ex = xPos(exitIdx);
      const ey = yPos(exitPrice);
      exitPosRef.current = { x: ex, y: ey };
      exitLabelRef.current = `Exit ${short}`;
      ctx.save();
      ctx.fillStyle = "#ef4444";
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(ex, ey - 7);
      ctx.lineTo(ex + 7, ey);
      ctx.lineTo(ex, ey + 7);
      ctx.lineTo(ex - 7, ey);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    // auto-scroll to end if user hasn't dragged away
    if (atEndRef.current) {
      const endX = containerW - 280 - (ticks.length - 1) * PX_PER_TICK;
      const targetX = Math.min(0, endX);
      if (Math.abs(offset.x - targetX) > 0.5) {
        offsetRef.current = { x: targetX, y: offset.y };
        setOffset(prev => ({ ...prev, x: targetX }));
      }
    }

  }, [ticks, entryPrice, entryTime, exitTime, exitPrice, currentSl, tpLevels, color, chartH, offset]);

  if (entryPrice === null) {
    return (
      <div className="flex items-center justify-center text-gray-500 text-xs tracking-wider uppercase h-full">
        Idle
      </div>
    );
  }

  function handleMouseDown(e: React.MouseEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    drag.dragging = true;
    setIsDragging(true);
    drag.startX = e.clientX;
    drag.startY = e.clientY;
    drag.offsetX = offset.x;
    drag.offsetY = offset.y;
    atEndRef.current = false;
  }

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (drag.dragging) {
      const dx = e.clientX - drag.startX;
      const dy = e.clientY - drag.startY;
      const newX = drag.offsetX + dx;
      const newY = drag.offsetY + dy;
      offsetRef.current = { x: newX, y: newY };
      setOffset({ x: newX, y: newY });
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const hit = (pos: { x: number; y: number } | null) =>
      pos && Math.sqrt((mx - pos.x) ** 2 + (my - pos.y) ** 2) < 15;

    if (hit(entryPosRef.current)) {
      setTooltip({ x: e.clientX, y: e.clientY + 6, text: entryLabelRef.current });
    } else if (hit(exitPosRef.current)) {
      setTooltip({ x: e.clientX, y: e.clientY + 6, text: exitLabelRef.current });
    } else {
      setTooltip(null);
    }
  }

  function handleMouseUp() {
    dragRef.current.dragging = false;
    setIsDragging(false);

    if (ticks.length > 0) {
      const containerW = outerRef.current?.clientWidth || 800;
      const lastTickX = 120 + (ticks.length - 1) * PX_PER_TICK + offsetRef.current.x;
      if (lastTickX < containerW - 100) {
        atEndRef.current = true;
      }
    }
  }

  const H = chartH;
  const yPos = (p: number) => 4 + (H - 8) - ((p - lo) / range) * (H - 8) + offset.y;

  const lastTick = ticks[ticks.length - 1];

  return (
    <div ref={outerRef} className="relative h-full overflow-hidden">
      {/* Left Y-axis labels (Entry, TP's, below SL) */}
      <div className="absolute left-0 top-0 bottom-0 w-[102px] z-10 pointer-events-none">
        {leftLevels.map((lvl, i) => {
          const y = yPos(lvl.price);
          return (
            <div
              key={`l-${i}`}
              className="absolute right-1 leading-none px-1.5 py-0.5 rounded"
              style={{
                top: y,
                transform: "translateY(-50%)",
                backgroundColor: "rgba(10, 10, 10, 0.7)",
                backdropFilter: "blur(4px)",
                WebkitBackdropFilter: "blur(4px)",
              }}
            >
              <span className="font-mono text-[11px] font-bold whitespace-nowrap" style={{ color: lvl.color }}>
                {lvl.label}
              </span>
            </div>
          );
        })}
        {belowLevels.map((lvl, i) => {
          const y = yPos(lvl.price);
          return (
            <div
              key={`b-${i}`}
              className="absolute right-1 leading-none px-1.5 py-0.5 rounded"
              style={{
                top: y,
                transform: "translateY(-50%)",
                backgroundColor: "rgba(10, 10, 10, 0.7)",
                backdropFilter: "blur(4px)",
                WebkitBackdropFilter: "blur(4px)",
              }}
            >
              <span className="font-mono text-[11px] font-bold whitespace-nowrap" style={{ color: lvl.color }}>
                {lvl.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Right SL label */}
      {slLevel && (
        <div className="absolute right-0 top-0 bottom-0 w-[100px] z-10 pointer-events-none">
          <div
            className="absolute left-1 leading-none px-1.5 py-0.5 rounded"
            style={{
              top: yPos(slLevel.price),
              transform: "translateY(-50%)",
              backgroundColor: "rgba(10, 10, 10, 0.7)",
              backdropFilter: "blur(4px)",
              WebkitBackdropFilter: "blur(4px)",
            }}
          >
            <span className="font-mono text-[11px] font-bold whitespace-nowrap" style={{ color: slLevel.color }}>
              {slLevel.label}
            </span>
          </div>
        </div>
      )}

      {/* Draggable chart area */}
      <div
        className="absolute left-0 right-0 top-0 bottom-0 overflow-hidden select-none"
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <canvas ref={canvasRef} className="block" />
        {tooltip && (() => {
          const tipW = 120;
          const clampedX = Math.min(tooltip.x, window.innerWidth - tipW - 8);
          return (
            <div className="fixed z-50 pointer-events-none" style={{ left: clampedX, top: tooltip.y }}>
              <div className={`bg-gray-900 text-[10px] font-mono px-1.5 py-0.5 rounded border border-gray-700 whitespace-nowrap shadow-lg ${tooltip.text.startsWith("Entry") ? "text-green-400" : "text-red-400"}`}>
                {tooltip.text}
              </div>
            </div>
          );
        })()}
      </div>

      {/* LTP + P&L overlay (kept between left labels and right SL label) */}
      <div className="absolute left-[102px] right-[100px] bottom-0 h-5 pointer-events-none flex items-center justify-between px-2 text-[10px] font-mono font-bold bg-gradient-to-t from-[#0a0a0a] to-transparent">
        <span style={{ color }}>{lastTick?.ltp.toFixed(2)}</span>
        {lastTick?.pnl != null && (
          <span style={{ color: lastTick.pnl >= 0 ? "#10b981" : "#ef4444" }}>
            {lastTick.pnl >= 0 ? "+" : ""}{lastTick.pnl.toFixed(2)}
          </span>
        )}
      </div>
    </div>
  );
}
