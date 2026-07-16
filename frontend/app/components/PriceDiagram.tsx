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

export default function PriceDiagram({ ticks, entryPrice, currentSl, width = 280, height = 160 }: Props) {
  if (ticks.length < 2 || entryPrice === null) {
    return (
      <div className="flex items-center justify-center text-[#64748b] text-xs h-[160px]">
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

  return (
    <svg width={width} height={height} className="w-full">
      {/* Entry line */}
      <line
        x1={pad}
        y1={entryY}
        x2={width - pad}
        y2={entryY}
        stroke="#64748b"
        strokeWidth={1}
        strokeDasharray="4 2"
      />
      <text x={width - pad - 4} y={entryY - 4} fill="#64748b" fontSize={9} textAnchor="end">
        ENTRY {entryPrice.toFixed(2)}
      </text>

      {/* SL line */}
      {slY !== null && (
        <line
          x1={pad}
          y1={slY}
          x2={width - pad}
          y2={slY}
          stroke="#ef4444"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
      )}

      {/* Price path */}
      <path d={pathD} fill="none" stroke="#6366f1" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />

      {/* Glow effect on latest point */}
      <circle cx={lastX} cy={lastY} r={4} fill="#6366f1" opacity={0.3} />
      <circle cx={lastX} cy={lastY} r={2} fill="#6366f1" />
    </svg>
  );
}
