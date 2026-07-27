# --- nifty_spot_collector_by_month.py --- THE FINAL ONE YOU WANTED
import upstox_client
import pandas as pd
import csv
import os
from datetime import datetime, timedelta
from calendar import monthrange
from upstox_client.rest import ApiException
from time import sleep
import config

# =======================================================
# SIRF EK NUMBER DAALO → MONTH (1-12)
# Year fixed 2025 (change if needed)
# =======================================================
TARGET_MONTH = 11  # ← Yahan sirf 9 daalo for September
YEAR = 2025

# =======================================================
# AUTOMATIC FOLDER NAME
month_names = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
FOLDER_NAME = f"{month_names[TARGET_MONTH]} {YEAR}"
OUTPUT_DIR = os.path.join("Nifty_Data_Collector", FOLDER_NAME)
# =======================================================

def setup_api():
    if not config.ACCESS_TOKEN or "YOUR" in config.ACCESS_TOKEN:
        raise ValueError("Fresh ACCESS_TOKEN daal bhai config.py mein!")
    conf = upstox_client.Configuration()
    conf.access_token = config.ACCESS_TOKEN
    return upstox_client.HistoryApi(upstox_client.ApiClient(conf))

def fetch_and_save_5min(date_str):
    final_file = os.path.join(OUTPUT_DIR, f"{date_str[-2:]}.csv")  # 01.csv, 02.csv etc.
    
    if os.path.exists(final_file):
        print(f"   {date_str} → Already done, skipping")
        return

    temp_1min = f"temp_{date_str}.csv"
    try:
        print(f"   Downloading {date_str} ...", end="")
        resp = api.get_historical_candle_data1(
            config.NIFTY_INDEX_KEY, "1minute", date_str, date_str, "2.0"
        )
        candles = resp.data.candles
        if not candles:
            print("  Holiday/No data")
            return

        # Save temp 1min
        with open(temp_1min, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp','open','high','low','close','volume','oi'])
            writer.writerows(candles)

        # Convert to 5min
        df = pd.read_csv(temp_1min)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('Asia/Kolkata')
        df.set_index('timestamp', inplace=True)

        df5 = df.resample('5min').agg({
            'open':'first', 'high':'max', 'low':'min',
            'close':'last', 'volume':'sum', 'oi':'last'
        }).dropna().reset_index()

        df5['timestamp'] = df5['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df5.to_csv(final_file, index=False)

        os.remove(temp_1min)  # Clean up
        print(f"  Done → {date_str[-2:]}.csv ({len(df5)} candles)")

    except Exception as e:
        print(f"  Failed: {e}")
        if os.path.exists(temp_1min):
            os.remove(temp_1min)

# ===================== MAIN =====================
print("="*70)
print(f"    NIFTY 5MIN COLLECTOR → {FOLDER_NAME}")
print("    Files: 01.csv, 02.csv, ..., 30.csv (clean & beautiful)")
print("="*70)

os.makedirs(OUTPUT_DIR, exist_ok=True)
api = setup_api()

# Get first & last day of the month
first_day = datetime(YEAR, TARGET_MONTH, 1).date()
last_day_num = monthrange(YEAR, TARGET_MONTH)[1]
last_day = datetime(YEAR, TARGET_MONTH, last_day_num).date()

current = first_day
while current <= last_day:
    if current.weekday() < 5:  # Mon-Fri only
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n→ {date_str} ({current.strftime('%a')})", end="")
        fetch_and_save_5min(date_str)
        sleep(1.2)
    else:
        print(f"\n   {current.strftime('%Y-%m-%d')} → Weekend, skipping")
    
    current += timedelta(days=1)

print("\n" + "="*70)
print(f"ALL DONE! Check folder:")
print(f"   → {OUTPUT_DIR}")
print("   Files like: 01.csv, 15.csv, 30.csv (only 5min, super clean)")
print("="*70)