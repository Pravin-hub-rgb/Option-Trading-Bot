import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Options Trading Bot",
  description: "NIFTY Options Trading Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="h-full flex flex-col bg-[#0a0a0a] text-[#e5e7eb]">
        <Navbar />
        <StatusBar />
        <main className="flex-1 overflow-auto p-4">{children}</main>
      </body>
    </html>
  );
}

function Navbar() {
  return (
    <nav className="flex items-center gap-1 px-4 py-2 bg-[#111] border-b border-[rgba(255,255,255,0.06)]">
      <Tab href="/" label="Terminal" icon="▣" />
      <Tab href="/analytics" label="Analytics" icon="📊" />
      <Tab href="/history" label="History" icon="📋" />
      <Tab href="/settings" label="Settings" icon="⚙" />
    </nav>
  );
}

function Tab({ href, label, icon }: { href: string; label: string; icon: string }) {
  return (
    <a
      href={href}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-[#64748b] hover:text-[#e5e7eb] hover:bg-[rgba(255,255,255,0.06)] transition-colors"
    >
      <span>{icon}</span>
      <span>{label}</span>
    </a>
  );
}

function StatusBar() {
  return (
    <div className="flex items-center gap-3 px-4 py-1.5 bg-[#0d0d0d] border-b border-[rgba(255,255,255,0.04)] text-xs text-[#64748b]">
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-[#10b981]" />
        API
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-[#64748b]" />
        WS
      </span>
      <span className="text-[#64748b]">|</span>
      <span id="status-strikes">Strikes: --</span>
      <span className="text-[#64748b]">|</span>
      <span id="status-pnl">P&L: --</span>
      <span className="ml-auto" id="status-clock">
        {new Date().toLocaleTimeString("en-IN", { hour12: false })}
      </span>
    </div>
  );
}
