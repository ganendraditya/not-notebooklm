"use client";

import { useState } from "react";
import {
  Binary,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sliders,
  AlertTriangle,
  Eye,
  EyeOff,
  Copy,
  Check,
} from "lucide-react";
import type { AdminConfig, TestResult } from "@/types/admin";

interface EmbeddingTabProps {
  config: AdminConfig["embedding"];
  rerankerConfig?: AdminConfig["reranker"];
  backendUrl: string;
  onSaved: () => void;
}

const LOCAL_CATALOG_OPTIONS = [
  {
    id: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    name: "FastEmbed MiniLM-L12 (384-dim, ~220MB)",
    desc: "Default local offline engine. Lightweight, sub-millisecond CPU speed.",
  },
  {
    id: "intfloat/multilingual-e5-large",
    name: "FastEmbed Multilingual E5-Large (1024-dim, ~2.2GB)",
    desc: "Maximum academic rigor across 100+ languages.",
  },
];

const FLASHRANK_RERANKER_OPTIONS = [
  { id: "ms-marco-TinyBERT-L-2-v2", name: "TinyBERT (Ultra-fast <10ms, ~15MB)" },
  { id: "ms-marco-MiniLM-L-12-v2", name: "MiniLM-L-12-v2 (Higher precision, ~30MB)" },
  { id: "ms-marco-MultiBERT-L-12", name: "MultiBERT-L-12 (Multilingual cross-encoder)" },
  { id: "rank-T5-flan", name: "Rank-T5 Flan (T5 reasoning ranker)" },
];

export default function EmbeddingTab({
  config,
  rerankerConfig,
  backendUrl,
  onSaved,
}: EmbeddingTabProps) {
  // Embedding State
  const [provider, setProvider] = useState<"local" | "gemini" | "openai" | "custom">(
    config.provider || "local"
  );
  const [localModel, setLocalModel] = useState(
    config.local_model || "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
  );
  const [geminiKey, setGeminiKey] = useState("");
  const [geminiModel, setGeminiModel] = useState(config.gemini_model || "models/gemini-embedding-001");

  // OpenAI-Compatible / Custom Embedding State
  const [customBaseUrl, setCustomBaseUrl] = useState(config.custom_base_url || "http://localhost:11434/v1");
  const [customKey, setCustomKey] = useState("");
  const [customModelName, setCustomModelName] = useState(config.custom_model_name || "nomic-embed-text");
  const [customLocalPath, setCustomLocalPath] = useState(config.custom_local_path || "");

  // Reranker State
  const [rerankerModel, setRerankerModel] = useState(
    rerankerConfig?.model || "ms-marco-TinyBERT-L-2-v2"
  );
  const [topN, setTopN] = useState(rerankerConfig?.top_n ?? 12);

  // Secret toggles & copy states
  const [showCustomKey, setShowCustomKey] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (text: string, id: string) => {
    if (!text || !navigator.clipboard) return;
    navigator.clipboard
      .writeText(text)
      .then(() => {
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
      })
      .catch(() => {});
  };
  const [isSaving, setIsSaving] = useState(false);
  const [isTestingEmbed, setIsTestingEmbed] = useState(false);
  const [isTestingRerank, setIsTestingRerank] = useState(false);
  const [embedTestResult, setEmbedTestResult] = useState<TestResult & { dimensions?: number } | null>(null);
  const [rerankTestResult, setRerankTestResult] = useState<TestResult | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const handleTestEmbedding = async () => {
    setIsTestingEmbed(true);
    setEmbedTestResult(null);
    try {
      const res = await fetch(`${backendUrl}/admin/test/embeddings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: customBaseUrl,
          api_key: customKey.trim() || undefined,
          model_name: customModelName,
        }),
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setEmbedTestResult(data);
    } catch (e) {
      setEmbedTestResult({
        success: false,
        message: e instanceof Error ? e.message : "Failed to connect to embedding endpoint",
      });
    } finally {
      setIsTestingEmbed(false);
    }
  };

  const handleTestReranker = async () => {
    setIsTestingRerank(true);
    setRerankTestResult(null);
    try {
      const res = await fetch(`${backendUrl}/admin/test/reranker`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: rerankerModel }),
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setRerankTestResult(data);
    } catch (e) {
      setRerankTestResult({
        success: false,
        message: e instanceof Error ? e.message : "Failed to benchmark reranker",
      });
    } finally {
      setIsTestingRerank(false);
    }
  };

  const handleSaveAll = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMessage(null);
    try {
      // 1. Save Embedding Config
      const embedRes = await fetch(`${backendUrl}/admin/config/embeddings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: provider,
          local_model: localModel,
          gemini_key: geminiKey.trim() || undefined,
          gemini_model: geminiModel.trim() || undefined,
          custom_base_url: customBaseUrl.trim() || undefined,
          custom_key: customKey.trim() || undefined,
          custom_model_name: customModelName.trim() || undefined,
          custom_local_path: customLocalPath.trim() || undefined,
        }),
      });
      if (!embedRes.ok) throw new Error("Failed to save embedding configuration");

      // 2. Save Reranker Config
      const rankRes = await fetch(`${backendUrl}/admin/config/reranker`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: rerankerModel,
          top_n: Number(topN),
        }),
      });
      if (!rankRes.ok) throw new Error("Failed to save reranker configuration");

      setStatusMessage({
        text: "Settings saved! Changes are staged and will take effect on next workspace reload.",
      });
      setGeminiKey("");
      setCustomKey("");
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
          <Binary size={18} className="text-blue-500" />
          Universal Embedding Vault & Reranker Manager
        </h2>
        <p className="text-xs text-app-text-muted mt-1">
          Configure document retrieval engines: local offline models, OpenAI-compatible endpoints (Ollama/Voyage), Google Gemini, and cross-encoder rerankers.
        </p>
      </div>

      <form onSubmit={handleSaveAll} className="space-y-6">
        {/* SECTION 1: EMBEDDING ENGINE SELECTION */}
        <div className="space-y-3">
          <label className="text-xs font-semibold text-app-text">Active Embedding Provider</label>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <button
              type="button"
              onClick={() => setProvider("local")}
              className={`p-3 rounded-xl border text-left transition-colors cursor-pointer ${
                provider === "local"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">FastEmbed (Local)</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">CPU ONNX, 100% offline</div>
            </button>

            <button
              type="button"
              onClick={() => setProvider("openai")}
              className={`p-3 rounded-xl border text-left transition-colors cursor-pointer ${
                provider === "openai" || provider === "custom"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">OpenAI / Ollama</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">Universal /v1/embeddings</div>
            </button>

            <button
              type="button"
              onClick={() => setProvider("gemini")}
              className={`p-3 rounded-xl border text-left transition-colors cursor-pointer ${
                provider === "gemini"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">Google Gemini</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">Cloud GenAI 3072-dim</div>
            </button>

            <button
              type="button"
              onClick={() => setProvider("custom")}
              className={`p-3 rounded-xl border text-left transition-colors cursor-pointer ${
                provider === "custom"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">Custom Local Path</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">From local disk folder</div>
            </button>
          </div>
        </div>

        {/* DETAILS: LOCAL FASTEMBED */}
        {provider === "local" && (
          <div className="p-4 rounded-xl border border-app-border bg-app-card space-y-3">
            <label className="text-xs font-medium text-app-text">Choose Built-in Local Model</label>
            <div className="space-y-2">
              {LOCAL_CATALOG_OPTIONS.map((opt) => (
                <label
                  key={opt.id}
                  className={`flex items-start gap-2.5 p-3 rounded-lg border cursor-pointer transition-colors ${
                    localModel === opt.id
                      ? "border-blue-500 bg-blue-500/10"
                      : "border-app-border bg-app-input-surface hover:bg-app-item-hover"
                  }`}
                >
                  <input
                    type="radio"
                    name="localModel"
                    checked={localModel === opt.id}
                    onChange={() => setLocalModel(opt.id)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-xs font-semibold text-app-text">{opt.name}</div>
                    <div className="text-[11px] text-app-text-dim">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* DETAILS: OPENAI-COMPATIBLE / OLLAMA */}
        {provider === "openai" && (
          <div className="p-4 rounded-xl border border-app-border bg-app-card space-y-3">
            <div className="text-xs font-medium text-app-text">Universal OpenAI-Compatible Embeddings (/v1)</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1 md:col-span-2">
                <label className="text-[11px] text-app-text-dim">Base URL (/v1)</label>
                <input
                  type="text"
                  value={customBaseUrl}
                  onChange={(e) => setCustomBaseUrl(e.target.value)}
                  placeholder="http://localhost:11434/v1 or https://api.openai.com/v1"
                  className="w-full px-3 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-app-text-dim">Model Identifier</label>
                <input
                  type="text"
                  value={customModelName}
                  onChange={(e) => setCustomModelName(e.target.value)}
                  placeholder="nomic-embed-text or text-embedding-3-small"
                  className="w-full px-3 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-[11px] text-app-text-dim">API Key (Optional for Ollama)</label>
                  {config.has_custom_key && (
                    <span className="text-[10px] font-mono text-emerald-400">
                      Configured: {config.custom_key_masked}
                    </span>
                  )}
                </div>
                <div className="relative flex items-center">
                  <input
                    type={showCustomKey ? "text" : "password"}
                    value={customKey}
                    onChange={(e) => setCustomKey(e.target.value)}
                    placeholder={config.has_custom_key ? "Leave blank to keep key" : "sk-..."}
                    className="w-full h-8 pl-3 pr-16 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text font-mono focus:outline-none focus:border-blue-500"
                  />
                  <div className="absolute right-1.5 flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setShowCustomKey(!showCustomKey)}
                      className="p-1 rounded text-app-text-dim hover:text-app-text transition-colors cursor-pointer"
                      title={showCustomKey ? "Hide Secret" : "Show Secret"}
                    >
                      {showCustomKey ? <EyeOff size={13} /> : <Eye size={13} />}
                    </button>
                    {(customKey || config.has_custom_key) && (
                      <button
                        type="button"
                        onClick={() => handleCopy(customKey || config.custom_key_masked || "", "custom_embed_key")}
                        className="p-1 rounded text-app-text-dim hover:text-app-text transition-colors cursor-pointer"
                        title="Copy Key"
                      >
                        {copiedId === "custom_embed_key" ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2">
              <button
                type="button"
                onClick={handleTestEmbedding}
                disabled={isTestingEmbed}
                className="h-8 min-w-[210px] px-3 text-xs font-medium rounded-lg border border-app-border bg-app-input-surface hover:bg-app-card-hover text-app-text flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-40 transition-colors"
              >
                <RefreshCw size={12} className={isTestingEmbed ? "animate-spin" : ""} />
                <span>{isTestingEmbed ? "Testing..." : "Test Connection & Dimensions"}</span>
              </button>

              <div className="min-h-[22px] flex items-center text-xs">
                {embedTestResult && (
                  <div
                    className={`flex items-center gap-1.5 ${
                      embedTestResult.success ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {embedTestResult.success ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                    <span>{embedTestResult.message}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* DETAILS: GOOGLE GEMINI */}
        {provider === "gemini" && (
          <div className="p-4 rounded-xl border border-app-border bg-app-card space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] text-app-text-dim">Gemini Embedding Model</label>
                <input
                  type="text"
                  value={geminiModel}
                  onChange={(e) => setGeminiModel(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-[11px] text-app-text-dim">Gemini API Key</label>
                  {config.has_gemini_key && (
                    <span className="text-[10px] font-mono text-emerald-400">
                      Configured: {config.gemini_key_masked}
                    </span>
                  )}
                </div>
                <div className="relative flex items-center">
                  <input
                    type={showGeminiKey ? "text" : "password"}
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    placeholder={config.has_gemini_key ? "Leave blank to keep key" : "AIzaSy..."}
                    className="w-full h-8 pl-3 pr-16 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text font-mono focus:outline-none focus:border-blue-500"
                  />
                  <div className="absolute right-1.5 flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setShowGeminiKey(!showGeminiKey)}
                      className="p-1 rounded text-app-text-dim hover:text-app-text transition-colors cursor-pointer"
                      title={showGeminiKey ? "Hide Secret" : "Show Secret"}
                    >
                      {showGeminiKey ? <EyeOff size={13} /> : <Eye size={13} />}
                    </button>
                    {(geminiKey || config.has_gemini_key) && (
                      <button
                        type="button"
                        onClick={() => handleCopy(geminiKey || config.gemini_key_masked || "", "gemini_embed_key")}
                        className="p-1 rounded text-app-text-dim hover:text-app-text transition-colors cursor-pointer"
                        title="Copy Key"
                      >
                        {copiedId === "gemini_embed_key" ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* DETAILS: CUSTOM LOCAL PATH */}
        {provider === "custom" && (
          <div className="p-4 rounded-xl border border-app-border bg-app-card space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-app-text">Custom Model Directory Path</label>
              <input
                type="text"
                value={customLocalPath}
                onChange={(e) => setCustomLocalPath(e.target.value)}
                placeholder="/Users/username/models/my-custom-embedder"
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-start gap-2.5">
              <AlertTriangle size={16} className="shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Custom Model Notice</p>
                <p className="text-[11px] text-amber-300/80 mt-0.5 leading-relaxed">
                  If loading a custom model from disk or external runtime, please ensure any required packages, drivers, or software dependencies needed by that model are available on your machine.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* SECTION 2: RERANKER (CROSS-ENCODER) MANAGER */}
        <div className="space-y-3 pt-4 border-t border-app-border">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-xs font-semibold text-app-text flex items-center gap-2">
                <Sliders size={14} className="text-purple-400" />
                Cross-Encoder Reranker Manager
              </label>
              <p className="text-[11px] text-app-text-dim mt-0.5">
                Re-ranks retrieved hybrid chunks before passing them to the synthesis prompt.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-app-border bg-app-card space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-app-text">Reranker Model</label>
                <select
                  value={rerankerModel}
                  onChange={(e) => setRerankerModel(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text cursor-pointer focus:outline-none focus:border-blue-500"
                >
                  {FLASHRANK_RERANKER_OPTIONS.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-medium text-app-text">Top Chunks to Context (top_n)</label>
                  <span className="text-xs font-mono text-blue-400">{topN} Chunks</span>
                </div>
                <input
                  type="range"
                  min="3"
                  max="25"
                  step="1"
                  value={topN}
                  onChange={(e) => setTopN(parseInt(e.target.value, 10))}
                  className="w-full h-1.5 bg-app-border rounded-lg appearance-none cursor-pointer accent-blue-600"
                />
                <div className="text-[10px] text-app-text-dim">
                  Recommended: 10–12 chunks for comprehensive academic literature coverage.
                </div>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1">
              <button
                type="button"
                onClick={handleTestReranker}
                disabled={isTestingRerank}
                className="h-8 min-w-[170px] px-3 text-xs font-medium rounded-lg border border-app-border bg-app-input-surface hover:bg-app-card-hover text-app-text flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-40 transition-colors"
              >
                <RefreshCw size={12} className={isTestingRerank ? "animate-spin" : ""} />
                <span>{isTestingRerank ? "Benchmarking..." : "Test Reranker Speed"}</span>
              </button>

              <div className="min-h-[22px] flex items-center text-xs">
                {rerankTestResult && (
                  <div
                    className={`flex items-center gap-1.5 ${
                      rerankTestResult.success ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {rerankTestResult.success ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                    <span>{rerankTestResult.message}</span>
                  </div>
                )}
              </div>
            </div>
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
            className="h-8 min-w-[240px] px-4 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save Retrieval & Reranker Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
