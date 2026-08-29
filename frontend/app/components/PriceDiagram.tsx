"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { createChart, ColorType, AreaSeries, type IChartApi, type ISeriesApi, type IPriceLine, type Time } from "lightweight-charts";

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
  realizedPnl?: number | null;
  onSlChange?: (newSl: number) => void;
  isTrading?: boolean;
}

function tickTime(ts: string): number {
  const today = new Date().toISOString().slice(0, 10);
  return Math.floor(new Date(`${today}T${ts}`).getTime() / 1000);
}

function createPriceLineOptions(price: number, color: string, title: string, dashed = true): Parameters<ISeriesApi<"Area">["createPriceLine"]>[0] {
  return {
    price,
    color,
    lineWidth: 1,
    lineStyle: dashed ? 2 : 0,
    axisLabelVisible: true,
    title,
  };
}

export default function PriceDiagram({
  ticks,
  entryPrice,
  entryTime,
  exitTime,
  exitPrice,
  currentSl,
  tpLevels = [],
  belowSlCount = 1,
  slStep = 5,
  color = "#6366f1",
  realizedPnl,
  onSlChange,
  isTrading,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  const entryLineRef = useRef<IPriceLine | null>(null);
  const slLineRef = useRef<IPriceLine | null>(null);
  const ghostSlLineRef = useRef<IPriceLine | null>(null);
  const tpLineRefs = useRef<IPriceLine[]>([]);
  const belowLineRefs = useRef<IPriceLine[]>([]);

  const atEndRef = useRef(true);
  const lastTickCountRef = useRef(0);
  const slOverrideRef = useRef<number | null>(null);
  const prevEntryTimeRef = useRef<string | null | undefined>(null);

  const slDragRef = useRef({ active: false, startY: 0, startPrice: 0 });
  const [slDragState, setSlDragState] = useState({ active: false, price: 0 });
  const isDraggingRef = useRef(false);
  const slFiredRef = useRef(false);

  const [, setScrollTick] = useState(0);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string; color: string } | null>(null);
  const [chartReady, setChartReady] = useState(false);

  const displaySl = slDragState.active ? slDragState.price : currentSl;

  const getMarkerXY = useCallback(
    (tickTimestamp: string, price: number, fallbackToLastTick = false): { x: number; y: number } | null => {
      const chart = chartRef.current;
      const series = seriesRef.current;
      if (!chart || !series) return null;

      let time = tickTime(tickTimestamp) as Time;
      let x = chart.timeScale().timeToCoordinate(time);
      let y = series.priceToCoordinate(price);

      if (fallbackToLastTick) {
        const data = series.data();
        if (data.length > 0) {
          const lastPoint = data[data.length - 1] as { time: Time; value: number };
          if (x === null) {
            x = chart.timeScale().timeToCoordinate(lastPoint.time);
          }
          y = series.priceToCoordinate(lastPoint.value);
        }
      }

      if (x === null || y === null) return null;
      return { x, y };
    },
    []
  );

  useEffect(() => {
    if (!containerRef.current) return;

    const w = containerRef.current.clientWidth || 400;
    const h = containerRef.current.clientHeight || 200;

    const chart = createChart(containerRef.current, {
      width: w,
      height: h,
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#94a3b8",
        fontFamily: '"SF Mono", "Fira Code", monospace',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: "#6366f1", width: 1, style: 2, labelBackgroundColor: "#6366f1" },
        horzLine: { color: "#6366f1", width: 1, style: 2, labelBackgroundColor: "#6366f1" },
      },
      timeScale: {
        borderColor: "#1e293b",
        timeVisible: true,
        secondsVisible: true,
        tickMarkFormatter: (time: number) => {
          const d = new Date(time * 1000);
          return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        },
      },
      rightPriceScale: {
        borderColor: "#1e293b",
        scaleMargins: {
          top: 0.43,
          bottom: 0.43,
        },
      },
      handleScroll: { vertTouchDrag: false },
    });

    chartRef.current = chart;

    const series = chart.addSeries(AreaSeries, {
      topColor: color + "40",
      bottomColor: color + "05",
      lineColor: color,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 3,
    });

    seriesRef.current = series;

    setChartReady(true);

    const ro = new ResizeObserver(([entry]) => {
      if (entry && chartRef.current) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          chartRef.current.applyOptions({ width, height });
          requestAnimationFrame(() => setScrollTick((v) => v + 1));
        }
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series || ticks.length === 0) return;

    if (ticks.length !== lastTickCountRef.current) {
      const raw = ticks.map((t) => ({
        time: tickTime(t.timestamp) as Time,
        value: t.ltp,
      }));

      const data = raw.length > 0
        ? raw.reduce<{ time: Time; value: number }[]>((acc, pt) => {
            if (acc.length === 0) {
              acc.push(pt);
              return acc;
            }
            const lastTime = acc[acc.length - 1].time as number;
            const curTime = pt.time as number;
            if (curTime > lastTime) {
              acc.push(pt);
            } else if (curTime === lastTime) {
              acc[acc.length - 1] = pt;
            }
            return acc;
          }, [])
        : raw;

      try {
        if (lastTickCountRef.current === 0 || series.data().length === 0) {
          lastTickCountRef.current = 0;
          series.setData(data);
        } else {
          const last = data[data.length - 1];
          if (last) series.update(last);
        }
      } catch {
        lastTickCountRef.current = 0;
        try { series.setData(data); } catch {}
      }

      lastTickCountRef.current = ticks.length;

      requestAnimationFrame(() => setScrollTick((v) => v + 1));

      if (atEndRef.current) {
        try { chartRef.current?.timeScale().scrollToRealTime(); } catch {}
      }
    }
  }, [ticks, chartReady]);

  useEffect(() => {
    if (prevEntryTimeRef.current === null) {
      prevEntryTimeRef.current = entryTime;
      return;
    }
    if (entryTime !== prevEntryTimeRef.current) {
      prevEntryTimeRef.current = entryTime;
      lastTickCountRef.current = 0;
      atEndRef.current = true;
      slOverrideRef.current = null;
      slFiredRef.current = false;
      isDraggingRef.current = false;
      slDragRef.current = { active: false, startY: 0, startPrice: 0 };
      setSlDragState({ active: false, price: 0 });
      if (seriesRef.current) {
        try { seriesRef.current.setData([]); } catch {}
      }
      if (chartRef.current) {
        try { chartRef.current.timeScale().resetTimeScale(); } catch {}
      }
    }
  }, [entryTime]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series || entryPrice === null) return;

    if (entryLineRef.current) {
      try { series.removePriceLine(entryLineRef.current); } catch {}
    }
    entryLineRef.current = series.createPriceLine(
      createPriceLineOptions(entryPrice, "#3b82f6", "Entry")
    );

    return () => {
      if (entryLineRef.current) {
        try { series.removePriceLine(entryLineRef.current); } catch {}
        entryLineRef.current = null;
      }
    };
  }, [entryPrice]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    if (slOverrideRef.current !== null && currentSl === slOverrideRef.current) {
      slOverrideRef.current = null;
    }

    if (slLineRef.current) {
      try { series.removePriceLine(slLineRef.current); } catch {}
      slLineRef.current = null;
    }

    const effectiveSl = slDragState.active ? slDragState.price : (slOverrideRef.current ?? currentSl);

    if (effectiveSl !== null) {
      slLineRef.current = series.createPriceLine({
        price: effectiveSl,
        color: "#ef4444",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "SL",
      });
    }

    return () => {
      if (slLineRef.current) {
        try { series.removePriceLine(slLineRef.current); } catch {}
        slLineRef.current = null;
      }
    };
  }, [currentSl, slDragState.active, slDragState.price]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series || entryPrice === null) return;

    if (ghostSlLineRef.current) {
      try { series.removePriceLine(ghostSlLineRef.current); } catch {}
      ghostSlLineRef.current = null;
    }

    ghostSlLineRef.current = series.createPriceLine(
      createPriceLineOptions(entryPrice - slStep, "#94a3b8", `-${slStep}`)
    );

    return () => {
      if (ghostSlLineRef.current) {
        try { series.removePriceLine(ghostSlLineRef.current); } catch {}
        ghostSlLineRef.current = null;
      }
    };
  }, [entryPrice, slStep]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    tpLineRefs.current.forEach((line) => {
      try { series.removePriceLine(line); } catch {}
    });
    tpLineRefs.current = [];

    tpLevels.forEach((tp, i) => {
      const offset = entryPrice !== null ? Math.round(tp - entryPrice) : i + 1;
      const line = series.createPriceLine(
        createPriceLineOptions(tp, "#10b981", `+${offset}`)
      );
      tpLineRefs.current.push(line);
    });

    return () => {
      tpLineRefs.current.forEach((line) => {
        try { series.removePriceLine(line); } catch {}
      });
      tpLineRefs.current = [];
    };
  }, [tpLevels]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series || entryPrice === null) return;

    belowLineRefs.current.forEach((line) => {
      try { series.removePriceLine(line); } catch {}
    });
    belowLineRefs.current = [];

    for (let i = 1; i <= belowSlCount; i++) {
      const price = entryPrice - (i + 1) * slStep;
      const line = series.createPriceLine(
        createPriceLineOptions(price, "#94a3b8", `-${(i + 1) * slStep}`)
      );
      belowLineRefs.current.push(line);
    }

    return () => {
      belowLineRefs.current.forEach((line) => {
        try { series.removePriceLine(line); } catch {}
      });
      belowLineRefs.current = [];
    };
  }, [entryPrice, belowSlCount, slStep]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const handleScroll = () => {
      const ts = chart.timeScale();
      const range = ts.getVisibleLogicalRange();
      if (!range) return;

      const data = seriesRef.current?.data();
      if (!data || data.length === 0) return;

      const lastBar = data[data.length - 1] as { time: number };
      const isAtEnd = range.to >= (lastBar.time ?? 0) - 2;
      atEndRef.current = isAtEnd;

      setScrollTick((v) => v + 1);
    };

    chart.timeScale().subscribeVisibleLogicalRangeChange(handleScroll);
    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleScroll);
    };
  }, []);

  const handleSlDragStart = useCallback(
    (e: React.MouseEvent) => {
      if (!currentSl || !onSlChange || !isTrading) return;
      e.stopPropagation();
      e.preventDefault();

      isDraggingRef.current = true;
      slFiredRef.current = false;
      slDragRef.current = { active: true, startY: e.clientY, startPrice: currentSl };
      setSlDragState({ active: true, price: currentSl });
      document.body.style.cursor = "ns-resize";
      document.body.style.userSelect = "none";
    },
    [currentSl, onSlChange, isTrading]
  );

  useEffect(() => {
    if (!slDragState.active) return;

    const containerEl = containerRef.current;
    const series = seriesRef.current;
    if (!containerEl || !series) return;

    function onMove(e: MouseEvent) {
      if (!slDragRef.current.active) return;

      const rect = containerEl!.getBoundingClientRect();
      const relY = e.clientY - rect.top;
      const newPrice = series!.coordinateToPrice(relY) ?? slDragRef.current.startPrice;

      const lastLtp = ticks[ticks.length - 1]?.ltp;
      const upperBound = lastLtp ? lastLtp - 1 : (entryPrice ?? 100) - 0.5;
      const clamped = Math.max(0.05, Math.min(newPrice, upperBound));

      setSlDragState((prev) => ({ ...prev, price: clamped }));
    }

    function onUp() {
      if (!slDragRef.current.active || slFiredRef.current) return;
      slFiredRef.current = true;
      slDragRef.current.active = false;
      isDraggingRef.current = false;

      document.body.style.cursor = "";
      document.body.style.userSelect = "";

      setSlDragState((prev) => {
        if (onSlChange && currentSl !== null && Math.abs(prev.price - currentSl) > 0.01) {
          slOverrideRef.current = prev.price;
          onSlChange(prev.price);
        }
        return { active: false, price: prev.price };
      });
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [slDragState.active, ticks, currentSl, entryPrice, onSlChange]);

  const entryXY = entryTime && entryPrice != null ? getMarkerXY(entryTime, entryPrice) : null;
  const exitXY = exitTime && exitPrice != null ? getMarkerXY(exitTime, exitPrice, true) : null;
  const entryShort = entryTime ? `${+entryTime.slice(0, 2)}:${entryTime.slice(3, 5)}` : "";
  const exitShort = exitTime ? `${+exitTime.slice(0, 2)}:${exitTime.slice(3, 5)}` : "";

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {entryPrice === null ? (
        <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-xs tracking-wider uppercase pointer-events-none">
          Idle
        </div>
      ) : (
        <>
      {/* Entry diamond marker */}
      {entryXY && (
        <div
          className="absolute z-20 pointer-events-auto cursor-pointer"
          style={{ left: entryXY.x - 7, top: entryXY.y - 7, width: 14, height: 14 }}
          onMouseEnter={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            setTooltip({ x: rect.left + rect.width / 2, y: rect.top - 8, text: `Entry ${entryShort}`, color: "#22c55e" });
          }}
          onMouseLeave={() => setTooltip(null)}
        >
          <svg width="14" height="14" viewBox="0 0 14 14">
            <polygon points="7,0 14,7 7,14 0,7" fill="#22c55e" stroke="#fff" strokeWidth="1.5" />
          </svg>
        </div>
      )}

      {/* Exit diamond marker */}
      {exitXY && (
        <div
          className="absolute z-20 pointer-events-auto cursor-pointer"
          style={{ left: exitXY.x - 7, top: exitXY.y - 7, width: 14, height: 14 }}
          onMouseEnter={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            setTooltip({ x: rect.left + rect.width / 2, y: rect.top - 8, text: `Exit ${exitShort}`, color: "#ef4444" });
          }}
          onMouseLeave={() => setTooltip(null)}
        >
          <svg width="14" height="14" viewBox="0 0 14 14">
            <polygon points="7,0 14,7 7,14 0,7" fill="#ef4444" stroke="#fff" strokeWidth="1.5" />
          </svg>
        </div>
      )}

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none"
          style={{ left: tooltip.x - 50, top: tooltip.y - 28 }}
        >
          <div
            className="bg-gray-900 text-[10px] font-mono px-1.5 py-0.5 rounded border border-gray-700 whitespace-nowrap shadow-lg"
            style={{ color: tooltip.color }}
          >
            {tooltip.text}
          </div>
        </div>
      )}

      {/* SL drag visual line */}
      {currentSl !== null && isTrading && slDragState.active && (
        <div
          className="absolute left-0 right-0 z-20 pointer-events-none"
          style={{
            top: seriesRef.current?.priceToCoordinate(slDragState.price) ?? 0,
            height: "2px",
            backgroundColor: "#ef4444",
            opacity: 0.9,
          }}
        />
      )}

      {/* SL drag handle */}
      {currentSl !== null && isTrading && (
        <div
          className="absolute left-0 right-0 z-30"
          style={{
            top: (seriesRef.current?.priceToCoordinate(displaySl ?? currentSl) ?? 0) - 19,
            height: "40px",
            cursor: slDragState.active ? "ns-resize" : "grab",
          }}
          onMouseDown={handleSlDragStart}
        />
      )}
        </>
      )}
    </div>
  );
}
