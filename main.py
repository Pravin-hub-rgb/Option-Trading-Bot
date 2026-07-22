"""
NIFTY Options Trading Bot - Main Entry Point

Usage:
    python main.py                    # Trade both CE and PE (default)
    python main.py --instruments CE   # Trade only CE
    python main.py --instruments PE   # Trade only PE
    python main.py --instruments BOTH # Trade both CE and PE (explicit)
"""
import argparse
from upstox.data_streamer import DataStreamer  # ← UPDATED IMPORT
from scheduler import TradingScheduler
import asyncio
import signal
import sys
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

def signal_handler(sig, frame):
    print(f"[{datetime.now(IST).strftime('%H:%M:%S.%f')[:-3]}] 🛑 Ctrl+C received")
    if 'scheduler' in globals():
        scheduler.stop()
    sys.exit(0)

def parse_instruments(instruments_arg):
    """
    Parse instruments argument and return list of instruments to trade
    
    Args:
        instruments_arg: 'CE', 'PE', or 'BOTH'
    
    Returns:
        list: ['CE'], ['PE'], or ['CE', 'PE']
    """
    if instruments_arg == 'CE':
        return ['CE']
    elif instruments_arg == 'PE':
        return ['PE']
    else:  # 'BOTH'
        return ['CE', 'PE']

async def main():
    global scheduler
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='NIFTY Options Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Trade both CE and PE
  python main.py --instruments CE   # Trade only CE
  python main.py --instruments PE   # Trade only PE
        """
    )
    parser.add_argument(
        '--instruments',
        type=str,
        choices=['CE', 'PE', 'BOTH'],
        default='BOTH',
        help='Which instruments to trade (default: BOTH)'
    )
    
    args = parser.parse_args()
    
    # Convert to list format
    instruments_to_trade = parse_instruments(args.instruments)
    
    print(f"[{datetime.now(IST).strftime('%H:%M:%S.%f')[:-3]}] 🚀 Starting bot...")
    print(f"[{datetime.now(IST).strftime('%H:%M:%S.%f')[:-3]}] 📊 Trading: {', '.join(instruments_to_trade)}")
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create scheduler with data streamer class and instruments
    def create_data_streamer(session_name):
        return DataStreamer(session_name=session_name, instruments=instruments_to_trade)
    
    scheduler = TradingScheduler(create_data_streamer)
    
    try:
        await scheduler.start()
    except Exception as e:
        print(f"[{datetime.now(IST).strftime('%H:%M:%S.%f')[:-3]}] ❌ Error: {e}")
        scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())