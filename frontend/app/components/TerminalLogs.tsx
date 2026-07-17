"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@iconify/react";

interface Log {
  type: string;
  timestamp: string;
  message: string;
}

export default function TerminalLogs() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [isOpen, setIsOpen] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource("http://127.0.0.1:8002/api/logs/stream");

    es.onmessage = (event) => {
      try {
        const log: Log = JSON.parse(event.data);
        setLogs((prev) => [...prev.slice(-200), log]);
      } catch {
        // ignore
      }
    };

    return () => es.close();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  function detectType(msg: string): { label: string; color: string } {
    if (msg.includes("ENTRY") || msg.includes("EXIT") || msg.includes("Order")) return { label: "EXECUTION", color: "#10b981" };
    if (msg.includes("SL") || msg.includes("Trailing") || msg.includes("Stop Loss")) return { label: "RISK", color: "#f59e0b" };
    if (msg.includes("Error") || msg.includes("❌") || msg.includes("failed")) return { label: "SYSTEM", color: "#3b82f6" };
    if (msg.includes("Strategy") || msg.includes("candle") || msg.includes("breakout")) return { label: "STRATEGY", color: "#6366f1" };
    return { label: "SYSTEM", color: "#3b82f6" };
  }

  return (
    <footer className="bg-[#111] border border-white/5 rounded-xl overflow-hidden shadow-2xl">
      <div
        className="flex items-center justify-between px-4 py-2 bg-white/[0.03] border-b border-white/5 cursor-pointer hover:bg-white/[0.05] transition-all"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-gray-400">
          <Icon icon="lucide:terminal" className="text-indigo-400" />
          Terminal Logs
          <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded font-mono ml-1">v1.2.4</span>
        </div>
        <Icon
          icon="lucide:chevron-down"
          className="text-gray-500 transition-transform duration-200"
          style={{ transform: isOpen ? "rotate(0deg)" : "rotate(-90deg)" }}
        />
      </div>
      {isOpen && (
        <div className="max-h-32 overflow-y-auto p-3 font-mono text-[11px] leading-relaxed custom-scrollbar">
          {logs.length === 0 && (
            <div className="text-gray-600 text-center py-2">Waiting for logs...</div>
          )}
          {logs.map((log, i) => {
            const { label, color } = detectType(log.message);
            const alt = i % 2 === 1;
            return (
              <div key={i} className={`flex gap-3 py-1 px-2 ${alt ? "bg-white/[0.02]" : ""} ${i < logs.length - 3 ? "opacity-60" : "opacity-90"}`}>
                <span className="text-gray-600 shrink-0">[{log.timestamp}]</span>
                <span className="font-bold shrink-0" style={{ color }}>{label}:</span>
                <span style={{ color: log.message.includes("❌") ? "#ef4444" : "#e5e7eb" }}>{log.message}</span>
              </div>
            );
          })}
          <div ref={endRef} />
        </div>
      )}
    </footer>
  );
}