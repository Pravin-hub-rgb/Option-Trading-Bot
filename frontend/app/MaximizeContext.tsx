"use client";
import { createContext, useContext, useState, ReactNode } from "react";

const MaximizeCtx = createContext<{
  maximized: boolean;
  toggle: () => void;
}>({ maximized: false, toggle: () => {} });

export function MaximizeProvider({ children }: { children: ReactNode }) {
  const [maximized, setMaximized] = useState(false);
  return (
    <MaximizeCtx.Provider value={{ maximized, toggle: () => setMaximized(m => !m) }}>
      {children}
    </MaximizeCtx.Provider>
  );
}

export const useMaximize = () => useContext(MaximizeCtx);
