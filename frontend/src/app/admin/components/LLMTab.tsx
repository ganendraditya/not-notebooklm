"use client";

import { useState } from "react";
import { Cpu, CheckCircle2, AlertCircle, RefreshCw, Plus, Trash2, Server } from "lucide-react";
import type { AdminConfig, GatewayProfile, TestResult } from "@/types/admin";

interface LLMTabProps {
  config: AdminConfig["llm"];
  backendUrl: string;
  onSaved: () => void;
}

const PRESET_GATEWAYS = [
  { name: "9Router", url: "http://localhost:20128/v1" },
  { name: "DeepSeek", url: "https://api.deepseek.com/v1" },
  { name: "xAI Grok", url: "https://api.x.ai/v1" },
  { name: "Groq", url: "https://api.groq.com/openai/v1" },
  { name: "OpenRouter", url: "https://openrouter.ai/api/v1" },
  { name: "Ollama (Local)", url: "http://localhost:11434/v1" },
  { name: "OpenAI Official", url: "https://api.openai.com/v1" },
];

export default function LLMTab({ config, backendUrl, onSaved }: LLMTabProps) {
  // Profiles State
  const initialProfiles: GatewayProfile[] = config.profiles && config.profiles.length > 0
    ? config.profiles
    : [
        {
          id: "default",
          name: "Default Gateway",
          base_url: config.base_url || "http://localhost:20128/v1",
          api_key_masked: config.api_key_masked || "",
          has_api_key: config.has_api_key || false,
        },
      ];

  const [profiles, setProfiles] = useState<GatewayProfile[]>(initialProfiles);
  const [profileKeys, setProfileKeys] = useState<Record<string, string>>({});

  // Tier Bindings & Models
  const [primaryProfileId, setPrimaryProfileId] = useState(config.primary_profile_id || "default");
  const [fastProfileId, setFastProfileId] = useState(config.fast_profile_id || primaryProfileId);
  const [fallbackProfileId, setFallbackProfileId] = useState(config.fallback_profile_id || primaryProfileId);

  const [model, setModel] = useState(config.model || "gpt-4o");
  const [fastModel, setFastModel] = useState(config.fast_model || "");
  const [fallbackModel, setFallbackModel] = useState(config.fallback_model || "");
  const [temperature, setTemperature] = useState(config.temperature ?? 0.1);

  // Status & Testing States
  const [isSaving, setIsSaving] = useState(false);
  const [testingProfileId, setTestingProfileId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [statusMessage, setStatusMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const handleAddProfile = () => {
    const newId = `profile_${Date.now()}`;
    setProfiles((prev) => [
      ...prev,
      {
        id: newId,
        name: `Gateway ${prev.length + 1}`,
        base_url: "http://localhost:11434/v1",
        api_key_masked: "",
        has_api_key: false,
      },
    ]);
  };

  const handleRemoveProfile = (id: string) => {
    if (profiles.length <= 1) return;
    setProfiles((prev) => prev.filter((p) => p.id !== id));
    if (primaryProfileId === id) setPrimaryProfileId("default");
    if (fastProfileId === id) setFastProfileId("default");
    if (fallbackProfileId === id) setFallbackProfileId("default");
  };

  const handleUpdateProfileField = (id: string, field: "name" | "base_url", value: string) => {
    setProfiles((prev) =>
      prev.map((p) => (p.id === id ? { ...p, [field]: value } : p))
    );
  };

  const handleUpdateProfileKey = (id: string, key: string) => {
    setProfileKeys((prev) => ({ ...prev, [id]: key }));
  };

  const handleTestConnection = async (profile: GatewayProfile) => {
    setTestingProfileId(profile.id);
    setTestResults((prev) => {
      const next = { ...prev };
      delete next[profile.id];
      return next;
    });

    const keyToTest = profileKeys[profile.id]?.trim() || undefined;

    try {
      const res = await fetch(`${backendUrl}/admin/test/llm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: profile.base_url,
          api_key: keyToTest,
          model: model || "gpt-4o",
        }),
      });
      const data = await res.json();
      setTestResults((prev) => ({ ...prev, [profile.id]: data }));
    } catch (e) {
      setTestResults((prev) => ({
        ...prev,
        [profile.id]: {
          success: false,
          message: e instanceof Error ? e.message : "Failed to connect to backend",
        },
      }));
    } finally {
      setTestingProfileId(null);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMessage(null);
    try {
      const payloadProfiles = profiles.map((p) => ({
        id: p.id,
        name: p.name,
        base_url: p.base_url,
        api_key: profileKeys[p.id]?.trim() || undefined,
      }));

      // Find the primary profile for default fallback base_url & key
      const activePrimary = profiles.find((p) => p.id === primaryProfileId) || profiles[0];

      const res = await fetch(`${backendUrl}/admin/config/llm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: activePrimary.base_url,
          api_key: profileKeys[activePrimary.id]?.trim() || undefined,
          model: model,
          fast_model: fastModel.trim() || undefined,
          fallback_model: fallbackModel.trim() || undefined,
          temperature: Number(temperature),
          profiles: payloadProfiles,
          primary_profile_id: primaryProfileId,
          fast_profile_id: fastProfileId,
          fallback_profile_id: fallbackProfileId,
        }),
      });
      if (!res.ok) throw new Error("Failed to save LLM configuration");
      setStatusMessage({ text: "Universal gateway profiles and model bindings saved successfully." });
      setProfileKeys({});
      onSaved();
    } catch (e) {
      setStatusMessage({
        text: e instanceof Error ? e.message : "Error saving configuration",
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
          <Cpu size={18} className="text-blue-500" />
          Universal OpenAI-Compatible Gateway Vault
        </h2>
        <p className="text-xs text-app-text-muted mt-1">
          Configure arbitrary OpenAI-compatible endpoints (DeepSeek, Grok, 9Router, Ollama, Groq, vLLM) and route Primary, Fast, and Fallback models to separate keys and endpoints.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Section 1: Registered Gateway Profiles */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-app-text flex items-center gap-2">
              <Server size={14} className="text-purple-400" />
              Registered Gateway Profiles
            </label>
            <button
              type="button"
              onClick={handleAddProfile}
              className="px-2.5 py-1 text-xs font-medium rounded-lg border border-app-border hover:bg-app-item-hover text-app-text transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Plus size={13} />
              Add Gateway Profile
            </button>
          </div>

          <div className="space-y-3">
            {profiles.map((prof) => {
              const testResult = testResults[prof.id];
              const isTesting = testingProfileId === prof.id;

              return (
                <div
                  key={prof.id}
                  className="p-4 rounded-xl border border-app-border bg-app-card space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <input
                      type="text"
                      value={prof.name}
                      onChange={(e) => handleUpdateProfileField(prof.id, "name", e.target.value)}
                      placeholder="Profile Name (e.g. DeepSeek Official)"
                      required
                      className="text-xs font-semibold bg-transparent text-app-text border-b border-transparent hover:border-app-border focus:border-blue-500 focus:outline-none px-1 py-0.5"
                    />

                    {profiles.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveProfile(prof.id)}
                        className="p-1 rounded text-app-text-dim hover:text-rose-400 transition-colors cursor-pointer"
                        title="Delete Profile"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>

                  {/* Preset Helper Chips */}
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    <span className="text-[10px] text-app-text-dim py-0.5">Quick Presets:</span>
                    {PRESET_GATEWAYS.map((preset) => (
                      <button
                        key={preset.name}
                        type="button"
                        onClick={() => handleUpdateProfileField(prof.id, "base_url", preset.url)}
                        className="text-[10px] px-2 py-0.5 rounded bg-app-surface hover:bg-app-item-hover border border-app-border text-app-text-muted hover:text-app-text font-mono transition-colors cursor-pointer"
                      >
                        {preset.name}
                      </button>
                    ))}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-app-text-dim">Base URL (/v1)</label>
                      <input
                        type="text"
                        value={prof.base_url}
                        onChange={(e) => handleUpdateProfileField(prof.id, "base_url", e.target.value)}
                        placeholder="https://api.deepseek.com/v1"
                        required
                        className="w-full px-3 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <div className="flex justify-between items-center">
                        <label className="text-[11px] font-medium text-app-text-dim">API Key / Token</label>
                        {prof.has_api_key && (
                          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                            Configured: {prof.api_key_masked}
                          </span>
                        )}
                      </div>
                      <input
                        type="password"
                        value={profileKeys[prof.id] ?? ""}
                        onChange={(e) => handleUpdateProfileKey(prof.id, e.target.value)}
                        placeholder={prof.has_api_key ? "Leave blank to keep key" : "sk-..."}
                        className="w-full px-3 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
                      />
                    </div>
                  </div>

                  {/* Test Connection Button & Result */}
                  <div className="flex items-center justify-between pt-1">
                    <button
                      type="button"
                      onClick={() => handleTestConnection(prof)}
                      disabled={isTesting || (!profileKeys[prof.id] && !prof.has_api_key && !prof.base_url.includes("11434"))}
                      className="px-2.5 py-1 text-xs rounded border border-app-border hover:bg-app-item-hover text-app-text-muted hover:text-app-text flex items-center gap-1.5 cursor-pointer disabled:opacity-40 transition-colors"
                    >
                      <RefreshCw size={12} className={isTesting ? "animate-spin" : ""} />
                      {isTesting ? "Testing..." : `Test ${prof.name}`}
                    </button>

                    {testResult && (
                      <div
                        className={`text-[11px] flex items-center gap-1.5 ${
                          testResult.success ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {testResult.success ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
                        <span>
                          {testResult.message}
                          {testResult.latency_ms !== undefined && ` (${testResult.latency_ms}ms)`}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Section 2: Model & Profile Tier Routing */}
        <div className="space-y-4 pt-3 border-t border-app-border">
          <label className="text-xs font-semibold text-app-text">Tiered Model Routing</label>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Primary Tier */}
            <div className="p-3.5 rounded-xl border border-app-border bg-app-card space-y-2.5">
              <div className="text-xs font-semibold text-app-text">Primary Heavy Model</div>
              <div className="space-y-1">
                <label className="text-[11px] text-app-text-dim">Gateway Profile</label>
                <select
                  value={primaryProfileId}
                  onChange={(e) => setPrimaryProfileId(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 cursor-pointer"
                >
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-app-text-dim">Model Identifier</label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="deepseek-reasoner or gpt-4o"
                  required
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            {/* Fast Tier */}
            <div className="p-3.5 rounded-xl border border-app-border bg-app-card space-y-2.5">
              <div className="text-xs font-semibold text-app-text">Fast Micro-Model (Triage)</div>
              <div className="space-y-1">
                <label className="text-[11px] text-app-text-dim">Gateway Profile</label>
                <select
                  value={fastProfileId}
                  onChange={(e) => setFastProfileId(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 cursor-pointer"
                >
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-app-text-dim">Model Identifier</label>
                <input
                  type="text"
                  value={fastModel}
                  onChange={(e) => setFastModel(e.target.value)}
                  placeholder="llama3.2:3b or gpt-4o-mini"
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            {/* Fallback Tier */}
            <div className="p-3.5 rounded-xl border border-app-border bg-app-card space-y-2.5">
              <div className="text-xs font-semibold text-app-text">Fallback Model (Safety Net)</div>
              <div className="space-y-1">
                <label className="text-[11px] text-app-text-dim">Gateway Profile</label>
                <select
                  value={fallbackProfileId}
                  onChange={(e) => setFallbackProfileId(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 cursor-pointer"
                >
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-app-text-dim">Model Identifier</label>
                <input
                  type="text"
                  value={fallbackModel}
                  onChange={(e) => setFallbackModel(e.target.value)}
                  placeholder="e.g. grok-beta or gemini-1.5-flash"
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>
          </div>

          <div className="space-y-1 max-w-sm pt-2">
            <div className="flex justify-between items-center">
              <label className="text-xs font-medium text-app-text">Sampling Temperature</label>
              <span className="text-[11px] font-mono text-app-text-muted">{temperature}</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="1.0"
              step="0.05"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-app-border rounded-lg appearance-none cursor-pointer accent-blue-600"
            />
          </div>
        </div>

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
            {isSaving ? "Saving..." : "Save Gateway Profiles & Model Bindings"}
          </button>
        </div>
      </form>
    </div>
  );
}
