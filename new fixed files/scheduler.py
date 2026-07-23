import asyncio
from datetime import datetime
import pytz
from config import ACCESS_TOKEN, MARKET_START, MARKET_END, CONNECTION_START
from upstox.strike_selector import StrikeSelector
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
        s = int(parts[2]) if len(parts) == 3 else 0  # ← FIXED: Handle HH:MM:SS format
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
                'Authorization': f'Bearer {ACCESS_TOKEN}',
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
                'Authorization': f'Bearer {ACCESS_TOKEN}',
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

    def find_strikes_ge_target(self, chain, target=100):
        """Find CE/PE strikes with premium >= target, closest to target"""
        ce_list = []
        pe_list = []

        for entry in chain:
            strike = int(float(entry.get('strike_price', 0)))

            # CE
            ce = entry.get('call_options', {})
            if ce:
                ltp = float(ce.get('market_data', {}).get('ltp', 0))
                key = ce.get('instrument_key', '')
                if ltp >= target and ltp > 0:
                    ce_list.append({
                        'strike': strike,
                        'premium': ltp,
                        'key': key,
                        'diff': ltp - target
                    })

            # PE
            pe = entry.get('put_options', {})
            if pe:
                ltp = float(pe.get('market_data', {}).get('ltp', 0))
                key = pe.get('instrument_key', '')
                if ltp >= target and ltp > 0:
                    pe_list.append({
                        'strike': strike,
                        'premium': ltp,
                        'key': key,
                        'diff': ltp - target
                    })

        ce_best = min(ce_list, key=lambda x: x['diff']) if ce_list else None
        pe_best = min(pe_list, key=lambda x: x['diff']) if pe_list else None

        return ce_best, pe_best

    def prepare_session(self):
        """
        Prepare trading session using live premium-based strike selection
        
        Fetches option chain at 9:15:40, finds strikes with premium >= ₹100
        """
        self.log(f"🔧 Preparing session with live premiums...")
        
        # Get expiry
        expiry = self.get_expiry()
        if not expiry:
            return False

        # Fetch option chain
        chain = self.fetch_chain(expiry)
        if not chain:
            return False

        # Find strikes >= ₹100
        self.log("Scanning ≥ ₹100 ...")
        ce, pe = self.find_strikes_ge_target(chain, 100)

        if not ce or not pe:
            self.log("No ≥100 → trying ≥80")
            ce, pe = self.find_strikes_ge_target(chain, 80)

        if not ce or not pe:
            self.log("❌ No suitable strikes found")
            return False

        # Save to option_keys.txt
        try:
            with open('option_keys.txt', 'w') as f:
                f.write(f"CE_KEY={ce['key']}\n")
                f.write(f"CE_SYMBOL={ce['key']}\n")
                f.write(f"CE_STRIKE={ce['strike']}\n")
                f.write(f"CE_PREMIUM_FROZEN={ce['premium']}\n")
                f.write(f"CE_ESTIMATED_OPENING={ce['premium']}\n")
                f.write(f"PE_KEY={pe['key']}\n")
                f.write(f"PE_SYMBOL={pe['key']}\n")
                f.write(f"PE_STRIKE={pe['strike']}\n")
                f.write(f"PE_PREMIUM_FROZEN={pe['premium']}\n")
                f.write(f"PE_ESTIMATED_OPENING={pe['premium']}\n")
                f.write(f"GAP=0\n")
            
            self.log(f"✅ Live CE: {ce['strike']} ({ce['premium']:.2f}), PE: {pe['strike']} ({pe['premium']:.2f})")
            return True
            
        except Exception as e:
            self.log(f"❌ Error saving option keys: {e}")
            return False

    def start_streaming(self):
        """Start the data streamer (updated to use factory)"""
        self.log(f"🚀 Starting streaming...")
        self.current_session = "day"
        # Use factory to create data streamer
        self.data_streamer = self.data_streamer_factory(session_name="day")
        threading.Thread(target=self.data_streamer.run, daemon=True).start()
        self.log(f"✅ Streaming started")

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
        
        if current_time > MARKET_END:
            self.log(f"🔒 Market closed")
            return
        
        # STEP 1: Wait until market opens
        market_open_time = "09:15"
        if current_time < market_open_time:
            self.log(f"⏳ Waiting for market open at {market_open_time}")
            self.wait_until(market_open_time, "Market open")
        
        # STEP 2: Wait until 09:15:40 for premium selection ✅ FIXED!
        live_selection_time = "09:15:40"
        self.log(f"⏳ Waiting for live premium selection at {live_selection_time}")
        self.wait_until(live_selection_time, "Live premium selection")
        
        # STEP 3: Fetch live premiums and select strikes FIRST ✅ CRITICAL FIX!
        self.log(f"🔍 Fetching live premiums and selecting strikes...")
        if not self.prepare_session():
            self.log(f"❌ Live premium selection failed, exiting")
            return
        
        # STEP 4: NOW start streaming with CORRECT strikes ✅ FIXED ORDER!
        self.log(f"🚀 Starting streaming with selected strikes...")
        self.start_streaming()
        
        # Give WebSocket time to connect and subscribe
        await asyncio.sleep(2)
        
        # STEP 5: Wait until 09:16:00 to start strategy
        strategy_start_time = "09:16:00"
        self.log(f"⏳ Waiting for strategy start at {strategy_start_time}")
        self.wait_until(strategy_start_time, "Strategy start")
        
        self.log(f"📈 Strategy starting! Trading active...")
        
        # STEP 6: Wait until market end (silent wait)
        while self.is_running and self.get_current_time_str() < MARKET_END:
            time.sleep(60)  # Check every minute without logging
        self.stop_streaming()
        self.log(f"✅ Done for today")
        self.is_running = False

    def stop(self):
        self.log(f"🛑 Stopping...")
        self.is_running = False
        self.stop_streaming()
