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
  gross_pnl?: number | null;
  net_pnl?: number | null;
  charges?: number | null;
  buy_value?: number | null;
  sell_value?: number | null;
  /** Premium the strike selector paid for this option, and when. Null on trades logged before selection capture existed. */
  sel_premium?: number | null;
  /** Which basket the selector landed on: 100 / 80 / 50. */
  sel_tier?: number | null;
  sel_at?: string | null;
  /** Exit-rule generation live when this trade ran: 5 = bank-first, 1 = the retired charges-only ladder. NULL on archive rows logged before the switch. */
  bank_rung?: number | null;
}

export interface DayPnl {
  date: string;
  trade_count: number;
  net_pnl: number | null;
  net_rupees?: number | null;
}

export interface ExitRulesTrade {
  id: number | null;
  date: string;
  entry_time: string;
  symbol: string;
  entry_price: number | null;
  exit_price: number | null;
  exit_reason: string;
  mfe_points: number | null;
  mfe_source: "exact" | "rung" | "unknown" | null;
  mfe_bucket: number;
  mfe_bucket_label: string;
  giveback_points: number | null;
  dips_below_bank: number | null;
  /** Exit-rule generation this trade ran under; NULL on archive rows. */
  bank_rung: number | null;
  actual_pnl: number | null;
  actual_net: number | null;
  legacy_pnl: number | null;
  legacy_net: number | null;
  /** Report rows swap these for the bank-first pass (rule_book.rows). */
  rule_pnl?: number | null;
  rule_net?: number | null;
  delta_points: number | null;
  delta_net: number | null;
  rule_fired: string;
  /** False when the counterfactual is a peak-based guess, not measured. */
  verified: boolean;
  /** True only when the outcome was replayed over recorded ticks. */
  replayed: boolean;
  /** helped / hurt / same / unknown - the delta decides, not the label. */
  verdict: string;
  evidence: {
    ticks: number;
    armed_at_tick: number | null;
    fired_at_tick: number | null;
    rungs_locked: number;
    exit_price: number | null;
    exit_points: number | null;
    fired_early: boolean;
  } | null;
  proof: "tick" | "crossing" | "live" | "assumed";
  day_stopped: boolean;
}

export interface ExitRulesDay {
  date: string;
  trades_actual: number;
  trades_taken: number;
  actual_net: number | null;
  legacy_net: number | null;
  delta_net: number;
  stopped_early: boolean;
  first_trade_pnl: number | null;
}

export interface RunSummary {
  trades: number;
  trades_skipped: number;
  gross_points: number;
  net_rupees: number;
  win_rate: number;
  /** The as-traded book alongside, for honest comparisons. */
  actual_gross_points: number;
  actual_net_rupees: number;
  /** Trades whose counterfactual was replayed over recorded ticks. */
  verified_trades: number;
  unverified_trades: number;
  verified_net_rupees: number;
  verified_actual_net_rupees: number;
  /** Subset of verified_trades replayed tick by tick (the gold standard). */
  replayed_trades?: number;
  replayed_helped?: number;
  replayed_hurt?: number;
  replayed_same?: number;
  replayed_points?: number;
  replayed_actual_points?: number;
}

export interface MfeBucket {
  bucket: number;
  label: string;
  count: number;
  pct: number;
  avg_pnl: number;
  avg_net: number;
  avg_giveback: number;
  total_net: number;
}

export interface MfeReport {
  total_trades: number;
  mfe_known: number;
  mfe_unknown: number;
  exact_count: number;
  rung_count: number;
  histogram: MfeBucket[];
  leak: {
    count: number;
    actual_net: number;
    /** HINDSIGHT guess: assumes every one of them banked a clean +5. */
    hindsight_net: number;
    hindsight_recoverable: number;
    /** MEASURED: only trades whose real tick path we captured. */
    verified_trades: number;
    unverified_trades: number;
    verified_gain: number;
  };
  never_reached_5: {
    count: number;
    pct: number;
    avg_pnl: number;
    total_net: number;
  };
  reached_10: { count: number; pct: number };
}

/** The live rule's own book: the bank-first ladder replayed over every
 * settled trade - the would-have study on archive rows, the live mirror on
 * post-switch rows. This is the headline the rule card renders. */
export interface RuleBook {
  bank_at: number;
  trades: number;
  trades_skipped: number;
  gross_points: number;
  net_rupees: number;
  actual_gross_points: number;
  actual_net_rupees: number;
  delta_points: number;
  delta_net: number;
  /** The book per trade: bank-first would-have on archive rows (`rule_pnl` /
   * `rule_net`), a mirror of reality on post-switch rows. */
  rows?: ExitRulesTrade[];
}

export interface ExitRulesReport {
  settings: { bank_at: number; day_stop_at: number | null; exit_buffer_pts: number };
  trades: ExitRulesTrade[];
  days: ExitRulesDay[];
  summary: RunSummary;
  baseline: RunSummary;
  delta_net: number;
  per_day_delta: number;
  /** Delta counting ONLY trades whose tick path was actually recorded. */
  verified_delta_net: number;
  verified_coverage_pct: number;
  /**
   * Splits the headline delta_net by how strong each row's evidence actually
   * is. Only `tick_replayed` rests on real recorded prices; `crossing_estimated`
   * proves the stop fired but ASSUMES where it filled.
   */
  evidence_split: {
    tick_replayed: { trades: number; delta_net: number; delta_points: number };
    crossing_estimated: { trades: number; delta_net: number };
    not_provable: { trades: number; delta_net: number };
    unchanged: { trades: number; delta_net: number };
  };
  /**
   * The definitive view: trades replayed tick by tick over recorded paths,
   * each with a helped/hurt/same verdict and the evidence behind it.   */
  replay_verdict: {
    trades: number;
    helped: number;
    hurt: number;
    same: number;
    actual_points: number;
    sim_points: number;
    delta_points: number;
    rows: {
      id: number | null;
      date: string;
      entry_time: string;
      symbol: string;
      verdict: "helped" | "hurt" | "same" | "unknown";
      actual_points: number | null;
      sim_points: number | null;
      delta_points: number | null;
      mfe_points: number | null;
      dips: number | null;
      evidence: {
        ticks: number;
        armed_at_tick: number | null;
        fired_at_tick: number | null;
        rungs_locked: number;
        exit_price: number | null;
        exit_points: number | null;
        fired_early: boolean;
      } | null;
    }[];
  };
  monthly: {
    month: string;
    trades: number;
    actual_net: number;
    legacy_net: number;
    delta_net: number;
  }[];
  /** The bank-first ledger - see RuleBook. */
  rule_book: RuleBook;
  mfe_coverage: MfeReport;
}

export interface StrategyRow {
  key: string;
  label: string;
  bank_at: number | null;
  prove_at: number | null;
  day_stop_at: number | null;
  trades: number;
  skipped: number;
  net_rupees: number;
  per_day: number;
  win_rate: number;
}

export interface SweepRow {
  day_stop_at: number | null;
  trades: number;
  net_rupees: number;
  per_day: number;
}

export interface RiskScenario {
  key: string;
  label: string;
  trades_taken: number;
  points: number;
  vs_baseline: number;
  days_better: number;
  days_same: number;
  days_worse: number;
  worst_days: { date: string; delta: number }[];
}

export interface RiskReport {
  baseline_points: number;
  total_days: number;
  total_trades: number;
  scenarios: RiskScenario[];
  coverage: {
    bankable: number;
    never_reached: number;
    runner: number;
    unknown: number;
  };
  runner_dips?: {
    measured_trades: number;
    dipped: number;
    dipped_pct: number;
    runner_dipped: number;
    bankable_measured: number;
    bankable_dipped: number;
    note: string;
  };
}

export interface TradeStats {
  total_trades: number;
  profitable: number;
  breakeven: number;
  losing: number;
  unsettled: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
  breakeven_tolerance?: number;
  gross_total_pnl?: number;
  total_charges?: number;
  net_total_pnl?: number;
  per_point?: number;
  days_traded?: number;
}

export interface SettingMeta {
  key: string;
  value: string;
  type: string;
  label: string;
  category: string;
  options?: string;
}

