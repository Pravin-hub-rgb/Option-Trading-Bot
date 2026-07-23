# Task: Add diagnostic logging + fix candle-completion race condition

Scope: `backend/core/candle.py`, `backend/upstox/data_streamer.py`, `backend/strategies/red_candle_high_break.py`

Goal: (1) log every OHLC candle exactly as the bot receives it, and every time a
reference candle is set/shifted, so the next false-entry can be diagnosed from
real captured data instead of guesswork. (2) fix a real race condition where
candle "completed" status is decided by `datetime.now()` at processing time
instead of the feed's own timestamp.

Apply all four changes below, then run the bot live and paste back the new
`CANDLE` / `REF` log lines around the next entry.

---

## 1. `backend/core/candle.py` — use feed time, not wall clock, to classify candles

**Find:**
```python
    def update_from_ohlc(self, timestamp, open_price, high_price, low_price, close_price):
        minute = timestamp.replace(second=0, microsecond=0)
        minute_key = minute.strftime('%Y-%m-%d %H:%M')
        
        if minute_key in self.processed_minutes:
            return False
        
        candle = {
            'timestamp': minute,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'symbol': self.symbol
        }
        
        current_time = datetime.now(IST).replace(second=0, microsecond=0)
        
        if minute < current_time:
```

**Replace with:**
```python
    def update_from_ohlc(self, timestamp, open_price, high_price, low_price, close_price, feed_time=None):
        minute = timestamp.replace(second=0, microsecond=0)
        minute_key = minute.strftime('%Y-%m-%d %H:%M')
        
        if minute_key in self.processed_minutes:
            return False
        
        candle = {
            'timestamp': minute,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'symbol': self.symbol
        }
        
        # Use the feed's own trade timestamp (ltt) to decide if a candle is
        # complete, NOT datetime.now() at processing time. Wall-clock time can
        # be milliseconds late relative to the minute boundary, which would
        # otherwise let a still-forming candle get committed to history early
        # with only a partial high/low.
        ref_time = feed_time if feed_time else datetime.now(IST)
        current_time = ref_time.replace(second=0, microsecond=0)
        
        if minute < current_time:
```

No other lines in this method need to change — the `elif minute == current_time:` branch and everything below stays as-is.

---

## 2. `backend/upstox/data_streamer.py` — pass feed time through, and log every candle + reference change

**2a. `process_ohlc_candles` — accept and forward `feed_time`, log each committed candle**

**Find:**
```python
    def process_ohlc_candles(self, inst_type, ohlc_list):
        comp = self.components[inst_type]
        
        i1_candles = [c for c in ohlc_list if c.get('interval') == 'I1']
        i1_candles.sort(key=lambda c: int(c.get('ts', 0)), reverse=True)
        
        for candle_data in i1_candles[:2]:
            ts_ms = int(candle_data.get('ts', 0))
            candle_ts = datetime.fromtimestamp(ts_ms / 1000, IST)
            
            open_price = float(candle_data.get('open', 0))
            high_price = float(candle_data.get('high', 0))
            low_price = float(candle_data.get('low', 0))
            close_price = float(candle_data.get('close', 0))
            
            is_new = comp['candle_aggregator'].update_from_ohlc(
                timestamp=candle_ts,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price
            )
            
            if is_new:
                comp['strategy'].on_new_candle_closed()
```

**Replace with:**
```python
    def process_ohlc_candles(self, inst_type, ohlc_list, feed_time=None):
        comp = self.components[inst_type]
        
        i1_candles = [c for c in ohlc_list if c.get('interval') == 'I1']
        i1_candles.sort(key=lambda c: int(c.get('ts', 0)), reverse=True)
        
        for candle_data in i1_candles[:2]:
            ts_ms = int(candle_data.get('ts', 0))
            candle_ts = datetime.fromtimestamp(ts_ms / 1000, IST)
            
            open_price = float(candle_data.get('open', 0))
            high_price = float(candle_data.get('high', 0))
            low_price = float(candle_data.get('low', 0))
            close_price = float(candle_data.get('close', 0))
            
            is_new = comp['candle_aggregator'].update_from_ohlc(
                timestamp=candle_ts,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                feed_time=feed_time
            )
            
            if is_new:
                color = 'RED' if open_price > close_price else 'GREEN'
                print(f"[{inst_type}] CANDLE {candle_ts.strftime('%H:%M')} "
                      f"O={open_price:.2f} H={high_price:.2f} L={low_price:.2f} "
                      f"C={close_price:.2f} {color} (feed_time={feed_time.strftime('%H:%M:%S.%f')[:-3] if feed_time else 'N/A'})")
                comp['strategy'].on_new_candle_closed()
```

**2b. Both call sites of `process_ohlc_candles` inside `on_message` — pass `timestamp` through as `feed_time`**

There are two call sites (dict/JSON path and protobuf/binary path).

**Dict path — find:**
```python
                    if ohlc_list:
                        self.process_ohlc_candles(inst_type, ohlc_list)
                    
                    self.process_tick(inst_type, ltp, timestamp)
```

**Replace with:**
```python
                    if ohlc_list:
                        self.process_ohlc_candles(inst_type, ohlc_list, feed_time=timestamp)
                    
                    self.process_tick(inst_type, ltp, timestamp)
```

**Protobuf path — find:**
```python
                                    if ohlc_list:
                                        self.process_ohlc_candles(inst_type, ohlc_list)
```

**Replace with:**
```python
                                    if ohlc_list:
                                        self.process_ohlc_candles(inst_type, ohlc_list, feed_time=timestamp)
```

---

## 3. `backend/strategies/red_candle_high_break.py` — log reference candle set/shift

**Find (Stage 1 block):**
```python
        # STAGE 1: Looking for reference red candle
        if not self.reference_candle:
            if candle_history:
                last_candle = candle_history[-1]
                if self.is_red_candle(last_candle):
                    self.reference_candle = last_candle
                    self.candles_since_reference = 0
                    # Don't enter yet, just set reference
                    return None
            return None
```

**Replace with:**
```python
        # STAGE 1: Looking for reference red candle
        if not self.reference_candle:
            if candle_history:
                last_candle = candle_history[-1]
                if self.is_red_candle(last_candle):
                    self.reference_candle = last_candle
                    self.candles_since_reference = 0
                    print(f"[STRATEGY] Reference SET: "
                          f"{last_candle['timestamp'].strftime('%H:%M')} "
                          f"O={last_candle['open']:.2f} H={last_candle['high']:.2f} "
                          f"L={last_candle['low']:.2f} C={last_candle['close']:.2f} | "
                          f"current_ltp={current_ltp:.2f}")
                    # Don't enter yet, just set reference
                    return None
            return None
```

**Find (Stage 2 shift block):**
```python
        # Check if newer red candle appeared (shift reference)
        if self.allow_reference_shift and candle_history:
            last_candle = candle_history[-1]
            if self.is_red_candle(last_candle) and last_candle != self.reference_candle:
                self.reference_candle = last_candle
                self.candles_since_reference = 0
                return None
```

**Replace with:**
```python
        # Check if newer red candle appeared (shift reference)
        if self.allow_reference_shift and candle_history:
            last_candle = candle_history[-1]
            if self.is_red_candle(last_candle) and last_candle != self.reference_candle:
                print(f"[STRATEGY] Reference SHIFTED: "
                      f"{last_candle['timestamp'].strftime('%H:%M')} "
                      f"O={last_candle['open']:.2f} H={last_candle['high']:.2f} "
                      f"L={last_candle['low']:.2f} C={last_candle['close']:.2f} | "
                      f"current_ltp={current_ltp:.2f}")
                self.reference_candle = last_candle
                self.candles_since_reference = 0
                return None
```

---

## 4. What to check once it's live

You'll now see lines like this in the console before every entry:

```
[CE] CANDLE 09:15 O=133.00 H=133.00 L=121.00 C=121.50 RED (feed_time=09:16:01.240)
[STRATEGY] Reference SET: 09:15 O=133.00 H=133.00 L=121.00 C=121.50 | current_ltp=123.30
[CE] ENTRY at 133.00 | SL: 128.00 (slot 1)
```

Paste back the `CANDLE` and `Reference SET/SHIFTED` lines around the next
entry — that tells us definitively what candle the bot actually used, instead
of inferring it from entry price + your Upstox chart. If the reference's
logged `H=` value ever disagrees with what you see on the chart for that
minute, that's a feed-data issue (Upstox side), not a strategy bug — and this
log is what proves it either way.