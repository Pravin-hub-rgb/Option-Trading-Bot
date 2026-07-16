#!/usr/bin/env python3
"""
Test script to check if Yahoo Finance works for Forex data
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def test_yahoo_forex():
    """Test Yahoo Finance Forex data availability"""
    print("Testing Yahoo Finance Forex data availability...")
    print("=" * 50)
    
    # Test symbol for EUR/USD
    symbol = "EURUSD=X"
    
    # Test recent dates
    test_dates = [
        (2024, 12, 31),
        (2025, 1, 1),
        (2025, 1, 2),
    ]
    
    for year, month, day in test_dates:
        try:
            start_date = f"{year}-{month:02d}-{day:02d}"
            end_date = f"{year}-{month:02d}-{day+1:02d}"
            
            print(f"Checking {start_date}: ", end="")
            data = yf.download(symbol, start=start_date, end=end_date, interval='1m')
            
            if not data.empty:
                print(f"✓ Available ({len(data)} minutes)")
            else:
                print("✗ No data")
                
        except Exception as e:
            print(f"✗ Error: {e}")
    
    # Test year availability
    print("\nTesting year availability...")
    current_year = datetime.now().year
    
    for year in range(current_year - 5, current_year + 1):
        try:
            start_date = f"{year}-01-01"
            end_date = f"{year}-01-02"
            
            data = yf.download(symbol, start=start_date, end=end_date, interval='1d')
            
            if not data.empty:
                print(f"✓ {year} available")
            else:
                print(f"✗ {year} not available")
                
        except Exception as e:
            print(f"✗ {year} error: {e}")

if __name__ == "__main__":
    test_yahoo_forex()
