import os
import sys
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_conn, init_db

IST = pytz.timezone('Asia/Kolkata')


class TradeLogger:
    def __init__(self, session_name, symbol):
        self.symbol = symbol
        self.session_name = session_name
        init_db()

    def log_entry(self, symbol, entry_price, stop_loss, entry_time):
        conn = get_conn()
        conn.execute("""
            INSERT INTO trades (symbol, entry_time, entry_price, stop_loss)
            VALUES (?, ?, ?, ?)
        """, (
            symbol,
            entry_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            entry_price,
            stop_loss,
        ))
        conn.commit()
        conn.close()

    def log_exit(self, symbol, exit_price, stop_loss, exit_time, exit_reason, pnl,
                 mfe_points=None, mae_points=None, sl_rungs_locked=None,
                 ticks_seen=None, peak_tick=None, bank_touched=None,
                 first_bank_tick=None, dips_below_bank=None):
        conn = get_conn()
        try:
            exit_time_str = exit_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cursor = conn.execute("""
                SELECT id FROM trades
                WHERE symbol = ? AND (exit_time IS NULL OR exit_time = '')
                ORDER BY id DESC LIMIT 1
            """, (symbol,))
            row = cursor.fetchone()
            if row:
                conn.execute("""
                    UPDATE trades
                    SET exit_time = ?, exit_price = ?, exit_reason = ?, pnl = ?,
                        mfe_points = ?, mae_points = ?, sl_rungs_locked = ?,
                        ticks_seen = ?, peak_tick = ?, bank_touched = ?,
                        first_bank_tick = ?, dips_below_bank = ?
                    WHERE id = ?
                """, (exit_time_str, exit_price, exit_reason, pnl,
                      mfe_points, mae_points, sl_rungs_locked,
                      ticks_seen, peak_tick, int(bool(bank_touched)),
                      first_bank_tick, dips_below_bank, row[0]))
            else:
                print(f"[WARN] log_exit: no open trade found for {symbol} (exit not recorded)")
            conn.commit()
        except Exception as e:
            print(f"[ERROR] log_exit: {e}")
            conn.rollback()
        finally:
            conn.close()

    def close(self):
        pass
