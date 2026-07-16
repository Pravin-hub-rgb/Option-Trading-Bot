"use client";

import { useEffect, useRef, useState } from "react";

interface Log {
  type: string;
  timestamp: string;
  message: string;
}

export default function TerminalLogs() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource("http://localhost:8002/api/logs/stream");

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

  const logColor = (msg: string) => {
    if (msg.includes("EXIT")) return "#ef4444";
    if (msg.includes("ENTRY")) return "#10b981";
    if (msg.includes("SL moved")) return "#facc15";
    if (msg.includes("Error") || msg.includes("❌")) return "#ef4444";
    return "#64748b";
  };

  if (collapsed) {
    return (
      <button
        className="fixed bottom-0 left-0 right-0 bg-[#111] border-t border-[rgba(255,255,255,0.06)] px-4 py-1 text-xs text-[#64748b]"
        onClick={() => setCollapsed(false)}
      >
        Logs ({logs.length}) ▲
      </button>
    );
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 h-40 bg-[#0d0d0d] border-t border-[rgba(255,255,255,0.06)] flex flex-col">
      <div className="flex items-center justify-between px-4 py-1 border-b border-[rgba(255,255,255,0.04)]">
        <span className="text-xs text-[#64748b]">Terminal Logs ({logs.length})</span>
        <button className="text-xs text-[#64748b] hover:text-[#e5e7eb]" onClick={() => setCollapsed(true)}>
          ▼ Minimize
        </button>
      </div>
      <div className="flex-1 overflow-auto px-4 py-2 text-[11px] font-mono">
        {logs.map((log, i) => (
          <div key={i} style={{ color: logColor(log.message) }}>
            <span className="text-[#64748b]">[{log.timestamp}]</span> {log.message}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
