import pandas as pd
import os
from datetime import datetime

# ----------------------------- SETTINGS -----------------------------
CSV_FILENAME = "SBIN.csv"          # Your downloaded file name
YEAR = 2025
OUTPUT_FOLDER = f"stocks/{YEAR}"

# Create output folder if it doesn't exist
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

print("Loading SBIN.csv ...")
df = pd.read_csv(CSV_FILENAME)

# Basic checks
print(f"Loaded {len(df)} rows")
print("Columns found:", list(df.columns))

# Expected columns: date,open,high,low,close,volume
df.rename(columns={'date': 'timestamp'}, inplace=True)

# Convert timestamp to datetime (already in IST from your sample)
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Filter only 2025
df = df[df['timestamp'].dt.year == YEAR].copy()
df.sort_values('timestamp', inplace=True)
df.reset_index(drop=True, inplace=True)

print(f"Filtered to {YEAR}: {len(df)} rows")

# Add dummy x,y columns with 0,0
df['x'] = 0
df['y'] = 0

# Reorder columns exactly as you want
df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'x', 'y']]

# Format timestamp as string exactly like your backtester expects
df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

# ===================== SAVE 1-MINUTE FILE =====================
file_1min = os.path.join(OUTPUT_FOLDER, "SBI_1min_2025.csv")
df.to_csv(file_1min, index=False, header=False)
print(f"Saved 1min data → {file_1min} ({len(df)} candles)")

# ===================== RESAMPLE TO 15-MINUTE =====================
df15 = df.copy()
df15['timestamp'] = pd.to_datetime(df15['timestamp'])  # back to datetime for resampling
df15.set_index('timestamp', inplace=True)

df15_resampled = df15.resample('15min').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum',
    'x': 'last',   # will be 0
    'y': 'last'    # will be 0
}).dropna()

df15_resampled.reset_index(inplace=True)
df15_resampled['timestamp'] = df15_resampled['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
df15_resampled = df15_resampled[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'x', 'y']]

file_15min = os.path.join(OUTPUT_FOLDER, "SBI_15min_2025.csv")
df15_resampled.to_csv(file_15min, index=False, header=False)
print(f"Saved 15min data → {file_15min} ({len(df15_resampled)} candles)")

print("\nAll done!")
print(f"Check folder: {OUTPUT_FOLDER}")
print("Files ready for your backtester ✅")