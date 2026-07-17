from datetime import datetime, timedelta
import pytz
import threading
import time
import requests

IST = pytz.timezone('Asia/Kolkata')

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
                self.log(f"Expiry: {expiry}")
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
            
            # Build CE/PE lists with numeric keys from chain (like test script)
            ce_list = []
            pe_list = []
            
            for entry in chain:
                strike = int(float(entry.get('strike_price', 0)))
                
                # Only process strikes near spot (±500 points)
                if abs(strike - spot) > 500:
                    continue
                
                # CE - get numeric instrument_key from chain
                ce = entry.get('call_options', {})
                if ce:
                    ltp = float(ce.get('market_data', {}).get('ltp', 0))
                    key = ce.get('instrument_key', '')  # NUMERIC format: NSE_FO|12345
                    if ltp > 0 and key:
                        ce_list.append({
                            'strike': strike,
                            'premium': ltp,
                            'key': key,  # NUMERIC key for WebSocket
                            'diff': abs(ltp - 100)
                        })
                
                # PE - get numeric instrument_key from chain
                pe = entry.get('put_options', {})
                if pe:
                    ltp = float(pe.get('market_data', {}).get('ltp', 0))
                    key = pe.get('instrument_key', '')  # NUMERIC format: NSE_FO|12345
                    if ltp > 0 and key:
                        pe_list.append({
                            'strike': strike,
                            'premium': ltp,
                            'key': key,  # NUMERIC key for WebSocket
                            'diff': abs(ltp - 100)
                        })
            
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
                'ce_key': ce_best['key'],  # NUMERIC format
                'ce_strike': ce_best['strike'],
                'ce_premium': ce_best['premium'],
                'pe_key': pe_best['key'],  # NUMERIC format
                'pe_strike': pe_best['strike'],
                'pe_premium': pe_best['premium']
            }
            
        except Exception as e:
            self.log(f"❌ Error in fetch_live_strikes: {e}")
            return None

    def start_streaming(self, ce_key, pe_key, ce_strike=None, pe_strike=None):
        """Start the data streamer with specific strikes"""
        self.log(f"🚀 Starting streaming with strikes...")
        self.current_session = "day"
        # Use factory to create data streamer with specific strikes
        self.data_streamer = self.data_streamer_factory(
            session_name="day",
            ce_key=ce_key,
            pe_key=pe_key,
            ce_strike=ce_strike,
            pe_strike=pe_strike,
        )
        threading.Thread(target=self.data_streamer.run, daemon=True).start()
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
        
        if current_time > market_end:
            self.log(f"🔒 Market closed")
            return
        
        # STEP 1: Wait until market_open + market_open_delay
        market_start_time = datetime.strptime(market_start, "%H:%M")
        live_selection_time = (market_start_time + timedelta(seconds=market_open_delay)).strftime("%H:%M:%S")
        current_time_full = datetime.now(IST).strftime("%H:%M:%S")
        
        if current_time_full < live_selection_time:
            self.log(f"⏳ Waiting for live premium selection at {live_selection_time}")
            self.wait_until(live_selection_time, "Live premium selection")
        
        # STEP 2: Fetch live strikes (NEW APPROACH - happens BEFORE streaming starts!)
        self.log(f"🔧 Fetching live strikes...")
        strikes = self.fetch_live_strikes()
        
        if not strikes:
            self.log(f"❌ Could not fetch strikes, exiting")
            return
        
        # Log selected strikes
        self.log(f"✅ Selected strikes:")
        self.log(f"   CE: {strikes['ce_strike']} (Premium: ₹{strikes['ce_premium']:.2f}) | Key: {strikes['ce_key']}")
        self.log(f"   PE: {strikes['pe_strike']} (Premium: ₹{strikes['pe_premium']:.2f}) | Key: {strikes['pe_key']}")
        
        # STEP 3: Start streaming with CORRECT strikes (happens AFTER we know which strikes to use!)
        self.log(f"🚀 Starting streaming with selected strikes...")
        self.start_streaming(
            strikes['ce_key'], strikes['pe_key'],
            ce_strike=strikes['ce_strike'], pe_strike=strikes['pe_strike']
        )
        
        # STEP 4: Strategy will start automatically when first OHLC candle is received
        # No hardcoded timing - strategy starts when data is available
        self.log(f"📊 Waiting for first OHLC candle to start strategy...")
        
        # STEP 5: Wait until market end (silent wait)
        s = get_as_dict()
        market_end = s.get('market_end', '15:30')
        while self.is_running and self.get_current_time_str() < market_end:
            time.sleep(60)  # Check every minute without logging
        self.stop_streaming()
        self.log(f"✅ Done for today")
        self.is_running = False

    def stop(self):
        self.log(f"🛑 Stopping...")
        self.is_running = False
        self.stop_streaming()
