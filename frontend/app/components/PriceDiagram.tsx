"use client";

interface Tick {
  timestamp: string;
  ltp: number;
}

interface Props {
  ticks: Tick[];
  entryPrice: number | null;
  currentSl: number | null;
  width?: number;
  height?: number;
}

export default function PriceDiagram({ ticks, entryPrice, currentSl, width = 280, height = 180 }: Props) {
  if (ticks.length < 2 || entryPrice === null) {
    return (
      <div className="flex items-center justify-center text-[#64748b] text-xs" style={{ height }}>
        No price data
      </div>
    );
  }

  const prices = ticks.map((t) => t.ltp);
  const minP = Math.min(...prices, entryPrice, currentSl ?? entryPrice);
  const maxP = Math.max(...prices, entryPrice, currentSl ?? entryPrice);
  const range = maxP - minP || 1;

  const pad = 20;
  const chartW = width - pad * 2;
  const chartH = height - pad * 2;

  const yPos = (p: number) => pad + chartH - ((p - minP) / range) * chartH;
  const xPos = (i: number) => pad + (i / (ticks.length - 1)) * chartW;

  const pathD = ticks
    .map((t, i) => `${i === 0 ? "M" : "L"}${xPos(i).toFixed(1)},${yPos(t.ltp).toFixed(1)}`)
    .join("");

  const entryY = yPos(entryPrice);
  const slY = currentSl !== null ? yPos(currentSl) : null;

  const lastTick = ticks[ticks.length - 1];
  const lastX = xPos(ticks.length - 1);
  const lastY = yPos(lastTick.ltp);

  const gridPcts = [0.75, 0.5, 0.25];
  const gridLabels = [
    `+${((maxP - minP) * 0.75 + minP - entryPrice).toFixed(1)}`,
    `ENTRY (0)`,
    `${((maxP - minP) * 0.25 + minP - entryPrice).toFixed(1)}`,
  ];

  const isCe = entryPrice >= (currentSl ?? entryPrice);

  return (
    <div className="relative price-line-gradient border-b border-white/5 rounded-t-lg overflow-hidden" style={{ height }}>
      {/* Gridlines */}
      <div className="absolute inset-0 grid grid-rows-4 pointer-events-none">
        {gridPcts.map((pct, i) => {
          const y = pad + chartH * (1 - pct);
          const isEntry = i === 1;
          return (
            <div
              key={i}
              className="relative"
              style={{ position: "absolute", top: y - 12, left: 0, right: 0, height: 24 }}
            >
              <div
                className={`absolute inset-x-0 top-1/2 ${isEntry ? "border-t border-indigo-500/30 bg-indigo-500/[0.02]" : "border-t border-white/[0.03]"}`}
              />
              <span
                className={`absolute left-2 top-1/2 -translate-y-1/2 text-[10px] font-mono ${
                  isEntry ? "text-indigo-400/80 font-bold" : "text-gray-600"
                }`}
              >
                {gridLabels[i]}
              </span>
            </div>
          );
        })}
      </div>

      {/* Price path SVG */}
      <svg width={width} height={height} className="absolute inset-0 w-full h-full">
        <defs>
          <linearGradient id={`grad-${isCe ? "ce" : "pe"}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isCe ? "#6366f1" : "#f59e0b"} stopOpacity="0.08" />
            <stop offset="100%" stopColor={isCe ? "#6366f1" : "#f59e0b"} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Gradient fill under path */}
        <path
          d={`${pathD} L${xPos(ticks.length - 1)},${pad + chartH} L${pad},${pad + chartH} Z`}
          fill={`url(#grad-${isCe ? "ce" : "pe"})`}
        />

        {/* Entry line */}
        <line x1={pad} y1={entryY} x2={width - pad} y2={entryY} stroke="#64748b" strokeWidth={1} strokeDasharray="4 2" />
        <text x={width - pad - 4} y={entryY - 4} fill="#64748b" fontSize={9} fontFamily="monospace" textAnchor="end">
          ENTRY {entryPrice.toFixed(2)}
        </text>

        {/* SL line */}
        {slY !== null && (
          <>
            <line x1={pad} y1={slY} x2={width - pad} y2={slY} stroke="#ef4444" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />
            <text x={width - pad - 4} y={slY - 4} fill="#ef4444" fontSize={9} fontFamily="monospace" textAnchor="end">
              SL {currentSl!.toFixed(2)}
            </text>
          </>
        )}

        {/* Price path */}
        <path
          d={pathD}
          fill="none"
          stroke={isCe ? "#6366f1" : "#f59e0b"}
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="drop-shadow-[0_0_8px_rgba(99,102,241,0.5)]"
        />

        {/* Pulsing dot on latest point */}
        <circle cx={lastX} cy={lastY} r={5} fill={isCe ? "#6366f1" : "#f59e0b"} opacity={0.3} className="pulse-dot" />
        <circle cx={lastX} cy={lastY} r={2.5} fill={isCe ? "#6366f1" : "#f59e0b"} />
      </svg>
    </div>
  );
}