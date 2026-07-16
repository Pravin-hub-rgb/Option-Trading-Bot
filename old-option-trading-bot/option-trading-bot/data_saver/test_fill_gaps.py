import pandas as pd
import numpy as np
from datetime import datetime

def aggregate_to_bars(ticks_df, freq):
    """Aggregate tick data to OHLC bars with improved error handling"""
    if ticks_df.empty:
        return pd.DataFrame()

    try:
        ticks_df = ticks_df.set_index('timestamp')

        # Create complete time index from min to max timestamp with the specified frequency
        start_time = ticks_df.index.min()
        end_time = ticks_df.index.max()
        complete_index = pd.date_range(start=start_time, end=end_time, freq=freq)

        # Resample to get OHLC
        ohlc = ticks_df['price'].resample(freq).ohlc()

        # Reindex to complete time range to fill gaps
        ohlc = ohlc.reindex(complete_index)

        # Forward fill open/high/low/close for missing bars
        ohlc = ohlc.ffill().dropna()
        ohlc.reset_index(inplace=True)
        ohlc.rename(columns={'index': 'timestamp'}, inplace=True)
        return ohlc
    except Exception as e:
        print(f"Error in aggregate_to_bars: {e}")
        return pd.DataFrame()

# Test data similar to user's example (2-minute intervals with gap at 17:03)
test_data = [
    {'timestamp': '2025-01-01 17:00:00', 'price': 1.03503},
    {'timestamp': '2025-01-01 17:02:00', 'price': 1.03514},  # Missing 17:01
    {'timestamp': '2025-01-01 17:04:00', 'price': 1.03514},  # Missing 17:03
    {'timestamp': '2025-01-01 17:05:00', 'price': 1.03514},
    {'timestamp': '2025-01-01 17:06:00', 'price': 1.03516},
    {'timestamp': '2025-01-01 17:07:00', 'price': 1.03512},
    {'timestamp': '2025-01-01 17:08:00', 'price': 1.03504},
    {'timestamp': '2025-01-01 17:09:00', 'price': 1.03495},
]

df_test = pd.DataFrame(test_data)
df_test['timestamp'] = pd.to_datetime(df_test['timestamp'])

print("Original data:")
print(df_test)
print()

# Test aggregation to 1-minute bars
result_1m = aggregate_to_bars(df_test.copy(), '1min')
print("1-minute bars (with gaps filled):")
print(result_1m)
print()

# Test aggregation to 2-minute bars
result_2m = aggregate_to_bars(df_test.copy(), '2min')
print("2-minute bars (with gaps filled):")
print(result_2m)
print()

print("Test completed - gaps should now be filled with forward-filled values.")
