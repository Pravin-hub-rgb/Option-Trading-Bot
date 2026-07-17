import type { Metadata } from "next";
import "./globals.css";
import AppHeader from "./components/AppHeader";

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
      <body className="min-h-screen flex flex-col bg-[#0a0a0a] text-[#e5e7eb]">
        <AppHeader />
        <main className="flex-1 p-0 overflow-y-auto">{children}</main>
      </body>
    </html>
  );
}