from datetime import datetime, timedelta
import pytz
import threading
import time
import requests

IST = pytz.timezone('Asia/Kolkata')

NIFTY_STRIKE_INTERVAL = 50
PRESCAN_STRIKE_RANGE = 25  # number of strikes above/below ATM to pre-subscribe
PRESCAN_RANGE_PTS = PRESCAN_STRIKE_RANGE * NIFTY_STRIKE_INTERVAL  # 25 × 50 = 1250 pts
class TradingScheduler:
    def __init__(self, data_streamer_factory):
        """
        Args:
            data_streamer_factory: Function that creates DataStreamer instance
                                  Should accept session_name parameter
        """
        self.data_streamer_factory = data_streamer_factory
        self.data_streamer = None
        self.is_running = True
        self.current_session = None

    def _get_token(self):
        from settings_db import get_setting
        return get_setting("access_token") or ""

    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

    def log(self, message):
        print(f"[{self.now()}] {message}")

    def get_current_time_str(self):
        return datetime.now(IST).strftime("%H:%M")

    def time_to_seconds(self, time_str):
        parts = time_str.split(":")
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return h * 3600 + m * 60 + s

    def seconds_until(self, target_time):
        now = datetime.now(IST)
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        target_seconds = self.time_to_seconds(time_str=target_time)
        diff = target_seconds - current_seconds
        if diff < 0:
            diff += 86400
        return diff

    def wait_until(self, target_time, description):
        while self.is_running:
            seconds_left = self.seconds_until(target_time)
            if seconds_left < 1:
                break
            if seconds_left <= 60:
                self.log(f"⏳ {description} in {seconds_left}s")
                time.sleep(min(seconds_left, 5))
            else:
                # Only log every 10 minutes to reduce spam
                if seconds_left // 60 % 10 == 0:
                    self.log(f"⏳ {description} in {seconds_left//60}m")
                time.sleep(min(seconds_left, 60))

    def get_expiry(self):
        """Get next weekly expiry date"""
        try:
            base_url = "https://api.upstox.com/v2"
            headers = {
                'Authorization': f'Bearer {self._get_token()}',
                'Accept': 'application/json'
            }
            
            resp = requests.get(
                f"{base_url}/option/contract",
                headers=headers,
                params={'instrument_key': 'NSE_INDEX|Nifty 50'},
                timeout=10
            )
            data = resp.json().get('data', [])
            today = datetime.now(IST).date()
            expiries = sorted(set(
                item['expiry'] for item in data
                if datetime.strptime(item['expiry'], "%Y-%m-%d").date() >= today
            ))
            if expiries:
                expiry = expiries[0]
                is_today = datetime.strptime(expiry, "%Y-%m-%d").date() == today
                self.log(f"Expiry: {expiry}{' (TODAY — expiry day)' if is_today else ''}")
                return expiry
        except Exception as e:
            self.log(f"Expiry fetch failed: {e}")
        return None

    def fetch_chain(self, expiry):
        """Fetch option chain for given expiry"""
        try:
            base_url = "https://api.upstox.com/v2"
            headers = {
                'Authorization': f'Bearer {self._get_token()}',
                'Accept': 'application/json'
            }
            
            self.log(f"Fetching chain for {expiry}...")
            resp = requests.get(
                f"{base_url}/option/chain",
                headers=headers,
                params={
                    'instrument_key': 'NSE_INDEX|Nifty 50',
                    'expiry_date': expiry
                },
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data:
                    self.log(f"Chain fetched – {len(data['data'])} strikes")
                    return data['data']
        except Exception as e:
            self.log(f"Chain error: {e}")
        return None

    def get_spot(self):
        """Get current NIFTY spot price"""
        try:
            base_url = "https://api.upstox.com/v2"
            headers = {
                'Authorization': f'Bearer {self._get_token()}',
                'Accept': 'application/json'
            }
            
            resp = requests.get(
                f"{base_url}/market-quote/ltp",
                headers=headers,
                params={'instrument_key': 'NSE_INDEX|Nifty 50'},
                timeout=10
            )
            data = resp.json().get('data', {}).get('NSE_INDEX:Nifty 50', {})
            spot = float(data.get('last_price', 0))
            if spot > 0:
                self.log(f"NIFTY Spot: {spot:.2f}")
                return spot
        except Exception as e:
            self.log(f"Spot fetch failed: {e}")
        return None

    def _get_chain_candidates(self, range_pts):
        """Fetch chain and return candidates within range_pts of spot.
        Returns list of {strike, key, type} or None on failure.
        Shared by get_prescan_keys() and fetch_live_strikes()."""
        expiry = self.get_expiry()
        if not expiry:
            self.log(f"❌ Could not get expiry")
            return None
        spot = self.get_spot()
        if not spot:
            self.log(f"❌ Could not get spot price")
            return None
        chain = self.fetch_chain(expiry)
        if not chain:
            self.log(f"❌ Could not fetch option chain")
            return None
        candidates = []
        for entry in chain:
            strike = int(float(entry.get('strike_price', 0)))
            if abs(strike - spot) > range_pts:
                continue
            for opt, side in [(entry.get('call_options', {}), 'CE'),
                              (entry.get('put_options', {}), 'PE')]:
                if opt:
                    key = opt.get('instrument_key', '')
                    if key:
                        candidates.append({'strike': strike, 'key': key, 'type': side})
        self.log(f"🔍 Found {len([c for c in candidates if c['type'] == 'CE'])} CE and {len([c for c in candidates if c['type'] == 'PE'])} PE candidates within {range_pts} pts of spot")
        return candidates

    def fetch_live_strikes(self):
        """
        Fetch live strikes using real-time LTP with spot-based filtering
        Returns dict with CE/PE keys and premiums
        Uses NUMERIC instrument_key format (NSE_FO|12345) for WebSocket compatibility
        """
        try:
            # Get expiry
            expiry = self.get_expiry()
            if not expiry:
                self.log(f"❌ Could not get expiry")
                return None
            
            # Get current spot price
            spot = self.get_spot()
            if not spot:
                self.log(f"❌ Could not get spot price")
                return None
            
            # Fetch chain directly to get numeric instrument keys
            self.log(f"📊 Fetching option chain for live strikes...")
            chain = self.fetch_chain(expiry)
            if not chain:
                self.log(f"❌ Could not fetch option chain")
                return None
            
            # Collect all strikes near spot (±500 pts) from chain (keys only)
            near = []
            for entry in chain:
                strike = int(float(entry.get('strike_price', 0)))
                if abs(strike - spot) > 500:
                    continue
                for opt, side in [(entry.get('call_options', {}), 'CE'),
                                  (entry.get('put_options', {}), 'PE')]:
                    if opt and opt.get('instrument_key'):
                        near.append({
                            'strike': strike,
                            'key': opt['instrument_key'],
                            'type': side,
                        })

            self.log(f"🔍 Found {len([x for x in near if x['type'] == 'CE'])} CE and "
                     f"{len([x for x in near if x['type'] == 'PE'])} PE strikes near spot")

            # Batch live LTP (chunk 50 — Upstox limit)
            keys = [x['key'] for x in near]
            ltp_map = {}
            base_url = "https://api.upstox.com/v2"
            headers = {
                'Authorization': f'Bearer {self._get_token()}',
                'Accept': 'application/json'
            }
            for i in range(0, len(keys), 50):
                chunk = keys[i:i+50]
                try:
                    resp = requests.get(
                        f"{base_url}/market-quote/ltp",
                        headers=headers,
                        params={'instrument_key': ','.join(chunk)},
                        timeout=10
                    )
                    data = resp.json().get('data', {})
                    for k, v in data.items():
                        token = v.get('instrument_token') or k.replace(':', '|')
                        ltp_map[token] = float(v.get('last_price', 0))
                        ltp_map[k] = float(v.get('last_price', 0))
                except Exception as e:
                    self.log(f"⚠️ LTP batch failed: {e}")

            ce_list = []
            pe_list = []
            for x in near:
                prem = ltp_map.get(x['key'], 0) or ltp_map.get(x['key'].replace('|', ':'), 0)
                if prem <= 0:
                    continue
                row = {
                    'strike': x['strike'],
                    'premium': prem,
                    'key': x['key'],
                    'diff': abs(prem - 100),
                }
                if x['type'] == 'CE':
                    ce_list.append(row)
                else:
                    pe_list.append(row)
            
            self.log(f"🔍 Found {len(ce_list)} CE and {len(pe_list)} PE strikes near spot")
            
            # Find strikes >= ₹100, closest to ₹100
            self.log(f"🔍 Scanning for strikes >= ₹100...")
            ce_candidates = [x for x in ce_list if x['premium'] >= 100]
            pe_candidates = [x for x in pe_list if x['premium'] >= 100]
            
            # Fallback to >= ₹80 if needed
            if not ce_candidates or not pe_candidates:
                self.log(f"⚠️ No strikes >= ₹100, trying >= ₹80...")
                ce_candidates = [x for x in ce_list if x['premium'] >= 80]
                pe_candidates = [x for x in pe_list if x['premium'] >= 80]
            
            # Fallback to >= ₹50 if needed
            if not ce_candidates or not pe_candidates:
                self.log(f"⚠️ No strikes >= ₹80, trying >= ₹50...")
                ce_candidates = [x for x in ce_list if x['premium'] >= 50]
                pe_candidates = [x for x in pe_list if x['premium'] >= 50]
            
            if not ce_candidates or not pe_candidates:
                self.log(f"❌ No suitable strikes found")
                return None
            
            # Select best (closest to ₹100)
            ce_best = min(ce_candidates, key=lambda x: x['diff'])
            pe_best = min(pe_candidates, key=lambda x: x['diff'])
            
            self.log(f"✅ Selected: CE={ce_best['strike']}@{ce_best['premium']:.2f} ({ce_best['key']}), PE={pe_best['strike']}@{pe_best['premium']:.2f} ({pe_best['key']})")
            
            return {
                'ce_key': ce_best['key'],
                'ce_strike': ce_best['strike'],
                'ce_premium': ce_best['premium'],
                'pe_key': pe_best['key'],
                'pe_strike': pe_best['strike'],
                'pe_premium': pe_best['premium']
            }
            
        except Exception as e:
            self.log(f"❌ Error in fetch_live_strikes: {e}")
            return None

    def get_prescan_keys(self):
        """Fetch option chain and return all candidate instrument keys for pre-subscribe"""
        try:
            candidates = self._get_chain_candidates(PRESCAN_RANGE_PTS)
            if not candidates:
                return None
            return [c['key'] for c in candidates]
        except Exception as e:
            self.log(f"❌ Error in get_prescan_keys: {e}")
            return None

    def _poll_rest_ohlc(self, ce_key, pe_key, hold_minute):
        """Poll REST OHLC for the held first candle at multiple offsets, then at
        the last offset commit the confirmed candle (or fall back to the parked WS
        candle). Poll lines only — no tick-level logging."""
        POLL_OFFSETS = [10, 12, 15, 18, 20]
        base_url = "https://api.upstox.com/v3"
        snap_history = {}
        raw_dumped = False

        def wait_until_offset(offset):
            target_dt = hold_minute + timedelta(minutes=1, seconds=offset)
            while self.is_running:
                if datetime.now(IST) >= target_dt:
                    return
                time.sleep(0.2)

        for offset in POLL_OFFSETS:
            wait_until_offset(offset)
            if not self.is_running:
                return
            for key, label in [(ce_key, 'CE'), (pe_key, 'PE')]:
                try:
                    headers = {
                        'Authorization': f'Bearer {self._get_token()}',
                        'Accept': 'application/json'
                    }
                    resp = requests.get(
                        f"{base_url}/market-quote/ohlc",
                        headers=headers,
                        params={'instrument_key': key, 'interval': 'I1'},
                        timeout=10
                    )
                    data = resp.json()
                    if not raw_dumped:
                        raw_dumped = True
                        print(f"[{self.now()}] [REST-OHLC] raw response: {data}")

                    prev = None
                    if data.get('status') == 'success':
                        for inst_data in data.get('data', {}).values():
                            if inst_data.get('instrument_token') == key:
                                prev = inst_data.get('prev_ohlc')
                                break

                    if not prev:
                        print(f"[{self.now()}] [REST-{label}] @09:16:{offset:02d} — prev_ohlc not available")
                        continue

                    ts_ms = prev.get('ts', 0)
                    o = float(prev.get('open', 0))
                    h = float(prev.get('high', 0))
                    l = float(prev.get('low', 0))
                    c = float(prev.get('close', 0))
                    candle_ts = datetime.fromtimestamp(ts_ms / 1000, IST) if ts_ms else None
                    ct_str = candle_ts.strftime('%H:%M') if candle_ts else '?'
                    color = 'GREEN' if c >= o else 'RED'
                    snap = (candle_ts, o, h, l, c)
                    history = snap_history.setdefault(label, [])
                    history.append(snap)
                    stable = len(history) >= 2 and history[-1] == history[-2]
                    tag = " STABLE (unchanged)" if stable else ""
                    print(f"[{self.now()}] [REST-{label}] @09:16:{offset:02d} CANDLE {ct_str} "
                          f"O={o} H={h} L={l} C={c} {color}{tag}")
                except Exception as e:
                    print(f"[{self.now()}] [REST-{label}] @09:16:{offset:02d} — fetch failed: {e}")

        if not self.is_running:
            return

        ds = self.data_streamer
        if ds is None:
            self.log("REST OHLC commit skipped — streamer gone")
            return

        for key, label in [(ce_key, 'CE'), (pe_key, 'PE')]:
            history = snap_history.get(label, [])
            confirmed = False
            # Commit only if the last two polls agree (stability check) and the
            # candle's timestamp matches the held minute.
            if len(history) >= 2 and history[-1] == history[-2]:
                snap = history[-1]
                candle_ts = snap[0]
                if candle_ts is not None and candle_ts.replace(second=0, microsecond=0) == hold_minute:
                    o, h, l, c = snap[1], snap[2], snap[3], snap[4]

                    # Sanity: reject impossible OHLC (e.g. Monday's H<O on PE)
                    if h < o or l > o or h < c or l > c or h < l:
                        print(f"[{self.now()}] [REST-{label}] REJECTED impossible OHLC "
                              f"O={o} H={h} L={l} C={c} — falling back to WS")
                    else:
                        held = None
                        comp = ds.components.get(label)
                        if comp:
                            held = comp['candle_aggregator'].get_pending_held()

                        if held is not None:
                            hw, lw = held['high'], held['low']
                            print(f"[{self.now()}] [REST-{label}] WS held: "
                                  f"O={held['open']:.2f} H={hw:.2f} "
                                  f"L={lw:.2f} C={held['close']:.2f}")
                            print(f"[{self.now()}] [REST-{label}] REST snap: "
                                  f"O={o} H={h} L={l} C={c}")
                            # Take the wider, more complete range; keep REST open/close.
                            h = max(h, hw)
                            l = min(l, lw)
                            if abs(held['open'] - o) > 1:
                                print(f"[{self.now()}] [REST-{label}] OPEN_MISMATCH "
                                      f"O_ws={held['open']:.2f} O_rest={o:.2f} (diff {abs(held['open'] - o):.2f}) — "
                                      f"kept REST open, flagged for Tuesday comparison")

                        confirmed = True
                        candle = {
                            'timestamp': candle_ts,
                            'open': o,
                            'high': h,
                            'low': l,
                            'close': c,
                        }
                        ds.commit_confirmed_candle(label, candle)
                        print(f"[{self.now()}] [REST-{label}] COMMITTED confirmed 09:15 candle "
                              f"O={o} H={h} L={l} C={c}")
            if not confirmed:
                ds.commit_ws_fallback(label)
                print(f"[{self.now()}] [REST-{label}] no stable REST confirm — WS fallback")

        # Diagnostic only (no behavior change): compare the chart-backed Intraday Candle
        # historical API for the held minute, then retry once ~35s in for CDN-settled data.
        self._historical_diagnostic(ce_key, pe_key, hold_minute)

    def _historical_diagnostic(self, ce_key, pe_key, hold_minute):
        """Log the chart-backed historical candle for the held minute (Tuesday comparison).

        Two passes: immediately after commit (may lag) and again ~35s later (CDN-settled).
        Logs the candle matching hold_minute and the latest candle present in the response.
        """
        try:
            targets = [(ce_key, 'CE'), (pe_key, 'PE')]
            passes = [
                (timedelta(seconds=3), 'pass1'),
                (timedelta(minutes=1, seconds=35), 'pass2'),
            ]
            for delay, tag in passes:
                target_dt = hold_minute + delay
                while self.is_running and datetime.now(IST) < target_dt:
                    time.sleep(0.5)
                if not self.is_running:
                    return
                for key, label in targets:
                    self._fetch_historical_candle(key, label, hold_minute, tag)
        except Exception as e:
            print(f"[{self.now()}] [HIST] diagnostic aborted: {e}")

    def _parse_candle_ts(self, value):
        """Parse a historical-candle timestamp. Upstox V3 returns ISO datetime
        strings ('2026-08-04T09:15:00+05:30'); fall back to epoch-ms ints."""
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value / 1000, IST)
            s = str(value)
            try:
                parsed = datetime.fromisoformat(s)
            except ValueError:
                parsed = datetime.fromtimestamp(int(s) / 1000, IST)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=IST)
            return parsed.astimezone(IST)
        except (ValueError, TypeError, OverflowError):
            return None

    def _fetch_historical_candle(self, key, label, hold_minute, tag):
        """Fetch Intraday Candle V3 (chart-backed) and log the held-minute candle."""
        try:
            headers = {
                'Authorization': f'Bearer {self._get_token()}',
                'Accept': 'application/json',
            }
            today = datetime.now(IST).strftime('%Y-%m-%d')
            resp = requests.get(
                f"https://api.upstox.com/v3/historical-candle/intraday/{key}/minutes/1",
                headers=headers,
                params={'to_date': today},
                timeout=10,
            )
            data = resp.json()
            candles = (data.get('data') or {}).get('candles', [])
            if not candles:
                print(f"[{self.now()}] [HIST-{label}] [{tag}] no candles in historical response")
                return
            target = None
            for row in candles:
                if len(row) >= 6:
                    cts = self._parse_candle_ts(row[0])
                    if cts is not None and cts.replace(second=0, microsecond=0) == hold_minute:
                        target = row
            last_ts = '?'
            if candles:
                last_ts_parsed = self._parse_candle_ts(candles[-1][0])
                if last_ts_parsed is not None:
                    last_ts = last_ts_parsed.strftime('%H:%M')
            if target:
                o, h, l, c = float(target[1]), float(target[2]), float(target[3]), float(target[4])
                color = 'GREEN' if c >= o else 'RED'
                print(f"[{self.now()}] [HIST-{label}] [{tag}] CANDLE {hold_minute.strftime('%H:%M')} "
                      f"O={o} H={h} L={l} C={c} {color} (latest in response: {last_ts})")
            else:
                print(f"[{self.now()}] [HIST-{label}] [{tag}] {hold_minute.strftime('%H:%M')} candle "
                      f"not in historical yet (CDN lag) — latest available: {last_ts}")
        except Exception as e:
            print(f"[{self.now()}] [HIST-{label}] [{tag}] fetch failed: {e}")

    def start_streaming(self, ce_key=None, pe_key=None, ce_strike=None, pe_strike=None, prescan_keys=None):
        """Start the data streamer with specific strikes or prescan keys for Path A"""
        if prescan_keys:
            self.log(f"🚀 Starting pre-subscribe streaming with {len(prescan_keys)} instruments...")
        else:
            self.log(f"🚀 Starting streaming with strikes...")
        self.current_session = "day"
        self.data_streamer = self.data_streamer_factory(
            session_name="day",
            ce_key=ce_key,
            pe_key=pe_key,
            ce_strike=ce_strike,
            pe_strike=pe_strike,
            prescan_keys=prescan_keys,
        )
        threading.Thread(target=self.data_streamer.run, daemon=True).start()
        if prescan_keys:
            self.log(f"✅ Pre-subscribe streaming started — waiting for strike selection")
        else:
            self.log(f"✅ Streaming started")
            self.log(f"📊 Strategy will start automatically when first OHLC candle is received")

    def stop_streaming(self):
        if self.data_streamer:
            self.log(f"🛑 Stopping streaming...")
            self.data_streamer.close()
            self.data_streamer = None
            self.current_session = None
            self.log(f"✅ Streaming stopped")

    async def start(self):
        self.is_running = True
        self.log(f"🚀 Bot Started")
        current_time = self.get_current_time_str()
        
        from settings_db import get_as_dict
        s = get_as_dict()
        
        market_start = s.get('market_start', '09:15')
        market_end = s.get('market_end', '15:30')
        market_open_delay = int(s.get('market_open_delay', 40))
        market_start_time = datetime.strptime(market_start, "%H:%M")
        
        if current_time > market_end:
            self.log(f"🔒 Market closed")
            return
        
        live_selection_time = (market_start_time + timedelta(seconds=market_open_delay)).strftime("%H:%M:%S")
        current_time_full = datetime.now(IST).strftime("%H:%M:%S")
        
        # Decide Path A (pre-subscribe) vs Path B (mid-session)
        PATH_A_CUTOFF = "09:20"
        is_path_a = current_time < PATH_A_CUTOFF
        
        if is_path_a:
            # ── Path A: Pre-subscribe ~200 strikes before market open ──
            prescan_start = (market_start_time - timedelta(seconds=30)).strftime("%H:%M:%S")
            self.log(f"⏳ Path A: Pre-subscribing at {prescan_start}")
            self.wait_until(prescan_start, "Pre-subscribe start")
            
            prescan_keys = self.get_prescan_keys()
            if prescan_keys:
                self.start_streaming(prescan_keys=prescan_keys)
                self.log(f"📡 Pre-subscribed {len(prescan_keys)} instruments — collecting pre-open OHLC")
            else:
                self.log(f"⚠️ Prescan keys unavailable, falling back to Path B")
                is_path_a = False
            
            # Wait for live selection time (shared with Path B)
            if current_time_full < live_selection_time:
                self.log(f"⏳ Waiting for live premium selection at {live_selection_time}")
                self.wait_until(live_selection_time, "Live premium selection")
        else:
            # ── Path B: Wait and start directly ──
            if current_time_full < live_selection_time:
                self.log(f"⏳ Waiting for live premium selection at {live_selection_time}")
                self.wait_until(live_selection_time, "Live premium selection")
        
        # STEP: Fetch live strikes (shared by both paths)
        self.log(f"🔧 Fetching live strikes...")
        strikes = self.fetch_live_strikes()
        
        if not strikes:
            self.log(f"❌ Could not fetch strikes, exiting")
            if is_path_a and self.data_streamer:
                self.stop_streaming()
            return
        
        self.log(f"✅ Selected strikes:")
        self.log(f"   CE: {strikes['ce_strike']} (Premium: ₹{strikes['ce_premium']:.2f}) | Key: {strikes['ce_key']}")
        self.log(f"   PE: {strikes['pe_strike']} (Premium: ₹{strikes['pe_premium']:.2f}) | Key: {strikes['pe_key']}")
        
        # STEP: Finalize (Path A) or start streaming (Path B)
        if is_path_a and self.data_streamer:
            # If finalize_selection fails (shouldn't), fall back to Path B
            if hasattr(self.data_streamer, '_prescan_aggregators') and not self.data_streamer._prescan_aggregators:
                self.log(f"⚠️ Prescan aggregators already empty — switching to Path B")
                is_path_a = False
            else:
                hold_minute = datetime.now(IST).replace(second=0, microsecond=0)
                self.data_streamer.finalize_selection(
                    ce_key=strikes['ce_key'],
                    pe_key=strikes['pe_key'],
                    ce_strike=strikes['ce_strike'],
                    pe_strike=strikes['pe_strike'],
                    hold_minute=hold_minute,
                )
                self.log(f"📊 Strategy started — prescan aggregators injected")
                # Publish the finalized strikes so the dashboard navbar (bot_manager.strikes)
                # stops showing CE-- / PE-- on Path A runs.
                if self.data_streamer and self.data_streamer.bot_manager:
                    self.data_streamer.bot_manager.strikes = {
                        "CE": str(strikes['ce_strike']),
                        "PE": str(strikes['pe_strike']),
                    }
                threading.Thread(
                    target=self._poll_rest_ohlc,
                    args=(strikes['ce_key'], strikes['pe_key'], hold_minute),
                    daemon=True
                ).start()

        if not is_path_a or not self.data_streamer:
            if is_path_a and self.data_streamer:
                self.stop_streaming()
            self.start_streaming(
                strikes['ce_key'], strikes['pe_key'],
                ce_strike=strikes['ce_strike'], pe_strike=strikes['pe_strike']
            )
            self.log(f"📊 Waiting for first OHLC candle to start strategy...")
        
        # STEP: Wait until market end with streamer health watchdog
        STALE_THRESHOLD = timedelta(seconds=90)
        s = get_as_dict()
        market_end = s.get('market_end', '15:30')
        while self.is_running and self.get_current_time_str() < market_end:
            time.sleep(30)
            ds = self.data_streamer
            if ds:
                # Auto-stop: if both sides have finished all their trades (can_trade False
                # on CE and PE, and neither is holding a position), end the session early.
                comps = getattr(ds, 'components', None)
                if comps:
                    sides = [c for inst, c in comps.items() if inst in ('CE', 'PE')]
                    if len(sides) == 2 and all(
                        not c.get('can_trade', False)
                        and not c['position_manager'].is_in_position()
                        for c in sides
                    ):
                        self.log("🛑 All trades complete — auto-stopping session")
                        self.stop_streaming()
                        self.log(f"✅ Done for today")
                        self.is_running = False
                        return
                tick_times = [t for t in ds.last_tick_time.values() if t is not None]
                if tick_times:
                    newest = max(tick_times)
                    gap = datetime.now(IST) - newest
                    if gap > STALE_THRESHOLD:
                        self.log(f"🔴 No ticks for {gap.seconds}s — streamer may be dead")
                        if not ds.running:
                            self.log("🔴 Streamer confirmed dead — stopping session")
                            break
        self.stop_streaming()
        self.log(f"✅ Done for today")
        self.is_running = False

    def stop(self):
        self.log(f"🛑 Stopping...")
        self.is_running = False
        self.stop_streaming()
