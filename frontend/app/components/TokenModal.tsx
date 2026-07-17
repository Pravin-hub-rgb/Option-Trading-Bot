"use client";

import { Icon } from "@iconify/react";
import { useRouter } from "next/navigation";

interface TokenModalProps {
  open: boolean;
  message: string;
  onClose: () => void;
}

export default function TokenModal({ open, message, onClose }: TokenModalProps) {
  const router = useRouter();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#111] border border-white/10 rounded-xl p-6 shadow-2xl max-w-md w-full mx-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
            <Icon icon="lucide:alert-triangle" className="text-red-500 text-lg" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-[#f1f5f9]">Token Required</h3>
            <p className="text-xs text-[#64748b]">Upstox API token issue</p>
          </div>
          <button onClick={onClose} className="ml-auto text-[#64748b] hover:text-[#e5e7eb] transition-colors">
            <Icon icon="lucide:x" width="18" />
          </button>
        </div>

        <p className="text-sm text-[#94a3b8] mb-6 leading-relaxed">{message}</p>

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-[#64748b] hover:text-[#e5e7eb] border border-white/5 rounded-lg hover:bg-white/[0.04] transition-all"
          >
            Cancel
          </button>
          <button
            onClick={() => { router.push("/token"); onClose(); }}
            className="px-4 py-2 text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all"
          >
            <Icon icon="lucide:key-round" className="inline mr-1.5 text-sm" />
            Update Token
          </button>
        </div>
      </div>
    </div>
  );
}
