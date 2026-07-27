import os
import pandas as pd
import requests
from datetime import datetime
import time
import zipfile
from io import BytesIO
from bs4 import BeautifulSoup

# ------------------- CONFIG -------------------
pair = "EURUSD"                          # Forex pair
base_folder = "eur_usd_data"             # Folder name
# ---------------------------------------------

def download_monthly_zip(year, month):
    """Download and extract 1min CSV for a month from HistData.com"""
    url = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair.lower()}/{year}/{month}"
    
    print(f"   {year}-{month:02d}: ", end="", flush=True)
    
    try:
        session = requests.Session()
        
        # Get the download page and extract hidden token
        page_resp = session.get(url, timeout=60)
        page_resp.raise_for_status()
        
        soup = BeautifulSoup(page_resp.text, 'html.parser')
        hidden_div = soup.find("div", style="display:none;")
        if not hidden_div:
            print("No data page")
            return pd.DataFrame()
        
        tk_input = hidden_div.find("input", {"id": "tk"})
        if not tk_input:
            print("Token missing")
            return pd.DataFrame()
        tk = tk_input["value"]
        
        # POST to download the zip
        post_data = {
            "tk": tk,
            "date": year,
            "datemonth": f"{year}{month:02d}",
            "platform": "ASCII",
            "timeframe": "M1",
            "fxpair": pair.upper()
        }
        headers = {
            "Origin": "https://www.histdata.com",
            "Referer": url,
            "User-Agent": "Mozilla/5.0"
        }
        
        zip_resp = session.post("https://www.histdata.com/get.php", data=post_data, headers=headers, timeout=60)
        zip_resp.raise_for_status()
        
        if "text/html" in zip_resp.headers.get("Content-Type", "") or len(zip_resp.content) < 1000:
            print("No data available")
            return pd.DataFrame()
        
        # Extract CSV from zip
        with zipfile.ZipFile(BytesIO(zip_resp.content)) as z:
            csv_files = [name for name in z.namelist() if name.endswith(".csv")]
            if not csv_files:
                print("No CSV in zip")
                return pd.DataFrame()
            with z.open(csv_files[0]) as f:
                df = pd.read_csv(f, sep=";", header=None,
                                 names=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Parse timestamp: YYYYMMDD HHMMSS
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='%Y%m%d %H%M%S', errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df = df[['timestamp', 'open', 'high', 'low', 'close']]
        
        print(f"{len(df):,} candles")
        return df
        
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()

def aggregate_to_15min(df_1min):
    """Resample 1min to 15min OHLC"""
    if df_1min.empty:
        return pd.DataFrame()
    df_1min = df_1min.set_index('timestamp')
    df_15min = df_1min.resample('15T').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    df_15min.reset_index(inplace=True)
    return df_15min

# =============== MAIN ===============
os.makedirs(base_folder, exist_ok=True)

print("="*70)
print("EUR/USD Forex Downloader (1m + 15m) from HistData.com")
print("→ Full year data in single files (timestamps in UTC)")
print("="*70)

while True:
    try:
        year = int(input("Enter year (e.g., 2024): "))
        if 2001 <= year <= datetime.now().year:
            break
    except:
        pass

print(f"\nDownloading full year {year} for EUR/USD...\n")

year_folder = os.path.join(base_folder, str(year))
os.makedirs(year_folder, exist_ok=True)

# Download and merge all months
all_1min_dfs = []
for month in range(1, 13):
    df_month = download_monthly_zip(year, month)
    if not df_month.empty:
        all_1min_dfs.append(df_month)
    time.sleep(2)  # Polite delay

if not all_1min_dfs:
    print("No data downloaded for this year.")
else:
    # Combine all months
    df_1min_year = pd.concat(all_1min_dfs).sort_values('timestamp').reset_index(drop=True)
    
    # Ensure UTC (HistData times are generally treated as UTC-equivalent for forex)
    df_1min_year['timestamp'] = pd.to_datetime(df_1min_year['timestamp'], utc=True)
    
    # === Save 1min ===
    df_1min_final = df_1min_year.copy()
    df_1min_final['x'] = 0
    df_1min_final['y'] = 0
    df_1min_final = df_1min_final[['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']]
    df_1min_final.columns = ['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']
    
    file_1m = os.path.join(year_folder, f"{pair}_1m.csv")
    df_1min_final.to_csv(file_1m, index=False, header=True,
                         date_format='%Y-%m-%d %H:%M:%S', float_format='%.5f')
    size_mb_1m = os.path.getsize(file_1m) / (1024*1024)
    print(f"   Saved {pair}_1m.csv → {len(df_1min_final):,} rows ({size_mb_1m:.2f} MB)")

    # === Create and save 15min ===
    df_15min_year = aggregate_to_15min(df_1min_year.copy())
    if not df_15min_year.empty:
        df_15min_year['timestamp'] = pd.to_datetime(df_15min_year['timestamp'], utc=True)
        
        df_15min_final = df_15min_year.copy()
        df_15min_final['x'] = 0
        df_15min_final['y'] = 0
        df_15min_final = df_15min_final[['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']]
        df_15min_final.columns = ['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']
        
        file_15m = os.path.join(year_folder, f"{pair}_15m.csv")
        df_15min_final.to_csv(file_15m, index=False, header=True,
                              date_format='%Y-%m-%d %H:%M:%S', float_format='%.5f')
        size_mb_15m = os.path.getsize(file_15m) / (1024*1024)
        print(f"   Saved {pair}_15m.csv → {len(df_15min_final):,} rows ({size_mb_15m:.2f} MB)")

print("\nALL DONE! 🚀")
print(f"Check folder: {year_folder}")
print("Files: EURUSD_1m.csv and EURUSD_15m.csv")
print("Timestamps in UTC — perfect match for your SOL format and backtester!")

# Required: pip install beautifulsoup4