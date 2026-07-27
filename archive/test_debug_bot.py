#!/usr/bin/env python3
"""
Debug Bot Test Script

This script tests the complete bot flow with comprehensive debugging logs
to identify why trades aren't being taken after successful strike selection.

Usage: python test_debug_bot.py
"""

import asyncio
from datetime import datetime
import pytz
from config import ACCESS_TOKEN, MARKET_START, MARKET_END, MARKET_OPEN_DELAY
from upstox.data_streamer import DataStreamer
from scheduler import TradingScheduler

IST = pytz.timezone('Asia/Kolkata')

def now():
    return datetime.now(IST).strftime("%H:%M:%S.%f")[:-3]

def debug_data_streamer_factory(session_name, ce_key, pe_key):
    """Factory function that creates a DataStreamer with debugging"""
    print(f"[{now()}] 🏭 Creating DataStreamer with strikes:")
    print(f"[{now()}] 🏭 CE: {ce_key}")
    print(f"[{now()}] 🏭 PE: {pe_key}")
    
    return DataStreamer(
        session_name=session_name,
        instruments=['CE', 'PE'],  # Trade both CE and PE
        ce_key=ce_key,
        pe_key=pe_key
    )

async def main():
    print(f"[{now()}] 🔍 Starting Debug Bot Test...")
    print(f"[{now()}] 📊 This will test the complete bot flow with detailed logging")
    print(f"[{now()}] 📊 If you see '🎯 FIRST OHLC CANDLE DETECTED!' - OHLC processing is working")
    print(f"[{now()}] 📊 If you see '📊 RED CANDLE DETECTED!' - Strategy is working")
    print(f"[{now()}] 📊 If you see '🎯 BREAKOUT DETECTED!' - Entry logic is working")
    print(f"[{now()}] 📊 If you see '🚀 ENTRY at...' - Trade execution is working")
    print(f"[{now()}] 📊 Press Ctrl+C to stop the test")
    print()
    
    # Create scheduler with debug factory
    scheduler = TradingScheduler(debug_data_streamer_factory)
    
    try:
        await scheduler.start()
    except Exception as e:
        print(f"[{now()}] ❌ Error: {e}")
        scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())