import os
import pandas as pd
import requests
from datetime import datetime
import time

# ------------------- CONFIG -------------------
symbol = "BTCUSDT"                    # Spot symbol
base_folder = "SPOT"                  # All data will go here
intervals = ["30s", "1m", "15m"]       # 30s is supported on Spot
# ---------------------------------------------

def get_binance_klines(symbol, interval, start_ts, end_ts):
    url = "https://api.binance.com/api/v3/klines"   # Spot endpoint (supports 30s)
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
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(1)
            continue
            
        if not data or isinstance(data, dict):
            break
            
        all_data.extend(data)
        current = data[-1][0] + 1
        time.sleep(0.05)   # Be nice to the API
        
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
    # Convert to Indian Standard Time (IST)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True).dt.tz_convert('Asia/Kolkata')
    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
    
    return df

# =============== MAIN ===============
os.makedirs(base_folder, exist_ok=True)

print("="*70)
print("BTCUSDT SPOT Downloader (30s + 1m + 15m)")
print("Saves timestamps in INDIAN TIME (IST)")
print("All data goes into folder: SPOT")
print("="*70)

while True:
    try:
        year = int(input("Enter year (e.g., 2025): "))
        if year >= 2017:   # Spot BTCUSDT trading started ~2017
            break
    except:
        pass

print(f"\nDownloading full year {year} for BTCUSDT Spot...\n")

# Create year folder inside SPOT
year_folder = os.path.join(base_folder, str(year))
os.makedirs(year_folder, exist_ok=True)

# Full year timestamps
start_date = datetime(year, 1, 1)
end_date = datetime(year + 1, 1, 1)

start_ts = int(start_date.timestamp() * 1000)
end_ts = int(end_date.timestamp() * 1000)

for interval in intervals:
    print(f"Downloading {interval}...", flush=True)
    df = get_binance_klines(symbol, interval, start_ts, end_ts)

    if df.empty:
        print("   No data returned (interval may not be supported or no trading that year)")
        continue

    # Add required x/y columns (as in your original format)
    df['x'] = 0
    df['y'] = 0
    df_final = df[['open_time', 'open', 'high', 'low', 'close', 'x', 'y']]
    df_final.columns = ['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']

    filename = os.path.join(year_folder, f"BTCUSDT_{interval}.csv")

    df_final.to_csv(filename, index=False, header=True,
                    date_format='%Y-%m-%d %H:%M:%S', float_format='%.2f')

    size_mb = os.path.getsize(filename) / (1024 * 1024)
    print(f"   Saved {filename} → {len(df):,} rows ({size_mb:.2f} MB)")

print("\nAll done! Spot data saved in 'SPOT' folder with IST timestamps.")
print("You can now use the 30s CSV for higher-resolution backtesting.")