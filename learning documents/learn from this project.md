# Learn Programming From This Option Trading Bot

This document maps **196 programming concepts** across **Python**, **TypeScript**, **React**, **Next.js**, and more — each with a small standalone example and a reference to where it's used in this codebase.

---

## How to Use This

1. Pick any concept below
2. Read the short explanation
3. Run the small example to understand the concept in isolation
4. Open the referenced file/line in this project to see it used in a real trading bot

---

## Table of Contents

- [Section 1: Python — Language Fundamentals](#section-1-python--language-fundamentals)
- [Section 2: Python — Classes & OOP](#section-2-python--classes--oop)
- [Section 3: Python — Error Handling](#section-3-python--error-handling)
- [Section 4: Python — File I/O & Data](#section-4-python--file-io--data)
- [Section 5: Python — SQLite Database](#section-5-python--sqlite-database)
- [Section 6: Python — Threading](#section-6-python--threading)
- [Section 7: Python — Async / Await Concurrency](#section-7-python--async--await-concurrency)
- [Section 8: Python — HTTP & APIs (FastAPI)](#section-8-python--http--apis-fastapi)
- [Section 9: Python — WebSocket & Protobuf](#section-9-python--websocket--protobuf)
- [Section 10: TypeScript — Fundamentals](#section-10-typescript--fundamentals)
- [Section 11: React — Components, Hooks & State](#section-11-react--components-hooks--state)
- [Section 12: Next.js — App Router](#section-12-nextjs--app-router)
- [Section 13: Web APIs — Browser](#section-13-web-apis--browser)
- [Section 14: JavaScript — Collections, Math & Patterns](#section-14-javascript--collections-math--patterns)
- [Section 15: Tailwind CSS v4](#section-15-tailwind-css-v4)
- [Section 16: Architecture Patterns used in this Project](#section-16-architecture-patterns-used-in-this-project)

---

# Section 1: Python — Language Fundamentals

All examples in this section you can run in a Python file or in the Python REPL (`python` in terminal).

### 1. Variables & Basic Types (`str`, `int`, `float`, `bool`, `None`)

**What:** Variables store data. Python infers the type automatically. Core types are string (text), integer (whole number), float (decimal), boolean (True/False), and None (null/nothing).

**Small example:**
```python
name = "NIFTY"       # str
price = 100.50       # float
quantity = 2         # int
is_active = True     # bool
result = None        # NoneType (null/empty)

print(f"{name}: {price} x {quantity} = {price * quantity}")
```

**In this project:** `scheduler.py:36-137` — variables like `spot = float(data.get('last_price', 0))`, `strike` as int, `ce_list` as list, etc.

---

### 2. `if` / `elif` / `else`

**What:** Conditional execution — run different code based on conditions. `if` checks first condition, `elif` checks additional conditions, `else` runs if nothing matched.

**Small example:**
```python
pnl = 15
if pnl > 10:
    print("Big win!")
elif pnl > 0:
    print("Small win")
else:
    print("Loss")
```

**In this project:** `data_streamer.py:312-316` — checks if instrument key matches CE or PE:
```python
if instrument_key == self.CE_KEY:
    inst_type = 'CE'
elif instrument_key == self.PE_KEY:
    inst_type = 'PE'
else:
    continue
```

---

### 3. `for` loops (over lists, dicts)

**What:** Iterate over each item in a collection. Works on lists, dicts, strings, etc.

**Small example:**
```python
# Over list
strikes = [25800, 25850, 25900]
for s in strikes:
    print(s)

# Over dict
premiums = {"CE": 100, "PE": 95}
for key, value in premiums.items():
    print(f"{key}: {value}")
```

**In this project:** `scheduler.py:175` — `for entry in chain:` iterates option chain data. `data_streamer.py:310` — `for instrument_key, feed_data in feeds.items():`

---

### 4. `while` loops

**What:** Repeat code as long as a condition is true. Use when you don't know how many iterations you need.

**Small example:**
```python
count = 0
while count < 5:
    print(count)
    count += 1
```

**In this project:** `live_feed_server.py:41` — `while True:` (infinite loop for draining queue). `scheduler.py:51` — `while self.is_running:` (keep running until stop).

---

### 5. `break`, `continue`, `pass`

**What:** `break` exits the loop entirely. `continue` skips to the next iteration. `pass` does nothing (placeholder).

**Small example:**
```python
for i in range(10):
    if i == 3:
        continue    # skip 3
    if i == 7:
        break       # stop at 7
    print(i)
# Output: 0, 1, 2, 4, 5, 6
```

**In this project:** `scheduler.py:54` — `break` when seconds_left < 1. `data_streamer.py:316` — `continue` to skip unmatched instrument keys.

---

### 6. `range()`

**What:** Generate a sequence of numbers. Often used with `for` loops.

**Small example:**
```python
for i in range(5):          # 0, 1, 2, 3, 4
    print(i)
for i in range(2, 8, 2):    # 2, 4, 6 (start=2, stop=8, step=2)
    print(i)
```

**In this project:** `position_manager.py:160` — `for i in range(5)` to generate 5 take-profit levels.

---

### 7. Lists (`[]`, `.append()`, `.sort()`, slicing)

**What:** Ordered, mutable collection of items. Can hold any types.

**Small example:**
```python
trades = []
trades.append(10.5)
trades.append(-2.3)
trades.append(5.0)
trades.sort(reverse=True)  # biggest first
print(trades[:2])           # first 2 items (slicing)
```

**In this project:** `candle.py:17` — `self.listeners.append(callback)`. `data_streamer.py:265` — `i1_candles.sort(key=lambda c: int(c.get('ts', 0)), reverse=True)`

---

### 8. Dicts (`{}`, `.get()`, `.items()`, `.keys()`)

**What:** Key-value pairs. Fast lookup by key. `.get(key, default)` returns default if key missing (no error).

**Small example:**
```python
position = {"entry_price": 100, "stop_loss": 95, "pnl": None}
print(position.get("entry_price"))     # 100
print(position.get("exit_price", "N/A"))  # "N/A" (key missing)
for k, v in position.items():
    print(f"{k}: {v}")
```

**In this project:** `scheduler.py:79` — `resp.json().get('data', [])` safely gets 'data' key. `settings_db.py:33` — `for key, default in DEFAULT_SETTINGS.items():`

---

### 9. Sets (`.add()`, `.discard()`, `-=`)

**What:** Unordered collection of **unique** items. Fast membership test. `.discard()` removes without error if missing.

**Small example:**
```python
clients = set()
clients.add("ws1")
clients.add("ws2")
clients.add("ws1")     # ignored (already exists)
clients.discard("ws3") # no error even though not found
print(clients)         # {'ws1', 'ws2'}
```

**In this project:** `live_feed_server.py:11` — `self.clients = set()` to track WebSocket connections. `.discard()` at line 24 safely removes disconnected clients.

---

### 10. Functions (`def`, `return`, parameters)

**What:** Reusable block of code. Takes inputs (parameters), returns outputs.

**Small example:**
```python
def calc_pnl(entry, exit):
    return exit - entry

result = calc_pnl(100, 110)  # 10
```

**In this project:** `scheduler.py:31` — `def get_current_time_str(self):` returns formatted time string.

---

### 11. Default Parameter Values

**What:** Function parameters can have default values, making them optional when calling.

**Small example:**
```python
def create_order(symbol, quantity=1, side="BUY"):
    return f"{side} {quantity} {symbol}"

print(create_order("NIFTY"))                    # BUY 1 NIFTY
print(create_order("NIFTY", 2, "SELL"))          # SELL 2 NIFTY
```

**In this project:** `position_manager.py:7` — `def __init__(self, initial_sl_points=5, trailing_trigger=5, trailing_step=5):`

---

### 12. `*args`, `**kwargs`

**What:** `*args` captures extra positional args as a tuple. `**kwargs` captures extra keyword args as a dict. Used when you don't know how many arguments will be passed.

**Small example:**
```python
def log_all(*args, **kwargs):
    print("Positional:", args)
    print("Keyword:", kwargs)

log_all("hello", 42, key="value", count=3)
# Positional: ('hello', 42)
# Keyword: {'key': 'value', 'count': 3}
```

**In this project:** `bot_manager.py:47` — `def patched_print(*args, **kwargs):` captures everything the original `print()` receives.

---

### 13. `lambda` Functions

**What:** A one-line anonymous function. Used where you need a quick function without defining it with `def`.

**Small example:**
```python
pairs = [(1, 5), (3, 2), (2, 8)]
sorted_pairs = sorted(pairs, key=lambda x: x[1])  # sort by second element
# Result: [(3, 2), (1, 5), (2, 8)]
```

**In this project:** `scheduler.py:232` — `min(ce_candidates, key=lambda x: x['diff'])` finds strike closest to target premium. `main.py:20` — `lambda: asyncio.run(live_feed.start())` wraps async call for thread target.

---

### 14. `yield` (Generators)

**What:** A function that uses `yield` instead of `return` becomes a generator — it produces values one at a time, pausing between each. Memory-efficient for streams.

**Small example:**
```python
def count_up_to(n):
    i = 0
    while i < n:
        yield i
        i += 1

for num in count_up_to(3):
    print(num)  # 0, 1, 2
```

**In this project:** `api_server.py:147` — `yield f"data: {json.dumps(entry)}\n\n"` yields SSE events one at a time as they come in.

---

### 15. List Comprehensions

**What:** A concise way to create lists: `[expression for item in iterable if condition]`. More readable than a for loop + append.

**Small example:**
```python
numbers = [1, 2, 3, 4, 5, 6]
evens = [n for n in numbers if n % 2 == 0]
squared = [n*n for n in numbers]
# evens: [2, 4, 6]
# squared: [1, 4, 9, 16, 25]
```

**In this project:** `scheduler.py:212` — `[x for x in ce_list if x['premium'] >= 100]` filters CE strikes with premium >= 100.

---

### 16. `is` vs `==` (None checking)

**What:** `is` checks if two variables point to the **same object**. `==` checks if they have the **same value**. Use `is None` / `is not None` to check for null.

**Small example:**
```python
a = None
b = None
print(a is None)   # True (correct - use 'is' for None)
print(a == None)   # True (works but not idiomatic)
print(a is b)      # True (both point to the same None singleton)
```

**In this project:** `position_manager.py:25` — `return self.position is not None` (correct way to check None).

---

### 17. Ternary (`x if cond else y`)

**What:** A one-line `if/else` expression. Returns `x` if condition is true, `y` otherwise.

**Small example:**
```python
pnl = 10
status = "Profit" if pnl > 0 else "Loss"
```

**In this project:** `data_streamer.py:37` — `self.CE_SYMBOL = f"{ce_strike} CE" if ce_strike else ce_key`

---

### 18. Chained Comparisons (`a <= x <= b`)

**What:** Python allows chaining comparison operators, which reads like math notation. Other languages need `a <= x && x <= b`.

**Small example:**
```python
price = 100
if 90 <= price <= 110:
    print("In target range")
```

**In this project:** `data_streamer.py:83` — `s.get('market_start', '09:15') <= current_time <= s.get('market_end', '15:30')` checks if current time is within market hours.

---

### 19. `in` operator (membership)

**What:** Checks if an item exists in a collection (list, dict keys, set, string). For dicts, `in` checks keys by default.

**Small example:**
```python
settings = {"market_start": "09:15", "market_end": "15:30"}
if "market_start" in settings:
    print("Found")  # This runs (checks keys)

trades = ["CE", "PE"]
if "CE" in trades:
    print("CE trading enabled")
```

**In this project:** `settings_db.py:62` — `if key in settings:` checks if a setting exists before saving.

---

### 20. String Formatting: f-strings

**What:** Embed expressions directly in strings using `f"..."` and `{expression}`. Can include format specifiers like `:.2f` for 2 decimal places.

**Small example:**
```python
name = "NIFTY"
price = 100.5
print(f"{name} @ {price:.2f}")
# "NIFTY @ 100.50"
```

**In this project:** `scheduler.py:29` — `print(f"[{self.now()}] {message}")`. `data_streamer.py:155` — `f"...{exit_price:.2f}...P&L: {trade_summary['pnl']:.2f}..."`

---

### 21. String Methods: `.split()`, `.join()`, `.strip()`

**What:** `.split(sep)` breaks string into list. `.join(list)` merges list into string. `.strip()` removes whitespace from both ends.

**Small example:**
```python
time_str = "09:15:30"
parts = time_str.split(":")     # ['09', '15', '30']
restored = ":".join(parts)      # '09:15:30'
dirty = "  hello  "
clean = dirty.strip()           # 'hello'
```

**In this project:** `scheduler.py:35` — `parts = time_str.split(":")`. `bot_manager.py:48` — `" ".join(str(a) for a in args)` reconstructs print message.

---

### 22. `datetime`, `strftime`, `strptime`

**What:** `datetime` represents a moment in time. `strftime(format)` converts datetime → string. `strptime(string, format)` converts string → datetime.

**Small example:**
```python
from datetime import datetime
now = datetime.now()
str_now = now.strftime("%Y-%m-%d %H:%M:%S")    # "2026-07-27 14:30:00"
parsed = datetime.strptime("2026-07-27", "%Y-%m-%d")
```

**In this project:** `bot_manager.py:38` — `datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]` formats time with milliseconds. `scheduler.py:83` — `datetime.strptime(item['expiry'], "%Y-%m-%d")`.

---

### 23. `timedelta`

**What:** A duration of time. Can add/subtract from datetimes. Access `.seconds` or use `.total_seconds()`.

**Small example:**
```python
from datetime import datetime, timedelta
now = datetime.now()
later = now + timedelta(minutes=5, seconds=30)
diff = later - now
print(diff.total_seconds())   # 330.0
```

**In this project:** `position_manager.py:118` — `(exit_time - self.position['entry_time']).total_seconds()` calculates trade duration. `scheduler.py:335` — `gap.seconds` checks how long since last tick.

---

### 24. `min()`, `max()`, `sum()`, `abs()`, `round()`

**What:** Built-in functions for math/comparison. `min/max` can take a `key=` argument like `sorted()`.

**Small example:**
```python
pnls = [10, -5, 15, -2, 8]
print(max(pnls))                           # 15
print(min(pnls))                           # -5
print(sum(pnls))                           # 26
print(abs(-10))                            # 10
print(round(10.567, 2))                    # 10.57

# min/max with key=
words = ["apple", "banana", "kiwi"]
longest = max(words, key=len)              # "banana"
```

**In this project:** `scheduler.py:232` — `min(ce_candidates, key=lambda x: x['diff'])`. `trade_log_reader.py:51` — `sum(t["pnl"] for t in trades if t.get("pnl") is not None)`.

---

### 25. `sorted()`, `len()`

**What:** `sorted(iterable)` returns a new sorted list. `len(collection)` returns the number of items.

**Small example:**
```python
items = [3, 1, 4, 1, 5]
sorted_items = sorted(items)           # [1, 1, 3, 4, 5]
sorted_desc = sorted(items, reverse=True)  # [5, 4, 3, 1, 1]
print(len(items))                      # 5
```

**In this project:** `scheduler.py:81` — `sorted(set(item['expiry'] for item in data))` gets sorted unique expiry dates.

---

### 26. `enumerate`, `zip`

**What:** `enumerate(iterable)` yields (index, item) pairs. `zip(a, b)` pairs items from two iterables together.

**Small example:**
```python
# enumerate
names = ["CE", "PE"]
for i, name in enumerate(names):
    print(f"{i}: {name}")       # 0: CE, 1: PE

# zip
strikes = [25900, 25850]
premiums = [100, 95]
for s, p in zip(strikes, premiums):
    print(f"Strike {s}: {p}")   # Strike 25900: 100, Strike 25850: 95
```

**In this project:** `live_feed_server.py:54` — `for ws, result in zip(self.clients, results):` pairs each WebSocket with its send result.

---

### 27. `type()` / `isinstance()`

**What:** `type(x)` returns the type of x. `isinstance(x, Type)` checks if x is an instance of Type (also works with inheritance).

**Small example:**
```python
val = 100
print(type(val))          # <class 'int'>
print(isinstance(val, float))  # False
print(isinstance(val, (int, float)))  # True
```

**In this project:** `data_streamer.py:298` — `if isinstance(message, dict) and 'marketInfo' in message:` checks message type before processing.

---

### 28. `hasattr()`, `delattr`

**What:** `hasattr(obj, name)` checks if an object has a given attribute. `delattr(obj, name)` removes an attribute.

**Small example:**
```python
class Trader:
    def __init__(self):
        self.position = None

t = Trader()
print(hasattr(t, "position"))   # True
print(hasattr(t, "balance"))    # False
```

**In this project:** `bot_manager.py:44` — `if hasattr(builtins, "__original_print__"):` checks if print was already patched. `del builtins.__original_print__` at line 57 restores original.

---

### 29. `import`, `from x import y`

**What:** `import module` imports the whole module. `from module import name` imports just that name. `from module import name as alias` imports with a nickname.

**Small example:**
```python
import os                               # use os.path.join()
from datetime import datetime            # use datetime directly
from datetime import datetime as dt      # use dt.now()
```

**In this project:** Every file uses imports. E.g., `api_server.py:4` — `from fastapi import FastAPI, HTTPException, Request`. `data_streamer.py:1` — `import upstox_client`.

---

### 30. `if __name__ == "__main__"`

**What:** This block only runs when the file is executed directly (not when imported as a module). Allows a file to be both reusable and runnable.

**Small example:**
```python
# my_script.py
def greet(name):
    return f"Hello {name}"

if __name__ == "__main__":
    print(greet("World"))   # Only runs when you do: python my_script.py
```

**In this project:** `server.py:23` — `if __name__ == "__main__": uvicorn.run(app, host="127.0.0.1", port=8002)`

---

# Section 2: Python — Classes & OOP

### 31. `class`, `__init__`, `self`

**What:** A class is a blueprint for objects. `__init__` is the constructor (runs when you create an instance). `self` is the instance itself.

**Small example:**
```python
class Position:
    def __init__(self, symbol, entry):
        self.symbol = symbol       # instance variable
        self.entry = entry
        self.pnl = 0

pos = Position("NIFTY", 100)       # calls __init__
print(pos.symbol)                  # "NIFTY"
```

**In this project:** `position_manager.py:7` — `class PositionManager:` with `def __init__(self, initial_sl_points=5, ...):` sets up trading parameters.

---

### 32. Instance Variables (`self.xxx`)

**What:** Variables attached to `self` inside methods. Each instance gets its own copy. Store object state.

**Small example:**
```python
class Trade:
    def __init__(self):
        self.entry_price = None
        self.exit_price = None
        self.is_open = False

t = Trade()
t.entry_price = 100
t.is_open = True
```

**In this project:** `candle.py:8-14` — `self.symbol = symbol`, `self.candle_history = []`, `self.current_candle = None`, `self.listeners = []`.

---

### 33. Instance Methods

**What:** Functions defined inside a class that operate on an instance. First parameter is always `self`.

**Small example:**
```python
class Position:
    def __init__(self, entry):
        self.entry = entry
        self.sl = entry - 5
    
    def check_exit(self, current_price):
        return current_price <= self.sl
    
    def update_sl(self, new_sl):
        self.sl = new_sl

pos = Position(100)
print(pos.check_exit(90))   # True (90 <= 95)
```

**In this project:** `position_manager.py:23-160` — methods like `is_in_position()`, `open_position()`, `update_trailing_sl()`, `check_exit()`, `close_position()`.

---

### 34. Docstrings (`"""..."""`)

**What:** Multi-line string right after `def` or `class` that documents what it does. Accessible via `help()` or doc tools.

**Small example:**
```python
def calc_pnl(entry, exit):
    """Calculate profit/loss. Positive = profit, negative = loss."""
    return exit - entry

help(calc_pnl)  # shows the docstring
```

**In this project:** `position_manager.py:2-5` — `"""Position Manager: Handles single position lifecycle with trailing stop loss"""`. Each method also has docstrings.

---

### 35. Nested / Inner Functions

**What:** A function defined inside another function. Can access variables from the outer function (closure).

**Small example:**
```python
def make_counter():
    count = 0
    def increment():
        nonlocal count
        count += 1
        return count
    return increment

counter = make_counter()
print(counter())  # 1
print(counter())  # 2
```

**In this project:** `bot_manager.py:47` — `def patched_print(*args, **kwargs):` is defined inside `_patch_print()` and accesses `self` from outer scope.

---

### 36. Dict as Return Value

**What:** Returning a dictionary from a function lets you return multiple named values without creating a class.

**Small example:**
```python
def get_trade_summary(entry, exit):
    return {
        "entry": entry,
        "exit": exit,
        "pnl": exit - entry,
        "duration_seconds": 300,
    }

result = get_trade_summary(100, 110)
print(result["pnl"])  # 10
```

**In this project:** `position_manager.py:121-132` — returns trade summary dict with keys: symbol, entry_price, exit_price, pnl, duration_seconds, sl_initial, sl_final, highest_price.

---

### 37. Chained Dict Access (`dict['a']['b']`)

**What:** Access nested dict values by chaining square bracket lookups.

**Small example:**
```python
data = {"feeds": {"CE": {"ltp": 100}}}
ltp = data["feeds"]["CE"]["ltp"]
print(ltp)  # 100
```

**In this project:** `bot_manager.py:63-65` — `["CE"]["trade1"]` access from `self.positions` nested dict. `data_streamer.py:326` — `feed_data['fullFeed']['marketFF']` chain.

---

### 38. `.copy()` on dicts

**What:** Creates a **shallow copy** of a dict. Modifying the copy doesn't affect the original (but nested objects are still shared).

**Small example:**
```python
original = {"entry": 100, "sl": 95}
backup = original.copy()
backup["entry"] = 200
print(original["entry"])  # 100 (unchanged)
```

**In this project:** `position_manager.py:50` — `return self.position.copy()` returns a copy so external code can't accidentally modify internal state.

---

# Section 3: Python — Error Handling

### 39. `try` / `except`

**What:** Wrap risky code in `try`. If an error occurs, `except` runs instead of crashing.

**Small example:**
```python
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Can't divide by zero!")
```

**In this project:** `main.py:38-41` — `try: api_thread.join() except KeyboardInterrupt: pass` (graceful shutdown on Ctrl+C).

---

### 40. `try` / `except` / `finally`

**What:** `finally` block **always** runs, whether there was an error or not. Used for cleanup (close files, reset state).

**Small example:**
```python
def process():
    try:
        return risky_operation()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Cleanup runs always")
```

**In this project:** `data_streamer.py:195-208` — `try: exit_position() ... finally: comp['_exiting'] = False` ensures exit flag is always cleared. `trade_logger.py:34-55` — `try: ... finally: conn.close()` ensures DB connection is always closed.

---

### 41. `raise`

**What:** Manually trigger an error. Can use built-in exceptions or custom ones. Stops normal execution unless caught.

**Small example:**
```python
def validate_price(price):
    if price <= 0:
        raise ValueError(f"Invalid price: {price}")
    return price
```

**In this project:** `data_streamer.py:34` — `raise ValueError("CE and PE keys must be provided")` if missing required keys.

---

### 42. `traceback.print_exc()`

**What:** Prints the full error traceback (which file, which line, call stack). Useful for debugging.

**Small example:**
```python
import traceback
try:
    1/0
except:
    traceback.print_exc()
# Prints full trace with line numbers
```

**In this project:** `data_streamer.py:436` — `traceback.print_exc()` in the outer exception handler for debugging WebSocket messages.

---

### 43. Multiple Exception Types

**What:** Catch different exception types in the same `except` block using a tuple.

**Small example:**
```python
try:
    with open("data.json") as f:
        data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print("File missing or corrupt")
```

**In this project:** `settings_db.py:37` — `except (json.JSONDecodeError, IOError):` catches both JSON parse errors and file I/O errors.

---

# Section 4: Python — File I/O & Data

### 44. `with open()` (Context Manager)

**What:** `with` automatically closes the file when the block ends, even if an error occurs. The preferred way to work with files.

**Small example:**
```python
with open("hello.txt", "w") as f:
    f.write("Hello World!")
# file is auto-closed here
```

**In this project:** `settings_db.py:31` — `with open(SETTINGS_FILE, "r") as f: data = json.load(f)`. Line 49 — `with open(tmp, "w") as f: json.dump(settings, f, indent=2)`.

---

### 45. `json.load()` / `json.dump()`

**What:** `json.load(file)` reads JSON from a file object. `json.dump(data, file)` writes JSON to a file object. `indent=2` makes it human-readable.

**Small example:**
```python
import json
data = {"name": "NIFTY", "price": 100}
with open("data.json", "w") as f:
    json.dump(data, f, indent=2)
with open("data.json", "r") as f:
    loaded = json.load(f)
print(loaded["name"])  # NIFTY
```

**In this project:** `settings_db.py:32` — `json.load(f)`. Line 50 — `json.dump(settings, f, indent=2)`.

---

### 46. `json.dumps()` (String)

**What:** `json.dumps(data)` converts Python object to JSON **string** (not file). Used for sending JSON over network. `default=str` handles non-serializable types like datetime.

**Small example:**
```python
import json
data = {"ltp": 100.5, "time": "14:30:00"}
payload = json.dumps(data)
print(payload)  # '{"ltp": 100.5, "time": "14:30:00"}'
```

**In this project:** `live_feed_server.py:48` — `json.dumps(message, default=str)` converts message to JSON string for WebSocket broadcast.

---

### 47. `os.path.join()`, `os.path.dirname()`, `os.path.abspath()`

**What:** `os.path.join()` builds paths with correct separator (`/` or `\`). `os.path.dirname()` gets parent directory. `os.path.abspath()` resolves to full absolute path.

**Small example:**
```python
import os
path = os.path.join("backend", "data", "trades.db")
abs_path = os.path.abspath(__file__)
folder = os.path.dirname(abs_path)
print(folder)  # full path to current file's folder
```

**In this project:** `db.py:4` — `os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.db")` builds path to database file next to the script.

---

### 48. `os.path.exists()`

**What:** Checks if a file or directory exists at the given path. Returns `True`/`False`.

**Small example:**
```python
import os
if os.path.exists("settings.json"):
    print("Settings file found")
else:
    print("Creating default settings")
```

**In this project:** `settings_db.py:27` — `if not os.path.exists(SETTINGS_FILE): save_settings(DEFAULT_SETTINGS)` creates default settings file if missing.

---

### 49. `shutil.move()`

**What:** Moves a file from source to destination. Used for atomic file replacement (write to temp, then move to overwrite).

**Small example:**
```python
import shutil
# Write to a temp file first (safe)
with open("data.tmp", "w") as f:
    f.write(new_data)
# Then atomically replace the real file
shutil.move("data.tmp", "data.json")
```

**In this project:** `settings_db.py:51` — `shutil.move(tmp, SETTINGS_FILE)` atomically replaces settings file (prevents corruption if write is interrupted).

---

### 50. `sys.path.insert()`

**What:** Adds a directory to Python's module search path. Used when importing from parent directories.

**Small example:**
```python
import sys, os
# Add parent directory to import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from my_module import my_function
```

**In this project:** `trade_log_reader.py:5` — `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` allows importing `db` from a different folder.

---

### 51. `logging.basicConfig` / `getLogger`

**What:** `logging` is Python's standard log system. `basicConfig` sets up once. `getLogger(name)` creates a logger. Better than `print()` because it can have levels, timestamps, and file output.

**Small example:**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Bot started")
logger.error("Something failed")
```

**In this project:** `live_feed_server.py:5` — `logger = logging.getLogger(__name__)`. Line 32 — `logger.info(f"WebSocket server started on ws://...")`. `server.py:10` — `logging.basicConfig(level=logging.INFO)`.

---

# Section 5: Python — SQLite Database

### 52. `sqlite3.connect()`, `.execute()`

**What:** `sqlite3.connect(path)` opens (or creates) a SQLite database. `.execute(sql, params)` runs a SQL statement with parameter substitution (safe from SQL injection).

**Small example:**
```python
import sqlite3
conn = sqlite3.connect("test.db")
conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)")
conn.execute("INSERT INTO items (name) VALUES (?)", ("hello",))
conn.commit()
conn.close()
```

**In this project:** `db.py:8` — `sqlite3.connect(DB_PATH)`. Line 16 — `conn.execute("""CREATE TABLE IF NOT EXISTS trades (... )""")`.

---

### 53. `CREATE TABLE IF NOT EXISTS`

**What:** Creates a table only if it doesn't already exist. Safe to run every time the app starts — won't overwrite existing data.

**Small example:**
```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        entry_price REAL
    )
""")
```

**In this project:** `db.py:16-29` — creates `trades` table with id, symbol, entry_time, entry_price, stop_loss, exit_time, exit_price, exit_reason, pnl, created_at.

---

### 54. `INSERT INTO ... VALUES (?, ?)`

**What:** Adds a new row. `?` placeholders are filled by the tuple argument — prevents SQL injection and handles quoting automatically.

**Small example:**
```python
conn.execute(
    "INSERT INTO trades (symbol, entry_price) VALUES (?, ?)",
    ("NIFTY", 100.50)
)
```

**In this project:** `trade_logger.py:22-28` — `INSERT INTO trades (symbol, entry_time, entry_price, stop_loss) VALUES (?, ?, ?, ?)`.

---

### 55. `UPDATE ... WHERE ...`

**What:** Modifies existing rows that match the `WHERE` condition.

**Small example:**
```python
conn.execute(
    "UPDATE trades SET exit_price = ?, pnl = ? WHERE id = ?",
    (110.0, 10.0, 1)
)
```

**In this project:** `trade_logger.py:43-47` — updates the open trade row with exit details when a position closes.

---

### 56. `SELECT ... ORDER BY`

**What:** Fetches rows matching conditions. `ORDER BY` sorts results (DESC for descending).

**Small example:**
```python
rows = conn.execute(
    "SELECT * FROM trades WHERE symbol = ? ORDER BY entry_time DESC",
    ("NIFTY",)
).fetchall()
```

**In this project:** `trade_log_reader.py:14-18` — `SELECT * FROM trades ORDER BY entry_time DESC` loads all trades newest first.

---

### 57. `DELETE FROM ... WHERE`

**What:** Deletes rows matching the condition.

**Small example:**
```python
conn.execute("DELETE FROM trades WHERE id = ?", (5,))
```

**In this project:** `api_server.py:83` — `conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))` via the DELETE /api/trades endpoint.

---

### 58. `.commit()`, `.rollback()`

**What:** `commit()` saves changes permanently. `rollback()` undoes all changes since last commit. Without commit, changes are lost when connection closes.

**Small example:**
```python
conn.execute("INSERT INTO trades (symbol) VALUES (?)", ("NIFTY",))
conn.commit()  # Save
# or
conn.rollback()  # Undo
```

**In this project:** `trade_logger.py:29,53` — `.commit()` after insert, `.rollback()` if error occurs during exit update.

---

### 59. `.fetchall()`, `.fetchone()`

**What:** `fetchall()` returns all matching rows as a list. `fetchone()` returns the first row only (or None if no match).

**Small example:**
```python
all_trades = conn.execute("SELECT * FROM trades").fetchall()
last_trade = conn.execute(
    "SELECT * FROM trades ORDER BY id DESC LIMIT 1"
).fetchone()
```

**In this project:** `trade_log_reader.py:16` — `.fetchall()`. `trade_log_reader.py:41` — `.fetchone()` to get the latest open trade.

---

### 60. `.row_factory = sqlite3.Row`

**What:** Makes rows accessible by column name (like a dict) instead of numeric index. `row["entry_price"]` vs `row[2]`.

**Small example:**
```python
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM trades LIMIT 1").fetchone()
print(row["symbol"])    # "NIFTY"
print(row["entry_price"])  # 100.5
```

**In this project:** `db.py:9` — `conn.row_factory = sqlite3.Row`. Used in `trade_log_reader.py:72-83` — `_row_to_dict()` accesses `row["id"]`, `row["symbol"]`, etc.

---

### 61. `PRAGMA journal_mode=WAL`

**What:** Changes SQLite's write mode to Write-Ahead Logging. Allows multiple readers to read while one writer writes — better performance.

**Small example:**
```python
conn.execute("PRAGMA journal_mode=WAL")
# No more "database is locked" errors
```

**In this project:** `db.py:10` — `conn.execute("PRAGMA journal_mode=WAL")` enables concurrent reads.

---

# Section 6: Python — Threading

### 62. `threading.Thread(target=..., daemon=True)`

**What:** Runs a function in a separate thread. `daemon=True` means the thread will be killed when the main program exits (no need to clean up manually).

**Small example:**
```python
import threading, time
def background_task():
    while True:
        print("Running...")
        time.sleep(1)

t = threading.Thread(target=background_task, daemon=True)
t.start()
time.sleep(3)
print("Main exiting")  # daemon thread auto-kills
```

**In this project:** `main.py:19-22` — creates a daemon thread for the WebSocket server: `threading.Thread(target=lambda: asyncio.run(live_feed.start()), daemon=True)`.

---

### 63. `.start()`

**What:** Begins execution of the thread. The target function runs in parallel.

**Small example:**
```python
t = threading.Thread(target=some_func)
t.start()  # some_func() starts running now
```

**In this project:** `bot_manager.py:171` — `self.bot_thread.start()` launches the bot trading loop in a background thread.

---

### 64. `.join()`

**What:** Blocks the current thread until the joined thread finishes. Waits for it to complete.

**Small example:**
```python
t = threading.Thread(target=worker)
t.start()
t.join()  # main thread waits here until worker finishes
print("Worker done")
```

**In this project:** `main.py:39` — `api_thread.join()` waits for the API server thread (blocks forever until Ctrl+C).

---

### 65. `threading.Lock` / `with lock:`

**What:** Prevents two threads from accessing the same data at the same time (race condition). Use `with lock:` for automatic acquire/release.

**Small example:**
```python
import threading
lock = threading.Lock()
shared_data = {"count": 0}

def increment():
    with lock:  # only one thread at a time
        shared_data["count"] += 1
```

**In this project:** `bot_manager.py:15` — `self.lock = threading.Lock()`. Every access to shared state like `self.positions`, `self.mode`, `self.running` is protected with `with self.lock:`.

---

### 66. Monkey-patching (`builtins.print = ...`)

**What:** Replacing a built-in function at runtime. Here, `print()` is patched so all print calls also go to a log buffer.

**Small example:**
```python
import builtins
original = builtins.print
def my_print(*args, **kwargs):
    original(*args)          # still prints to console
    log_message(" ".join(str(a) for a in args))

builtins.print = my_print
```

**In this project:** `bot_manager.py:42-57` — `builtins.print = patched_print` redirects all print statements to also emit to the log buffer (for the frontend SSE stream).

---

### 67. `global` keyword

**What:** Declares that a variable inside a function refers to the module-level global, not a local variable.

**Small example:**
```python
counter = 0
def increment():
    global counter
    counter += 1
```

**In this project:** `settings_db.py:43` — `global _cache` in `invalidate_cache()` resets the module-level cache variable.

---

# Section 7: Python — Async / Await Concurrency

### 68. `async def` / `await`

**What:** `async def` defines a coroutine (a function that can pause/resume). `await` pauses execution until the awaited coroutine completes, without blocking other tasks.

**Small example:**
```python
import asyncio
async def fetch_data():
    await asyncio.sleep(1)  # non-blocking wait
    return {"ltp": 100}

async def main():
    data = await fetch_data()
    print(data)
```

**In this project:** `live_feed_server.py:16` — `async def handler(self, websocket):` handles WebSocket clients asynchronously.

---

### 69. `asyncio.run()`

**What:** Creates an event loop, runs the given coroutine, and shuts down the loop. The standard way to start async code from sync code.

**Small example:**
```python
import asyncio
async def main():
    await asyncio.sleep(1)
    print("Done")

asyncio.run(main())
```

**In this project:** `server.py:19` — `asyncio.run(live_feed.start())` runs the async WebSocket server inside a thread.

---

### 70. `asyncio.sleep()`

**What:** The async version of `time.sleep()`. Pauses this coroutine but lets other tasks run.

**Small example:**
```python
async def poll():
    while True:
        await asyncio.sleep(0.2)  # 200ms, non-blocking
        print("tick")
```

**In this project:** `api_server.py:155` — `await asyncio.sleep(0.2)` in the SSE event generator loop.

---

### 71. `asyncio.Queue(maxsize=)`

**What:** A thread-safe FIFO queue for async code. `.put()` waits if full. `.put_nowait()` raises `QueueFull` if full. `.get()` waits if empty.

**Small example:**
```python
import asyncio
q = asyncio.Queue(maxsize=10)
async def producer():
    await q.put("message")        # waits if full
    q.put_nowait("urgent")         # raises QueueFull if full

async def consumer():
    msg = await q.get()            # waits if empty
```

**In this project:** `live_feed_server.py:29` — `self._queue = asyncio.Queue(maxsize=100)` buffers broadcast messages. Line 42 — `await self._queue.get()`. Line 79 — `self._queue.put_nowait(message)`.

---

### 72. `asyncio.gather(..., return_exceptions=True)`

**What:** Runs multiple coroutines concurrently. `return_exceptions=True` makes it return exceptions as results instead of raising them (one failure doesn't crash others).

**Small example:**
```python
import asyncio
async def task(i):
    await asyncio.sleep(i)
    return i

results = await asyncio.gather(
    task(1), task(2), task(3),
    return_exceptions=True
)
# results = [1, 2, 3]
```

**In this project:** `live_feed_server.py:49-51` — `await asyncio.gather(*(ws.send(data) for ws in self.clients), return_exceptions=True)` sends to all clients simultaneously.

---

### 73. `asyncio.create_task()`

**What:** Schedules a coroutine to run "in the background" without waiting for it. Like starting a thread but for async.

**Small example:**
```python
import asyncio
async def background():
    while True:
        await asyncio.sleep(1)

async def main():
    task = asyncio.create_task(background())
    await asyncio.sleep(5)
    task.cancel()
```

**In this project:** `live_feed_server.py:30` — `asyncio.create_task(self._drain_queue())` starts the queue drainer in the background.

---

### 74. `asyncio.run_coroutine_threadsafe()`

**What:** Safely submits a coroutine to an event loop running in a **different thread**. The bridge between threaded code and async code.

**Small example:**
```python
loop = asyncio.get_running_loop()
# From another thread:
asyncio.run_coroutine_threadsafe(my_coro(), loop)
```

**In this project:** `live_feed_server.py:75` — `asyncio.run_coroutine_threadsafe(self._put_message(message), self._loop)` lets threads add messages to the async queue.

---

### 75. `loop.run_until_complete()`

**What:** Runs the event loop until a specific coroutine finishes. Blocks until done.

**Small example:**
```python
loop = asyncio.new_event_loop()
loop.run_until_complete(some_coroutine())
```

**In this project:** `bot_manager.py:104` — `loop.run_until_complete(self._scheduler.start())` runs the trading session in a thread with its own event loop.

---

### 76. `new_event_loop()` / `set_event_loop()`

**What:** Creates a fresh event loop and makes it the "current" loop for the thread. Each thread needs its own event loop if using async.

**Small example:**
```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(some_coro())
```

**In this project:** `bot_manager.py:102-103` — creates a new event loop for the bot thread (each thread needs its own loop).

---

# Section 8: Python — HTTP & APIs (FastAPI)

### 77. `requests.get(url, headers, params, timeout)`

**What:** Make an HTTP GET request. `headers` sets auth/browser info. `params` adds query parameters. `timeout` sets max wait in seconds.

**Small example:**
```python
import requests
headers = {"Authorization": "Bearer my_token"}
params = {"instrument_key": "NSE_INDEX|Nifty 50"}
resp = requests.get(
    "https://api.upstox.com/v2/market-quote/ltp",
    headers=headers,
    params=params,
    timeout=10,
)
```

**In this project:** `scheduler.py:73-78` — fetches option contract data from Upstox. Line 130-134 — validates access token.

---

### 78. `response.json()` / `response.status_code`

**What:** `.json()` parses response body as JSON (returns dict/list). `.status_code` gives HTTP status (200 = OK, 4xx = client error, 5xx = server error).

**Small example:**
```python
resp = requests.get("https://api.example.com/data")
if resp.status_code == 200:
    data = resp.json()
    print(data)
else:
    print(f"Error: {resp.status_code}")
```

**In this project:** `scheduler.py:79,112` — `resp.json().get('data', [])` safely accesses response data.

---

### 79. FastAPI: `app = FastAPI()`, `@app.get()`, `@app.post()`

**What:** FastAPI is a web framework. Create an app, then decorate functions with `@app.get("/path")` to define API endpoints. Functions can be async.

**Small example:**
```python
from fastapi import FastAPI
app = FastAPI()

@app.get("/hello")
async def hello():
    return {"message": "World"}

@app.post("/echo")
async def echo(data: dict):
    return data
```

**In this project:** `api_server.py:16` — `app = FastAPI(title="Options Trading Bot API")`. Line 26 — `@app.get("/api/status")`. Line 33 — `@app.post("/api/start")`.

---

### 80. `@app.put()`, `@app.delete()`

**What:** Same pattern as GET/POST but for HTTP PUT (update) and DELETE (remove) methods.

**Small example:**
```python
@app.put("/settings/{key}")
async def update(key: str, body: dict):
    save_to_db(key, body["value"])
    return {"status": "saved"}

@app.delete("/items/{id}")
async def delete(id: int):
    delete_from_db(id)
    return {"status": "deleted"}
```

**In this project:** `api_server.py:67` — `@app.put("/api/settings/{key}")`. Line 78 — `@app.delete("/api/trades/{trade_id}")`.

---

### 81. Pydantic: `class Body(BaseModel)`

**What:** Defines the expected shape of a request body. FastAPI automatically validates incoming JSON against the model and returns 422 if invalid.

**Small example:**
```python
from pydantic import BaseModel
class StartBody(BaseModel):
    instruments: list[str] | None = None
    quantity: int = 1

@app.post("/start")
async def start(body: StartBody):
    return body.instruments
```

**In this project:** `api_server.py:30-31` — `class StartBody(BaseModel): instruments: list[str] | None = None`.

---

### 82. `HTTPException(status_code=)`

**What:** Returns an error HTTP response with the given status code and message. FastAPI handles the JSON formatting.

**Small example:**
```python
from fastapi import HTTPException, FastAPI

@app.get("/items/{id}")
async def get_item(id: int):
    if id > 100:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": id}
```

**In this project:** `api_server.py:37` — `raise HTTPException(status_code=400, detail=result["message"])` if bot is already running.

---

### 83. `CORSMiddleware`

**What:** CORS (Cross-Origin Resource Sharing) lets browsers allow requests from a different origin (e.g., frontend on port 3001 → backend on port 8002).

**Small example:**
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**In this project:** `api_server.py:18-24` — allows frontend at http://localhost:3001 and 127.0.0.1:3001.

---

### 84. SSE: `StreamingResponse` + `yield`

**What:** Server-Sent Events — server pushes messages to client over a single long-lived HTTP connection. Format: `data: {json}\n\n`. Client uses `new EventSource(url)`.

**Small example:**
```python
from fastapi.responses import StreamingResponse
import asyncio, json

@app.get("/events")
async def stream():
    async def generator():
        while True:
            yield f"data: {json.dumps({'time': 'now'})}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(generator(), media_type="text/event-stream")
```

**In this project:** `api_server.py:141-164` — streams log entries to the frontend in real-time.

---

### 85. `uvicorn.Config` / `uvicorn.Server`

**What:** Programmatic way to configure and run a Uvicorn ASGI server (the server that runs FastAPI). Can be used instead of `uvicorn.run()`.

**Small example:**
```python
import uvicorn
app = FastAPI()
config = uvicorn.Config(app, host="0.0.0.0", port=8002, log_level="info")
server = uvicorn.Server(config)
server.run()
```

**In this project:** `api_server.py:170-171` — creates `uvicorn.Server` from config and returns it (so it can run in a thread).

---

# Section 9: Python — WebSocket & Protobuf

### 86. `websockets.serve(handler, host, port)`

**What:** Starts a WebSocket server. The `handler` coroutine is called for each new client connection.

**Small example:**
```python
import asyncio, websockets

async def handler(websocket):
    async for msg in websocket:
        await websocket.send(f"Echo: {msg}")

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()  # run forever
```

**In this project:** `live_feed_server.py:31` — `self.server = await websockets.serve(self.handler, self.host, self.port)`.

---

### 87. `async for msg in websocket:`

**What:** Iterates over messages from a WebSocket connection as they arrive. Each iteration receives one message.

**Small example:**
```python
async def handler(websocket):
    async for message in websocket:
        print(f"Received: {message}")
```

**In this project:** `live_feed_server.py:19` — `async for _ in websocket: pass` (just tracks connected clients, doesn't process messages).

---

### 88. `ws.send(data)`

**What:** Sends a string/binary message to a WebSocket client.

**Small example:**
```python
async def handler(websocket):
    await websocket.send("Hello from server!")
```

**In this project:** `live_feed_server.py:67` — `await ws.send(data)` sends JSON-encoded tick/trade data to frontend clients.

---

### 89. Upstox `MarketDataStreamerV3`

**What:** Upstox-specific WebSocket client that connects to their market data feed. Part of the `upstox-python-sdk` package.

**Small example:**
```python
import upstox_client
configuration = upstox_client.Configuration()
configuration.access_token = "my_token"
streamer = upstox_client.MarketDataStreamerV3(
    upstox_client.ApiClient(configuration)
)
```

**In this project:** `data_streamer.py:464` — creates the streamer with the ApiClient.

---

### 90. `.on("open")`, `.on("message")`, `.on("close")`

**What:** Register callback functions for WebSocket lifecycle events. Called when connection opens, receives data, or closes.

**Small example:**
```python
streamer.on("open", my_on_open)
streamer.on("message", my_on_message)
streamer.on("close", my_on_close)
```

**In this project:** `data_streamer.py:467-470` — registers `on_open`, `on_message`, `on_error`, and `on_close` callbacks.

---

### 91. `.subscribe(keys, mode)`

**What:** Tells the WebSocket which instruments to receive data for. `"full"` mode gives full market data (LTP, OHLC, etc.).

**Small example:**
```python
keys = ["NSE_FO|12345", "NSE_FO|67890"]
streamer.subscribe(keys, "full")
```

**In this project:** `data_streamer.py:451` — `self.streamer.subscribe(keys_to_subscribe, "full")` subscribes to CE and PE instrument keys.

---

### 92. `.connect()`, `.disconnect()`

**What:** `.connect()` opens the WebSocket connection (blocking). `.disconnect()` closes it.

**Small example:**
```python
streamer.connect()      # blocks until disconnected
# later:
streamer.disconnect()
```

**In this project:** `data_streamer.py:473` — `self.streamer.connect()`. Line 516 — `self.streamer.disconnect()`.

---

### 93. Protobuf `.ParseFromString()`

**What:** Parses binary Protobuf data into structured message objects. Protobuf is a compact binary format (smaller/faster than JSON).

**Small example:**
```python
from my_protobuf_pb2 import FeedResponse
response = FeedResponse()
response.ParseFromString(binary_data)
print(response.some_field)
```

**In this project:** `data_streamer.py:374-376` — `from upstox.MarketDataFeedV3_pb2 import FeedResponse`... `feed_response.ParseFromString(message)`.

---

### 94. Protobuf `.HasField()`

**What:** Checks if an optional field was set in the Protobuf message. Prevents errors from accessing missing fields.

**Small example:**
```python
if feed_data.HasField('fullFeed'):
    full_feed = feed_data.fullFeed
    if full_feed.HasField('marketFF'):
        # process market feed
```

**In this project:** `data_streamer.py:392` — `feed_data.HasField('fullFeed')`. Line 396 — `full_feed.HasField('marketFF')`.

---

# Section 10: TypeScript — Fundamentals

### 95. `const` / `let`

**What:** `const` declares a variable that cannot be reassigned (but objects/arrays can still be mutated). `let` allows reassignment. Prefer `const` unless you need to reassign.

**Small example:**
```typescript
const MAX_TRADES = 2;        // cannot reassign
let currentTrade = "CE";     // can reassign
currentTrade = "PE";         // OK

const trades = ["CE"];       // can't reassign trades, but can modify array
trades.push("PE");           // OK
```

**In this project:** `page.tsx:10` — `const [status, setStatus] = useState<any>(null)`. `TerminalQuadrant.tsx:167` — `let ws: WebSocket | null = null`.

---

### 96. Basic Types: `string`, `number`, `boolean`

**What:** The core primitive types. `string` for text, `number` for all numbers (no separate int/float), `boolean` for true/false.

**Small example:**
```typescript
const symbol: string = "NIFTY";
const price: number = 100.50;
const isActive: boolean = true;
```

**In this project:** `types.ts:2` — `trade_slot: number`, line 13 — `running: boolean`.

---

### 97. `null` vs `undefined`

**What:** `null` is an intentional "no value". `undefined` means a variable hasn't been assigned. Different types!

**Small example:**
```typescript
let a: string | null = null;     // intentional empty
let b: string | undefined;        // not assigned yet
let c: string | null | undefined; // either

console.log(a === null);   // true
console.log(b === null);   // false
console.log(b === undefined); // true
```

**In this project:** `page.tsx:10` — `useState<any>(null)` (starts with null). `TerminalQuadrant.tsx:90` — `if (initialPos !== undefined)`.

---

### 98. `interface`

**What:** Defines the shape of an object. Lists property names and their types. Can be exported and reused.

**Small example:**
```typescript
interface Trade {
  symbol: string;
  entryPrice: number;
  exitPrice: number | null;
  pnl: number | null;
}

const trade: Trade = { symbol: "NIFTY", entryPrice: 100, exitPrice: null, pnl: null };
```

**In this project:** `types.ts:1-71` — defines `PositionState`, `BotStatus`, `TradeEntry`, `DayPnl`, `TradeStats`, `SettingMeta`.

---

### 99. `type` aliases

**What:** Creates a name for a type. Can be used for unions, tuples, and object shapes (like `interface`).

**Small example:**
```typescript
type Status = "idle" | "running" | "stopped";
type Point = { x: number; y: number };
type Callback = () => void;

const s: Status = "running";
const p: Point = { x: 10, y: 20 };
```

**In this project:** `token/page.tsx:7` — `type TokenStatus = "unknown" | "valid" | "invalid"`. `PriceDiagram.tsx:28` — `type Level = { label: string; price: number; color: string }`.

---

### 100. Union Types (`|`)

**What:** A value that can be one of several types. Used with primitive literals (like an enum) or mixed types.

**Small example:**
```typescript
type Pnl = number | null;
type Side = "CE" | "PE";
type State = "idle" | "in_position" | "exited_win" | "exited_loss";

let s: State = "idle";
s = "in_position";   // OK
s = "something_else"; // ERROR
```

**In this project:** `types.ts:3` — `state: "idle" | "watching" | "in_position" | "exited_win" | "exited_loss" | "stopped"`.

---

### 101. Optional Properties (`?`)

**What:** A property that may or may not exist. Accessing it returns `undefined` if missing.

**Small example:**
```typescript
interface Config {
  label: string;
  value: string;
  options?: string;       // optional
}

const c1: Config = { label: "Mode", value: "auto" };          // OK
const c2: Config = { label: "Mode", value: "auto", options: "a,b" }; // OK
```

**In this project:** `types.ts:69` — `options?: string`. `PriceDiagram.tsx:15` — `entryTime?: string | null`.

---

### 102. `Record<K, V>`

**What:** A dictionary type where keys are type `K` and values are type `V`. Like `{ [key: string]: number }` but cleaner.

**Small example:**
```typescript
const prices: Record<string, number> = {
  "CE": 100.5,
  "PE": 95.2,
};

const colors: Record<string, string> = {
  "running": "#10b981",
  "stopped": "#ef4444",
};
```

**In this project:** `types.ts:19` — `strikes: Record<string, string>`. `TerminalQuadrant.tsx:80` — `const stateColors: Record<string, string> = {...}`.

---

### 103. Generics (`<T>`)

**What:** A way to make components/types work with any type while preserving type safety. `<T>` is a type parameter.

**Small example:**
```typescript
function identity<T>(value: T): T {
  return value;
}
const n = identity<number>(42);    // type: number
const s = identity("hello");       // type: string (inferred)

// With useState
const [data, setData] = useState<BotStatus | null>(null);
```

**In this project:** `MaximizeContext.tsx:4` — `createContext<{ maximized: boolean; toggle: () => void }>(...)`. `TradeCalendar.tsx:27` — `useState<Record<string, DayPnl>>({})`.

---

### 104. `import type`

**What:** Importing a type specifically (only for type checking, removed at runtime). Slightly smaller bundle and clearer intent.

**Small example:**
```typescript
import type { BotStatus } from "./types";
// vs
import { BotStatus } from "./types";   // imports both type and value
```

**In this project:** `api.ts:1` — `import type { BotStatus, TradeEntry, DayPnl, TradeStats, SettingMeta } from "./types"`. `layout.tsx:1` — `import type { Metadata } from "next"`.

---

### 105. Arrow Functions (`=>`)

**What:** A shorter syntax for functions. `(param) => expression` — inherits `this` from surrounding scope (important in classes/callbacks).

**Small example:**
```typescript
const double = (x: number) => x * 2;
const add = (a: number, b: number) => a + b;

// With array methods
const prices = [100, 200, 150];
const doubled = prices.map(p => p * 2);
```

**In this project:** `page.tsx:15` — `.then((r) => r.json())`. `SettingsAccordion.tsx:21` — `settings.map((s) => s.category)`.

---

### 106. Template Literals (`` `text ${var}` ``)

**What:** Strings that embed expressions using `${}`. Backticks instead of quotes. Can span multiple lines.

**Small example:**
```typescript
const name = "NIFTY";
const price = 100.5;
const msg = `${name} @ ${price.toFixed(2)}`;
// "NIFTY @ 100.50"

// Multi-line
const html = `
  <div>${name}</div>
  <div>${price}</div>
`;
```

**In this project:** `api.ts:6` — `` fetch(`${API}/api/status`) ``. `AppHeader.tsx:163` — `` `${isProfit ? "+" : ""}${netPnl.toFixed(2)}` ``.

---

### 107. Optional Chaining (`?.`)

**What:** Safely access nested properties without checking each level. Returns `undefined` if any part is null/undefined instead of crashing.

**Small example:**
```typescript
interface Status { positions?: { CE?: { trade1?: any } } }
const s: Status = {};

// Without: crashes if s.positions is undefined
// With: safe
console.log(s?.positions?.CE?.trade1?.pnl);   // undefined (no crash)
```

**In this project:** `page.tsx:36` — `status?.positions?.CE?.trade1`. `AppHeader.tsx:70` — `pos?.CE?.trade1?.pnl ?? 0`.

---

### 108. Nullish Coalescing (`??`)

**What:** Returns the right-hand value only if left is `null` or `undefined`. Unlike `||` which treats `0` and `""` as falsy too.

**Small example:**
```typescript
const pnl = 0;
const displayPnl = pnl ?? 100;     // 0 (0 is not null/undefined)
const displayPnl2 = pnl || 100;    // 100 (0 is falsy)

const value = null;
const display = value ?? "N/A";    // "N/A"
```

**In this project:** `positions/page.tsx:30` — `position={pos?.CE?.trade1 ?? null}`. `AppHeader.tsx:33` — `const running = s?.running ?? false`.

---

### 109. Spread Operator (`...`)

**What:** "Spreads" elements of an array or properties of an object into another. Used for cloning, merging, adding items.

**Small example:**
```typescript
// Array spread (clone + add)
const old = [1, 2, 3];
const newArr = [...old, 4, 5];  // [1, 2, 3, 4, 5]

// Object spread (merge/override)
const base = { entry: 100, sl: 95 };
const full = { ...base, pnl: 10 };  // { entry: 100, sl: 95, pnl: 10 }
```

**In this project:** `TerminalQuadrant.tsx:178` — `ticks: [...prev.ticks.slice(-2000), { ... }]`. `TerminalLogs.tsx:33` — `const log: Log = { ...raw, label, color }`.

---

### 110. Destructuring (Object/Array)

**What:** Unpack values from objects or arrays into variables in one line.

**Small example:**
```typescript
// Object destructuring
const position = { entry: 100, sl: 95, pnl: 10 };
const { entry, pnl } = position;
console.log(entry, pnl);  // 100, 10

// Array destructuring
const [status, setStatus] = useState(null);
```

**In this project:** `page.tsx:11` — `const { maximized, toggle } = useMaximize()`. `token/page.tsx:10` — `const [status, setStatus] = useState<TokenStatus>("unknown")`.

---

### 111. `typeof` Guard (SSR Check)

**What:** `typeof` checks a variable's type at runtime. Used here to check if code is running in browser vs server (SSR).

**Small example:**
```typescript
// Check if running in browser
if (typeof window === "undefined") {
  console.log("Running on server (SSR)");
  return;
}
// Now safe to use browser APIs like WebSocket
```

**In this project:** `TerminalQuadrant.tsx:164` — `if (typeof window === "undefined") return` (prevents WebSocket creation during server-side rendering).

---

### 112. `as` (Type Assertion)

**What:** Tell TypeScript "I know this type better than you". Used when you're sure about a type but TS can't infer it.

**Small example:**
```typescript
const value: any = 42;
const num = value as number;     // tell TS it's a number

// Or with generics
const [data, setData] = useState<any>(null);  // when you can't name the type
```

**In this project:** `page.tsx:10` — `useState<any>(null)` (casts the whole status as `any` for simplicity).

---

# Section 11: React — Components, Hooks & State

### 113. `"use client"` directive

**What:** Placed at the top of a file to mark it as a Client Component (runs in the browser, can use hooks, state, browser APIs). Without it, component is a Server Component.

**Small example:**
```typescript
"use client";

import { useState } from "react";

export default function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
```

**In this project:** Every `.tsx` file in `app/` has this — all pages are client-side rendered.

---

### 114. Function Components

**What:** A React component is just a function that returns JSX. Props are the function's parameters.

**Small example:**
```typescript
interface Props { name: string; price: number; }

export default function TradeCard({ name, price }: Props) {
  return <div>{name}: {price}</div>;
}
```

**In this project:** `page.tsx:9` — `export default function TerminalPage() { ... }`.

---

### 115. Typing Props with `interface`

**What:** Define an `interface` for the props a component expects. Provides autocomplete and type-checking.

**Small example:**
```typescript
interface Props {
  instrument: "CE" | "PE";
  slot: 1 | 2;
  initialPos?: PositionState | null;
}

export default function TerminalQuadrant({ instrument, slot, initialPos }: Props) {
  // ...
}
```

**In this project:** `TerminalQuadrant.tsx:23-38` defines `Props` + `TickData` + `InitialPos` interfaces.

---

### 116. `useState<T>(initial)`

**What:** Adds state to a function component. Returns `[value, setter]` tuple. The setter triggers a re-render.

**Small example:**
```typescript
const [count, setCount] = useState(0);
const [user, setUser] = useState<User | null>(null);

return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
```

**In this project:** `page.tsx:10` — `useState<any>(null)`. `TerminalQuadrant.tsx:67-71` — 5 useStates for state, tickData, synced, enteredAt, exitedAt.

---

### 117. `useEffect(fn, [deps])`

**What:** Runs a function after render. `[deps]` — re-runs only when deps change. Empty `[]` runs once on mount.

**Small example:**
```typescript
useEffect(() => {
  fetch("/api/data")
    .then(r => r.json())
    .then(setData);
}, []);  // runs once on mount
```

**In this project:** `page.tsx:13-18` — one-time fetch of bot status on mount.

---

### 118. `useEffect` Cleanup (`return fn`)

**What:** The function returned from `useEffect` runs when the component unmounts (or before re-running). Used to clean up timers, event listeners, WebSockets.

**Small example:**
```typescript
useEffect(() => {
  const ws = new WebSocket("ws://example.com");
  return () => {
    ws.close();  // cleanup on unmount
  };
}, []);
```

**In this project:** `TerminalQuadrant.tsx:213-216` — returns cleanup that closes WebSocket and clears reconnect timer. `AppHeader.tsx:22-23` — `return () => clearInterval(t)`.

---

### 119. `useRef<T>(initial)`

**What:** A mutable ref that persists across renders. Two uses: (1) access DOM elements, (2) store mutable values that don't trigger re-render on change.

**Small example:**
```typescript
// DOM ref
const inputRef = useRef<HTMLInputElement>(null);
inputRef.current?.focus();

// Mutable value (no re-render)
const frozenRef = useRef(false);
frozenRef.current = true;  // no re-render
```

**In this project:** `PriceDiagram.tsx:57` — `canvasRef = useRef<HTMLCanvasElement>(null)` for Canvas rendering. `TerminalQuadrant.tsx:72` — `frozenRef` prevents data overwrite after trade exit.

---

### 120. `useCallback(fn, [deps])`

**What:** Returns a memoized version of the function. Only re-creates the function if deps change. Prevents unnecessary re-renders of child components.

**Small example:**
```typescript
const handleClick = useCallback(() => {
  console.log(count);
}, [count]);  // new function only when count changes
```

**In this project:** `token/page.tsx:18` — `fetchStatus` wrapped in `useCallback` to avoid infinite loops in useEffect. `TerminalLogs.tsx:56` — `onMouseDown` for drag resize.

---

### 121. `useMemo(fn, [deps])`

**What:** Memoizes an expensive computed value. Only recalculates when deps change. The function should be pure (no side effects).

**Small example:**
```typescript
const expensive = useMemo(() => {
  return data.filter(x => x > 0).map(x => x * 2);
}, [data]);
```

**In this project:** `TradeCalendar.tsx:39-77` — computes weeks, month groups, and month-end columns from raw day data (expensive iteration). `PriceDiagram.tsx:71` — computes chart levels.

---

### 122. `createContext` / `useContext`

**What:** Share state across components without passing props through every level. `createContext` defines the context. `useContext` consumes it. A `<Provider>` wraps the tree.

**Small example:**
```typescript
const ThemeCtx = createContext({ dark: true, toggle: () => {} });

function App() {
  const [dark, setDark] = useState(true);
  return (
    <ThemeCtx.Provider value={{ dark, toggle: () => setDark(d => !d) }}>
      <Child />
    </ThemeCtx.Provider>
  );
}

function Child() {
  const { dark } = useContext(ThemeCtx);
  return <div className={dark ? "dark" : "light"}>Hello</div>;
}
```

**In this project:** `MaximizeContext.tsx:4` — creates context for fullscreen toggle. `LayoutClient.tsx:19` wraps app in `MaximizeProvider`.

---

### 123. Custom Hooks (`useXxx`)

**What:** Extract reusable logic into a function starting with `use`. Can call other hooks inside it.

**Small example:**
```typescript
function useWindowSize() {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const handler = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);
  return size;
}
```

**In this project:** `MaximizeContext.tsx:18` — `export const useMaximize = () => useContext(MaximizeCtx)` is a custom hook that wraps context usage.

---

### 124. Default Parameters in Components

**What:** Component props can have default values, used when the prop isn't passed.

**Small example:**
```typescript
function PriceDiagram({
  ticks,
  entryPrice = null,
  tpLevels = [],
  color = "#6366f1",
}: Props) {
  // color defaults to "#6366f1" if not passed
}
```

**In this project:** `PriceDiagram.tsx:54-56` — default values for `tpLevels = []`, `belowSlCount = 3`, `slStep = 5`, `color = "#6366f1"`.

---

### 125. Conditional Rendering (`&&`, ternary, early return)

**What:** Different ways to show/hide elements based on conditions.

**Small example:**
```typescript
// AND (show when true)
{running && <span>Active</span>}

// Ternary (choose between two)
<div className={maximized ? "fullscreen" : "normal"}>

// Early return (component returns nothing)
if (!open) return null;
```

**In this project:** `page.tsx:22` — `{maximized && (<button>...</button>)}`. Line 21 — `className={maximized ? "h-screen flex flex-col" : "p-2 space-y-2"}`. `TokenModal.tsx:15` — `if (!open) return null`.

---

### 126. JSX Fragments (`<></>`)

**What:** Group multiple elements without adding an extra DOM node (no wrapper div).

**Small example:**
```typescript
function Pair() {
  return (
    <>
      <div>First</div>
      <div>Second</div>
    </>
  );
}
```

**In this project:** `AppHeader.tsx:87-207` — wraps entire nav content in `<>...</>`.

---

### 127. Event Handlers (`onClick`, `onChange`, etc.)

**What:** Pass functions to JSX attributes like `onClick`, `onChange`, `onMouseDown` to handle user interactions.

**Small example:**
```typescript
<button onClick={() => setCount(c => c + 1)}>+</button>
<input onChange={(e) => setName(e.target.value)} />
<div onMouseDown={handleDrag} />
```

**In this project:** `page.tsx:24` — `onClick={toggle}`. `token/page.tsx:95` — `onChange={(e) => setAccessToken(e.target.value)}`. `PriceDiagram.tsx:388` — `onMouseMove={handleMouseMove}`.

---

### 128. `React.MouseEvent<HTMLDivElement>` typing

**What:** The correct TypeScript type for mouse event handlers on a div element.

**Small example:**
```typescript
function handleMouseDown(e: React.MouseEvent<HTMLDivElement>) {
  console.log(e.clientX, e.clientY);
}
```

**In this project:** `PriceDiagram.tsx:261` — `(e: React.MouseEvent<HTMLDivElement>)`. `TerminalLogs.tsx:56` — `(e: React.MouseEvent)`.

---

### 129. `React.ReactNode` type

**What:** The type for anything React can render: strings, numbers, JSX, null, arrays of these.

**Small example:**
```typescript
interface Props {
  children: React.ReactNode;  // any valid React content
}
```

**In this project:** `layout.tsx:13` — `children: React.ReactNode`. `LayoutClient.tsx:3` — `{ children: ReactNode }`.

---

# Section 12: Next.js — App Router

### 130. File-based Routing (`page.tsx`)

**What:** Each `page.tsx` file becomes a route automatically. `app/page.tsx` = `/`, `app/settings/page.tsx` = `/settings`, `app/token/page.tsx` = `/token`.

**Small example:**
```
app/
  page.tsx          → /
  settings/
    page.tsx        → /settings
  analytics/
    page.tsx        → /analytics
```

**In this project:** Routers: `/` (TerminalQuadrant dashboard), `/analytics`, `/history`, `/positions`, `/settings`, `/token`.

---

### 131. Root Layout (`layout.tsx`)

**What:** A wrapper around all pages. The root `layout.tsx` defines the HTML structure, fonts, and shared UI that persists across routes.

**Small example:**
```typescript
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header>Shared Header</header>
        {children}  {/* page content goes here */}
      </body>
    </html>
  );
}
```

**In this project:** `layout.tsx` — sets up HTML, Google Fonts, and wraps children in `LayoutClient`.

---

### 132. Server Component (no `"use client"`)

**What:** A component that only runs on the server. Can be async, can access databases directly, sends only HTML to the client. Smaller JS bundle.

**Small example:**
```typescript
// app/page.tsx (NO "use client")
export default async function Page() {
  const data = await db.query(...); // server-only
  return <div>{data.name}</div>;
}
```

**In this project:** Only `layout.tsx` is a server component (no `"use client"`). It sets up HTML, then delegates to client components.

---

### 133. Client Component (`"use client"`)

**What:** A component that runs in the browser. Can use React hooks, state, effects, browser APIs. Everything interactive must be a client component.

**Small example:**
```typescript
"use client";
import { useState } from "react";
export default function CountButton() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
```

**In this project:** Every page and component file except `layout.tsx` has `"use client"`.

---

### 134. `usePathname()`

**What:** Returns the current URL path. Used for highlighting active navigation links.

**Small example:**
```typescript
import { usePathname } from "next/navigation";
const pathname = usePathname();
return <a className={pathname === "/" ? "active" : ""}>Home</a>;
```

**In this project:** `AppHeader.tsx:12` — `const pathname = usePathname()`. `BottomNav.tsx:7` — determines active tab.

---

### 135. `useRouter()`

**What:** Allows programmatic navigation (redirect to another page without a link click).

**Small example:**
```typescript
import { useRouter } from "next/navigation";
const router = useRouter();
router.push("/settings");    // navigate to /settings
```

**In this project:** `TokenModal.tsx:13,43` — `router.push("/token")` when user clicks "Update Token" button.

---

### 136. Metadata API

**What:** Set page title, description, and other SEO metadata. Only works in Server Components.

**Small example:**
```typescript
import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "My App",
  description: "Description of my app",
};
```

**In this project:** `layout.tsx:5-8` — `title: "Options Trading Bot"`, `description: "NIFTY Options Trading Dashboard"`.

---

### 137. `next.config.ts`

**What:** TypeScript configuration file for Next.js. Controls dev indicators, webpack, images, rewrites, etc.

**Small example:**
```typescript
import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  devIndicators: false,
  webpack: (config) => {
    config.cache = false;
    return config;
  },
};
export default nextConfig;
```

**In this project:** `next.config.ts` — disables dev indicators and webpack caching.

---

# Section 13: Web APIs — Browser

### 138. `fetch(url)` — GET Request

**What:** The modern way to make HTTP requests from the browser. Returns a Promise that resolves to a Response object.

**Small example:**
```typescript
fetch("http://localhost:8002/api/status")
  .then(res => res.json())
  .then(data => console.log(data))
  .catch(err => console.error(err));
```

**In this project:** `page.tsx:14` — `fetch("http://127.0.0.1:8002/api/status").then(r => r.json()).then(setStatus)`.

---

### 139. `fetch()` with POST / PUT / DELETE

**What:** Use `method` option for non-GET requests. Add `body` for POST/PUT. Add `headers` for Content-Type.

**Small example:**
```typescript
// POST
fetch("/api/start", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ instruments: ["CE", "PE"] }),
});

// DELETE
fetch("/api/trades/5", { method: "DELETE" });

// PUT
fetch("/api/settings/max_wait_candles", {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ value: "3" }),
});
```

**In this project:** `api.ts:11-15` — POST to `/api/start`. Line 75 — DELETE to `/api/trades/${id}`. Line 66-70 — PUT to `/api/settings/${key}`.

---

### 140. `new WebSocket(url)`

**What:** Opens a bi-directional real-time connection to a server. Can send and receive messages without HTTP overhead.

**Small example:**
```typescript
const ws = new WebSocket("ws://localhost:8765");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
ws.onclose = () => console.log("disconnected");
```

**In this project:** `TerminalQuadrant.tsx:171` — `ws = new WebSocket(wsUrl)` connects to live feed.

---

### 141. `ws.onmessage`, `ws.onclose`, `ws.onopen`

**What:** Event handlers for WebSocket lifecycle. `onopen` = connected. `onmessage` = data received. `onclose` = connection lost.

**Small example:**
```typescript
ws.onopen = () => console.log("Connected");
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "tick") updatePrice(msg.ltp);
  if (msg.type === "trade") updateTrade(msg);
};
ws.onclose = () => setTimeout(connect, 2000); // reconnect
```

**In this project:** `TerminalQuadrant.tsx:173-206` — handles "tick" and "trade" message types. Line 207 — reconnects on close.

---

### 142. `new EventSource(url)` (SSE)

**What:** Connects to a Server-Sent Events endpoint. Receives a stream of events over HTTP. Simpler than WebSocket (server → client only).

**Small example:**
```typescript
const es = new EventSource("http://localhost:8002/api/logs/stream");
es.onmessage = (event) => {
  const entry = JSON.parse(event.data);
  console.log(entry.message);
};
// Clean up:
return () => es.close();
```

**In this project:** `TerminalLogs.tsx:27` — `new EventSource("http://127.0.0.1:8002/api/logs/stream")`. Line 40 — `return () => es.close()`.

---

### 143. `JSON.parse()` / `JSON.stringify()`

**What:** `JSON.parse(string)` converts JSON string → JS object. `JSON.stringify(object)` converts JS object → JSON string.

**Small example:**
```typescript
const str = '{"ltp": 100, "sl": 95}';
const obj = JSON.parse(str);
console.log(obj.ltp);  // 100

const back = JSON.stringify(obj);  // '{"ltp":100,"sl":95}'
```

**In this project:** `TerminalQuadrant.tsx:175` — `JSON.parse(event.data)` (WebSocket message). `api.ts:14` — `JSON.stringify(...)` (request body).

---

### 144. `setInterval()` / `clearInterval()`

**What:** `setInterval(fn, ms)` calls `fn` repeatedly every `ms` milliseconds. Returns a timer ID. `clearInterval(id)` stops it.

**Small example:**
```typescript
useEffect(() => {
  const t = setInterval(() => {
    fetchStatus();
  }, 5000);  // every 5 seconds
  return () => clearInterval(t);  // cleanup on unmount
}, []);
```

**In this project:** `AppHeader.tsx:22` — polls bot status every 5s. Line 23 — `return () => clearInterval(t)`. `positions/page.tsx:15` — polls every 3s.

---

### 145. `setTimeout()` / `clearTimeout()`

**What:** `setTimeout(fn, ms)` calls `fn` once after `ms` milliseconds. Returns a timer ID. `clearTimeout(id)` cancels it.

**Small example:**
```typescript
const timer = setTimeout(() => {
  reconnect();
}, 2000);  // wait 2 seconds, then reconnect

// To cancel:
clearTimeout(timer);
```

**In this project:** `TerminalQuadrant.tsx:208` — `reconnectTimer = setTimeout(connect, 2000)` (reconnect after 2s). Line 215 — `clearTimeout(reconnectTimer)` (cleanup).

---

### 146. Canvas 2D: `getContext("2d")`, drawing primitives

**What:** HTML Canvas is a pixel-based drawing surface. Uses JavaScript to draw lines, shapes, text, gradients. `getContext("2d")` gives the drawing API.

**Small example:**
```typescript
const canvas = canvasRef.current!;
const ctx = canvas.getContext("2d")!;
ctx.clearRect(0, 0, canvas.width, canvas.height);
ctx.strokeStyle = "#6366f1";
ctx.lineWidth = 2;
ctx.beginPath();
ctx.moveTo(0, 100);   // start
ctx.lineTo(200, 150);  // line to
ctx.stroke();          // render
```

**In this project:** `PriceDiagram.tsx:123-249` — full canvas chart with reference lines, gradient fill, price path, entry/exit markers, tooltips.

---

### 147. `ResizeObserver`

**What:** Watches an element for size changes. Fires callback when element resizes. Used here to make the canvas responsive.

**Small example:**
```typescript
const el = outerRef.current!;
const ro = new ResizeObserver(([entry]) => {
  const h = entry.contentRect.height;
  setChartH(h);
});
ro.observe(el);
return () => ro.disconnect();  // cleanup
```

**In this project:** `PriceDiagram.tsx:88-90` — updates chart height when container resizes.

---

### 148. `window.devicePixelRatio`

**What:** The ratio of physical pixels to CSS pixels on the screen. Retina displays have 2 or 3. Used to make Canvas rendering sharp (not blurry).

**Small example:**
```typescript
const dpr = window.devicePixelRatio || 1;
canvas.width = cssWidth * dpr;
canvas.height = cssHeight * dpr;
canvas.style.width = cssWidth + "px";
canvas.style.height = cssHeight + "px";
ctx.scale(dpr, dpr);  // scale all drawing
```

**In this project:** `PriceDiagram.tsx:105,118-125` — scales canvas for sharp rendering on high-DPI screens.

---

### 149. `addEventListener` / `removeEventListener` (Custom Drag)

**What:** Attach event listeners to DOM elements. Used for custom interactions like drag-to-resize. Must clean up with `removeEventListener` to avoid memory leaks.

**Small example:**
```typescript
const onMouseDown = useCallback((e: React.MouseEvent) => {
  const onMove = (e: MouseEvent) => { /* drag logic */ };
  const onUp = () => {
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
  };
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
}, []);
```

**In this project:** `TerminalLogs.tsx:56-79` — custom drag-to-resize handler for the log panel height.

---

# Section 14: JavaScript — Collections, Math & Patterns

### 150. `.map()`

**What:** Creates a new array by transforming every element. Original array unchanged.

**Small example:**
```typescript
const prices = [100, 200, 150];
const doubled = prices.map(p => p * 2);  // [200, 400, 300]
```

**In this project:** `SettingsAccordion.tsx:21` — `settings.map((s) => s.category)` extracts categories.

---

### 151. `.filter()`

**What:** Creates a new array with only elements that pass the test.

**Small example:**
```typescript
const prices = [100, 50, 200, 30];
const above100 = prices.filter(p => p >= 100);  // [100, 200]
```

**In this project:** `SettingsAccordion.tsx:58` — `settings.filter((s) => s.category === cat)` groups settings by category.

---

### 152. `.slice()`

**What:** Returns a portion of an array. `array.slice(start, end)` — negative indices count from end. Does not modify original.

**Small example:**
```typescript
const arr = [1, 2, 3, 4, 5];
arr.slice(-2)    // [4, 5] (last 2)
arr.slice(0, 3)  // [1, 2, 3]
```

**In this project:** `TerminalQuadrant.tsx:178` — `.slice(-2000)` keeps only the last 2000 ticks.

---

### 153. `.sort()`

**What:** Sorts an array **in place** (modifies original). By default sorts as strings. For numbers, pass compare function.

**Small example:**
```typescript
const nums = [3, 1, 4];
nums.sort((a, b) => a - b);       // [1, 3, 4] (ascending)
nums.sort((a, b) => b - a);       // [4, 3, 1] (descending)
```

**In this project:** `PriceDiagram.tsx:49` — `left.sort((a, b) => a.price - b.price)` sorts chart levels by price.

---

### 154. `.forEach()`

**What:** Executes a function for each element. Like a for loop but functional style.

**Small example:**
```typescript
[1, 2, 3].forEach(n => console.log(n));
```

**In this project:** `PriceDiagram.tsx:132` — `allLevels.forEach(lvl => { ctx.beginPath(); ... })`. `TradeCalendar.tsx:58` — `w.forEach((week, wi) => { ... })`.

---

### 155. `.findIndex()`

**What:** Returns the index of the first element that passes the test. Returns -1 if not found.

**Small example:**
```typescript
const arr = [10, 20, 30, 40];
const idx = arr.findIndex(n => n > 25);  // 2 (value 30)
```

**In this project:** `PriceDiagram.tsx:187` — `ticks.findIndex(t => t.timestamp >= entryTime)` finds where entry occurred in the tick array.

---

### 156. `.includes()`

**What:** Checks if a string or array contains a given value. Returns true/false.

**Small example:**
```typescript
const msg = "Trailing SL Hit";
console.log(msg.includes("SL"));    // true
console.log(msg.includes("ENTRY")); // false
```

**In this project:** `TerminalLogs.tsx:82-86` — `msg.includes("ENTRY")`, `msg.includes("EXIT")`, `msg.includes("SL")` for log coloring.

---

### 157. `.toFixed(n)`

**What:** Formats a number with `n` decimal places. Returns a **string**.

**Small example:**
```typescript
const pnl = 10.5678;
console.log(pnl.toFixed(2));  // "10.57"
```

**In this project:** `analytics/page.tsx:26` — `(stats?.total_pnl ?? 0).toFixed(2)`.

---

### 158. `.trim()`

**What:** Removes whitespace from both ends of a string.

**Small example:**
```typescript
const input = "  abc123  ";
console.log(input.trim());  // "abc123"
```

**In this project:** `token/page.tsx:36` — `if (!accessToken.trim()) return;` (rejects empty whitespace-only tokens).

---

### 159. `.match(regex)`

**What:** Extracts matches from a string using a regular expression. Returns array of matches or null.

**Small example:**
```typescript
const iso = "2026-07-27T14:30:00.123";
const m = iso.match(/T(\d{2}:\d{2}:\d{2})\.?(\d*)/);
if (m) {
  console.log(m[1]);  // "14:30:00"
  console.log(m[2]);  // "123"
}
```

**In this project:** `TerminalQuadrant.tsx:41` — extracts time from ISO timestamp. Line 59 — parses "HH:MM" format.

---

### 160. `.padStart()` / `.padEnd()`

**What:** Pads a string to a minimum length by adding characters at the start/end.

**Small example:**
```typescript
"5".padStart(2, "0");    // "05"
"hello".padEnd(8, ".");  // "hello..."
```

**In this project:** `TradeCalendar.tsx:79` — `String(d.getFullYear()) + String(d.getMonth() + 1).padStart(2, "0")`.

---

### 161. `Math.min`, `Math.max`, `Math.abs`, `Math.sqrt`

**What:** Math utility functions. `min`/`max` take comma-separated args OR spread an array. `abs` for absolute value.

**Small example:**
```typescript
const nums = [10, -5, 20, 8];
Math.min(...nums)     // -5
Math.max(...nums)     // 20
Math.abs(-10)         // 10
Math.sqrt(64)         // 8
```

**In this project:** `PriceDiagram.tsx:96-97` — `const lo = Math.min(...allVals)`, `const hi = Math.max(...allVals)`. Line 288 — `Math.sqrt((mx - pos.x) ** 2 + (my - pos.y) ** 2)`.

---

### 162. `isNaN()`

**What:** Checks if a value is NaN (Not-a-Number). Returns true for NaN, false for valid numbers. Important to check before using a parsed number.

**Small example:**
```typescript
console.log(isNaN(parseInt("abc")));  // true
console.log(isNaN(42));               // false
```

**In this project:** `TerminalQuadrant.tsx:62` — `if (!isNaN(d.getTime()))` validates that a parsed date is valid.

---

### 163. `new Date()`, `.toLocaleTimeString()`

**What:** `new Date()` creates a Date object representing now. `.toLocaleTimeString()` formats time according to locale.

**Small example:**
```typescript
const now = new Date();
console.log(now.toLocaleTimeString("en-IN", { hour12: false }));
// "14:30:00"
```

**In this project:** `AppHeader.tsx:27` — updates clock display every second.

---

### 164. `Set` / `Set.has()`

**What:** A collection of unique values. Useful for deduplication. `.has()` checks membership.

**Small example:**
```typescript
const unique = new Set([1, 2, 2, 3, 3, 3]);
console.log(unique);   // Set(3) {1, 2, 3}
console.log(unique.has(2));  // true

// Deduplicate array
const arr = [...new Set([1, 2, 2, 3])];  // [1, 2, 3]
```

**In this project:** `SettingsAccordion.tsx:21` — `[...new Set(settings.map((s) => s.category))]` gets unique categories. `TradeCalendar.tsx:75,132` — `new Set(monthEndCols)`.

---

### 165. `Object.keys()` / `Object.entries()`

**What:** `Object.keys(obj)` returns array of keys. `Object.entries(obj)` returns array of `[key, value]` pairs.

**Small example:**
```typescript
const stats = { wins: 10, losses: 5, pnl: 100 };
console.log(Object.keys(stats));       // ["wins", "losses", "pnl"]
console.log(Object.entries(stats));    // [["wins",10], ["losses",5], ["pnl",100]]
```

**In this project:** `TradeCalendar.tsx:65-66` — `Object.keys(counts).length`, `Object.entries(counts).sort(...)`.

---

### 166. `for` / `while` loops

**What:** Traditional loops. `for (init; condition; increment)` — run code a known number of times. `while` — run while condition is true.

**Small example:**
```typescript
for (let i = 0; i < 5; i++) {
  console.log(i);
}

let i = 0;
while (i < 5) {
  console.log(i);
  i++;
}
```

**In this project:** `PriceDiagram.tsx:44` — `for (let i = 1; i <= belowSlCount; i++)` builds SL levels. `TradeCalendar.tsx:48` — `while (cursor <= last)` iterates dates.

---

### 167. `Promise.then().catch()`

**What:** Handle asynchronous operations. `then()` runs on success. `catch()` runs on failure.

**Small example:**
```typescript
fetch("/api/data")
  .then(r => r.json())
  .then(data => console.log(data))
  .catch(err => console.error(err));
```

**In this project:** `page.tsx:15-17` — `fetch(...).then(r => r.json()).then(setStatus).catch(() => {})`.

---

### 168. `async` / `await`

**What:** Syntactic sugar over Promises. `await` pauses execution until the Promise resolves. `async` marks a function as returning a Promise.

**Small example:**
```typescript
async function loadData() {
  try {
    const res = await fetch("/api/data");
    const data = await res.json();
    return data;
  } catch (err) {
    console.error(err);
  }
}
```

**In this project:** All API functions in `api.ts:5-82` are `async`. `token/page.tsx:18` — `const fetchStatus = useCallback(async () => { ... }, [])`.

---

### 169. `try` / `catch`

**What:** Error handling. `try` wraps risky code. `catch` runs if an error occurs. Can have optional `finally` that always runs.

**Small example:**
```typescript
try {
  const res = await fetch("/api/start");
  const data = await res.json();
} catch (err) {
  console.log("Network error:", err);
}
```

**In this project:** `token/page.tsx:19` — `try { ... fetch / validate token ... } catch { setStatus("unknown") }`.

---

### 170. IIFE `(() => { ... })()` in JSX

**What:** Immediately Invoked Function Expression — define and call a function in the same expression. Used in JSX where you can't use `if/else` or `return`.

**Small example:**
```typescript
return (
  <div>
    {(() => {
      if (state === "loading") return <Spinner />;
      if (state === "error") return <Error />;
      return <Data />;
    })()}
  </div>
);
```

**In this project:** `PriceDiagram.tsx:393` — tooltip rendering logic. Line 409 — PnL display logic.

---

### 171. `new Set([...])` for Deduplication

**What:** Create a Set from an array to remove duplicates, then spread back to array.

**Small example:**
```typescript
const arr = ["a", "b", "a", "c", "b"];
const unique = [...new Set(arr)];  // ["a", "b", "c"]
```

**In this project:** `SettingsAccordion.tsx:21` — `const categories = [...new Set(settings.map((s) => s.category))]`.

---

# Section 15: Tailwind CSS v4

### 172. `@import "tailwindcss"`

**What:** Tailwind v4 uses `@import "tailwindcss"` instead of the old `@tailwind` directives. Single import at the top of your CSS file.

**Small example:**
```css
/* app/globals.css */
@import "tailwindcss";
```

**In this project:** `globals.css:1` — starts with `@import "tailwindcss"`.

---

### 173. `@theme inline { --color-* }` (Custom Design Tokens)

**What:** Define your app's design tokens (colors, fonts) in the `@theme` block. These become available as Tailwind utility classes and CSS variables.

**Small example:**
```css
@theme inline {
  --color-brand: #6366f1;
  --color-surface: #111111;
  --font-sans: "Inter", sans-serif;
}

/* Use as: bg-surface text-brand font-sans */
```

**In this project:** `globals.css:3-16` — custom colors like `--color-ce: #9333ea`, `--color-pe: #f59e0b`, `--color-profit: #10b981`, `--color-loss: #ef4444`.

---

### 174. `@keyframes` + Custom CSS Class

**What:** Define and use CSS animations. `@keyframes` specifies the animation. Custom class applies it.

**Small example:**
```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.pulse-dot {
  animation: pulse 1.5s ease-in-out infinite;
}
```

**In this project:** `globals.css:66-74` — `.pulse-dot` animation for live indicator.

---

### 175. `::-webkit-scrollbar` Styling

**What:** Customize the scrollbar appearance (WebKit browsers: Chrome, Edge, Safari). Supports track, thumb, and width.

**Small example:**
```css
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}
```

**In this project:** `globals.css:84-107` — custom thin dark scrollbar for logs and panels.

---

### 176. Grid: `grid grid-cols-2 gap-2`

**What:** CSS Grid layout. `grid-cols-2` = 2 equal columns. `gap-2` = 8px gap between cells.

**Small example:**
```tsx
<div className="grid grid-cols-2 gap-2">
  <div>Item 1</div>
  <div>Item 2</div>
  <div>Item 3</div>
  <div>Item 4</div>
</div>
```

**In this project:** `page.tsx:33` — `grid grid-cols-2 gap-2` creates the 2×2 quadrant layout.

---

### 177. Flex: `flex flex-col items-center`

**What:** Flexbox layout. `flex` = display flex. `flex-col` = vertical direction. `items-center` = center horizontally.

**Small example:**
```tsx
<div className="flex flex-col items-center justify-between h-full">
  <div>Top</div>
  <div>Middle</div>
  <div>Bottom</div>
</div>
```

**In this project:** `page.tsx:21` — `flex flex-col`. Used extensively across all components.

---

### 178. Spacing: `p-2`, `m-4`, `px-3`, `py-1`

**What:** Padding and margin. `p` = all sides, `px` = left+right, `py` = top+bottom. Numbers: 1=4px, 2=8px, 3=12px, 4=16px, etc.

**Small example:**
```tsx
<div className="p-4 px-6 py-2 m-2">Content</div>
<!-- padding: 16px all, 24px left/right, 8px top/bottom -->
```

**In this project:** Every component. E.g., `page.tsx:21` — `p-2`. `TokenModal.tsx` — various margins.

---

### 179. Sizing: `w-full`, `h-8`, `max-w-3xl`

**What:** Width/height utilities. `w-full` = 100% width. `h-8` = 32px height. `max-w-3xl` = max width 768px (responsive).

**Small example:**
```tsx
<div className="w-full max-w-3xl h-8">Content</div>
```

**In this project:** `TokenModal.tsx` — `max-w-md`. Layout — `h-full`, `min-h-screen`.

---

### 180. Colors: `bg-[#0a0a0a]`, `text-white`

**What:** Background and text colors. Custom hex via `bg-[#hex]` or use theme tokens like `bg-surface`. The project uses a dark theme.

**Small example:**
```tsx
<div className="bg-[#111] text-[#e5e7eb] border border-white/10 rounded-lg">
  Dark card
</div>
```

**In this project:** Every component uses dark theme colors. `bg-[#0a0a0a]` (body), `bg-[#111]` (cards), `text-[#e5e7eb]` (primary text).

---

### 181. Borders: `border-white/10`, `rounded-lg`

**What:** `/10` = 10% opacity. So `border-white/10` is a subtle white border. `rounded-lg` = large border radius.

**Small example:**
```tsx
<div className="border border-white/10 rounded-lg bg-[#111]">
  Subtle dark card
</div>
```

**In this project:** `PositionCard.tsx:28` — `border-t-4` for left accent border. Cards use `rounded-lg`.

---

### 182. Transitions: `transition-opacity duration-200`

**What:** Smoothly animate CSS property changes. `transition-opacity` animates opacity. `duration-200` = 200ms.

**Small example:**
```tsx
<button className="opacity-60 hover:opacity-100 transition-opacity duration-200">
  Hover me
</button>
```

**In this project:** `page.tsx:25` — `opacity-60 hover:opacity-100 transition-opacity`.

---

### 183. Dynamic Styles: `style={{ gridTemplateRows }}`

**What:** When Tailwind utility classes can't express a value, use inline `style={{}}` for dynamic values.

**Small example:**
```tsx
<div style={{ gridTemplateRows: "1fr 1fr" }}>
  <div>Top</div>
  <div>Bottom</div>
</div>
```

**In this project:** `page.tsx:34` — `style={{ gridTemplateRows: "1fr 1fr" }}`. `history/page.tsx:56` — `style={{ borderLeftColor: color }}`.

---

### 184. `backdrop-blur-sm`, `opacity-60` (Glassmorphism)

**What:** `backdrop-blur-sm` applies a blur to what's behind the element (glass effect). `opacity-60` makes it semi-transparent.

**Small example:**
```tsx
<div className="backdrop-blur-sm bg-white/10 rounded-lg">
  Frosted glass effect
</div>
```

**In this project:** `page.tsx:25` — `backdrop-blur-sm`. `TokenModal.tsx:18` — `backdrop-blur-sm bg-black/60`.

---

# Section 16: Architecture Patterns used in this Project

### 185. State Machine (Trade Lifecycle)

**What:** A state machine has defined states and transitions. Here, a trade goes through: idle → watching → in_position → exited_win/exited_loss.

**Where used:**
- Frontend: `TerminalQuadrant.tsx` — renders differently based on state
- Backend: `bot_manager.py:19-22` — tracks `self.positions["CE"]["trade1"]` state
- Strategy: `red_candle_high_break.py` — internal state machine (no reference candle → waiting → breakout detected)

---

### 186. Observer Pattern (Pub/Sub)

**What:** One object (subject) maintains a list of listeners and notifies them when something changes. The listeners don't know about each other.

**Where used:** `candle.py:16-21` — `add_listener(callback)` registers listeners. `_notify(event_type, candle)` calls all listeners when a candle closes/updates. `data_streamer.py:51` — registers listener that forwards candle events to WebSocket.

---

### 187. Factory Pattern

**What:** A function that creates and returns objects, hiding the construction details.

**Where used:** `scheduler.py:10,82-97` — `data_streamer_factory(session_name, ce_key, pe_key, ...)` creates and returns a configured `DataStreamer` instance. The factory is passed to `TradingScheduler.__init__()` so the scheduler can create streamers when needed.

---

### 188. Producer-Consumer Queue

**What:** Multiple threads/processes produce items into a queue. A single consumer processes them asynchronously. Decouples producers from consumer.

**Where used:** `live_feed_server.py:29,42,79` — threads call `broadcast_sync()` → `_put_message()` (producer), the async `_drain_queue()` task consumes and broadcasts to WebSocket clients (consumer).

---

### 189. Auto-Reconnect with Exponential Backoff

**What:** When a connection drops, retry with increasing delays to avoid hammering the server. After a point, give up.

**Where used:** `data_streamer.py:479-510` — `reconnect_attempts` starts at 0, `delay = min(base_delay * reconnect_attempts, 30)` → delays: 2, 4, 6, 8... up to 30s. Max 20 attempts.

---

### 190. Stale Watchdog

**What:** Monitor a health signal (last tick time). If too much time passes without a signal, assume something is wrong and take action.

**Where used:** `scheduler.py:325-339` — checks if no tick received for 90 seconds. If so, logs warning and checks if streamer is dead.

---

### 191. SSR Guard (`typeof window === "undefined"`)

**What:** During Server-Side Rendering, browser APIs like WebSocket don't exist. Guard against running browser-only code on the server.

**Where used:** `TerminalQuadrant.tsx:164` — `if (typeof window === "undefined") return` prevents WebSocket creation during SSR.

---

### 192. Memoized Calendar (useMemo)

**What:** Compute a grid of dates (weeks, months) once and cache it. Only recompute when the year changes, not on every render.

**Where used:** `TradeCalendar.tsx:39-77` — generates weeks, month groups, and month-end columns from raw PnL data. Uses `useMemo` to avoid recalculating the calendar grid on every render.

---

### 193. Optimistic UI Update

**What:** Update the UI immediately (before the server confirms) so the user gets instant feedback. Revert on error.

**Where used:** `TradeLogsTable.tsx:38-42` — when deleting a trade, the row is removed from the local state immediately, then the API call is made.

---

### 194. Frozen State Guard

**What:** After a trade exits, prevent tick data from overwriting the final state. "Freeze" the display at the exit moment.

**Where used:** `TerminalQuadrant.tsx:72,176,190,196` — `frozenRef` is set to `true` after exit event. As long as it's true, incoming ticks are ignored (display stays frozen).

---

### 195. Custom Drag-to-Resize

**What:** Implement a draggable resize handle using `mousedown`, `mousemove`, `mouseup` events on `document` (so drag works even outside the element).

**Where used:** `TerminalLogs.tsx:56-79` — `onMouseDown` starts the drag, attaches `mousemove`/`mouseup` listeners to `document`, updates height, cleanup on `mouseup`.

---

### 196. Polling vs Pushing

**What:** Two strategies for getting live data: **polling** (client repeatedly asks server) and **pushing** (server sends data when available).

**Where used in this project:**
- **Polling:** `AppHeader.tsx:22-23` — polls `/api/status` every 5s for bot state updates. `positions/page.tsx:15` — polls every 3s.
- **Pushing (WebSocket):** `TerminalQuadrant.tsx:171` — real-time tick/trade stream. Server pushes ticks as they arrive.
- **Pushing (SSE):** `TerminalLogs.tsx:27` — server pushes log entries via EventSource.

---

## Next Steps After Reading This

1. **Clone a concept** — pick one concept (e.g., "Python Classes"), write your own small project using it
2. **Find it in the code** — open the referenced file:line and read the surrounding context
3. **Modify it** — change a value, comment out a line, see what breaks (the bot is in paper mode, safe)
4. **Teach someone** — explain a concept to a friend; if you can't explain it simply, you haven't understood it

Happy learning!
