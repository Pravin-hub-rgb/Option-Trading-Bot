#!/usr/bin/env python3
"""
Test the updated scheduler with spot-based filtering
"""

from scheduler import TradingScheduler
import asyncio

# Create a simple test data streamer factory
def create_test_streamer(session_name, ce_key, pe_key):
    print(f'Test: Would create DataStreamer with CE: {ce_key}, PE: {pe_key}')
    return None

async def test_scheduler():
    print("🚀 Testing updated scheduler with spot-based filtering...")
    
    # Create scheduler
    scheduler = TradingScheduler(create_test_streamer)
    
    # Test the fetch_live_strikes method
    result = scheduler.fetch_live_strikes()
    
    if result:
        print('✅ SUCCESS: Found strikes with spot-based filtering')
        print(f'   CE: {result["ce_strike"]} (₹{result["ce_premium"]:.2f}) - {result["ce_key"]}')
        print(f'   PE: {result["pe_strike"]} (₹{result["pe_premium"]:.2f}) - {result["pe_key"]}')
        print(f'   Distance from ₹100: CE={abs(result["ce_premium"]-100):.2f}, PE={abs(result["pe_premium"]-100):.2f}')
    else:
        print('❌ FAILED: No strikes found')

if __name__ == "__main__":
    asyncio.run(test_scheduler())