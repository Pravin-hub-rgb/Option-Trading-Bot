export interface PositionState {
  trade_slot: number;
  state: "idle" | "watching" | "in_position" | "exited_win" | "exited_loss" | "exited_breakeven" | "stopped";
  instrument: "CE" | "PE";
  entry_price: number | null;
  current_sl: number | null;
  highest_price: number | null;
  pnl: number | null;
  exit_price: number | null;
  exit_reason: string | null;
}

export interface BotStatus {
  running: boolean;
  mode: string;
  connected: boolean;
  instruments: string[];
  strikes: Record<string, string>;
  positions: {
    CE: { trade1: PositionState | null; trade2: PositionState | null };
    PE: { trade1: PositionState | null; trade2: PositionState | null };
  };
  stats: {
    total_trades: number;
    wins: number;
    losses: number;
    win_rate: number;
    total_pnl: number;
  };
}

export interface TradeEntry {
  id: number;
  entry_time: string;
  exit_time: string;
  symbol: string;
  entry_price: number | null;
  exit_price: number | null;
  stop_loss: number | null;
  pnl: number | null;
  exit_reason: string;
}

export interface DayPnl {
  date: string;
  trade_count: number;
  net_pnl: number | null;
}

export interface TradeStats {
  total_trades: number;
  profitable: number;
  losing: number;
  unsettled: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
}

export interface SettingMeta {
  key: string;
  value: string;
  type: string;
  label: string;
  category: string;
  options?: string;
}

