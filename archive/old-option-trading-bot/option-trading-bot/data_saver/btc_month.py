import os
import pandas as pd
import requests
from datetime import datetime
import time
import pytz  # only added this one line

# ------------------- CONFIG -------------------
symbol = "BTCUSDT"
base_folder = "30_1_15_data"  # New base folder as requested
intervals = ["30s", "1m", "15m"]
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
    # THIS IS THE ONLY CHANGE → convert straight to IST
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True).dt.tz_convert('Asia/Kolkata')
    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
    
    return df

# =============== MAIN ===============
os.makedirs(base_folder, exist_ok=True)

print("="*70)
print("BTC Year Downloader (30s/1m/15m) → Now saves timestamps in INDIAN TIME (IST)")
print("Full year data per interval in single CSVs")
print("="*70)

while True:
    try:
        year = int(input("Enter year (e.g., 2025): "))
        if year >= 2000: break
    except:
        pass

print(f"\nDownloading full year for {year} → Indian Standard Time (IST)\n")

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
        print("   No data")
        continue

    df['x'] = 0
    df['y'] = 0
    df_final = df[['open_time', 'open', 'high', 'low', 'close', 'x', 'y']]
    df_final.columns = ['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']

    filename = os.path.join(year_folder, f"BTCUSDT_{interval}.csv")   # ← EXACTLY SAME NAME AS BEFORE

    df_final.to_csv(filename, index=False, header=True,
                    date_format='%Y-%m-%d %H:%M:%S', float_format='%.2f')

    size_mb = os.path.getsize(filename) / (1024*1024)
    print(f"   Saved BTCUSDT_{interval}.csv → {len(df):,} rows ({size_mb:.2f} MB)")

print("\nDone! All files have full year data in Indian time (IST)")
print("Example: 13:15 candle will show as 13:15:00 directly")