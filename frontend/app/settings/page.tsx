"use client";

import { useEffect, useState } from "react";
import { Icon } from "@iconify/react";
import { fetchSettings } from "../lib/api";
import SettingsAccordion from "../components/SettingsAccordion";
import BottomNav from "../components/BottomNav";
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
    <div className="max-w-3xl mx-auto space-y-6 pb-24">
      <div className="flex items-center gap-2">
        <Icon icon="lucide:settings" className="text-indigo-400" />
        <h1 className="text-lg font-semibold">Strategy Settings</h1>
      </div>
      <SettingsAccordion settings={settings} onRefresh={load} />
      <BottomNav />
    </div>
  );
}