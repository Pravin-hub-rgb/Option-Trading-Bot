Chalo dono kaam karte hain — pehle web pe check karta hoon ki trading-bot type codebases mein "dead code / cleanup" audit kaise professionally kiya jaata hai, phir apne actual code pe wahi lens laga ke concrete list deta hoon.Good context — paper trading hone ki wajah se pehle wale #1/#2 (order execution, feed-gap protection) ki urgency kam ho gayi, wo "jab real money jaoge tab handle karna" wali list mein chale gaye. Ab professional dead-code-audit format mein (jaisa serious tech-debt audits karte hain — severity + confidence + effort tag ke saath) apna poora review deta hoon:

## 🔴 Sabse pehle — ye "cleanup" nahi, genuine bug lagta hai

**`data_streamer.py` → `_broadcast_tick()`:**
```python
"tp_levels": pm.get_tp_levels(current_ltp=ltp) if in_pos else [],
```

Maine `position_manager.py` poora dekha — usmein **`get_tp_levels` method exist hi nahi karta**. Methods jo hain: `is_in_position`, `open_position`, `update_trailing_sl`, `check_exit`, `close_position`, `get_current_state`, `get_current_sl`. Bas itne.

Agar ye file wahi hai jo actually run ho rahi hai, toh **har tick jab position open ho** (`in_pos=True`), ye line `AttributeError` throw karegi. Chunki `on_message()` poora `try/except` mein wrapped hai:
```python
except Exception as e:
    print(f"Error processing message: {e}")
```
Ye error **silently console mein print ho ke gum ho jaayegi** — aur us tick ke liye `_broadcast_tick` kabhi complete hi nahi hoga, matlab **frontend ko wo tick kabhi pahunchi hi nahi** jab tak position open thi.

Ye tumhare display-gap wale investigation se directly juda ho sakta hai — agar random ticks har baar crash ho rahe hain jab position open hai, toh `ticks[]` array mein gaps ban sakte hain jo humne dekhe the.

**Question:** kya ye method kisi aur jagah define hai jo maine nahi dekha (maybe ek dusri class mein, ya monkeypatch se), ya genuinely missing hai? Console logs check karo — agar wahan baar-baar `Error processing message: 'PositionManager' object has no attribute 'get_tp_levels'` dikh raha hai, toh confirm ho jayega.

## Dead Code — Confidence High

| Finding | File | Evidence |
|---|---|---|
| `stats` dict (total_trades, wins, losses, win_rate, total_pnl) | `bot_manager.py` | Init hota hai, **kabhi update hi nahi hota** — poori trading session mein `total_pnl` hamesha `0.0` rehta hai. AppHeader isko use bhi nahi karta (wo apna khud ka sum banata hai). Poora `stats` object dead weight hai. |
| `tickData.pnl` | `TerminalQuadrant.tsx` | Set hota hai (tick + entry + exit teeno jagah), **kahin bhi render nahi hota** — `PriceDiagram` sirf `lastTick.pnl` use karta hai. (Ye wahi cheez hai jo humne P&L discrepancy mein diagnose ki thi — display ka fix yahi dead state ko "alive" banana hoga.) |
| `synced` state | `TerminalQuadrant.tsx` | `setSynced(true)` call hoti hai, `synced` variable **kahin read hi nahi hoti** JSX mein. Piece of state jo pura hi useless hai. |
| `broadcast()` method | `live_feed_server.py` | Ek poora duplicate broadcast implementation (`async def broadcast`) jo direct loop karta hai clients pe — but poore codebase mein sirf `broadcast_sync()` (jo queue-based `_do_broadcast` use karta hai) call hoti hai. `broadcast()` method **kabhi invoke hi nahi hoti**. |
| `get_current_state()` | `position_manager.py` | Method defined hai, kisi bhi uploaded file mein iska call nahi mila. |
| `get_reference_info()` | `red_candle_high_break.py` | Same — defined, kahin called nahi dikha. |
| `debug` param | `candle.py` | `CandleAggregator(symbol, debug=False)` — `self.debug` set hota hai, **kabhi kahin check nahi hota** (koi `if self.debug:` nahi hai). |
| `current_session` | `scheduler.py` | Set hoti hai `start_streaming()` mein, kahin read nahi hoti. |

## Duplication (DRY violation) — High confidence

**`TerminalQuadrant.tsx`'s pehla `useEffect`** — poora `if (pos.state === "in_position") {...} else if (exited...) {...}` block **literally do baar copy-paste** hai — ek baar `initialPos` prop path ke liye, ek baar fallback `fetch()` ke andar. Ek helper function (`applyPosState(pos)`) banake dono jagah call karna chahiye — abhi agar kal isme koi field add/fix karni ho (jaisa humne `pnl` freeze wale fix mein karna hoga), **do jagah change karna padega**, aur ek jagah miss hone ka risk hai.

## "Looks bad but is actually fine" (mat chhedo ye)

- `candle.py` mein `feed_time`-based candle-close check (wall-clock ki jagah) — thoda unusual lagta hai pehli nazar mein, but comment khud explain karta hai ki ye ek intentional fix hai (partial-candle-commit bug se bachne ke liye). **Isse touch mat karo.**
- `check_exit()` phle call hota hai `update_trailing_sl()` se pehle `process_tick` mein — order ulta lagta hai, but maine verify kiya: jab LTP girta hai (exit trigger), `highest_price` update nahi hoti waise bhi, toh order se koi farak nahi padta. **Fine hai.**

## Quick wins (low effort, karne layak)

- [ ] `bot_manager.py`'s `stats` dict — ya toh actually update karo (`exit_position` se `on_trade_closed` callback bhej ke) ya poora hata do agar use nahi karna
- [ ] `TerminalQuadrant.tsx` ka `synced` state hata do
- [ ] `live_feed_server.py` ka unused `broadcast()` method hata do (sirf `broadcast_sync` rakho)
- [ ] `candle.py` ka `debug` param — ya to use karo ya hata do

## Open question for you

`get_tp_levels` wala part — pehle confirm karo ki ye genuine crash ho raha hai ya nahi (console logs check karke). Agar haan, toh ye "cleanup" se pehle "fix" ki list mein sabse upar jaana chahiye, kyunki ye potentially wahi cheez hai jo tumhare original P&L-mismatch investigation ko aur bhi bada bana sakti hai.