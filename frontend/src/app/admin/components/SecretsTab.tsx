"use client";

import { useState } from "react";
import { KeyRound, CheckCircle2, AlertCircle } from "lucide-react";
import type { AdminConfig } from "@/types/admin";

interface SecretsTabProps {
  config: AdminConfig["secrets"];
  backendUrl: string;
  onSaved: () => void;
}

export default function SecretsTab({ config, backendUrl, onSaved }: SecretsTabProps) {
  const [provider, setProvider] = useState<"local" | "infisical" | "doppler">(
    config.active_provider || "local"
  );
  const [infisicalProjectId, setInfisicalProjectId] = useState(config.infisical_project_id || "");
  const [infisicalEnv, setInfisicalEnv] = useState(config.infisical_env || "dev");
  const [dopplerProject, setDopplerProject] = useState(config.doppler_project || "");
  const [dopplerConfig, setDopplerConfig] = useState(config.doppler_config || "dev");

  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMessage(null);
    try {
      const res = await fetch(`${backendUrl}/admin/config/secrets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: provider,
          infisical_project_id: infisicalProjectId.trim() || undefined,
          infisical_env: infisicalEnv.trim() || undefined,
          doppler_project: dopplerProject.trim() || undefined,
          doppler_config: dopplerConfig.trim() || undefined,
        }),
      });
      if (!res.ok) throw new Error("Failed to configure secret manager");
      setStatusMessage({ text: `Secret management provider updated: ${provider}` });
      onSaved();
    } catch (e) {
      setStatusMessage({
        text: e instanceof Error ? e.message : "Error saving secret provider",
        error: true,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="border-b border-app-border pb-4">
        <h2 className="text-base font-semibold text-app-text flex items-center gap-2">
          <KeyRound size={18} className="text-blue-500" />
          Secret Providers & Vaults
        </h2>
        <p className="text-xs text-app-text-muted mt-1">
          Decouple secrets from flat files by syncing credentials through enterprise secret vaults (Infisical, Doppler) or local env files.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-5">
        <div className="space-y-2">
          <label className="text-xs font-medium text-app-text">Active Secret Provider</label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <button
              type="button"
              onClick={() => setProvider("local")}
              className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                provider === "local"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">Local .env</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">Read & write from local filesystem</div>
            </button>

            <button
              type="button"
              onClick={() => setProvider("infisical")}
              className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                provider === "infisical"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">Infisical CLI</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">Inject secrets via `infisical run`</div>
            </button>

            <button
              type="button"
              onClick={() => setProvider("doppler")}
              className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                provider === "doppler"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">Doppler CLI</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">Inject secrets via `doppler run`</div>
            </button>
          </div>
        </div>

        {provider === "infisical" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-app-text">Infisical Project ID</label>
              <input
                type="text"
                value={infisicalProjectId}
                onChange={(e) => setInfisicalProjectId(e.target.value)}
                placeholder="e.g. 64b8..."
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-app-text">Infisical Environment</label>
              <input
                type="text"
                value={infisicalEnv}
                onChange={(e) => setInfisicalEnv(e.target.value)}
                placeholder="dev, staging, prod"
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>
        )}

        {provider === "doppler" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-app-text">Doppler Project Name</label>
              <input
                type="text"
                value={dopplerProject}
                onChange={(e) => setDopplerProject(e.target.value)}
                placeholder="e.g. notbooklm-core"
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-app-text">Doppler Config</label>
              <input
                type="text"
                value={dopplerConfig}
                onChange={(e) => setDopplerConfig(e.target.value)}
                placeholder="dev, stg, prd"
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>
        )}

        {statusMessage && (
          <div
            className={`p-3 rounded-lg border text-xs flex items-center gap-2 ${
              statusMessage.error
                ? "bg-rose-500/10 border-rose-500/20 text-rose-400"
                : "bg-blue-500/10 border-blue-500/20 text-blue-400"
            }`}
          >
            {statusMessage.error ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
            <span>{statusMessage.text}</span>
          </div>
        )}

        <div className="flex justify-end pt-4 border-t border-app-border">
          <button
            type="submit"
            disabled={isSaving}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? "Saving..." : "Save Secret Configuration"}
          </button>
        </div>
      </form>
    </div>
  );
}
