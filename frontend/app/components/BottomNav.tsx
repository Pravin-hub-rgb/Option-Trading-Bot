"use client";

import { Icon } from "@iconify/react";
import { usePathname } from "next/navigation";

export default function BottomNav() {
  const pathname = usePathname();

  const items = [
    { href: "/", label: "Terminal", icon: "lucide:layout-grid" },
    { href: "/history", label: "History", icon: "lucide:history" },
    { href: "/mfe", label: "MFE Report", icon: "lucide:activity" },
    { href: "/settings", label: "Settings", icon: "lucide:settings-2" },
  ];

  return (
    <nav className="fixed bottom-8 left-1/2 -translate-x-1/2 z-40 bg-[#111] border border-white/10 px-6 py-3 rounded-2xl flex items-center gap-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <a
            key={item.href}
            href={item.href}
            className="flex flex-col items-center gap-1 group"
          >
            <Icon
              icon={item.icon}
              className={`transition-colors ${active ? "text-indigo-400" : "text-gray-400 group-hover:text-indigo-400"}`}
            />
            <span
              className={`text-[9px] uppercase font-bold transition-colors ${active ? "text-white" : "text-gray-400 group-hover:text-white"}`}
            >
              {item.label}
            </span>
          </a>
        );
      })}
    </nav>
  );
}