import type { BotStatus, TradeEntry, DayPnl, TradeStats, SettingMeta } from "./types";

const API = "http://localhost:8002";

export async function fetchStatus(): Promise<BotStatus> {
  const res = await fetch(`${API}/api/status`);
  return res.json();
}

export async function startBot(instruments?: string[]): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API}/api/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(instruments ? { instruments } : {}),
  });
  return res.json();
}

export async function stopBot(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API}/api/stop`, { method: "POST" });
  return res.json();
}

export async function fetchTrades(year?: number): Promise<{ trades: TradeEntry[]; count: number }> {
  const params = year ? `?year=${year}` : "";
  const res = await fetch(`${API}/api/trades${params}`);
  return res.json();
}

export async function fetchTradePnl(year?: number): Promise<{ days: DayPnl[] }> {
  const params = year ? `?year=${year}` : "";
  const res = await fetch(`${API}/api/trades/pnl${params}`);
  return res.json();
}

export async function fetchTradeStats(): Promise<TradeStats> {
  const res = await fetch(`${API}/api/trades/stats`);
  return res.json();
}

export async function fetchSettings(): Promise<{ settings: SettingMeta[] }> {
  const res = await fetch(`${API}/api/settings`);
  return res.json();
}

export async function updateSetting(key: string, value: string): Promise<{ status: string }> {
  const res = await fetch(`${API}/api/settings/${key}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  return res.json();
}

export async function resetSettings(): Promise<{ status: string }> {
  const res = await fetch(`${API}/api/settings/reset`, { method: "POST" });
  return res.json();
}
