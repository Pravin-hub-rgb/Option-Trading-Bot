import csv
import os
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")

class TradeLogger:
    def __init__(self, session_name, symbol):
        self.symbol = symbol
        date_str = datetime.now(IST).strftime('%d_%b_%y').lower()
        self.trade_log_file = os.path.join(LOGS_DIR, f"trade_log_{date_str}_{session_name}.csv")
        self.init_log()

    def init_log(self):
        os.makedirs(LOGS_DIR, exist_ok=True)
        if not os.path.exists(self.trade_log_file):
            with open(self.trade_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['time', 'symbol', 'type', 'price', 'stop_loss', 'target', 'exit_reason', 'pnl'])

    def log_entry(self, symbol, entry_price, stop_loss, entry_time):
        with open(self.trade_log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                entry_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                symbol,
                'entry',
                f"{entry_price:.2f}",
                f"{stop_loss:.2f}",
                '',
                '',
                ''
            ])

    def log_exit(self, symbol, exit_price, stop_loss, exit_time, exit_reason, pnl):
        with open(self.trade_log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                exit_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                symbol,
                'exit',
                f"{exit_price:.2f}",
                f"{stop_loss:.2f}",
                '',
                exit_reason,
                f"{pnl:.2f}"
            ])

    def close(self):
        pass  # File written incrementally