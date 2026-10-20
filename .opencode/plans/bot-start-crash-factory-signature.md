# Fix: "Start Bot" crashes silently — factory signature mismatch

## Diagnosis (confirmed statically)

`POST /api/start` returns **200** (token OK, market check OK, thread spawns). The thread then dies instantly:

1. `backend/bot_manager.py:87` — `create_streamer(...)` accepts `session_name, ce_key, pe_key, ce_strike, pe_strike, prescan_keys` — **no `selection`**, no `**kwargs` (verified via AST)
2. `backend/scheduler.py:338-346` — yesterday's selection-persistence change made `start_streaming()` pass `selection=selection` to `self.data_streamer_factory(...)` unconditionally, on **every** path (Path A pre-subscribe AND Path B)
3. → `TypeError: create_streamer() got an unexpected keyword argument 'selection'` the moment streaming starts
4. `backend/bot_manager.py:113-114` — `_bot_loop` catches it → `emit_log(f"Bot error: {e}")` → deposited into `log_buffer` only (UI log stream), **never the console** → `finally` resets `running=False`, `mode="stopped"`
5. `DataStreamer.__init__` *does* accept `selection` (verified) — the intermediate factory was the one missed piece. Yesterday's smoke test exercised `fetch_live_strikes` directly and never ran `start_streaming` → factory.

Result: console logs show only endless `GET /api/status` polls; UI shows bot immediately "not running".

## Edits

### 1. `backend/bot_manager.py` — factory accepts + forwards selection

Replace (line ~87):

```python
def create_streamer(session_name, ce_key=None, pe_key=None, ce_strike=None, pe_strike=None, prescan_keys=None):
    ds = DataStreamer(
        session_name=session_name,
        instruments=instruments,
        ce_key=ce_key,
        pe_key=pe_key,
        ce_strike=ce_strike,
        pe_strike=pe_strike,
        prescan_keys=prescan_keys,
```

with:

```python
def create_streamer(session_name, ce_key=None, pe_key=None, ce_strike=None, pe_strike=None, prescan_keys=None, selection=None):
    ds = DataStreamer(
        session_name=session_name,
        instruments=instruments,
        ce_key=ce_key,
        pe_key=pe_key,
        ce_strike=ce_strike,
        pe_strike=pe_strike,
        prescan_keys=prescan_keys,
        selection=selection,
```

(preserving the file's exact indentation — the existing block is one level deeper than shown here.)

### 2. `backend/bot_manager.py` — surface thread crashes

Currently:

```python
except Exception as e:
    self.emit_log(f"Bot error: {e}")
```

Replace with (add `import traceback` at module top):

```python
except Exception as e:
    tb = traceback.format_exc()
    self.emit_log(f"Bot error: {e}")
    self.emit_log(tb)
    print(f"[bot_manager] scheduler crashed:\n{tb}", flush=True)
```

Note: `print` is already patched by `_patch_print()` (prints to console AND mirrors into `log_buffer`), so the console will finally show the crash that today was invisible everywhere but the UI log stream.

### 3. New file `backend/test_factory_arguments.py` — regression guard

AST-parse `bot_manager.py`, find nested `create_streamer`, collect its param names. Drive the real `TradingScheduler.start_streaming()` with a recording stub factory and confirm every kwarg it passes exists in the factory signature (Path A: `prescan_keys` only; Path B: full args + `selection`). Fails loudly on any future signature drift:

```python
import ast
import inspect
from scheduler import TradingScheduler

recorded = {}

class StubStreamer:
    def run(self): pass
    def close(self): pass

def recorded_factory(*args, **kwargs):
    recorded.update(kwargs)
    return StubStreamer()

s = TradingScheduler(recorded_factory)
s.log = lambda msg: None

s.start_streaming(prescan_keys=["NSE_FO|47149"])
s.start_streaming("C", "P", ce_strike=1, pe_strike=2, selection={"ce_key": "C"})
s.start_streaming("C", "P", ce_strike=1, pe_strike=2)

src = open("bot_manager.py", encoding="utf-8-sig").read()
tree = ast.parse(src)
factory_params = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "create_streamer":
        factory_params = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]

assert factory_params, "create_streamer not found in bot_manager.py"

missing = [k for k in recorded if k not in factory_params]
assert not missing, f"start_streaming passes kwargs the factory refuses: {missing}"

assert "selection" in recorded, "start_streaming failed to forward selection"

print("ALL CHECKS PASSED")
```

Note: `bot_manager.py` starts with a BOM — read with `encoding="utf-8-sig"`. `TradingScheduler` takes the factory positionally (same call form `bot_manager.py` uses).

## Verification

1. `python test_factory_arguments.py` → `ALL CHECKS PASSED`
2. `python test_excursion_tracking.py` → `ALL CHECKS PASSED` (unchanged code path, sanity)
3. `python test_four_slots.py` → passes
4. Import check of `bot_manager` + `scheduler` (server.py boot path)
5. AST re-check: `create_streamer` params now include `selection`
6. User restarts app (`node dev.js` or however they run it), clicks Start; confirm UI log stream shows `🚀 Bot Started` and console now shows scheduler lines via patched print

## Notes

- No frontend changes; `tsc`/`next build` unaffected.
- If IST time is still before 15:30 on restart, today's session is recoverable.
- `settings.json` trailing values became strings (`"5"`) at some point (a UI save likely rewrote it) — unrelated to this crash; the scheduler tolerates strings (`int(...)` coercions). Leave as is.
