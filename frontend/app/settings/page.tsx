"use client";

import { useEffect, useState } from "react";
import { fetchSettings } from "../lib/api";
import SettingsAccordion from "../components/SettingsAccordion";
import type { SettingMeta } from "../lib/types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingMeta[]>([]);

  function load() {
    fetchSettings().then((res) => setSettings(res.settings));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold">Settings</h1>
      <SettingsAccordion settings={settings} onRefresh={load} />
    </div>
  );
}
