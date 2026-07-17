"use client";

import TerminalQuadrant from "./components/TerminalQuadrant";
import TerminalLogs from "./components/TerminalLogs";

export default function TerminalPage() {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 auto-rows-fr">
        <TerminalQuadrant instrument="CE" slot={1} />
        <TerminalQuadrant instrument="PE" slot={1} />
        <TerminalQuadrant instrument="CE" slot={2} dim />
        <TerminalQuadrant instrument="PE" slot={2} dim />
      </div>
      <TerminalLogs />
    </div>
  );
}
