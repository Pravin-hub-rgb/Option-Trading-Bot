#!/usr/bin/env python3
"""
Test script for Alpha Vantage forex data download
"""

import os
import sys
import pandas as pd
from datetime import datetime

# Add current directory to path to import forex_data_final
sys.path.append('.')

# Import the functions we want to test
try:
    from forex_data_final import download_alpha_vantage_day, check_alpha_vantage_availability, ALPHA_VANTAGE_API_KEY
    print("✓ Successfully imported Alpha Vantage functions")
except ImportError as e:
    print(f"✗ Failed to import functions: {e}")
    sys.exit(1)

def test_api_key_check():
    """Test if API key check works"""
    print(f"\nCurrent API key: {ALPHA_VANTAGE_API_KEY}")

    if ALPHA_VANTAGE_API_KEY == "YOUR_API_KEY_HERE":
        print("✓ API key is set to default placeholder")
        print("  To test Alpha Vantage, get a free API key from https://www.alphavantage.co/support/#api-key")
        print("  Then replace 'YOUR_API_KEY_HERE' in forex_data_final.py")
    else:
        print("✓ API key appears to be set (not the default placeholder)")

def test_availability_check():
    """Test availability check function"""
    print("\nTesting Alpha Vantage availability check...")
    try:
        available = check_alpha_vantage_availability(2024)
        if available:
            print("✓ Alpha Vantage reported as available")
        else:
            print("✗ Alpha Vantage reported as not available")
            print("  This could be due to API key not set or API limits")
    except Exception as e:
        print(f"✗ Error checking availability: {e}")

def test_download_function():
    """Test download function structure (won't actually download without API key)"""
    print("\nTesting download function structure...")

    test_date = datetime(2024, 1, 1)  # Monday, should be a trading day

    try:
        result = download_alpha_vantage_day(test_date)
        if result.empty:
            print("✓ Download function returned empty DataFrame (expected without valid API key)")
        else:
            print("✓ Download function returned data!")
            print(f"  Downloaded {len(result)} ticks")
            print(f"  Date range: {result['timestamp'].min()} to {result['timestamp'].max()}")
    except Exception as e:
        print(f"✗ Error in download function: {e}")

if __name__ == "__main__":
    print("="*60)
    print("ALPHA VANTAGE FOREX DATA TEST")
    print("="*60)

    test_api_key_check()
    test_availability_check()
    test_download_function()

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("\nTo use Alpha Vantage:")
    print("1. Get free API key from https://www.alphavantage.co/support/#api-key")
    print("2. Replace 'YOUR_API_KEY_HERE' in forex_data_final.py")
    print("3. Run the forex downloader - it will prioritize Alpha Vantage")
