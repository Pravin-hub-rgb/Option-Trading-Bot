# Replace PriceDiagram with lightweight-charts

## Phase 1: Setup
- [x] Create branch `feat/lightweight-charts-chart`
- [x] `bun install lightweight-charts` in `frontend/`
- [x] Verify install in `package.json`

## Phase 2: Rewrite PriceDiagram.tsx
- [x] Imports — `createChart`, `ColorType`, `AreaSeries`, `IPriceLine` from `lightweight-charts`
- [x] Props interface — keep identical (ticks, entryPrice, currentSl, tpLevels, onSlChange, isTrading, etc.)
- [x] Tick timestamp converter — `"HH:MM:SS.mmm"` -> unix seconds
- [x] Chart setup — dark theme: bg `#0a0a0a`, text `#94a3b8`, grid `#1e293b`
- [x] AreaSeries — LTP ticks with gradient fill (`topColor`/`bottomColor`)
- [x] Price line refs — entryLineRef, slLineRef, ghostSlLineRef, tpLineRefs[], belowLineRefs[]
- [x] Entry price line — gray dashed, axisLabelVisible, title
- [x] Initial SL ghost line — gray dashed, always visible, title
- [x] Current SL line — red solid, draggable
- [x] TP level lines — green dashed
- [x] Below-SL lines — gray dashed, initialSl - (i+1)*slStep
- [x] Price line lifecycle — create on mount, remove+recreate on prop change, cleanup on unmount
- [x] Initial data load — `series.setData()` with all historical ticks
- [x] Real-time updates — `series.update()` for each new tick
- [x] Auto-scroll — `scrollToRealTime()` gated by atEndRef
- [x] Resize — ResizeObserver -> `chart.applyOptions({width})`
- [x] LTP + PnL overlay — bottom bar div (same as current)
- [x] Cleanup — `chart.remove()` on unmount

## Phase 3: SL Drag Feature
- [x] Drag overlay div — positioned via `series.priceToCoordinate(currentSl)`
- [x] Red visible line — 2px centered in overlay
- [x] mousedown — start drag, freeze cursor
- [x] mousemove — `coordinateToPrice()`, clamp [0.05, lastLtp - 1]
- [x] mouseup — remove old SL line, create new, call onSlChange
- [x] Ghost SL stays fixed during drag

## Phase 4: Missing Features Fixed
- [x] Entry/exit diamond markers — SVG `<polygon>` divs positioned via `timeToCoordinate()` + `priceToCoordinate()`
- [x] Tooltip on marker hover — shows "Entry HH:MM" / "Exit HH:MM" on mouseenter
- [x] Gradient fill — switched from `LineSeries` to `AreaSeries` with `topColor`/`bottomColor`
- [x] Left-side labels — HTML overlay divs via `priceToCoordinate()` for Entry, TPs, ghost SL, below-SL
- [x] Left labels re-render on scroll via `setScrollTick` state counter on `visibleLogicalRangeChange`

## Phase 5: Cleanup & Verify
- [x] Old canvas PriceDiagram (549 lines) replaced (now ~530 lines with all features)
- [x] TerminalQuadrant.tsx — zero changes
- [x] `npx tsc --noEmit` — 0 type errors
- [x] `npx next build` — compiled successfully (pre-existing `/history` page error unrelated)
- [ ] Test all 4 slots render (manual — start dev server)
- [ ] Test SL drag end-to-end (manual)
- [ ] Test entry/exit markers appear at correct positions (manual)
- [ ] Test tooltip shows on marker hover (manual)
- [ ] Test after market close (manual)
- [ ] Test idle state (manual)
