"use client";

import { useEffect, useState } from "react";
import { fetchStatus } from "../lib/api";
import type { BotStatus } from "../lib/types";
import PositionCard from "../components/PositionCard";
import TerminalLogs from "../components/TerminalLogs";

export default function PositionsPage() {
  const [status, setStatus] = useState<BotStatus | null>(null);

  useEffect(() => {
    const load = () => fetchStatus().then(setStatus).catch(() => {});
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  const pos = status?.positions;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Position Management</h1>
        <span className={`text-xs font-bold uppercase tracking-widest ${status?.running ? "text-[#10b981]" : "text-[#64748b]"}`}>
          {status?.running ? "● Bot Running" : "○ Bot Stopped"}
        </span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PositionCard instrument="CE" slot={1} position={pos?.CE?.trade1 ?? null} />
        <PositionCard instrument="PE" slot={1} position={pos?.PE?.trade1 ?? null} />
      </div>
      <TerminalLogs />
    </div>
  );
}