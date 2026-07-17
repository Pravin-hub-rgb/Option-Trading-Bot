"""
Live Premium Strike Selector

Simple live premium-based strike selection for NIFTY options.
Fetches option chain and selects strikes with premium >= ₹100.

Usage:
- Run at 9:15:40 during market hours
- Finds CE and PE strikes with LTP >= ₹100
- Selects strikes closest to ₹100
- Saves to option_keys.txt
"""
import requests
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

class StrikeSelector:
    def __init__(self):
        self.base_url = "https://api.upstox.com/v2"
        from settings_db import get_setting
        token = get_setting("access_token") or ""
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
    
    def now(self):
        return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]
    
    def log(self, message):
        print(f"[{self.now()}] [STRIKE_SELECTOR] {message}")
    
    def get_expiry(self):
        """Get next weekly expiry date"""
        try:
            resp = requests.get(
                f"{self.base_url}/option/contract",
                headers=self.headers,
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
            self.log(f"Fetching chain for {expiry}...")
            resp = requests.get(
                f"{self.base_url}/option/chain",
                headers=self.headers,
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

    def select_strikes(self):
        """Main method - select strikes using live premiums"""
        self.log("🚀 Starting LIVE PREMIUM SELECTION...")
        
        # Get expiry
        expiry = self.get_expiry()
        if not expiry:
            return None

        # Fetch option chain
        chain = self.fetch_chain(expiry)
        if not chain:
            return None

        # Find strikes >= ₹100
        self.log("Scanning ≥ ₹100 ...")
        ce, pe = self.find_strikes_ge_target(chain, 100)

        if not ce or not pe:
            self.log("No ≥100 → trying ≥80")
            ce, pe = self.find_strikes_ge_target(chain, 80)

        if not ce or not pe:
            self.log("❌ No suitable strikes found")
            return None

        self.log(f"✅ CE: {ce['strike']} ({ce['premium']:.2f}), PE: {pe['strike']} ({pe['premium']:.2f})")
        
        return {
            'ce': {
                'strike': ce['strike'],
                'premium': ce['premium'],
                'instrument_key': ce['key'],
                'symbol': ce['key']
            },
            'pe': {
                'strike': pe['strike'],
                'premium': pe['premium'],
                'instrument_key': pe['key'],
                'symbol': pe['key']
            },
            'expiry': expiry,
            'gap': 0,
            'estimated_ce': ce['premium'],
            'estimated_pe': pe['premium']
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
                f.write(f"CE_ESTIMATED_OPENING={result.get('estimated_ce', 0)}\n")
                f.write(f"PE_KEY={result['pe']['instrument_key']}\n")
                f.write(f"PE_SYMBOL={result['pe']['symbol']}\n")
                f.write(f"PE_STRIKE={result['pe']['strike']}\n")
                f.write(f"PE_PREMIUM_FROZEN={result['pe']['premium']}\n")
                f.write(f"PE_ESTIMATED_OPENING={result.get('estimated_pe', 0)}\n")
                f.write(f"GAP=0\n")
            
            self.log(f"💾 Saved to option_keys.txt")
            return True
            
        except Exception as e:
            self.log(f"❌ Error saving file: {e}")
            return False
