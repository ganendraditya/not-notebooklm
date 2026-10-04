"use client";

import { useState } from "react";
import { Binary, CheckCircle2, AlertCircle } from "lucide-react";
import type { AdminConfig } from "@/types/admin";

interface EmbeddingTabProps {
  config: AdminConfig["embedding"];
  backendUrl: string;
  onSaved: () => void;
}

export default function EmbeddingTab({ config, backendUrl, onSaved }: EmbeddingTabProps) {
  const [provider, setProvider] = useState<"local" | "gemini">(config.provider || "local");
  const [geminiKey, setGeminiKey] = useState("");
  const [geminiModel, setGeminiModel] = useState(config.gemini_model || "models/gemini-embedding-001");

  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMessage(null);
    try {
      const res = await fetch(`${backendUrl}/admin/config/embeddings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: provider,
          gemini_key: geminiKey.trim() || undefined,
          gemini_model: geminiModel.trim() || undefined,
        }),
      });
      if (!res.ok) throw new Error("Failed to configure embedding engine");
      setStatusMessage({ text: `Embedding engine switched to: ${provider}` });
      setGeminiKey("");
      onSaved();
    } catch (e) {
      setStatusMessage({
        text: e instanceof Error ? e.message : "Error saving embedding engine",
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
          <Binary size={18} className="text-blue-500" />
          Embedding Engine & Vector Dimensions
        </h2>
        <p className="text-xs text-app-text-muted mt-1">
          Select between CPU-native FastEmbed ONNX (Zero-PyTorch, 384 dimensions) and Google Gemini Cloud Embedding.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-5">
        <div className="space-y-2">
          <label className="text-xs font-medium text-app-text">Active Vector Engine</label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg">
            <button
              type="button"
              onClick={() => setProvider("local")}
              className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                provider === "local"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">FastEmbed ONNX (Local)</span>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-400 font-mono px-1.5 py-0.5 rounded">
                  384-dim
                </span>
              </div>
              <div className="text-[11px] text-app-text-dim mt-1">
                Zero-PyTorch, ~220MB model weight, CPU-accelerated multilingual MiniLM.
              </div>
            </button>

            <button
              type="button"
              onClick={() => setProvider("gemini")}
              className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                provider === "gemini"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">Google Gemini (Cloud)</span>
                <span className="text-[10px] bg-blue-500/20 text-blue-400 font-mono px-1.5 py-0.5 rounded">
                  3072-dim
                </span>
              </div>
              <div className="text-[11px] text-app-text-dim mt-1">
                Cloud-hosted high-dimensional embeddings via Google GenAI API.
              </div>
            </button>
          </div>
        </div>

        {provider === "local" && (
          <div className="p-4 rounded-lg bg-app-surface border border-app-border space-y-2">
            <div className="text-xs font-medium text-app-text">Active Local Model:</div>
            <div className="font-mono text-xs text-blue-400 bg-app-code-bg p-2 rounded border border-app-border">
              {config.local_model}
            </div>
            <div className="flex items-center gap-3 text-[11px] text-app-text-dim pt-1">
              <span>Collection: <strong className="text-app-text">not_notebooklm_fastembed</strong></span>
              <span>•</span>
              <span>Hybrid BM25: <strong className="text-emerald-400">Active (RRF fusion)</strong></span>
            </div>
          </div>
        )}

        {provider === "gemini" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-app-text">Gemini Embedding Model</label>
              <input
                type="text"
                value={geminiModel}
                onChange={(e) => setGeminiModel(e.target.value)}
                placeholder="models/gemini-embedding-001"
                required={provider === "gemini"}
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="text-xs font-medium text-app-text">Gemini API Key</label>
                {config.has_gemini_key && (
                  <span className="text-[11px] font-mono text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded">
                    Configured: {config.gemini_key_masked}
                  </span>
                )}
              </div>
              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder={config.has_gemini_key ? "Leave blank to keep existing" : "AIzaSy..."}
                required={provider === "gemini" && !config.has_gemini_key}
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
            {isSaving ? "Saving..." : "Apply Embedding Engine"}
          </button>
        </div>
      </form>
    </div>
  );
}
