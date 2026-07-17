"use client";

import { useEffect, useState } from "react";
import TerminalQuadrant from "./components/TerminalQuadrant";
import TerminalLogs from "./components/TerminalLogs";

export default function TerminalPage() {
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    fetch("http://127.0.0.1:8002/api/status")
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => {});
  }, []);

  return (
    <div className="p-2 space-y-2">
      <div className="grid grid-cols-2 gap-2 min-h-[800px]" style={{ gridTemplateRows: "1fr 1fr" }}>
        <TerminalQuadrant instrument="CE" slot={1} initialPos={status?.positions?.CE?.trade1} />
        <TerminalQuadrant instrument="PE" slot={1} initialPos={status?.positions?.PE?.trade1} />
        <TerminalQuadrant instrument="CE" slot={2} initialPos={status?.positions?.CE?.trade2} />
        <TerminalQuadrant instrument="PE" slot={2} initialPos={status?.positions?.PE?.trade2} />
      </div>
      <TerminalLogs />
    </div>
  );
}
