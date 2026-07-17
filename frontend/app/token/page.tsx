"use client";

import { useState, useEffect, useCallback } from "react";
import { Icon } from "@iconify/react";
import { checkTokenStatus, checkToken, validateToken } from "../lib/api";

type TokenStatus = "unknown" | "valid" | "invalid";

export default function TokenPage() {
  const [status, setStatus] = useState<TokenStatus>("unknown");
  const [accessToken, setAccessToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [validating, setValidating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [result, setResult] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const s = await checkTokenStatus();
      if (!s.exists) { setStatus("unknown"); return; }
      const c = await checkToken();
      setStatus(c.valid ? "valid" : "invalid");
    } catch { setStatus("unknown"); }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchStatus();
    setRefreshing(false);
  };

  const handleValidate = async () => {
    if (!accessToken.trim()) return;
    setValidating(true);
    setResult("");
    try {
      const d = await validateToken(accessToken.trim());
      setResult(d.message || JSON.stringify(d, null, 2));
      if (d.valid) { setStatus("valid"); setShowForm(false); }
      else setStatus("invalid");
    } catch {
      setResult("Network error — could not reach server");
    }
    setValidating(false);
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-2">
          <Icon icon="lucide:key-round" className="text-[#9333ea] text-xl" />
          <h1 className="text-lg font-semibold text-[#f1f5f9]">Token Management</h1>
          {status === "valid" && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#d1fae5] text-[#065f46]">
              WORKING
            </span>
          )}
        </div>
        <p className="text-sm text-[#64748b] mb-5">
          Validate and update your Upstox access token. Required before live trading.
        </p>

        <div className="border border-indigo-500/30 rounded-lg p-5 bg-black/30">
          <div className="flex items-center gap-3 mb-3">
            <Icon icon="lucide:key-round" className="text-[#9333ea] text-lg" />
            <span className="text-sm font-semibold text-[#9333ea]">Access Token</span>
            {status === "valid" && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#d1fae5] text-[#065f46]">
                WORKING
              </span>
            )}
          </div>

          {status === "valid" && (
            <p className="text-sm text-[#10b981] font-medium mb-2">Token is working correctly</p>
          )}
          {status === "unknown" && (
            <p className="text-sm text-[#6b7280] mb-2">No token configured</p>
          )}
          {status === "invalid" && (
            <p className="text-sm text-[#ef4444] mb-2">Token is invalid or expired</p>
          )}

          {showForm && (
            <div className="mt-3 space-y-3">
              <p className="text-xs text-[#6b7280]">Enter new Upstox access token:</p>
              <div className="relative">
                <Icon icon="lucide:key-round" className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9333ea] text-sm" />
                <input
                  type={showToken ? "text" : "password"}
                  value={accessToken}
                  onChange={(e) => setAccessToken(e.target.value)}
                  placeholder="Paste your new access token here"
                  className="w-full bg-[#0d0d0d] border border-white/10 rounded-lg pl-9 pr-10 py-2 text-sm text-white placeholder-[#4b5563] focus:outline-none focus:border-[#9333ea] transition-colors"
                />
                <button
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748b] hover:text-[#e5e7eb]"
                >
                  <Icon icon={showToken ? "lucide:eye-off" : "lucide:eye"} className="text-sm" />
                </button>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleValidate}
                  disabled={validating || !accessToken.trim()}
                  className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold rounded-lg bg-gradient-to-r from-[#9333ea] to-[#7c3aed] hover:from-[#7c3aed] hover:to-[#6d28d9] text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {validating ? (
                    <>
                      <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Validating...
                    </>
                  ) : (
                    <>
                      <Icon icon="lucide:check-circle" className="text-sm" />
                      Validate & Update
                    </>
                  )}
                </button>
                <button
                  onClick={() => { setShowForm(false); setAccessToken(""); }}
                  className="px-4 py-1.5 text-xs text-[#6b7280] border border-[#666] rounded-lg hover:text-white hover:border-[#9333ea] transition-all"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {!showForm && (
            <div className="flex gap-2 mt-3">
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#6b7280] border border-white/20 rounded-lg hover:text-white hover:border-[#10b981] transition-all disabled:opacity-50"
              >
                {refreshing ? (
                  <>
                    <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    Refreshing...
                  </>
                ) : (
                  <>
                    <Icon icon="lucide:refresh-cw" className="text-xs" />
                    Refresh Status
                  </>
                )}
              </button>
              <button
                onClick={() => setShowForm(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#6b7280] border border-white/20 rounded-lg hover:text-white hover:border-[#9333ea] transition-all"
              >
                <Icon icon="lucide:edit" className="text-xs" />
                Update Token
              </button>
            </div>
          )}
        </div>

        {result && (
          <div className="mt-4 p-3 bg-[#0d0d0d] border border-[#333] rounded-lg font-mono text-xs text-[#e0e0e0] whitespace-pre-wrap">
            <p className="text-xs font-semibold text-[#94a3b8] mb-1">Token Validation Results:</p>
            {result}
          </div>
        )}

        <div className="mt-4 flex items-start gap-2 p-3 bg-blue-500/5 border border-blue-500/20 rounded-lg">
          <Icon icon="lucide:info" className="text-blue-500 text-sm mt-0.5 shrink-0" />
          <p className="text-xs text-[#64748b]">
            <strong className="text-blue-400">Note:</strong> Tests Upstox API connectivity with 3 symbols (RELIANCE, TCS, HDFCBANK), saves valid token on success.
          </p>
        </div>
      </div>
    </div>
  );
}
