import type { BotStatus, TradeEntry, DayPnl, TradeStats, SettingMeta } from "./types";

const API = "http://127.0.0.1:8002";

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

export async function checkToken(): Promise<{ valid: boolean; message: string }> {
  const res = await fetch(`${API}/api/token/check`);
  return res.json();
}

export async function checkTokenStatus(): Promise<{ exists: boolean }> {
  const res = await fetch(`${API}/api/token/status`);
  return res.json();
}

export async function validateToken(token: string): Promise<{ valid: boolean; message: string; test_results?: string[] }> {
  const res = await fetch(`${API}/api/token/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
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

export async function deleteTrade(id: number): Promise<{ status: string }> {
  const res = await fetch(`${API}/api/trades/${id}`, { method: "DELETE" });
  return res.json();
}

export async function resetSettings(): Promise<{ status: string }> {
  const res = await fetch(`${API}/api/settings/reset`, { method: "POST" });
  return res.json();
}

export async function fetchTickHistory(instrument: string, slot: number): Promise<{ timestamp: string; ltp: number; sl: number | null; pnl: number | null }[]> {
  const res = await fetch(`${API}/api/ticks/${instrument}/${slot}`);
  const data = await res.json();
  return data.ticks || [];
}

export async function modifySl(instrument: string, slot: number, sl: number): Promise<{ status: string; sl: number }> {
  const res = await fetch(`${API}/api/position/${instrument}/${slot}/sl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sl }),
  });
  return res.json();
}
