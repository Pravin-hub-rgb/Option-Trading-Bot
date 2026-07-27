"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { usePathname } from "next/navigation";
import { fetchStatus, startBot, stopBot, checkToken } from "../lib/api";
import type { BotStatus } from "../lib/types";
import TokenModal from "./TokenModal";
import { useMaximize } from "../MaximizeContext";

export default function AppHeader() {
  const pathname = usePathname();
  const [s, setS] = useState<BotStatus | null>(null);
  const [time, setTime] = useState("");
  const [busy, setBusy] = useState(false);
  const [tokenModal, setTokenModal] = useState<{ open: boolean; message: string }>({ open: false, message: "" });
  const { toggle } = useMaximize();

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
  const ceStrike = strikes.CE || "--";
  const peStrike = strikes.PE || "--";
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
        <div className="flex items-center justify-between bg-[#111] border border-white/10 rounded-xl px-4 py-1.5 shadow-2xl mx-4 mt-4">
          <div className="flex items-center gap-4">
            <div className="flex flex-col">
              <span className="text-[9px] uppercase tracking-widest text-white/70 font-bold">Strategy</span>
              <button className="flex items-center gap-1 bg-indigo-500/10 border border-indigo-500/30 px-2 py-0.5 rounded hover:bg-indigo-500/20 hover:border-indigo-500/50 transition-all text-xs font-medium text-indigo-300 whitespace-nowrap">
                Red C...
                <Icon icon="lucide:chevron-down" className="text-[10px]" />
              </button>
            </div>
            <div className="h-6 w-px bg-white/10" />
            <div className="flex flex-col items-center">
              <span className="text-[9px] uppercase tracking-widest text-white/70 font-bold">Live</span>
              <span className={`flex h-2 w-2 rounded-full ${connected ? "bg-blue-500 pulse-dot" : "bg-red-500"}`} />
            </div>
            <div className="flex flex-col">
              <span className="text-[9px] uppercase tracking-widest text-white/70 font-bold">Bot</span>
              <span className={`flex items-center gap-1 text-xs font-semibold ${running ? "text-[#10b981]" : "text-[#64748b]"}`}>
                <span className={`flex h-1.5 w-1.5 rounded-full ${running ? "bg-[#10b981] pulse-dot" : "bg-[#64748b]"}`} />
                {running ? "ON" : "OFF"}
              </span>
            </div>
            <div className="h-6 w-px bg-white/10" />
            <div className="flex items-center gap-3">
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-widest text-white/70 font-bold">CE</span>
                <span className="font-['JetBrains_Mono',monospace] text-xs font-bold text-indigo-400">{ceStrike}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-[9px] uppercase tracking-widest text-white/70 font-bold">PE</span>
                <span className="font-['JetBrains_Mono',monospace] text-xs font-bold text-amber-400">{peStrike}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={running ? handleStop : handleStart}
              disabled={busy || connecting}
              suppressHydrationWarning
              className={`flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
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
            <div className="h-6 w-px bg-white/10" />
            <div className="flex flex-col items-end">
              <span className="text-[9px] uppercase tracking-widest text-white/70 font-bold">P&L</span>
              <span
                className={`font-['JetBrains_Mono',monospace] text-sm font-bold tracking-tighter ${
                  isProfit ? "text-[#10b981]" : "text-[#ef4444]"
                }`}
              >
                {`${isProfit ? "+" : ""}${netPnl.toFixed(2)}`}
              </span>
            </div>
            <div className="flex flex-col items-end">
              <span className="font-['JetBrains_Mono',monospace] text-[10px] font-bold text-white/70 leading-none">
                {time || "--"}
              </span>
            </div>
          </div>
        </div>
        <nav className="flex items-center gap-1 px-8 py-2">
          {tabs.map((tab) => {
            const active = pathname === tab.href;
            return (
              <a
                key={tab.href}
                href={tab.href}
                className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm transition-all ${
                  active
                    ? "bg-indigo-500/10 text-indigo-400 font-semibold"
                    : "text-gray-400 hover:text-gray-300 hover:bg-white/[0.04]"
                }`}
              >
                <Icon icon={tab.icon} className="text-sm" />
                <span>{tab.label}</span>
              </a>
            );
          })}
          <div className="flex-1" />
          <button
            onClick={toggle}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-white/[0.04] transition-all"
            title="Maximize"
          >
            <Icon icon="lucide:maximize-2" className="text-sm" />
          </button>
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
