import pandas as pd
import os
from datetime import datetime

def main():
    print("="*70)
    print("XAUUSD Monthly Data Combiner")
    print("Combining monthly data files into full yearly format")
    print("="*70)
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Directory containing monthly data
    months_dir = os.path.join(script_dir, "months")
    
    if not os.path.exists(months_dir):
        print(f"Error: {months_dir} directory not found!")
        return
    
    # Month names in order
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Process both 1-minute and 15-minute data
    for timeframe in ["1m", "15m"]:
        print(f"\nProcessing {timeframe} data...")
        
        # Collect all monthly data
        combined_data = []
        
        for month_name in month_names:
            month_folder = os.path.join(months_dir, month_name)
            month_file = os.path.join(month_folder, f"XAUUSD_{timeframe}.csv")
            
            if os.path.exists(month_file):
                print(f"   Reading {month_name}: {month_file}")
                try:
                    df = pd.read_csv(month_file)
                    
                    # Check if we have the expected columns
                    expected_cols = ['timestamp', 'open', 'high', 'low', 'close', 'x', 'y']
                    if list(df.columns) != expected_cols:
                        print(f"   Warning: Unexpected column structure in {month_file}")
                        print(f"   Expected: {expected_cols}")
                        print(f"   Found: {list(df.columns)}")
                        continue
                    
                    # Remove x and y columns (they should be 0 anyway)
                    df = df[['timestamp', 'open', 'high', 'low', 'close']]
                    
                    # Convert timestamp to datetime for proper sorting
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    combined_data.append(df)
                    
                except Exception as e:
                    print(f"   Error reading {month_file}: {e}")
                    continue
            else:
                print(f"   Warning: {month_file} not found")
        
        if combined_data:
            # Combine all monthly data
            print(f"   Combining data from {len(combined_data)} months...")
            full_year_df = pd.concat(combined_data, ignore_index=True)
            
            # Sort by timestamp to ensure chronological order
            full_year_df = full_year_df.sort_values('timestamp')
            
            # Reset index
            full_year_df = full_year_df.reset_index(drop=True)
            
            # Format timestamp back to string
            full_year_df['timestamp'] = full_year_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Save the combined file
            output_file = os.path.join(script_dir, f"XAUUSD_{timeframe}_2025.csv")
            full_year_df.to_csv(output_file, index=False, float_format='%.3f')
            
            print(f"   ✓ Combined {timeframe} data saved to: {output_file}")
            print(f"   ✓ Total rows: {len(full_year_df)}")
        else:
            print(f"   No {timeframe} data found to combine")
    
    print("\n" + "="*70)
    print("ALL DONE! 🚀")
    print("Full yearly files created:")
    print("  - XAUUSD_1m_2025.csv")
    print("  - XAUUSD_15m_2025.csv")
    print("="*70)

if __name__ == "__main__":
    main()
