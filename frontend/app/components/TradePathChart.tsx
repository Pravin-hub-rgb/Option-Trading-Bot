/**
 * The real entry-to-exit tick path for one trade, with a stop parked at +5
 * replayed over it.
 *
 * This is the evidence behind the shadow study. The argument for the idea
 * rested on "it peaked at 8 but only banked 1" - which is hindsight, because
 * option prices travel 5 -> 4.5 -> 6 -> 8 and a stop at +5 fires on that 4.5.
 * Drawing the actual ticks makes that visible instead of arguable.
 *
 * Read-only. Nothing here changes how the bot trades.
 */
import { useEffect, useRef, useState } from "react";
import {
  LineSeries,
  createChart,
  ColorType,
  LineStyle,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
} from "lightweight-charts";
import { Icon } from "@iconify/react";

export interface TradePath {
  available: boolean;
  reason?: string;
  ticks?: number[];
  entry_price: number;
  exit_price: number | null;
  pnl: number | null;
  mfe_points: number | null;
  dips_below_bank: number | null;
  sim_stop_price: number;
  sim_armed_at: number | null;
  sim_exit_idx: number | null;
  sim_exit_points: number | null;
  sim_hit_stop: boolean;
  exit_buffer_pts: number;
}

const GREEN = "#10b981";
const AMBER = "#f59e0b";
const SLATE = "#64748b";

export default function TradePathChart({
  tradeId,
}: {
  tradeId: number;
}) {
  const [data, setData] = useState<TradePath | null>(null);
  const [loading, setLoading] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const price = useRef<ISeriesApi<"Line"> | null>(null);
  const sim = useRef<ISeriesApi<"Line"> | null>(null);
useEffect(() => {
    let alive = true;
    setLoading(true);
    setData(null);
    fetch(`/api/trades/${tradeId}/path`)
      .then((r) => r.json())
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [tradeId]);

  useEffect(() => {
    if (!data?.available || !data.ticks?.length || !box.current) return;

    const c = createChart(box.current, {
      width: box.current.clientWidth,
      height: 220,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", visible: false },
      crosshair: { mode: CrosshairMode.Normal },
      handleScroll: false,
      handleScale: false,
    });
    chart.current = c;

    price.current = c.addSeries(LineSeries, {
      color: "#e2e8f0",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    // The hypothetical stop: flat from the tick it was armed until the tick it
    // fired, then dropped to the fill price.
    sim.current = c.addSeries(LineSeries, {
      color: data.sim_hit_stop ? AMBER : GREEN,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    // lightweight-charts needs strictly ascending, unique times, so ticks are
    // mapped onto a plain integer index axis rather than wall-clock time.
    const p: LineData<Time>[] = data.ticks.map((v, i) => ({
      time: i as Time,
      value: v,
    }));
    price.current.setData(p);

    if (data.sim_armed_at != null && data.sim_exit_idx != null) {
      const line: LineData<Time>[] = [];
      for (let i = data.sim_armed_at; i <= data.sim_exit_idx; i++) {
        line.push({ time: i as Time, value: data.sim_stop_price });
      }
      if (data.sim_exit_idx < p.length - 1 && data.sim_exit_points != null) {
        line.push({
          time: data.sim_exit_idx as Time,
          value: data.sim_exit_points + data.entry_price,
        });
      }
      sim.current.setData(line);
    }

    const marks = [
      { price: data.entry_price, color: SLATE, title: "Entry" },
      {
        price: data.entry_price + 1,
        color: "rgba(100,116,139,0.7)",
        title: "Live stop (entry+1)",
      },
      {
        price: data.sim_stop_price,
        color: data.sim_hit_stop ? AMBER : GREEN,
        title: "SIM stop (entry+5)",
      },
    ];
    for (const m of marks) {
      price.current.createPriceLine({
        price: m.price,
        color: m.color,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: m.title,
      });
    }

    c.timeScale().fitContent();
    const el = box.current;
    const ro = new ResizeObserver(() => c.applyOptions({ width: el.clientWidth }));
    ro.observe(el);

    return () => {
      ro.disconnect();
      c.remove();
      chart.current = null;
      price.current = null;
      sim.current = null;
    };
  }, [data]);
if (loading) {
    return <div className="text-[11px] text-[#64748b] py-6 text-center">Loading path…</div>;
  }
  if (!data) {
    return <div className="text-[11px] text-[#ef4444] py-6 text-center">Could not load path.</div>;
  }
  if (!data.available) {
    return (
      <div className="text-[11px] text-[#64748b] py-6 text-center flex items-center justify-center gap-2">
        <Icon icon="lucide:line-chart" width={14} />
        {data.reason ?? "No tick path recorded for this trade."}
      </div>
    );
  }

  const stoppedEarly = data.sim_hit_stop;
  const simPts = data.sim_exit_points;
  const actualPts = data.pnl;
  const better = simPts != null && actualPts != null ? simPts - actualPts : null;

  return (
    <div className="space-y-2">
      <div ref={box} className="w-full" />

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px]">
        <span style={{ color: GREEN }}>
          Peak +{(data.mfe_points ?? 0).toFixed(1)} · Dips {data.dips_below_bank ?? 0} ·{" "}
          {data.ticks?.length ?? 0} ticks
        </span>
        <span style={{ color: stoppedEarly ? AMBER : GREEN }}>
          {stoppedEarly
            ? `SIM stop fired at tick ${data.sim_exit_idx} → +${simPts?.toFixed(2)} pts`
            : "SIM stop never hit → same as live"}
        </span>
        {better != null && Math.abs(better) > 0.01 && (
          <span style={{ color: better > 0 ? GREEN : "#ef4444" }}>
            {better > 0 ? "better by" : "worse by"} {Math.abs(better).toFixed(2)} pts
          </span>
        )}
      </div>

      <p className="text-[10px] text-[#64748b] leading-relaxed">
        {stoppedEarly ? (
          <>
            The dashed line is where a stop parked at <b className="text-white">entry+5</b> would have
            fired on the <i>real</i> ticks — the price traded back through it before reaching its peak.
            Peak-based maths would have claimed +{(data.mfe_points ?? 0).toFixed(1)} here; the replay says{" "}
            +{simPts?.toFixed(2)}. That gap is exactly why the old numbers looked too good.
          </>
        ) : (
          <>
            A stop parked at <b className="text-white">entry+5</b> would never have been hit on this path,
            so parking it there changes nothing. This is the case the idea is meant to help — and here it
            does, for free.
          </>
        )}
      </p>
    </div>
  );
}