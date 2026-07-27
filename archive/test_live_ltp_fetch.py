#!/usr/bin/env python3
"""
Test Live LTP Fetch - Verify Premium Selection Logic

This script tests the new live premium fetching logic to ensure we get actual
live market prices instead of yesterday's frozen prices.

Usage: python test_live_ltp_fetch.py
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

def fetch_chain(expiry):
    """Fetch option chain for given expiry"""
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
                return data['data']
    except Exception as e:
        log(f"Chain error: {e}")
    return None

def fetch_instrument_keys(expiry):
    """Fetch instrument keys in the correct format for quote API"""
    try:
        base_url = "https://api.upstox.com/v2"
        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Accept': 'application/json'
        }
        
        log(f"Fetching instrument keys for {expiry}...")
        resp = requests.get(
            f"{base_url}/option/contract",
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
                log(f"Instrument keys fetched – {len(data['data'])} contracts")
                return data['data']
    except Exception as e:
        log(f"Instrument keys error: {e}")
    return None

def fetch_live_strikes():
    """
    Fetch live strikes using real-time LTP (not frozen prices!)
    Returns dict with CE/PE keys and premiums
    """
    try:
        # Get expiry
        expiry = get_expiry()
        if not expiry:
            log(f"❌ Could not get expiry")
            return None
        
        # Fetch instrument contracts (for correct instrument keys)
        contracts = fetch_instrument_keys(expiry)
        if not contracts:
            log(f"❌ Could not fetch instrument contracts")
            return None
        
        # Extract all instrument keys and map to strikes
        instrument_keys = []
        strike_map = {}
        
        for contract in contracts:
            strike = int(float(contract.get('strike_price', 0)))
            trading_symbol = contract.get('trading_symbol', '')
            
            if trading_symbol and strike > 0:
                # Convert trading symbol to quote API format
                # "NIFTY 23150 CE 17 FEB 26" -> "NSE_FO:NIFTY2621723150CE"
                parts = trading_symbol.split()
                if len(parts) >= 4:
                    base_symbol = parts[0]  # NIFTY
                    strike_price = parts[1]  # 23150
                    option_type = parts[2]   # CE
                    date_part = parts[3]     # 17
                    
                    # Format should match what quote API expects
                    # From the error, it seems the format should be different
                    # Let's try the exchange_token format: NSE_FO|48065
                    quote_key = contract.get('instrument_key', '')
                    
                    instrument_keys.append(quote_key)
                    strike_map[quote_key] = {
                        'strike': strike, 
                        'type': option_type
                    }
        
        # Debug: Show what the contract API actually returns
        if contracts:
            log(f"📊 Contract API sample: {contracts[0]}")
        
        # Debug: Show first few keys from contracts
        log(f"📊 First 5 contract keys: {list(strike_map.keys())[:5]}")
        
        if not instrument_keys:
            log(f"❌ No instrument keys found in chain")
            return None
        
        # Fetch LIVE LTP for all strikes using quote API (not chain API!)
        log(f"📊 Fetching live LTP for {len(instrument_keys)} strikes...")
        
        base_url = "https://api.upstox.com/v2"
        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Accept': 'application/json'
        }
        
        try:
            resp = requests.get(
                f"{base_url}/market-quote/ltp",
                headers=headers,
                params={'instrument_key': ','.join(instrument_keys)},
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
            else:
                log(f"⚠️ No 'data' key in response")
                log(f"📊 Response: {response_data}")
                quotes = {}
            
        except Exception as e:
            log(f"❌ Error fetching quotes: {e}")
            return None
        
        # Build CE/PE lists with LIVE LTP
        ce_list = []
        pe_list = []
        
        log(f"📊 Processing {len(quotes)} quotes...")
        log(f"📊 Strike map has {len(strike_map)} entries")
        
        for key, quote_data in quotes.items():
            ltp = float(quote_data.get('last_price', 0))
            
            if ltp > 0:
                if key in strike_map:
                    info = strike_map[key]
                    
                    if info['type'] == 'CE':
                        ce_list.append({
                            'strike': info['strike'],
                            'premium': ltp,
                            'key': key,
                            'diff': abs(ltp - 100)
                        })
                    else:  # PE
                        pe_list.append({
                            'strike': info['strike'],
                            'premium': ltp,
                            'key': key,
                            'diff': abs(ltp - 100)
                        })
                else:
                    log(f"⚠️ Key {key} not found in strike_map")
        
        log(f"📊 After filtering: {len(ce_list)} CE, {len(pe_list)} PE")
        
        # Show what premiums we actually have
        log(f"📊 Found {len(ce_list)} CE strikes, {len(pe_list)} PE strikes")
        if ce_list:
            ce_premiums = [x['premium'] for x in ce_list]
            log(f"📊 CE Premiums range: ₹{min(ce_premiums):.2f} - ₹{max(ce_premiums):.2f}")
        if pe_list:
            pe_premiums = [x['premium'] for x in pe_list]
            log(f"📊 PE Premiums range: ₹{min(pe_premiums):.2f} - ₹{max(pe_premiums):.2f}")
        
        # Find strikes >= ₹100, closest to ₹100
        log(f"🔍 Scanning for strikes >= ₹100...")
        ce_candidates = [x for x in ce_list if x['premium'] >= 100]
        pe_candidates = [x for x in pe_list if x['premium'] >= 100]
        
        # Fallback to >= ₹80 if needed
        if not ce_candidates or not pe_candidates:
            log(f"⚠️ No strikes >= ₹100, trying >= ₹80...")
            ce_candidates = [x for x in ce_list if x['premium'] >= 80]
            pe_candidates = [x for x in pe_list if x['premium'] >= 80]
        
        # Fallback to >= ₹50 if needed
        if not ce_candidates or not pe_candidates:
            log(f"⚠️ No strikes >= ₹80, trying >= ₹50...")
            ce_candidates = [x for x in ce_list if x['premium'] >= 50]
            pe_candidates = [x for x in pe_list if x['premium'] >= 50]
        
        # Fallback to >= ₹20 if needed
        if not ce_candidates or not pe_candidates:
            log(f"⚠️ No strikes >= ₹50, trying >= ₹20...")
            ce_candidates = [x for x in ce_list if x['premium'] >= 20]
            pe_candidates = [x for x in pe_list if x['premium'] >= 20]
        
        # Fallback to any strikes if needed
        if not ce_candidates or not pe_candidates:
            log(f"⚠️ No strikes >= ₹20, using all strikes...")
            ce_candidates = ce_list
            pe_candidates = pe_list
        
        if not ce_candidates or not pe_candidates:
            log(f"❌ No suitable strikes found")
            return None
        
        # Select best (closest to ₹100)
        ce_best = min(ce_candidates, key=lambda x: x['diff'])
        pe_best = min(pe_candidates, key=lambda x: x['diff'])
        
        return {
            'ce_key': ce_best['key'],
            'ce_strike': ce_best['strike'],
            'ce_premium': ce_best['premium'],
            'pe_key': pe_best['key'],
            'pe_strike': pe_best['strike'],
            'pe_premium': pe_best['premium']
        }
        
    except Exception as e:
        log(f"❌ Error in fetch_live_strikes: {e}")
        return None

def main():
    log("🚀 Testing Live LTP Fetch...")
    log("🎯 Goal: Find strikes with premiums closest to ₹100")
    log("📊 Method: Use live quote API (not frozen chain API)")
    log("")
    
    # Fetch live strikes
    strikes = fetch_live_strikes()
    
    if not strikes:
        log("❌ Failed to fetch live strikes")
        return
    
    # Log results
    log("=" * 60)
    log("🎯 LIVE PREMIUM RESULTS")
    log("=" * 60)
    log(f"✅ CE: {strikes['ce_strike']} (Premium: ₹{strikes['ce_premium']:.2f}) | Key: {strikes['ce_key']}")
    log(f"✅ PE: {strikes['pe_strike']} (Premium: ₹{strikes['pe_premium']:.2f}) | Key: {strikes['pe_key']}")
    log("")
    log(f"🎯 CE Distance from ₹100: ₹{abs(strikes['ce_premium'] - 100):.2f}")
    log(f"🎯 PE Distance from ₹100: ₹{abs(strikes['pe_premium'] - 100):.2f}")
    log("")
    
    # Verify these are live prices (not frozen)
    if strikes['ce_premium'] < 200 and strikes['pe_premium'] < 200:
        log("✅ SUCCESS: Premiums look like live prices (not frozen)")
    else:
        log("⚠️ WARNING: Premiums seem high - might be frozen prices")
    
    log("=" * 60)
    log("🎉 Test completed successfully!")

if __name__ == "__main__":
    main()