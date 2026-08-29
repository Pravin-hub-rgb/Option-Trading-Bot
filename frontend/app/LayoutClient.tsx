"use client";

import { ReactNode, useEffect } from "react";
import AppHeader from "./components/AppHeader";
import { MaximizeProvider, useMaximize } from "./MaximizeContext";

function useIgnoreChartRaces() {
  useEffect(() => {
    const IGNORED = /Object is disposed|Cannot update oldest data/;

    const onError = (e: ErrorEvent) => {
      if (e.message && IGNORED.test(e.message)) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    };

    const onRejection = (e: PromiseRejectionEvent) => {
      const msg = e.reason instanceof Error ? e.reason.message : String(e.reason);
      if (IGNORED.test(msg)) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    };

    window.addEventListener("error", onError, true);
    window.addEventListener("unhandledrejection", onRejection, true);
    return () => {
      window.removeEventListener("error", onError, true);
      window.removeEventListener("unhandledrejection", onRejection, true);
    };
  }, []);
}

function LayoutInner({ children }: { children: ReactNode }) {
  useIgnoreChartRaces();
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
