"use client";

import TerminalQuadrant from "./components/TerminalQuadrant";
import TerminalLogs from "./components/TerminalLogs";

export default function TerminalPage() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 grid grid-cols-2 gap-3 auto-rows-fr">
        <TerminalQuadrant instrument="CE" slot={1} />
        <TerminalQuadrant instrument="PE" slot={1} />
        <TerminalQuadrant instrument="CE" slot={2} dim />
        <TerminalQuadrant instrument="PE" slot={2} dim />
      </div>
      <TerminalLogs />
    </div>
  );
}
