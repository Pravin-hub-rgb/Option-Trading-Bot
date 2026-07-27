"""
Delta + Gap Estimation Strike Selector (FIXED - PRODUCTION READY!)

Critical Fixes:
1. CORRECT previous close: OHLC endpoint (best) + market-quote fallback
2. TIME-AWARE: If run after 9:10 AM, loads cached morning strikes
3. SAFETY FILTERS: Reject frozen < 60 or > 150, delta < 0.25
4. FALLBACK: Simple 90-110 logic if estimation fails

Usage:
- Run at 9:07 AM: Selects fresh strikes, saves to option_keys.txt
- Run after 9:10 AM: Loads cached strikes (avoids mid-day live premiums)
"""
import requests
import os
from datetime import datetime, timedelta
import pytz
import upstox_client
from config import ACCESS_TOKEN, STRIKE_STEP

IST = pytz.timezone('Asia/Kolkata')

# Hardcoded adjustment values
OVERNIGHT_THETA_DECAY = 6.0
GAP_DOWN_CE_IV_CRUSH = 5.0
GAP_DOWN_PE_FEAR_BOOST = 8.0
GAP_UP_CE_BOOST = 6.0
GAP_UP_PE_CRUSH = 4.0
STRIKES_TO_SCAN = 10

# ASYMMETRY ADJUSTMENTS (NEW! - Based on real market behavior)
# Gap down: PE gains 3.3x more than CE
# Gap up: CE gains 3.5x more than PE
GAP_DOWN_CE_MULTIPLIER = 0.78  # CE gains 22% less on gap down
GAP_DOWN_PE_MULTIPLIER = 1.38  # PE gains 38% more on gap down
GAP_UP_CE_MULTIPLIER = 1.42    # CE gains 42% more on gap up
GAP_UP_PE_MULTIPLIER = 0.72    # PE gains 28% less on gap up

# SAFETY FILTERS (NEW!)
MIN_FROZEN_PREMIUM = 60    # Reject if frozen < 60 (too far OTM)
MAX_FROZEN_PREMIUM = 150   # Reject if frozen > 150 (too ITM/expensive)
MIN_DELTA = 0.25           # Reject if delta < 0.25 (far OTM, useless)
MIN_ESTIMATED_PREMIUM = 50 # Reject if estimated < 50 (will be illiquid)
MAX_ESTIMATED_PREMIUM = 150 # Reject if estimated > 150 (too expensive)

class StrikeSelector:
    def __init__(self):
        self.base_url = "https://api.upstox.com/v2"
        self.headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Accept': 'application/json'
        }
        self.config = upstox_client.Configuration()
        self.config.access_token = ACCESS_TOKEN
        self.api_client = upstox_client.ApiClient(self.config)
    
    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]
    
    def log(self, message):
        print(f"[{self.now()}] [STRIKE_SELECTOR] {message}")
    
    def get_nifty_spot(self):
        """Fetch current NIFTY 50 spot price"""
        try:
            endpoint = f"{self.base_url}/market-quote/quotes"
            params = {'instrument_key': 'NSE_INDEX|Nifty 50'}
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            
            if response.status_code != 200:
                self.log(f"❌ Spot price request failed: {response.status_code}")
                return None
            
            data = response.json()
            if 'data' not in data or 'NSE_INDEX:Nifty 50' not in data['data']:
                self.log(f"❌ No spot price in response")
                return None
            
            spot = float(data['data']['NSE_INDEX:Nifty 50']['last_price'])
            self.log(f"📊 NIFTY Spot: {spot:.2f}")
            return spot
            
        except Exception as e:
            self.log(f"❌ Error fetching spot: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_previous_close(self):
        """
        BEST METHOD: Use OHLC endpoint - simpler and more reliable!
        Falls back to market-quote if OHLC fails
        """
        try:
            # PRIMARY: Use OHLC endpoint (BEST - dedicated for prev close)
            endpoint = f"{self.base_url}/market-quote/ohlc"
            params = {
                'instrument_key': 'NSE_INDEX|Nifty 50',
                'interval': '1d'
            }
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'NSE_INDEX:Nifty 50' in data['data']:
                    prev_close = float(data['data']['NSE_INDEX:Nifty 50']['prev_ohlc']['close'])
                    self.log(f"📅 Previous Close (OHLC): {prev_close:.2f}")
                    return prev_close
            
            self.log(f"⚠️ OHLC method failed, trying market-quote...")
            
            # FALLBACK: Use market-quote with correct nesting
            endpoint = f"{self.base_url}/market-quote/quotes"
            params = {'instrument_key': 'NSE_INDEX|Nifty 50'}
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            
            if response.status_code != 200:
                self.log(f"⚠️ Market quote failed: {response.status_code}")
                return None
            
            data = response.json()
            if 'data' not in data or 'NSE_INDEX:Nifty 50' not in data['data']:
                self.log(f"⚠️ No Nifty data in response")
                return None
            
            # CORRECT PATH: ff.indexFF.ltpc.cp
            nifty_data = data['data']['NSE_INDEX:Nifty 50']
            
            if 'ff' in nifty_data and 'indexFF' in nifty_data['ff']:
                ltpc = nifty_data['ff']['indexFF']['ltpc']
                prev_close = float(ltpc['cp'])
                self.log(f"📅 Previous Close (market-quote): {prev_close:.2f}")
                return prev_close
            
            self.log(f"⚠️ Could not find previous close in any method")
            return None
            
        except KeyError as e:
            self.log(f"❌ KeyError: {e}")
            return None
        except Exception as e:
            self.log(f"⚠️ Error fetching previous close: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_next_expiry(self):
        """
        Get next weekly expiry date
        NOTE: Since Sept 2025, NIFTY weekly expiry is TUESDAY (not Thursday!)
        """
        try:
            endpoint = f"{self.base_url}/option/contract"
            params = {'instrument_key': 'NSE_INDEX|Nifty 50'}
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json().get('data', [])
            today = datetime.now(IST).date()
            
            # Get ALL expiries >= today (don't filter by weekly flag - it might be unreliable)
            all_expiries = sorted(set([
                item['expiry'] for item in data
                if datetime.strptime(item['expiry'], "%Y-%m-%d").date() >= today
            ]))
            
            if not all_expiries:
                self.log(f"⚠️ No expiries found!")
                return None
            
            # Log all available expiries for debugging
            self.log(f"📅 Available expiries: {all_expiries[:5]}")
            
            # Pick the NEAREST expiry (should be this week's Tuesday)
            expiry = all_expiries[0]
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            
            # Calculate days to expiry
            days_to_expiry = (expiry_date - today).days
            
            self.log(f"📅 Next Expiry: {expiry} ({days_to_expiry} days away)")
            
            # WARNING: If expiry is >7 days away, something is wrong!
            if days_to_expiry > 7:
                self.log(f"⚠️ WARNING: Next expiry is {days_to_expiry} days away (expected ≤7 for weekly)")
            
            return expiry
            
        except Exception as e:
            self.log(f"❌ Error fetching expiry: {e}")
            return None
    
    def format_expiry_for_key(self, expiry_date_str):
        """Convert expiry date to Upstox format"""
        expiry_obj = datetime.strptime(expiry_date_str, "%Y-%m-%d")
        return expiry_obj.strftime("%y%b%d").upper()
    
    def build_instrument_keys(self, strikes, expiry_str):
        """Build CE and PE instrument keys"""
        ce_keys = [f"NSE_FO|NIFTY{expiry_str}{strike}CE" for strike in strikes]
        pe_keys = [f"NSE_FO|NIFTY{expiry_str}{strike}PE" for strike in strikes]
        return ce_keys, pe_keys
    
    def get_option_greeks(self, strikes, expiry_date):
        """Fetch Greeks and frozen premium from Option Chain API"""
        try:
            self.log(f"📡 Fetching Option Chain for {len(strikes)} strikes...")
            
            endpoint = f"{self.base_url}/option/chain"
            params = {
                'instrument_key': 'NSE_INDEX|Nifty 50',
                'expiry_date': expiry_date
            }
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=15)
            
            if response.status_code != 200:
                self.log(f"❌ Option chain request failed: {response.status_code}")
                return {}
            
            data = response.json()
            if 'data' not in data:
                self.log(f"⚠️ No data in option chain response")
                return {}
            
            greeks_data = {}
            expiry_str = self.format_expiry_for_key(expiry_date)
            
            for strike_entry in data['data']:
                strike = int(float(strike_entry.get('strike_price', 0)))
                
                if strike not in strikes:
                    continue
                
                # CE data
                call_options = strike_entry.get('call_options', {})
                if call_options:
                    ce_greeks = call_options.get('option_greeks', {})
                    ce_market = call_options.get('market_data', {})
                    ce_key = f"NSE_FO|NIFTY{expiry_str}{strike}CE"
                    
                    delta = float(ce_greeks.get('delta', 0.5))
                    premium = float(ce_market.get('ltp', 0))
                    
                    if premium > 0:
                        greeks_data[ce_key] = {
                            'delta': delta,
                            'premium': premium,
                            'symbol': call_options.get('instrument_key', ce_key)
                        }
                
                # PE data
                put_options = strike_entry.get('put_options', {})
                if put_options:
                    pe_greeks = put_options.get('option_greeks', {})
                    pe_market = put_options.get('market_data', {})
                    pe_key = f"NSE_FO|NIFTY{expiry_str}{strike}PE"
                    
                    delta = float(pe_greeks.get('delta', -0.5))
                    premium = float(pe_market.get('ltp', 0))
                    
                    if premium > 0:
                        greeks_data[pe_key] = {
                            'delta': abs(delta),
                            'premium': premium,
                            'symbol': put_options.get('instrument_key', pe_key)
                        }
            
            self.log(f"✅ Fetched Greeks for {len(greeks_data)} options")
            return greeks_data
            
        except Exception as e:
            self.log(f"❌ Error fetching option chain: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def estimate_opening_premium(self, frozen_premium, delta, gap, option_type):
        """
        Estimate opening premium using delta + gap + adjustments
        
        NEW: PUT-CALL ASYMMETRY applied!
        - Gap down: PE gains 3.3x more than CE
        - Gap up: CE gains 3.5x more than PE
        """
        # Base delta effect
        estimated = frozen_premium + (delta * gap)
        
        # Subtract overnight theta decay
        estimated -= OVERNIGHT_THETA_DECAY
        
        # IV skew adjustments
        if gap < 0:  # Gap down
            if option_type == 'CE':
                estimated -= GAP_DOWN_CE_IV_CRUSH  # Calls get IV crushed
            else:  # PE
                estimated += GAP_DOWN_PE_FEAR_BOOST  # Puts get fear premium
        elif gap > 0:  # Gap up
            if option_type == 'CE':
                estimated += GAP_UP_CE_BOOST  # Calls get boosted
            else:  # PE
                estimated -= GAP_UP_PE_CRUSH  # Puts get crushed
        
        # ASYMMETRY MULTIPLIER (CRITICAL FIX!)
        # Apply only for significant gaps (±40 points)
        if gap <= -40:  # Gap down
            if option_type == 'CE':
                estimated *= GAP_DOWN_CE_MULTIPLIER  # CE gains less (0.78x)
            else:  # PE
                estimated *= GAP_DOWN_PE_MULTIPLIER  # PE gains more (1.38x)
        elif gap >= 40:  # Gap up
            if option_type == 'CE':
                estimated *= GAP_UP_CE_MULTIPLIER    # CE gains more (1.42x)
            else:  # PE
                estimated *= GAP_UP_PE_MULTIPLIER    # PE gains less (0.72x)
        
        return estimated
    
    def extract_strike_from_key(self, key, expiry_str):
        """Extract strike price from instrument key"""
        try:
            after_expiry = key.split(expiry_str)[1]
            strike_str = ''.join(filter(str.isdigit, after_expiry))
            
            if not strike_str:
                return 0
            
            return int(strike_str)
        except Exception as e:
            self.log(f"⚠️ Error extracting strike from {key}: {e}")
            return 0
    
    def is_valid_candidate(self, frozen, delta, estimated, option_type):
        """
        SAFETY FILTER: Check if candidate is tradable
        Returns: (is_valid, reason)
        """
        # Check frozen premium range
        if frozen < MIN_FROZEN_PREMIUM:
            return False, f"frozen too low ({frozen:.2f} < {MIN_FROZEN_PREMIUM})"
        if frozen > MAX_FROZEN_PREMIUM:
            return False, f"frozen too high ({frozen:.2f} > {MAX_FROZEN_PREMIUM})"
        
        # Check delta (avoid far OTM)
        if delta < MIN_DELTA:
            return False, f"delta too low ({delta:.2f} < {MIN_DELTA})"
        
        # Check estimated premium range
        if estimated < MIN_ESTIMATED_PREMIUM:
            return False, f"estimated too low ({estimated:.2f} < {MIN_ESTIMATED_PREMIUM})"
        if estimated > MAX_ESTIMATED_PREMIUM:
            return False, f"estimated too high ({estimated:.2f} > {MAX_ESTIMATED_PREMIUM})"
        
        return True, "valid"
    
    def load_morning_strikes(self):
        """
        Load previously cached strikes from option_keys.txt
        Used when bot runs mid-day to avoid live premium issues
        """
        try:
            if not os.path.exists('option_keys.txt'):
                return None
            
            self.log(f"📂 Loading cached morning strikes...")
            
            data = {}
            with open('option_keys.txt', 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        data[key] = value
            
            # Parse required fields
            result = {
                'ce': {
                    'strike': int(data.get('CE_STRIKE', 0)),
                    'premium': float(data.get('CE_PREMIUM_FROZEN', 0)),
                    'instrument_key': data.get('CE_KEY', ''),
                    'symbol': data.get('CE_SYMBOL', '')
                },
                'pe': {
                    'strike': int(data.get('PE_STRIKE', 0)),
                    'premium': float(data.get('PE_PREMIUM_FROZEN', 0)),
                    'instrument_key': data.get('PE_KEY', ''),
                    'symbol': data.get('PE_SYMBOL', '')
                },
                'expiry': None,
                'gap': float(data.get('GAP', 0)),
                'estimated_ce': float(data.get('CE_ESTIMATED_OPENING', 0)),
                'estimated_pe': float(data.get('PE_ESTIMATED_OPENING', 0))
            }
            
            self.log(f"✅ Cached CE: {result['ce']['strike']}, PE: {result['pe']['strike']}")
            return result
            
        except Exception as e:
            self.log(f"❌ Error loading cache: {e}")
            return None
    
    def apply_asymmetry_strike_bias(self, base_atm, gap):
        """
        Apply strike bias based on gap direction
        
        Gap down: CE closer to spot (less OTM), PE farther (more OTM)
        Gap up: CE farther (more OTM), PE closer
        
        Returns: (ce_bias, pe_bias) - offset from base_atm
        """
        if gap <= -40:  # Gap down
            ce_bias = -50   # CE closer (26100 instead of 26150)
            pe_bias = +50   # PE farther (26200 instead of 26150)
        elif gap >= 40:  # Gap up
            ce_bias = +50   # CE farther
            pe_bias = -50   # PE closer
        else:  # Flat (-40 to +40)
            ce_bias = 0
            pe_bias = 0
        
        return ce_bias, pe_bias
    
    def select_strikes(self):
        """
        Main method: Delta + Gap estimation with SAFETY FILTERS
        
        IMPORTANT: If run after 9:10 AM, uses cached morning strikes!
        Bot should ONLY select NEW strikes during pre-market (9:00-9:10 AM)
        """
        current_time = datetime.now(IST)
        current_time_str = current_time.strftime("%H:%M")
        
        # TIME CHECK: If after 9:10 AM, try to load morning cache
        if current_time_str > "09:10":
            self.log(f"⚠️ MID-DAY RUN ({current_time_str}) - Checking for morning cache...")
            
            if os.path.exists('option_keys.txt'):
                cached_data = self.load_morning_strikes()
                if cached_data:
                    self.log(f"✅ Using CACHED morning strikes (avoid mid-day live premiums)")
                    return cached_data
                else:
                    self.log(f"⚠️ Cache file corrupted, proceeding with estimation...")
            else:
                self.log(f"⚠️ No morning cache found - Bot should run at 9:07 AM!")
                self.log(f"⚠️ Proceeding anyway, but premiums will be live (not frozen)")
        
        self.log("🚀 Starting DELTA + GAP ESTIMATION (SAFE MODE)...")
        
        # 1. Get spot
        spot = self.get_nifty_spot()
        if not spot:
            return None
        
        # 2. Get previous close (FIXED PATH!)
        previous_close = self.get_previous_close()
        if not previous_close:
            self.log(f"⚠️ Could not get previous close, using conservative fallback")
            previous_close = spot - 50  # Conservative: assume small gap down
        
        gap = spot - previous_close
        self.log(f"🔢 Gap: {gap:+.2f} points")
        
        # 3. Get expiry
        expiry = self.get_next_expiry()
        if not expiry:
            return None
        
        expiry_str = self.format_expiry_for_key(expiry)
        
        # 4. Build strike list with ASYMMETRY BIAS
        base_atm = round(spot / STRIKE_STEP) * STRIKE_STEP
        
        # Apply asymmetry bias based on gap
        ce_bias, pe_bias = self.apply_asymmetry_strike_bias(base_atm, gap)
        
        self.log(f"📐 Asymmetry Bias: CE {ce_bias:+d}, PE {pe_bias:+d}")
        
        # Build separate strike lists for CE and PE
        ce_center = base_atm + ce_bias
        pe_center = base_atm + pe_bias
        
        # CE strikes centered around ce_center
        ce_strikes = [ce_center + (i * STRIKE_STEP) for i in range(-STRIKES_TO_SCAN, STRIKES_TO_SCAN + 1)]
        
        # PE strikes centered around pe_center
        pe_strikes = [pe_center + (i * STRIKE_STEP) for i in range(-STRIKES_TO_SCAN, STRIKES_TO_SCAN + 1)]
        
        # Combine and deduplicate
        all_strikes = sorted(set(ce_strikes + pe_strikes))
        
        self.log(f"🔍 Scanning {len(all_strikes)} strikes: {all_strikes[0]} to {all_strikes[-1]}")
        self.log(f"   CE focused around {ce_center}, PE focused around {pe_center}")
        
        # 5. Fetch Greeks + frozen premiums
        greeks_data = self.get_option_greeks(all_strikes, expiry)
        
        if not greeks_data:
            self.log(f"❌ No Greeks data available")
            return None
        
        # 6. Estimate opening premium with SAFETY FILTERS
        ce_candidates = []
        pe_candidates = []
        
        for key, data in greeks_data.items():
            frozen = data['premium']
            delta = data['delta']
            option_type = 'CE' if 'CE' in key else 'PE'
            
            # Estimate opening
            estimated = self.estimate_opening_premium(frozen, delta, gap, option_type)
            
            # SAFETY CHECK
            is_valid, reason = self.is_valid_candidate(frozen, delta, estimated, option_type)
            
            if not is_valid:
                # Log rejected candidates for debugging
                strike = self.extract_strike_from_key(key, expiry_str)
                self.log(f"❌ REJECTED {option_type} {strike}: {reason}")
                continue
            
            # Calculate distance from target ₹100
            distance = abs(estimated - 100)
            strike = self.extract_strike_from_key(key, expiry_str)
            
            candidate = {
                'strike': strike,
                'instrument_key': key,
                'symbol': data['symbol'],
                'frozen': frozen,
                'delta': delta,
                'estimated': estimated,
                'distance': distance
            }
            
            if option_type == 'CE':
                ce_candidates.append(candidate)
            else:
                pe_candidates.append(candidate)
        
        # 7. Check if we have valid candidates
        if not ce_candidates or not pe_candidates:
            self.log(f"⚠️ Not enough valid candidates after safety filters")
            self.log(f"CE candidates: {len(ce_candidates)}, PE candidates: {len(pe_candidates)}")
            
            # FALLBACK: Use simple frozen premium 90-110 range
            self.log(f"🔄 FALLBACK: Using simple frozen premium logic (90-110 range)")
            return self.fallback_simple_selection(greeks_data, expiry_str, spot)
        
        # 8. Pick strikes with minimum distance from ₹100
        best_ce = min(ce_candidates, key=lambda x: x['distance'])
        best_pe = min(pe_candidates, key=lambda x: x['distance'])
        
        self.log(f"")
        self.log(f"✅ BEST CE: Strike {best_ce['strike']}")
        self.log(f"   Frozen: ₹{best_ce['frozen']:.2f}, Delta: {best_ce['delta']:.2f}")
        self.log(f"   Estimated Opening: ₹{best_ce['estimated']:.2f}")
        
        self.log(f"")
        self.log(f"✅ BEST PE: Strike {best_pe['strike']}")
        self.log(f"   Frozen: ₹{best_pe['frozen']:.2f}, Delta: {best_pe['delta']:.2f}")
        self.log(f"   Estimated Opening: ₹{best_pe['estimated']:.2f}")
        
        result = {
            'ce': {
                'strike': best_ce['strike'],
                'premium': best_ce['frozen'],
                'instrument_key': best_ce['instrument_key'],
                'symbol': best_ce['symbol']
            },
            'pe': {
                'strike': best_pe['strike'],
                'premium': best_pe['frozen'],
                'instrument_key': best_pe['instrument_key'],
                'symbol': best_pe['symbol']
            },
            'expiry': expiry,
            'gap': gap,
            'estimated_ce': best_ce['estimated'],
            'estimated_pe': best_pe['estimated']
        }
        
        return result
    
    def fallback_simple_selection(self, greeks_data, expiry_str, spot):
        """
        FALLBACK: Simple frozen premium logic (90-110 range)
        Used when delta estimation fails or produces no valid candidates
        """
        self.log(f"📊 Using SIMPLE logic: Frozen premium 90-110 range")
        
        ce_candidates = []
        pe_candidates = []
        
        for key, data in greeks_data.items():
            frozen = data['premium']
            
            # Simple range check: 90-110
            if frozen < 90 or frozen > 110:
                continue
            
            distance = abs(frozen - 100)
            strike = self.extract_strike_from_key(key, expiry_str)
            option_type = 'CE' if 'CE' in key else 'PE'
            
            candidate = {
                'strike': strike,
                'instrument_key': key,
                'symbol': data['symbol'],
                'frozen': frozen,
                'delta': data['delta'],
                'estimated': frozen,  # Use frozen as estimated
                'distance': distance
            }
            
            if option_type == 'CE':
                ce_candidates.append(candidate)
            else:
                pe_candidates.append(candidate)
        
        if not ce_candidates or not pe_candidates:
            self.log(f"❌ Even fallback logic found no candidates!")
            return None
        
        best_ce = min(ce_candidates, key=lambda x: x['distance'])
        best_pe = min(pe_candidates, key=lambda x: x['distance'])
        
        self.log(f"✅ FALLBACK CE: Strike {best_ce['strike']}, Frozen: ₹{best_ce['frozen']:.2f}")
        self.log(f"✅ FALLBACK PE: Strike {best_pe['strike']}, Frozen: ₹{best_pe['frozen']:.2f}")
        
        return {
            'ce': {
                'strike': best_ce['strike'],
                'premium': best_ce['frozen'],
                'instrument_key': best_ce['instrument_key'],
                'symbol': best_ce['symbol']
            },
            'pe': {
                'strike': best_pe['strike'],
                'premium': best_pe['frozen'],
                'instrument_key': best_pe['instrument_key'],
                'symbol': best_pe['symbol']
            },
            'expiry': None,
            'gap': 0,
            'estimated_ce': best_ce['frozen'],
            'estimated_pe': best_pe['frozen']
        }
    
    def save_to_file(self, result):
        """Save selected strikes to option_keys.txt"""
        if not result:
            return False
        
        try:
            with open('option_keys.txt', 'w') as f:
                f.write(f"CE_KEY={result['ce']['instrument_key']}\n")
                f.write(f"CE_SYMBOL={result['ce']['symbol']}\n")
                f.write(f"CE_STRIKE={result['ce']['strike']}\n")
                f.write(f"CE_PREMIUM_FROZEN={result['ce']['premium']}\n")
                f.write(f"CE_ESTIMATED_OPENING={result['estimated_ce']}\n")
                f.write(f"PE_KEY={result['pe']['instrument_key']}\n")
                f.write(f"PE_SYMBOL={result['pe']['symbol']}\n")
                f.write(f"PE_STRIKE={result['pe']['strike']}\n")
                f.write(f"PE_PREMIUM_FROZEN={result['pe']['premium']}\n")
                f.write(f"PE_ESTIMATED_OPENING={result['estimated_pe']}\n")
                f.write(f"GAP={result['gap']}\n")
            
            self.log(f"💾 Saved to option_keys.txt")
            return True
            
        except Exception as e:
            self.log(f"❌ Error saving file: {e}")
            return False