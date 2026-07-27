import pandas as pd
import os
from datetime import datetime

def main():
    print("="*70)
    print("XAUUSD Monthly Data Splitter")
    print("Converting yearly data to monthly format with x,y columns")
    print("="*70)
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # File paths (absolute paths)
    file_1m = os.path.join(script_dir, "xauusd-m1-bid-2025-01-01-2025-12-30T13-56.csv")
    file_15m = os.path.join(script_dir, "xauusd-m15-bid-2025-01-01-2025-12-30T14-09.csv")
    
    # Month names for folder creation
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Create months directory in the script's directory
    months_dir = os.path.join(script_dir, "months")
    if not os.path.exists(months_dir):
        os.makedirs(months_dir)
        print(f"Created directory: {months_dir}")
    
    # Process 1-minute data
    if os.path.exists(file_1m):
        print(f"\nProcessing 1-minute data: {file_1m}")
        process_file(file_1m, months_dir, "1m", month_names)
    else:
        print(f"Warning: {file_1m} not found")
    
    # Process 15-minute data
    if os.path.exists(file_15m):
        print(f"\nProcessing 15-minute data: {file_15m}")
        process_file(file_15m, months_dir, "15m", month_names)
    else:
        print(f"Warning: {file_15m} not found")
    
    print("\n" + "="*70)
    print("ALL DONE! 🚀")
    print(f"Check the '{months_dir}' folder for monthly data files")
    print("Format: timestamp,open,high,low,close,x,y")
    print("="*70)

def process_file(input_file, months_dir, timeframe, month_names):
    """Process a CSV file and split into monthly files"""
    
    # Read the CSV file
    print(f"   Reading {input_file}...")
    df = pd.read_csv(input_file)
    
    # Check if we have the expected columns
    expected_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    if list(df.columns) != expected_cols:
        print(f"   Warning: Unexpected column structure in {input_file}")
        print(f"   Expected: {expected_cols}")
        print(f"   Found: {list(df.columns)}")
        return
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Group by month and process each month
    for month in range(1, 13):
        # Filter data for this month
        month_data = df[df['timestamp'].dt.month == month]
        
        if len(month_data) == 0:
            print(f"   Month {month_names[month-1]}: No data")
            continue
        
        # Create month folder
        month_folder = os.path.join(months_dir, month_names[month-1])
        if not os.path.exists(month_folder):
            os.makedirs(month_folder)
        
        # Convert format: remove volume, add x=0, y=0
        output_data = month_data[['timestamp', 'open', 'high', 'low', 'close']].copy()
        output_data['x'] = 0
        output_data['y'] = 0
        
        # Format timestamp back to string
        output_data['timestamp'] = output_data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Save file
        output_file = os.path.join(month_folder, f"XAUUSD_{timeframe}.csv")
        output_data.to_csv(output_file, index=False, float_format='%.3f')
        
        print(f"   Month {month_names[month-1]}: {len(month_data)} rows → {output_file}")

if __name__ == "__main__":
    main()
