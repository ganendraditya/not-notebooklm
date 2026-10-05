"use client";

import { useState, useEffect, useRef } from "react";
import {
  Cpu,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Plus,
  Trash2,
  Server,
  Eye,
  EyeOff,
  Copy,
  Check,
  Edit3,
  X,
} from "lucide-react";
import type { AdminConfig, GatewayProfile, TestResult } from "@/types/admin";

interface LLMTabProps {
  config: AdminConfig["llm"];
  backendUrl: string;
  onSaved: () => void;
}

const PRESET_OPENAI_GATEWAYS = [
  { name: "9Router", url: "http://localhost:20128/v1" },
  { name: "DeepSeek", url: "https://api.deepseek.com/v1" },
  { name: "xAI Grok", url: "https://api.x.ai/v1" },
  { name: "Groq", url: "https://api.groq.com/openai/v1" },
  { name: "OpenRouter", url: "https://openrouter.ai/api/v1" },
  { name: "Ollama (Local)", url: "http://localhost:11434/v1" },
  { name: "OpenAI Official", url: "https://api.openai.com/v1" },
];

const PRESET_ANTHROPIC_GATEWAYS = [
  { name: "Anthropic Official", url: "https://api.anthropic.com/v1" },
];

interface ModalState {
  isOpen: boolean;
  mode: "add" | "edit";
  protocol: "openai" | "anthropic";
  profileId: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  showKey: boolean;
  hasExistingKey: boolean;
  existingMaskedKey: string;
  isTesting: boolean;
  testResult: TestResult | null;
  isSaving: boolean;
  errorMessage: string | null;
}

export default function LLMTab({ config, backendUrl, onSaved }: LLMTabProps) {
  // Profiles State
  const initialProfiles: GatewayProfile[] =
    config.profiles && config.profiles.length > 0
      ? config.profiles
      : [
          {
            id: "default",
            name: "Default Gateway",
            base_url: config.base_url || "http://localhost:20128/v1",
            api_key_masked: config.api_key_masked || "",
            has_api_key: config.has_api_key || false,
            protocol: "openai",
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

  // Status & Testing States for Catalog Cards
  const [isSavingTiers, setIsSavingTiers] = useState(false);
  const [testingProfileId, setTestingProfileId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [statusMessage, setStatusMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);

  // Dedicated Modal State
  const [modal, setModal] = useState<ModalState>({
    isOpen: false,
    mode: "add",
    protocol: "openai",
    profileId: "",
    name: "",
    baseUrl: "",
    apiKey: "",
    showKey: false,
    hasExistingKey: false,
    existingMaskedKey: "",
    isTesting: false,
    testResult: null,
    isSaving: false,
    errorMessage: null,
  });

  const modalRef = useRef<HTMLDivElement>(null);

  // Keyboard accessibility: Escape closes modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && modal.isOpen) {
        closeModal();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [modal.isOpen]);

  const openAddModal = (protocol: "openai" | "anthropic") => {
    const newId = `profile_${Date.now()}`;
    const defaultUrl = protocol === "anthropic" ? "https://api.anthropic.com/v1" : "http://localhost:20128/v1";
    const defaultName = protocol === "anthropic" ? `Anthropic Claude ${profiles.length + 1}` : `Gateway ${profiles.length + 1}`;

    setModal({
      isOpen: true,
      mode: "add",
      protocol,
      profileId: newId,
      name: defaultName,
      baseUrl: defaultUrl,
      apiKey: "",
      showKey: false,
      hasExistingKey: false,
      existingMaskedKey: "",
      isTesting: false,
      testResult: null,
      isSaving: false,
      errorMessage: null,
    });
  };

  const openEditModal = (profile: GatewayProfile) => {
    setModal({
      isOpen: true,
      mode: "edit",
      protocol: profile.protocol || "openai",
      profileId: profile.id,
      name: profile.name,
      baseUrl: profile.base_url,
      apiKey: profileKeys[profile.id] || "",
      showKey: false,
      hasExistingKey: profile.has_api_key,
      existingMaskedKey: profile.api_key_masked,
      isTesting: false,
      testResult: null,
      isSaving: false,
      errorMessage: null,
    });
  };

  const closeModal = () => {
    setModal((prev) => ({ ...prev, isOpen: false }));
  };

  const handleCopy = (text: string, id: string) => {
    if (!text || !navigator.clipboard) return;
    navigator.clipboard
      .writeText(text)
      .then(() => {
        setCopiedKeyId(id);
        setTimeout(() => setCopiedKeyId(null), 2000);
      })
      .catch(() => {});
  };

  const handleTestConnection = async (profile: GatewayProfile, explicitKey?: string) => {
    setTestingProfileId(profile.id);
    setTestResults((prev) => {
      const next = { ...prev };
      delete next[profile.id];
      return next;
    });

    const keyToTest = (explicitKey !== undefined ? explicitKey : profileKeys[profile.id])?.trim() || undefined;

    try {
      const res = await fetch(`${backendUrl}/admin/test/llm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: profile.base_url,
          api_key: keyToTest,
          model: model || (profile.protocol === "anthropic" ? "claude-3-5-haiku-20241022" : "gpt-4o"),
          profile_id: profile.id,
          protocol: profile.protocol || "openai",
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

  const handleModalTestConnection = async () => {
    setModal((prev) => ({ ...prev, isTesting: true, testResult: null, errorMessage: null }));

    try {
      const res = await fetch(`${backendUrl}/admin/test/llm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: modal.baseUrl.trim(),
          api_key: modal.apiKey.trim() || undefined,
          model: model || (modal.protocol === "anthropic" ? "claude-3-5-haiku-20241022" : "gpt-4o"),
          profile_id: modal.mode === "edit" ? modal.profileId : undefined,
          protocol: modal.protocol,
        }),
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setModal((prev) => ({ ...prev, testResult: data, isTesting: false }));
    } catch (e) {
      setModal((prev) => ({
        ...prev,
        testResult: {
          success: false,
          message: e instanceof Error ? e.message : "Failed to test connection",
        },
        isTesting: false,
      }));
    }
  };

  const handleModalSaveProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modal.name.trim() || !modal.baseUrl.trim()) {
      setModal((prev) => ({ ...prev, errorMessage: "Name and Base URL are required." }));
      return;
    }

    setModal((prev) => ({ ...prev, isSaving: true, errorMessage: null }));

    try {
      const safeMaskedKey = modal.apiKey
        ? modal.apiKey.length > 8
          ? `${modal.apiKey.slice(0, 4)}...${modal.apiKey.slice(-4)}`
          : "••••••••"
        : modal.existingMaskedKey;

      const updatedProfile: GatewayProfile = {
        id: modal.profileId,
        name: modal.name.trim(),
        base_url: modal.baseUrl.trim(),
        api_key_masked: safeMaskedKey,
        has_api_key: Boolean(modal.apiKey.trim() || modal.hasExistingKey),
        protocol: modal.protocol,
      };

      let newProfiles: GatewayProfile[];
      if (modal.mode === "add") {
        newProfiles = [...profiles, updatedProfile];
      } else {
        newProfiles = profiles.map((p) => (p.id === modal.profileId ? updatedProfile : p));
      }

      // Update local profile keys if a new key was entered
      const newKeys = { ...profileKeys };
      if (modal.apiKey.trim()) {
        newKeys[modal.profileId] = modal.apiKey.trim();
        setProfileKeys(newKeys);
      }

      // Prepare payload to save directly to backend
      const payloadProfiles = newProfiles.map((p) => ({
        id: p.id,
        name: p.name,
        base_url: p.base_url,
        api_key: newKeys[p.id]?.trim() || undefined,
        protocol: p.protocol || "openai",
      }));

      const activePrimary = newProfiles.find((p) => p.id === primaryProfileId) || newProfiles[0];

      const res = await fetch(`${backendUrl}/admin/config/llm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: activePrimary.base_url,
          api_key: newKeys[activePrimary.id]?.trim() || undefined,
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

      if (!res.ok) throw new Error("Failed to persist gateway provider");

      setProfiles(newProfiles);
      setStatusMessage({
        text: `Provider "${updatedProfile.name}" saved successfully!`,
      });
      closeModal();
      onSaved();
    } catch (err) {
      setModal((prev) => ({
        ...prev,
        errorMessage: err instanceof Error ? err.message : "Error saving provider",
        isSaving: false,
      }));
    }
  };

  const handleRemoveProfile = async (id: string) => {
    if (profiles.length <= 1) return;
    const target = profiles.find((p) => p.id === id);
    if (!target) return;

    if (!confirm(`Are you sure you want to delete profile "${target.name}"?`)) return;

    const remainingProfiles = profiles.filter((p) => p.id !== id);
    const newPrimary = primaryProfileId === id ? (remainingProfiles[0]?.id || "default") : primaryProfileId;
    const newFast = fastProfileId === id ? newPrimary : fastProfileId;
    const newFallback = fallbackProfileId === id ? newPrimary : fallbackProfileId;

    setProfiles(remainingProfiles);
    setPrimaryProfileId(newPrimary);
    setFastProfileId(newFast);
    setFallbackProfileId(newFallback);

    // Persist removal directly to backend
    try {
      const payloadProfiles = remainingProfiles.map((p) => ({
        id: p.id,
        name: p.name,
        base_url: p.base_url,
        api_key: profileKeys[p.id]?.trim() || undefined,
        protocol: p.protocol || "openai",
      }));

      const activePrimary = remainingProfiles.find((p) => p.id === newPrimary) || remainingProfiles[0];

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
          primary_profile_id: newPrimary,
          fast_profile_id: newFast,
          fallback_profile_id: newFallback,
        }),
      });

      if (!res.ok) throw new Error("Failed to persist deletion to backend");

      setStatusMessage({ text: `Provider "${target.name}" deleted.` });
      onSaved();
    } catch (e) {
      setStatusMessage({
        text: e instanceof Error ? e.message : "Failed to delete provider",
        error: true,
      });
    }
  };

  const handleSaveTierRouting = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingTiers(true);
    setStatusMessage(null);

    try {
      const payloadProfiles = profiles.map((p) => ({
        id: p.id,
        name: p.name,
        base_url: p.base_url,
        api_key: profileKeys[p.id]?.trim() || undefined,
        protocol: p.protocol || "openai",
      }));

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

      if (!res.ok) throw new Error("Failed to save tier bindings");
      setStatusMessage({ text: "Tier routing bindings and sampling settings saved successfully." });
      onSaved();
    } catch (e) {
      setStatusMessage({
        text: e instanceof Error ? e.message : "Error saving tier routing",
        error: true,
      });
    } finally {
      setIsSavingTiers(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-app-border pb-4">
        <h2 className="text-base font-semibold text-app-text flex items-center gap-2">
          <Cpu size={18} className="text-blue-500" />
          Universal OpenAI-Compatible Gateway Vault
        </h2>
        <p className="text-xs text-app-text-muted mt-1">
          Configure arbitrary OpenAI-compatible endpoints (DeepSeek, Grok, 9Router, Ollama, Groq, vLLM) and direct Anthropic Claude protocol. Route Primary, Fast, and Fallback tiers to separate keys and endpoints.
        </p>
      </div>

      {/* Global Status Message */}
      {statusMessage && (
        <div
          className={`p-3 rounded-xl border text-xs flex items-center gap-2.5 transition-all ${
            statusMessage.error
              ? "bg-rose-500/10 border-rose-500/20 text-rose-400"
              : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
          }`}
        >
          {statusMessage.error ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* Section 1: Provider Catalog Cards */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <label className="text-xs font-semibold text-app-text flex items-center gap-2">
            <Server size={14} className="text-purple-400" />
            Registered Gateway Profiles ({profiles.length})
          </label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => openAddModal("openai")}
              className="h-8 px-3 text-xs font-medium rounded-lg border border-app-border bg-app-card hover:bg-app-card-hover text-app-text transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Plus size={13} />
              Add OpenAI Compatible
            </button>
            <button
              type="button"
              onClick={() => openAddModal("anthropic")}
              className="h-8 px-3 text-xs font-medium rounded-lg border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Plus size={13} />
              Add Anthropic Claude
            </button>
          </div>
        </div>

        {/* Catalog Grid */}
        <div className="space-y-3">
          {profiles.map((prof) => {
            const testResult = testResults[prof.id];
            const isTesting = testingProfileId === prof.id;
            const hasKey = prof.has_api_key || Boolean(profileKeys[prof.id]);
            const isAnthropic = prof.protocol === "anthropic";

            return (
              <div
                key={prof.id}
                className="p-4 rounded-xl border border-app-border bg-app-card space-y-3 hover:border-app-border-strong transition-colors"
              >
                {/* Card Top Row: Name, Protocol Badge & Fixed Action Buttons */}
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-semibold text-app-text">{prof.name}</span>
                    {isAnthropic ? (
                      <span className="px-2 py-0.5 text-[10px] font-mono rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 font-medium">
                        Anthropic Claude
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-[10px] font-mono rounded-full bg-blue-500/15 text-blue-300 border border-blue-500/30 font-medium">
                        OpenAI Compatible
                      </span>
                    )}
                  </div>

                  {/* Fixed-dimension Actions (Zero Cumulative Layout Shift) */}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleTestConnection(prof)}
                      disabled={isTesting || (!hasKey && !prof.base_url.includes("11434"))}
                      className="h-8 min-w-[76px] px-2.5 text-xs font-medium rounded-lg border border-app-border bg-app-input-surface hover:bg-app-card-hover text-app-text flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-40 transition-colors"
                      title="Test Connection"
                    >
                      <RefreshCw size={12} className={isTesting ? "animate-spin" : ""} />
                      <span>{isTesting ? "Testing" : "Test"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => openEditModal(prof)}
                      className="h-8 min-w-[68px] px-2.5 text-xs font-medium rounded-lg border border-app-border bg-app-input-surface hover:bg-app-card-hover text-app-text flex items-center justify-center gap-1.5 cursor-pointer transition-colors"
                      title="Edit Provider Settings"
                    >
                      <Edit3 size={12} />
                      <span>Edit</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleRemoveProfile(prof.id)}
                      disabled={profiles.length <= 1}
                      className="h-8 w-8 text-xs font-medium rounded-lg border border-app-border bg-app-input-surface hover:bg-rose-500/10 hover:border-rose-500/30 text-app-text-muted hover:text-rose-400 flex items-center justify-center cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      title={profiles.length <= 1 ? "Cannot delete the sole profile" : "Delete Profile"}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                {/* Card Mid Row: URL and Secret Preview */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="space-y-1">
                    <label className="text-[11px] text-app-text-dim">Base URL</label>
                    <div className="h-8 px-2.5 rounded-lg bg-app-input-surface border border-app-border font-mono text-app-text-muted flex items-center justify-between">
                      <span className="truncate">{prof.base_url}</span>
                      <button
                        type="button"
                        onClick={() => handleCopy(prof.base_url, `url_${prof.id}`)}
                        className="p-1 text-app-text-dim hover:text-app-text rounded transition-colors ml-2 cursor-pointer"
                        title="Copy Base URL"
                      >
                        {copiedKeyId === `url_${prof.id}` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] text-app-text-dim">API Key Status</label>
                    <div className="h-8 px-2.5 rounded-lg bg-app-input-surface border border-app-border font-mono text-app-text-muted flex items-center justify-between">
                      <span className="truncate">
                        {profileKeys[prof.id]
                          ? profileKeys[prof.id].length > 8
                            ? `${profileKeys[prof.id].slice(0, 4)}...${profileKeys[prof.id].slice(-4)} (Staged)`
                            : "•••••••• (Staged)"
                          : prof.has_api_key
                          ? `Configured (${prof.api_key_masked})`
                          : "No API Key (Local Ollama)"}
                      </span>
                      {hasKey && (
                        <button
                          type="button"
                          onClick={() => handleCopy(profileKeys[prof.id] || prof.api_key_masked, `key_${prof.id}`)}
                          className="p-1 text-app-text-dim hover:text-app-text rounded transition-colors ml-2 cursor-pointer"
                          title="Copy API Key"
                        >
                          {copiedKeyId === `key_${prof.id}` ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Card Bottom Row: Dedicated Feedback Container (Zero Cumulative Layout Shift) */}
                <div className="min-h-[22px] flex items-center text-xs">
                  {testResult && (
                    <div
                      className={`flex items-center gap-1.5 ${
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
      <form onSubmit={handleSaveTierRouting} className="space-y-4 pt-4 border-t border-app-border">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <label className="text-xs font-semibold text-app-text">Tiered Gateway Routing</label>
            <p className="text-[11px] text-app-text-dim mt-0.5">
              Bind Primary, Fast triage, and Fallback models to specific registered gateway profiles.
            </p>
          </div>
          <button
            type="submit"
            disabled={isSavingTiers}
            className="h-8 min-w-[150px] px-4 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 transition-colors"
          >
            {isSavingTiers ? "Saving..." : "Save Tier Routing"}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Primary Tier */}
          <div className="p-3.5 rounded-xl border border-app-border bg-app-card space-y-2.5">
            <div className="text-xs font-semibold text-app-text">Primary Heavy Model</div>
            <div className="space-y-1">
              <label className="text-[11px] text-app-text-dim">Gateway Profile</label>
              <select
                value={primaryProfileId}
                onChange={(e) => setPrimaryProfileId(e.target.value)}
                className="w-full h-8 px-2.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.protocol === "anthropic" ? "Anthropic" : "OpenAI"})
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
                placeholder="gpt-4o or claude-3-5-sonnet-20241022"
                required
                className="w-full h-8 px-2.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
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
                className="w-full h-8 px-2.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.protocol === "anthropic" ? "Anthropic" : "OpenAI"})
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
                placeholder="gpt-4o-mini or claude-3-5-haiku-20241022"
                className="w-full h-8 px-2.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
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
                className="w-full h-8 px-2.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.protocol === "anthropic" ? "Anthropic" : "OpenAI"})
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
                placeholder="grok-beta or gemini-1.5-flash"
                className="w-full h-8 px-2.5 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>
        </div>

        {/* Sampling Temperature */}
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
      </form>

      {/* DEDICATED MODAL: Add / Edit Gateway Provider */}
      {modal.isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={closeModal}
        >
          <div
            ref={modalRef}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg rounded-2xl border border-app-border bg-app-card shadow-2xl p-6 space-y-5 text-app-text"
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-app-border">
              <div className="flex items-center gap-2.5">
                <Server size={18} className={modal.protocol === "anthropic" ? "text-amber-400" : "text-blue-500"} />
                <div>
                  <h3 className="text-sm font-semibold text-app-text">
                    {modal.mode === "add"
                      ? modal.protocol === "anthropic"
                        ? "Add Anthropic Claude Gateway"
                        : "Add OpenAI Compatible Gateway"
                      : `Edit Gateway: ${modal.name}`}
                  </h3>
                  <p className="text-[11px] text-app-text-dim">
                    {modal.protocol === "anthropic"
                      ? "Direct native Anthropic Claude protocol with official messages API."
                      : "OpenAI-compatible /v1/chat/completions gateway endpoint."}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={closeModal}
                className="h-8 w-8 rounded-lg border border-app-border flex items-center justify-center text-app-text-muted hover:text-app-text hover:bg-app-input-surface transition-colors cursor-pointer"
                title="Close (Esc)"
              >
                <X size={14} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleModalSaveProvider} className="space-y-4">
              {/* Protocol selector if in Add mode */}
              {modal.mode === "add" && (
                <div className="space-y-1.5">
                  <label className="text-[11px] font-medium text-app-text-dim">Gateway Protocol</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        setModal((prev) => ({
                          ...prev,
                          protocol: "openai",
                          baseUrl: "http://localhost:20128/v1",
                        }))
                      }
                      className={`h-8 px-3 text-xs font-medium rounded-lg border text-center transition-colors cursor-pointer ${
                        modal.protocol === "openai"
                          ? "border-blue-500 bg-blue-500/10 text-blue-400"
                          : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
                      }`}
                    >
                      OpenAI Compatible
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setModal((prev) => ({
                          ...prev,
                          protocol: "anthropic",
                          baseUrl: "https://api.anthropic.com/v1",
                        }))
                      }
                      className={`h-8 px-3 text-xs font-medium rounded-lg border text-center transition-colors cursor-pointer ${
                        modal.protocol === "anthropic"
                          ? "border-amber-500 bg-amber-500/10 text-amber-400"
                          : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
                      }`}
                    >
                      Anthropic Claude
                    </button>
                  </div>
                </div>
              )}

              {/* Profile Name */}
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-app-text-dim">Profile Display Name</label>
                <input
                  type="text"
                  value={modal.name}
                  onChange={(e) => setModal((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g. DeepSeek Official or 9Router Local"
                  required
                  className="w-full h-9 px-3 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Base URL with Presets */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-[11px] font-medium text-app-text-dim">Base URL (/v1)</label>
                </div>
                <input
                  type="text"
                  value={modal.baseUrl}
                  onChange={(e) => setModal((prev) => ({ ...prev, baseUrl: e.target.value }))}
                  placeholder="https://api.deepseek.com/v1"
                  required
                  className="w-full h-9 px-3 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text font-mono focus:outline-none focus:border-blue-500"
                />

                {/* Quick Presets */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <span className="text-[10px] text-app-text-dim py-0.5">Quick Presets:</span>
                  {(modal.protocol === "anthropic" ? PRESET_ANTHROPIC_GATEWAYS : PRESET_OPENAI_GATEWAYS).map((preset) => (
                    <button
                      key={preset.name}
                      type="button"
                      onClick={() => setModal((prev) => ({ ...prev, baseUrl: preset.url }))}
                      className="text-[10px] px-2 py-0.5 rounded bg-app-input-surface hover:bg-app-card-hover border border-app-border text-app-text-muted hover:text-app-text font-mono transition-colors cursor-pointer"
                    >
                      {preset.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* API Key Input with Eye Toggle & Copy */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-[11px] font-medium text-app-text-dim">API Secret Key / Token</label>
                  {modal.hasExistingKey && (
                    <span className="text-[10px] font-mono text-emerald-400">
                      Configured: {modal.existingMaskedKey}
                    </span>
                  )}
                </div>
                <div className="relative flex items-center">
                  <input
                    type={modal.showKey ? "text" : "password"}
                    value={modal.apiKey}
                    onChange={(e) => setModal((prev) => ({ ...prev, apiKey: e.target.value }))}
                    placeholder={modal.hasExistingKey ? "Leave blank to preserve existing key" : "sk-..."}
                    className="w-full h-9 pl-3 pr-16 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text font-mono focus:outline-none focus:border-blue-500"
                  />
                  <div className="absolute right-1.5 flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setModal((prev) => ({ ...prev, showKey: !prev.showKey }))}
                      className="p-1 rounded text-app-text-dim hover:text-app-text transition-colors cursor-pointer"
                      title={modal.showKey ? "Hide Secret" : "Show Secret"}
                    >
                      {modal.showKey ? <EyeOff size={13} /> : <Eye size={13} />}
                    </button>
                    {(modal.apiKey || modal.hasExistingKey) && (
                      <button
                        type="button"
                        onClick={() => handleCopy(modal.apiKey || modal.existingMaskedKey, "modal_key")}
                        className="p-1 rounded text-app-text-dim hover:text-app-text transition-colors cursor-pointer"
                        title="Copy Key"
                      >
                        {copiedKeyId === "modal_key" ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* In-Modal Test Connection Button & Result (Zero Layout Shift) */}
              <div className="pt-2 space-y-2">
                <div className="flex items-center justify-between">
                  <button
                    type="button"
                    onClick={handleModalTestConnection}
                    disabled={modal.isTesting || (!modal.apiKey && !modal.hasExistingKey && !modal.baseUrl.includes("11434"))}
                    className="h-8 min-w-[130px] px-3 text-xs font-medium rounded-lg border border-app-border bg-app-input-surface hover:bg-app-card-hover text-app-text flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-40 transition-colors"
                  >
                    <RefreshCw size={12} className={modal.isTesting ? "animate-spin" : ""} />
                    <span>{modal.isTesting ? "Testing..." : "Test Connection"}</span>
                  </button>
                </div>

                <div className="min-h-[22px] flex items-center text-xs">
                  {modal.testResult && (
                    <div
                      className={`flex items-center gap-1.5 ${
                        modal.testResult.success ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {modal.testResult.success ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
                      <span>
                        {modal.testResult.message}
                        {modal.testResult.latency_ms !== undefined && ` (${modal.testResult.latency_ms}ms)`}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Error Message if any */}
              {modal.errorMessage && (
                <div className="p-2.5 rounded-lg border border-rose-500/20 bg-rose-500/10 text-xs text-rose-400 flex items-center gap-2">
                  <AlertCircle size={14} />
                  <span>{modal.errorMessage}</span>
                </div>
              )}

              {/* Modal Footer Actions (Fixed Dimensions) */}
              <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-app-border">
                <button
                  type="button"
                  onClick={closeModal}
                  className="h-8 min-w-[80px] px-3 text-xs font-medium rounded-lg border border-app-border bg-app-input-surface hover:bg-app-card-hover text-app-text transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modal.isSaving}
                  className="h-8 min-w-[130px] px-4 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 transition-colors"
                >
                  {modal.isSaving ? "Saving..." : "Save Provider"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
