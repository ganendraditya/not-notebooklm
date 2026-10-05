"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Sliders,
  Cpu,
  HardDrive,
  KeyRound,
  Binary,
  Activity,
  ArrowLeft,
  ExternalLink,
  RefreshCw,
  AlertCircle
} from "lucide-react";

import type { AdminConfig, AdminSystemHealth } from "@/types/admin";
import LLMTab from "./components/LLMTab";
import StorageTab from "./components/StorageTab";
import SecretsTab from "./components/SecretsTab";
import EmbeddingTab from "./components/EmbeddingTab";
import SystemHealthTab from "./components/SystemHealthTab";

type AdminTabKey = "llm" | "storage" | "secrets" | "embedding" | "health";

export default function AdminPage() {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [activeTab, setActiveTab] = useState<AdminTabKey>("llm");
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setError(null);
      const res = await fetch(`${backendUrl}/admin/config`);
      if (!res.ok) throw new Error(`HTTP error ${res.status} fetching admin config`);
      const data: AdminConfig = await res.json();
      setConfig(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load admin settings");
    }
  }, [backendUrl]);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${backendUrl}/admin/system/health`);
      if (!res.ok) throw new Error(`HTTP error ${res.status} fetching health`);
      const data: AdminSystemHealth = await res.json();
      setHealth(data);
    } catch (e) {
      console.warn("Failed to load health stats:", e);
    }
  }, [backendUrl]);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    await Promise.all([fetchConfig(), fetchHealth()]);
    setIsLoading(false);
  }, [fetchConfig, fetchHealth]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  return (
    <div className="min-h-screen bg-app-bg text-app-text flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="h-14 border-b border-app-border bg-app-sidebar/80 backdrop-blur-md px-4 md:px-6 flex items-center justify-between shrink-0 sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="p-1.5 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors"
            title="Return to Workspace"
          >
            <ArrowLeft size={16} />
          </Link>

          <div className="h-4 w-[1px] bg-app-border" />

          <div className="flex items-center gap-2">
            <Sliders size={16} className="text-blue-500" />
            <h1 className="text-sm font-semibold tracking-tight text-app-text">
              NotbookLM Control Dashboard
            </h1>
            <span className="text-[10px] font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded">
              Port 2027
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <Link
            href="/"
            className="px-2.5 py-1.5 rounded-lg border border-app-border hover:bg-app-item-hover text-app-text-muted hover:text-app-text transition-colors flex items-center gap-1.5"
          >
            <span>Research Workspace</span>
            <ExternalLink size={12} />
          </Link>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 max-w-6xl w-full mx-auto p-4 md:p-6 flex flex-col md:flex-row gap-6">
        {/* Navigation Tabs Menu */}
        <nav className="w-full md:w-56 shrink-0 space-y-1">
          <button
            onClick={() => setActiveTab("llm")}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
              activeTab === "llm"
                ? "bg-app-item-active text-app-text shadow-sm"
                : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
            }`}
          >
            <Cpu size={15} className={activeTab === "llm" ? "text-blue-500" : "text-app-text-dim"} />
            <span>Model Gateways</span>
          </button>

          <button
            onClick={() => setActiveTab("storage")}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
              activeTab === "storage"
                ? "bg-app-item-active text-app-text shadow-sm"
                : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
            }`}
          >
            <HardDrive size={15} className={activeTab === "storage" ? "text-blue-500" : "text-app-text-dim"} />
            <span>Storage & S3</span>
          </button>

          <button
            onClick={() => setActiveTab("secrets")}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
              activeTab === "secrets"
                ? "bg-app-item-active text-app-text shadow-sm"
                : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
            }`}
          >
            <KeyRound size={15} className={activeTab === "secrets" ? "text-blue-500" : "text-app-text-dim"} />
            <span>Secret Vaults</span>
          </button>

          <button
            onClick={() => setActiveTab("embedding")}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
              activeTab === "embedding"
                ? "bg-app-item-active text-app-text shadow-sm"
                : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
            }`}
          >
            <Binary size={15} className={activeTab === "embedding" ? "text-blue-500" : "text-app-text-dim"} />
            <span>Embedding Engine</span>
          </button>

          <button
            onClick={() => setActiveTab("health")}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
              activeTab === "health"
                ? "bg-app-item-active text-app-text shadow-sm"
                : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
            }`}
          >
            <Activity size={15} className={activeTab === "health" ? "text-blue-500" : "text-app-text-dim"} />
            <span>System Health</span>
          </button>
        </nav>

        {/* Tab Content Canvas */}
        <main className="flex-1 min-w-0 bg-app-card border border-app-border rounded-2xl p-5 md:p-6 shadow-sm">
          {isLoading ? (
            <div className="py-20 flex flex-col items-center justify-center text-app-text-dim gap-3">
              <RefreshCw size={22} className="animate-spin text-blue-500" />
              <span className="text-xs">Loading Management Plane...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2.5">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          ) : config ? (
            <>
              {activeTab === "llm" && (
                <LLMTab config={config.llm} backendUrl={backendUrl} onSaved={fetchConfig} />
              )}
              {activeTab === "storage" && (
                <StorageTab config={config.storage} backendUrl={backendUrl} onSaved={fetchConfig} />
              )}
              {activeTab === "secrets" && (
                <SecretsTab config={config.secrets} backendUrl={backendUrl} onSaved={fetchConfig} />
              )}
              {activeTab === "embedding" && (
                <EmbeddingTab
                  config={config.embedding}
                  rerankerConfig={config.reranker}
                  backendUrl={backendUrl}
                  onSaved={fetchConfig}
                />
              )}
              {activeTab === "health" && (
                <SystemHealthTab
                  health={health}
                  backendUrl={backendUrl}
                  onRefresh={fetchHealth}
                  isLoading={false}
                />
              )}
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
