#!/usr/bin/env python3
"""
Simple Live LTP Test - Find Strikes Near ₹100

This script fetches live LTP values for Nifty options near current spot price
and finds strikes with premiums closest to ₹100.
"""

import requests
from config import ACCESS_TOKEN
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

def now():
    return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

def log(message):
    print(f"[{now()}] {message}")

def get_expiry():
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
            log(f"Expiry: {expiry}")
            return expiry
    except Exception as e:
        log(f"Expiry fetch failed: {e}")
    return None

def get_spot():
    """Get current NIFTY spot price"""
    try:
        base_url = "https://api.upstox.com/v2"
        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
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
            log(f"NIFTY Spot: {spot:.2f}")
            return spot
    except Exception as e:
        log(f"Spot fetch failed: {e}")
    return None

def fetch_chain_and_filter_keys(expiry, spot, range_points=500):
    """Fetch option chain and filter keys near spot price"""
    try:
        base_url = "https://api.upstox.com/v2"
        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Accept': 'application/json'
        }
        
        log(f"Fetching chain for {expiry}...")
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
                log(f"Chain fetched – {len(data['data'])} strikes")
                
                # Filter keys near spot (±500 points)
                keys = []
                for entry in data['data']:
                    strike = float(entry.get('strike_price', 0))
                    if abs(strike - spot) <= range_points:
                        # Add CE
                        ce = entry.get('call_options', {})
                        if ce:
                            key = ce.get('instrument_key', '')
                            if key:
                                keys.append(key)
                        # Add PE  
                        pe = entry.get('put_options', {})
                        if pe:
                            key = pe.get('instrument_key', '')
                            if key:
                                keys.append(key)
                
                log(f"Filtered {len(keys)} near-spot keys (±{range_points} pts)")
                return keys
    except Exception as e:
        log(f"Chain error: {e}")
    return None

def fetch_live_ltp():
    """Fetch live LTP for strikes near spot price"""
    try:
        # Get expiry
        expiry = get_expiry()
        if not expiry:
            log(f"❌ Could not get expiry")
            return None
        
        # Get current spot price
        spot = get_spot()
        if not spot:
            log(f"❌ Could not get spot price")
            return None
        
        # Fetch chain and filter keys near spot
        keys = fetch_chain_and_filter_keys(expiry, spot, range_points=500)
        if not keys:
            log(f"❌ Could not fetch filtered keys")
            return None
        
        log(f"📊 Testing with {len(keys)} filtered keys...")
        log(f"📊 Sample keys: {keys[:5]}...")  # Show first 5
        
        # Fetch LIVE LTP for filtered strikes
        log(f"📊 Fetching live LTP for {len(keys)} strikes...")
        
        base_url = "https://api.upstox.com/v2"
        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Accept': 'application/json'
        }
        
        try:
            resp = requests.get(
                f"{base_url}/market-quote/ltp",
                headers=headers,
                params={'instrument_key': ','.join(keys)},
                timeout=15
            )
            
            if resp.status_code != 200:
                log(f"❌ Quote API error: {resp.status_code}")
                log(f"❌ Response: {resp.text}")
                return None
            
            response_data = resp.json()
            log(f"📊 Quote API response keys: {list(response_data.keys())}")
            
            if 'data' in response_data:
                quotes = response_data['data']
                log(f"📊 Received {len(quotes)} quotes")
                return quotes
            else:
                log(f"⚠️ No 'data' key in response")
                log(f"📊 Response: {response_data}")
                return {}
            
        except Exception as e:
            log(f"❌ Error fetching quotes: {e}")
            return None
        
    except Exception as e:
        log(f"❌ Error in fetch_live_ltp: {e}")
        return None

def main():
    log("🚀 Testing Live LTP Scan for ~₹100...")
    log("🎯 Goal: Find strikes with premiums near ₹100")
    log("📊 Method: Use spot-based filtering + live quote API")
    log("")
    
    # Fetch live LTP
    quotes = fetch_live_ltp()
    
    if not quotes:
        log("❌ Failed to fetch live LTP")
        return
    
    # Find strikes closest to ₹100
    log("=" * 60)
    log("🎯 LIVE LTP RESULTS - FINDING ~₹100 PREMIUMS")
    log("=" * 60)
    
    # Filter for premiums in 90-120 range (close to ₹100)
    candidates = []
    for key, quote_data in quotes.items():
        ltp = float(quote_data.get('last_price', 0))
        if ltp >= 90 and ltp <= 120:
            candidates.append({'key': key, 'ltp': ltp, 'diff': abs(ltp - 100)})
    
    # If no candidates in tight range, widen to 80-130
    if not candidates:
        log("⚠️ No premiums in 90-120 range, widening to 80-130...")
        for key, quote_data in quotes.items():
            ltp = float(quote_data.get('last_price', 0))
            if ltp >= 80 and ltp <= 130:
                candidates.append({'key': key, 'ltp': ltp, 'diff': abs(ltp - 100)})
    
    # Show all premiums for debugging
    log("📊 All premiums found:")
    for key, quote_data in quotes.items():
        ltp = float(quote_data.get('last_price', 0))
        if ltp > 0:
            log(f"   {key}: ₹{ltp:.2f}")
    
    log("")
    
    # Show candidates near ₹100
    if candidates:
        candidates.sort(key=lambda x: x['diff'])
        log("🎯 Premiums closest to ₹100:")
        for candidate in candidates[:5]:  # Show top 5 closest
            log(f"✅ {candidate['key']}: ₹{candidate['ltp']:.2f} (diff: ₹{candidate['diff']:.2f})")
    else:
        log("❌ No premiums found in 80-130 range")
    
    log("=" * 60)
    log("🎉 Test completed!")

if __name__ == "__main__":
    main()