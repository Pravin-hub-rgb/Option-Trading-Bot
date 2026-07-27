from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

class Trader:
    def __init__(self, logger, symbol, capital=100000.0, quantity=1):
        self.logger = logger
        self.symbol = symbol
        self.capital = capital
        self.quantity = quantity
        self.position = None

    def open_position(self, entry_price, stop_loss, entry_time):
        self.position = {
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'entry_time': entry_time,
            'quantity': self.quantity
        }
        self.logger.log_entry(
            symbol=self.symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            entry_time=entry_time
        )
        return self.position

    def close_position(self, exit_price, exit_time, exit_reason):
        if not self.position:
            return
        entry_price = self.position['entry_price']
        quantity = self.position['quantity']
        pnl = (exit_price - entry_price) * quantity
        self.capital += pnl
        self.logger.log_exit(
            symbol=self.symbol,
            exit_price=exit_price,
            stop_loss=self.position['stop_loss'],
            exit_time=exit_time,
            exit_reason=exit_reason,
            pnl=pnl
        )
        self.position = None