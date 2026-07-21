"use client";

import { ReactNode } from "react";
import AppHeader from "./components/AppHeader";
import { MaximizeProvider, useMaximize } from "./MaximizeContext";

function LayoutInner({ children }: { children: ReactNode }) {
  const { maximized } = useMaximize();
  return (
    <body className="min-h-screen flex flex-col bg-[#0a0a0a] text-[#e5e7eb]">
      {!maximized && <AppHeader />}
      <main className="flex-1 p-0 overflow-y-auto">{children}</main>
    </body>
  );
}

export default function LayoutClient({ children }: { children: ReactNode }) {
  return (
    <MaximizeProvider>
      <LayoutInner>{children}</LayoutInner>
    </MaximizeProvider>
  );
}
