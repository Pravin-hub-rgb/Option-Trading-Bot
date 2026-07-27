#!/usr/bin/env python3
"""
Test script to check if the debug version of forex_data.py works
and to verify data availability for 2025
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from forex_data_debug import check_dukascopy_availability, get_available_years

def test_data_availability():
    """Test if Dukascopy has data available for recent dates"""
    print("Testing Dukascopy data availability...")
    print("=" * 50)
    
    # Test some recent dates
    test_dates = [
        (2024, 12, 31),  # Last day of 2024
        (2025, 1, 1),    # First day of 2025
        (2025, 1, 2),    # Second day of 2025
        (2025, 12, 25),  # Christmas 2025 (if it exists)
    ]
    
    for year, month, day in test_dates:
        print(f"Checking {year}-{month:02d}-{day:02d}: ", end="")
        available = check_dukascopy_availability(year, month, day)
        print("✓ Available" if available else "✗ Not Available")
    
    print("\nChecking available years...")
    available_years = get_available_years()
    print(f"Available years: {available_years}")
    
    if 2025 in available_years:
        print("✓ 2025 data is available on Dukascopy")
    else:
        print("✗ 2025 data is NOT available on Dukascopy")
        print("You may need to use a different year or data source")

if __name__ == "__main__":
    test_data_availability()
