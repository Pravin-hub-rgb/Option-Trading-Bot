import os
import pandas as pd
import requests
from datetime import datetime
import time
import pytz

# ------------------- CONFIG -------------------
symbol = "BNBUSDT"                       # Changed to ETH
base_folder = "bnb_futures_data"         # New clean folder name
intervals = ["1m", "15m"]                # Only 1min and 15min
# ---------------------------------------------

def get_binance_klines(symbol, interval, start_ts, end_ts):
    url = "https://fapi.binance.com/fapi/v1/klines"
    limit = 1000
    all_data = []
    current = start_ts

    print(f"   → {interval}: ", end="", flush=True)
    
    while current < end_ts:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current,
            "endTime": end_ts,
            "limit": limit
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
        except:
            time.sleep(1)
            continue
            
        if not data or isinstance(data, dict):
            break
            
        all_data.extend(data)
        current = data[-1][0] + 1
        time.sleep(0.05)
        
        if len(data) < limit:
            break
    
    print(f"{len(all_data)} candles")
    
    if not all_data:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    df = df[['open_time', 'open', 'high', 'low', 'close']]
    # Convert to IST (Indian Standard Time)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True).dt.tz_convert('Asia/Kolkata')
    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
    
    return df

# =============== MAIN ===============
os.makedirs(base_folder, exist_ok=True)

print("="*70)
print("BNBUSDT Perpetual Futures Downloader (1m + 15m)")
print("→ Full year data in single files with INDIAN TIME (IST)")
print("="*70)

while True:
    try:
        year = int(input("Enter year (e.g., 2025): "))
        if year >= 2017:  # Binance futures started around 2019, but safe
            break
    except:
        pass

print(f"\nDownloading full year {year} for BNBUSDT → Indian Standard Time (IST)\n")

# Create year folder
year_folder = os.path.join(base_folder, str(year))
os.makedirs(year_folder, exist_ok=True)

# Full year timestamps
start_date = datetime(year, 1, 1)
end_date = datetime(year + 1, 1, 1)

start_ts = int(start_date.timestamp() * 1000)
end_ts = int(end_date.timestamp() * 1000)

print(f"Downloading data for {year}...")
print(f"Saving to → {year_folder}\n")

for interval in intervals:
    print(f"Downloading {interval}...", flush=True)
    df = get_binance_klines(symbol, interval, start_ts, end_ts)

    if df.empty:
        print("   No data available for this interval")
        continue

    # Add dummy x,y columns
    df['x'] = 0
    df['y'] = 0
    df_final = df[['open_time', 'open', 'high', 'low', 'close', 'x', 'y']]
    df_final.columns = ['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']

    # Filename
    filename = os.path.join(year_folder, f"BNBUSDT_{interval}.csv")

    # Save with header, proper time format, 2 decimal places
    df_final.to_csv(filename, index=False, header=True,
                    date_format='%Y-%m-%d %H:%M:%S', float_format='%.2f')

    size_mb = os.path.getsize(filename) / (1024*1024)
    print(f"   Saved BNBUSDT_{interval}.csv → {len(df):,} rows ({size_mb:.2f} MB)")

print("\nALL DONE! 🚀")
print(f"Check folder: {year_folder}")
print("Files: BNBUSDT_1m.csv and BNBUSDT_15m.csv")
print("Timestamps are in Indian time — ready for your backtester!")