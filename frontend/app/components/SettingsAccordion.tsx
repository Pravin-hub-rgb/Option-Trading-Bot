"use client";

import { useState } from "react";
import type { SettingMeta } from "../lib/types";
import { updateSetting, resetSettings } from "../lib/api";

interface Props {
  settings: SettingMeta[];
  onRefresh: () => void;
}

const categoryLabels: Record<string, string> = {
  timing: "Timing",
  strategy: "Strategy",
  risk: "Risk Management",
  limits: "Trade Limits",
  logging: "Logging",
};

export default function SettingsAccordion({ settings, onRefresh }: Props) {
  const categories = [...new Set(settings.map((s) => s.category))];
  const [openCat, setOpenCat] = useState<string | null>(categories[0] || null);
  const [dirty, setDirty] = useState(false);

  async function handleChange(key: string, value: string) {
    await updateSetting(key, value);
    setDirty(true);
  }

  async function handleReset() {
    await resetSettings();
    onRefresh();
  }

  return (
    <div>
      {categories.map((cat) => (
        <div key={cat} className="mb-2 card">
          <button
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium"
            onClick={() => setOpenCat(openCat === cat ? null : cat)}
          >
            {categoryLabels[cat] || cat}
            <span className="text-[#64748b]">{openCat === cat ? "−" : "+"}</span>
          </button>

          {openCat === cat && (
            <div className="px-4 pb-4 space-y-3">
              {settings
                .filter((s) => s.category === cat)
                .map((s) => (
                  <div key={s.key}>
                    <label className="text-xs text-[#64748b] block mb-1">{s.label}</label>
                    {s.type === "boolean" ? (
                      <button
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          s.value === "true"
                            ? "bg-[#10b981] text-white"
                            : "bg-[#1a1a1a] text-[#64748b]"
                        }`}
                        onClick={() => handleChange(s.key, s.value === "true" ? "false" : "true")}
                      >
                        {s.value === "true" ? "ON" : "OFF"}
                      </button>
                    ) : s.type === "select" ? (
                      <select
                        className="input-dark text-xs"
                        value={s.value}
                        onChange={(e) => handleChange(s.key, e.target.value)}
                      >
                        {(s.options || "").split(",").map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    ) : s.type === "password" ? (
                      <input
                        type="password"
                        className="input-dark text-xs"
                        value={s.value}
                        onChange={(e) => handleChange(s.key, e.target.value)}
                        placeholder="Enter token..."
                      />
                    ) : (
                      <input
                        type={s.type === "number" ? "number" : "text"}
                        className="input-dark text-xs"
                        value={s.value}
                        onChange={(e) => handleChange(s.key, e.target.value)}
                      />
                    )}
                  </div>
                ))}
            </div>
          )}
        </div>
      ))}

      {dirty && (
        <div className="text-xs text-[#10b981] px-1 mb-2">Settings saved</div>
      )}

      <button
        className="text-xs text-[#64748b] hover:text-[#ef4444] transition-colors px-1"
        onClick={handleReset}
      >
        Reset to defaults
      </button>
    </div>
  );
}
