# create_1min_ohlc.py
# Converts tick data from tick_log_10_nov_25_morning.csv to 1-minute OHLC candles
# Input: Timestamp,Symbol,LTP (e.g., 2025-11-10 09:15:00.452,NIFTY11NOV2525500PE,57.60)
# Output: Timestamp,Symbol,Open,High,Low,Close (e.g., 2025-11-10 09:15:00+05:30,NIFTY11NOV2525500CE,114.40,141.15,114.40,138.00)
# Run: python create_1min_ohlc.py

import pandas as pd
from datetime import datetime
import pytz

# Define timezone
IST = pytz.timezone('Asia/Kolkata')

def create_1min_ohlc_candles(input_csv, output_csv):
    """
    Convert tick data to 1-minute OHLC candles.
    :param input_csv: Path to input tick CSV (e.g., tick_log_10_nov_25_morning.csv)
    :param output_csv: Path to output OHLC CSV (e.g., ohlc_10_nov_25_morning.csv)
    """
    print(f"[INFO] Reading {input_csv}...")
    try:
        # Read tick data
        df = pd.read_csv(input_csv)
        
        # Validate required columns
        if not all(col in df.columns for col in ['Timestamp', 'Symbol', 'LTP']):
            raise ValueError("CSV must contain Timestamp,Symbol,LTP columns")
        
        # Convert Timestamp to datetime and localize to IST
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize(IST)
        
        print(f"[INFO] Aggregating {len(df)} ticks into 1-minute candles...")
        # Floor Timestamp to nearest minute
        df['TimeBucket'] = df['Timestamp'].dt.floor('1min')
        
        # Group by Symbol and TimeBucket, compute OHLC
        ohlc = df.groupby(['Symbol', 'TimeBucket']).agg({
            'LTP': [
                ('Open', 'first'),   # First LTP in the minute
                ('High', 'max'),     # Max LTP in the minute
                ('Low', 'min'),      # Min LTP in the minute
                ('Close', 'last')    # Last LTP in the minute
            ]
        }).reset_index()
        
        # Flatten multi-level columns
        ohlc.columns = ['Symbol', 'Timestamp', 'Open', 'High', 'Low', 'Close']
        
        # Round prices to 2 decimal places
        ohlc[['Open', 'High', 'Low', 'Close']] = ohlc[['Open', 'High', 'Low', 'Close']].round(2)
        
        # Sort by Symbol and Timestamp
        ohlc = ohlc.sort_values(['Symbol', 'Timestamp'])
        
        print(f"[INFO] Writing {len(ohlc)} candles to {output_csv}...")
        # Save to CSV
        ohlc.to_csv(output_csv, index=False)
        
        print(f"[INFO] Done! Check {output_csv}")
        
    except FileNotFoundError:
        print(f"[ERROR] {input_csv} not found")
    except Exception as e:
        print(f"[ERROR] Failed to process: {e}")

if __name__ == "__main__":
    # File paths
    input_csv = "tick_log_10_nov_25_morning.csv"
    output_csv = "ohlc_10_nov_25_morning.csv"
    
    # Create 1-minute OHLC candles
    create_1min_ohlc_candles(input_csv, output_csv)