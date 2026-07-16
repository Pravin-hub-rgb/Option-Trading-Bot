# get_atm_keys.py — FIXED
import upstox_client
from config import ACCESS_TOKEN
from datetime import datetime
import pytz
import requests

IST = pytz.timezone('Asia/Kolkata')
now = datetime.now(IST)
print(f"[{now.strftime('%H:%M:%S')}] Fetching ATM keys...")

config = upstox_client.Configuration()
config.access_token = ACCESS_TOKEN
api_client = upstox_client.ApiClient(config)

# 1. Get NIFTY LTP
quote_api = upstox_client.MarketQuoteApi(api_client)
nifty_resp = quote_api.get_full_market_quote("NSE_INDEX|Nifty 50", api_version="2.0")
nifty_key_in_response = "NSE_INDEX:Nifty 50"
nifty_ltp = nifty_resp.data[nifty_key_in_response].last_price
strike = round(nifty_ltp / 50) * 50

print(f"NIFTY LTP: ₹{nifty_ltp:.2f} → ATM Strike: {strike}")

# 2. Get Option Chain - USING DIRECT REST API (SDK method broken)
url = 'https://api.upstox.com/v2/option/contract'
params = {
    'instrument_key': 'NSE_INDEX|Nifty 50',
    # 'expiry_date': '2025-11-06'  # Optional - omit to get all expiries
}
headers = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}

print("Fetching option chain...")
chain_resp = requests.get(url, params=params, headers=headers)

if chain_resp.status_code != 200:
    print(f"❌ API Error: {chain_resp.status_code}")
    print(chain_resp.text)
    exit()

contracts = chain_resp.json()['data']
print(f"Total contracts fetched: {len(contracts)}")

# 3. Find ATM CE and PE for nearest expiry
ce_key = pe_key = None
ce_symbol = pe_symbol = None

# Filter for nearest weekly expiry (typically next Thursday)
from collections import defaultdict
expiry_strikes = defaultdict(list)

for contract in contracts:
    expiry_strikes[contract['expiry']].append(contract)

# Get nearest expiry
nearest_expiry = sorted(expiry_strikes.keys())[0]
print(f"Nearest expiry: {nearest_expiry}")

# Find strike
for contract in expiry_strikes[nearest_expiry]:
    if contract['strike_price'] == strike:
        if contract['instrument_type'] == 'CE':
            ce_key = contract['instrument_key']
            ce_symbol = contract['trading_symbol']
        if contract['instrument_type'] == 'PE':
            pe_key = contract['instrument_key']
            pe_symbol = contract['trading_symbol']

if ce_key and pe_key:
    print(f"\n✅ FOUND ATM OPTIONS:")
    print(f"CE: {ce_symbol} → {ce_key}")
    print(f"PE: {pe_symbol} → {pe_key}")
    
    # Save for WebSocket
    with open("option_keys.txt", "w") as f:
        f.write(f"CE_KEY={ce_key}\n")
        f.write(f"PE_KEY={pe_key}\n")
        f.write(f"CE_SYMBOL={ce_symbol}\n")
        f.write(f"PE_SYMBOL={pe_symbol}\n")
    print("\n✅ Keys saved to option_keys.txt")
else:
    print(f"\n❌ No keys found for strike {strike}. Available strikes for {nearest_expiry}:")
    strikes_found = set()
    for c in expiry_strikes[nearest_expiry]:
        strikes_found.add(c['strike_price'])
    print(sorted(strikes_found)[:10])  # Show first 10 strikes