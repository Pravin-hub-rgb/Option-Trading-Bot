"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import TerminalQuadrant from "./components/TerminalQuadrant";
import TerminalLogs from "./components/TerminalLogs";
import { useMaximize } from "./MaximizeContext";

export default function TerminalPage() {
  const [status, setStatus] = useState<any>(null);
  const { maximized, toggle } = useMaximize();

  useEffect(() => {
    fetch("http://127.0.0.1:8002/api/status")
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => {});
  }, []);

  return (
    <div className={`relative ${maximized ? "h-screen flex flex-col" : "p-2 space-y-2"}`}>
      {maximized && (
        <button
          onClick={toggle}
          className="absolute top-1 right-1 z-20 opacity-60 hover:opacity-100 transition-opacity p-1.5 rounded-lg bg-white/10 backdrop-blur-sm text-white hover:text-white"
          title="Restore"
        >
          <Icon icon="lucide:minimize-2" className="text-sm" />
        </button>
      )}

      <div
        className={`grid grid-cols-2 gap-2 ${maximized ? "flex-1" : "min-h-[800px]"}`}
        style={{ gridTemplateRows: "1fr 1fr" }}
      >
        <TerminalQuadrant instrument="CE" slot={1} initialPos={status?.positions?.CE?.trade1} />
        <TerminalQuadrant instrument="PE" slot={1} initialPos={status?.positions?.PE?.trade1} />
        <TerminalQuadrant instrument="CE" slot={2} initialPos={status?.positions?.CE?.trade2} />
        <TerminalQuadrant instrument="PE" slot={2} initialPos={status?.positions?.PE?.trade2} />
      </div>

      {!maximized && <TerminalLogs />}
    </div>
  );
}
