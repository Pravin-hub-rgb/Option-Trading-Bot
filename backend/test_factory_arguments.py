"""Regression: scheduler.start_streaming must only pass kwargs the streamer
factory accepts. On 20 Oct 2026 every bot start crashed inside the thread with
'TypeError: create_streamer() got an unexpected keyword argument selection'
because the factory in bot_manager._bot_loop had not received the new
`selection` parameter, and the crash only surfaced in the UI log buffer.

This drives the REAL scheduler with a recording stub factory, then verifies
against the AST of bot_manager.py that every forwarded kwarg exists in the
production create_streamer signature.
"""

import ast
from scheduler import TradingScheduler

recorded = {}


class StubStreamer:
    def run(self):
        pass

    def close(self):
        pass


def recording_factory(*args, **kwargs):
    recorded.update(kwargs)
    return StubStreamer()


s = TradingScheduler(recording_factory)
s.log = lambda msg: None

s.start_streaming(prescan_keys=["NSE_FO|47149"])
assert recorded.get("prescan_keys") == ["NSE_FO|47149"], recorded
assert "selection" in recorded, recorded

recorded.clear()
s.start_streaming("CE_KEY", "PE_KEY", ce_strike=1, pe_strike=2, selection={"ce_key": "CE_KEY"})
assert recorded.get("selection") == {"ce_key": "CE_KEY"}, recorded

recorded.clear()
s.start_streaming("CE_KEY", "PE_KEY", ce_strike=1, pe_strike=2)
assert recorded.get("selection") is None, recorded

src = open("bot_manager.py", encoding="utf-8-sig").read()
tree = ast.parse(src)
factory_params = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "create_streamer":
        factory_params = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]

assert factory_params, "create_streamer not found in bot_manager.py"

missing = [k for k in recorded if k not in factory_params]
assert not missing, f"start_streaming passes kwargs the factory refuses: {missing}"
assert "session_name" in factory_params, factory_params

print("ALL CHECKS PASSED")
print(f"create_streamer params: {', '.join(factory_params)}")
