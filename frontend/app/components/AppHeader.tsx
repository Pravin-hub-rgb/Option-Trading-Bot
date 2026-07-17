"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { usePathname } from "next/navigation";
import { fetchStatus, startBot, stopBot, checkToken } from "../lib/api";
import type { BotStatus } from "../lib/types";
import TokenModal from "./TokenModal";

export default function AppHeader() {
  const pathname = usePathname();
  const [s, setS] = useState<BotStatus | null>(null);
  const [time, setTime] = useState("");
  const [busy, setBusy] = useState(false);
  const [tokenModal, setTokenModal] = useState<{ open: boolean; message: string }>({ open: false, message: "" });

  useEffect(() => {
    const load = () => fetchStatus().then(setS).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString("en-IN", { hour12: false }));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  const running = s?.running ?? false;
  const connecting = s === null;

  const handleStart = async () => {
    setBusy(true);
    try {
      const tokenRes = await checkToken();
      if (!tokenRes.valid) {
        setTokenModal({ open: true, message: tokenRes.message });
        setBusy(false);
        return;
      }
      const res = await startBot();
      if (res.status === "error") {
        setTokenModal({ open: true, message: res.message });
      }
    } catch {
      setTokenModal({ open: true, message: "Could not connect to backend server." });
    }
    setBusy(false);
  };

  const handleStop = async () => {
    setBusy(true);
    try {
      await stopBot();
    } catch {
      // ignore
    }
    setBusy(false);
  };

  const strikes = s?.strikes || {};
  const pos = s?.positions;
  const ceStrike = (Object.values(strikes)[0] as string) || "--";
  const peStrike = (Object.values(strikes)[1] as string) || "--";
  const netPnl =
    (pos?.CE?.trade1?.pnl ?? 0) +
    (pos?.CE?.trade2?.pnl ?? 0) +
    (pos?.PE?.trade1?.pnl ?? 0) +
    (pos?.PE?.trade2?.pnl ?? 0);
  const connected = s?.connected ?? true;
  const isProfit = netPnl >= 0;

  const tabs = [
    { href: "/", label: "Terminal", icon: "lucide:terminal" },
    { href: "/positions", label: "Positions", icon: "lucide:layout-dashboard" },
    { href: "/analytics", label: "Strategy", icon: "lucide:bar-chart-3" },
    { href: "/history", label: "History", icon: "lucide:clock" },
    { href: "/token", label: "Token", icon: "lucide:key-round" },
    { href: "/settings", label: "Settings", icon: "lucide:settings" },
  ];

  return (
    <>
      <header className="main-nav">
        <div className="flex items-center justify-between bg-[#111] border border-white/10 rounded-xl px-6 py-3 shadow-2xl mx-4 mt-4">
          <div className="flex items-center gap-6">
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">Strategy Control</span>
              <button className="flex items-center gap-2 bg-black/40 border border-white/5 px-4 py-1.5 rounded-lg hover:border-indigo-500/50 transition-all text-sm font-medium">
                Red Candle High Break
                <Icon icon="lucide:chevron-down" className="text-xs opacity-50" />
              </button>
            </div>
            <div className="h-8 w-px bg-white/5" />
            <div className="flex items-center gap-6">
              <div className="flex flex-col">
                <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">Connection</span>
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <span className={`flex h-2 w-2 rounded-full ${connected ? "bg-blue-500 pulse-dot" : "bg-red-500"}`} />
                  <span className={connected ? "text-blue-500" : "text-red-500"}>{connected ? "DATA" : "OFFLINE"}</span>
                </div>
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">Bot</span>
                <div className="flex items-center gap-1.5 text-sm font-semibold">
                  <span className={`flex h-2 w-2 rounded-full ${running ? "bg-[#10b981] pulse-dot" : "bg-[#64748b]"}`} />
                  <span className={running ? "text-[#10b981]" : "text-[#64748b]"}>
                    {running ? (s?.mode === "starting" ? "STARTING" : "RUNNING") : "STOPPED"}
                  </span>
                </div>
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">CE Strike</span>
                <span className="font-['JetBrains_Mono',monospace] text-sm font-bold text-indigo-400">{ceStrike}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">PE Strike</span>
                <span className="font-['JetBrains_Mono',monospace] text-sm font-bold text-amber-400">{peStrike}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <button
              onClick={running ? handleStop : handleStart}
              disabled={busy || connecting}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-all ${
                running
                  ? "bg-red-600/20 text-red-400 border border-red-600/30 hover:bg-red-600/30"
                  : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20"
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {connecting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  Checking...
                </>
              ) : busy ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  {running ? "Stopping..." : "Starting..."}
                </>
              ) : running ? (
                <>
                  <Icon icon="lucide:square" className="text-xs" />
                  Stop Bot
                </>
              ) : (
                <>
                  <Icon icon="lucide:play" className="text-xs" />
                  Start Bot
                </>
              )}
            </button>
            <div className="h-8 w-px bg-white/5" />
            <div className="flex flex-col items-end">
              <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">Account Net P&L</span>
              <span
                className={`font-['JetBrains_Mono',monospace] text-xl font-bold tracking-tighter ${
                  isProfit ? "text-[#10b981]" : "text-[#ef4444]"
                }`}
              >
                {`${isProfit ? "+" : ""}₹${netPnl.toFixed(2)}`}
              </span>
            </div>
            <div className="flex flex-col items-end">
              <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">Time</span>
              <span className="font-['JetBrains_Mono',monospace] text-sm font-bold tracking-tighter text-gray-300">
                {time || "--"}
              </span>
            </div>
          </div>
        </div>
        <nav className="flex items-center gap-1 px-8 py-3">
          {tabs.map((tab) => {
            const active = pathname === tab.href;
            return (
              <a
                key={tab.href}
                href={tab.href}
                className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm transition-all ${
                  active
                    ? "bg-indigo-500/10 text-indigo-400 font-semibold"
                    : "text-gray-500 hover:text-gray-300 hover:bg-white/[0.04]"
                }`}
              >
                <Icon icon={tab.icon} className="text-sm" />
                <span>{tab.label}</span>
              </a>
            );
          })}
        </nav>
      </header>

      <TokenModal
        open={tokenModal.open}
        message={tokenModal.message}
        onClose={() => setTokenModal({ open: false, message: "" })}
      />
    </>
  );
}
