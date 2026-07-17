# Trailing Stop Loss - Review Notes

**Date:** 11 Feb 2026 (Reviewed 17 Jul 2026)  
**Status:** ✅ Reviewed — Intended Behavior, No Fix Needed

---

## Review Outcome — Intended Behavior

The trailing SL uses **only tick LTP** by design. The OHLC candle high is **not usable** for trailing SL because:

1. **Candle high is only known after the candle closes** — by 1+ minute later, the price action is already past. You can't react to a candle's high until that minute finishes.
2. **Using candle high for SL would require looking into the future** — the 13:52 candle's high wasn't known until 13:53. By then the price had already retraced to 104.90. You can't set a trailing SL at 110.50 based on future data.
3. **Tick LTP is the only real-time price source** — it's the correct input for a real-time trailing SL.

### Why the Example Trade is Not a Bug

```
[13:44:14] ENTRY at 100.50 | SL: 95.50
[13:49:20] SL moved to 100.50 (LTP: 105.60)     ← +5 hit, SL → 100
[13:50:34] SL moved to 105.50 (LTP: 110.55)     ← +10 hit, SL → 105
[14:10:47] EXIT at 104.90 | P&L: +4.40
```

The 13:52 candle high of 115.65 was unknown until 13:52:59 (candle close). By then, the price was already retracing. The bot correctly used tick LTPs of 110.55 (which actually hit during that candle) to move SL to 105.50.

**The SL at 105.50 was correct.** If it had been raised to 110.50 (based on candle high), the exit would not trigger until price dropped to 110.50, risking a much larger loss.

### How the 5-Point Step Trailing Works

The trailing moves in **5-point steps only**, not continuously:
- Entry 100, SL 95
- Price hits 105 → SL moves to 100 (breakeven)
- Price hits 110 → SL moves to 105
- Price hits 115 → SL moves to 110

This is by design — SL only steps up at 5-point profit milestones. A price spike to 107 does NOT move SL (still at 100). This prevents being stopped out by minor retracements.

### Formula Confirmation

```python
milestones_passed = int((profit - trailing_trigger) / trailing_step)
```

- Profit 5–9.99: `milestones_passed = 0`, SL stays at entry
- Profit 10–14.99: `milestones_passed = 1`, SL moves to entry + 5
- Profit 15–19.99: `milestones_passed = 2`, SL moves to entry + 10

The `int()` truncation is correct — it ensures SL only advances on full 5-point milestones.

---

**Status:** ✅ No fix needed. Behavior is correct and matches strategy design.