"use client";

import { useState } from "react";
import { Cpu, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import type { AdminConfig, TestResult } from "@/types/admin";

interface LLMTabProps {
  config: AdminConfig["llm"];
  backendUrl: string;
  onSaved: () => void;
}

export default function LLMTab({ config, backendUrl, onSaved }: LLMTabProps) {
  const [baseUrl, setBaseUrl] = useState(config.base_url || "http://localhost:20128/v1");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(config.model || "gpt-4o");
  const [fastModel, setFastModel] = useState(config.fast_model || "");
  const [fallbackModel, setFallbackModel] = useState(config.fallback_model || "");
  const [temperature, setTemperature] = useState(config.temperature ?? 0.1);

  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${backendUrl}/admin/test/llm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: baseUrl,
          api_key: apiKey.trim() || undefined,
          model: model,
        }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e) {
      setTestResult({
        success: false,
        message: e instanceof Error ? e.message : "Failed to connect to backend",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMessage(null);
    try {
      const res = await fetch(`${backendUrl}/admin/config/llm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: baseUrl,
          api_key: apiKey.trim() || undefined,
          model: model,
          fast_model: fastModel.trim() || undefined,
          fallback_model: fallbackModel.trim() || undefined,
          temperature: Number(temperature),
        }),
      });
      if (!res.ok) throw new Error("Failed to save LLM configuration");
      setStatusMessage({ text: "LLM configuration saved. Active client cache refreshed." });
      setApiKey("");
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
          Model Gateways & BYOK
        </h2>
        <p className="text-xs text-app-text-muted mt-1">
          Configure OpenAI-compatible endpoints (9Router, OpenAI, OpenRouter, vLLM, or Ollama) with tiered model execution.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5 md:col-span-2">
            <label className="text-xs font-medium text-app-text">Gateway Base URL</label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://localhost:20128/v1"
              required
              className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
            />
            <p className="text-[11px] text-app-text-dim">
              Standard OpenAI-compatible endpoint route.
            </p>
          </div>

          <div className="space-y-1.5 md:col-span-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-app-text">API Key / Bearer Token</label>
              {config.has_api_key && (
                <span className="text-[11px] font-mono text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Configured: {config.api_key_masked}
                </span>
              )}
            </div>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={config.has_api_key ? "Leave blank to keep existing key" : "sk-..."}
              className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-app-text">Primary Heavy Model (Main Stage)</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="gpt-4o"
              required
              className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
            />
            <p className="text-[11px] text-app-text-dim">
              Powers deep comparative synthesis, full-context extraction, and academic citation matrices.
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-app-text">Fast Micro-Model (Triage)</label>
            <input
              type="text"
              value={fastModel}
              onChange={(e) => setFastModel(e.target.value)}
              placeholder="Defaults to Primary Model"
              className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
            />
            <p className="text-[11px] text-app-text-dim">
              Powers auto-titling, query decomposition, and fast metadata auditing.
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-app-text">Fallback Model (Optional)</label>
            <input
              type="text"
              value={fallbackModel}
              onChange={(e) => setFallbackModel(e.target.value)}
              placeholder="e.g. gemini-1.5-flash"
              className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
            />
            <p className="text-[11px] text-app-text-dim">
              Cascade destination when primary model triggers 429 rate limit or 503 outage.
            </p>
          </div>

          <div className="space-y-1.5">
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
            <p className="text-[11px] text-app-text-dim">
              Recommended: 0.1 for high academic grounding, 0.0 for deterministic evaluation.
            </p>
          </div>
        </div>

        {/* Test Result Feedback */}
        {testResult && (
          <div
            className={`p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
              testResult.success
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                : "bg-rose-500/10 border-rose-500/20 text-rose-400"
            }`}
          >
            {testResult.success ? (
              <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
            ) : (
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium">{testResult.message}</p>
              {testResult.latency_ms !== undefined && (
                <p className="text-[11px] opacity-80 mt-0.5">Roundtrip: {testResult.latency_ms} ms</p>
              )}
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

        <div className="flex items-center justify-between pt-4 border-t border-app-border">
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={isTesting || (!apiKey && !config.has_api_key)}
            className="px-3 py-2 text-xs font-medium rounded-lg border border-app-border hover:bg-app-item-hover text-app-text transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw size={13} className={isTesting ? "animate-spin" : ""} />
            {isTesting ? "Testing Gateway..." : "Test Gateway Connection"}
          </button>

          <button
            type="submit"
            disabled={isSaving}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? "Saving..." : "Save LLM Configuration"}
          </button>
        </div>
      </form>
    </div>
  );
}
