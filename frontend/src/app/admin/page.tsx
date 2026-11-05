"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { AdminConfig, AdminSystemHealth } from "@/types/admin";
import { adminRequest, loadAdminConfig } from "@/lib/admin-api";
import type { ConfigUpdate } from "@/lib/admin-api";
import type { ConfigSection } from "@/lib/admin-config";
import { parseAdminPersistence } from "@/lib/admin-persistence";
import { useTranslation } from "@/lib/i18n";
import LLMTab from "./components/LLMTab";
import StorageTab from "./components/StorageTab";
import SecretsTab from "./components/SecretsTab";
import EmbeddingTab from "./components/EmbeddingTab";
import SystemHealthTab from "./components/SystemHealthTab";
import PersistenceNotice from "./components/PersistenceNotice";
import { AdminDraftContext, DiscardDialog, type DraftState } from "./components/AdminForms";
import "./admin.css";

const SECTIONS = [
  { id: "llm", label: "admin.models", help: "admin.modelsHelp" },
  { id: "storage", label: "admin.fileStorage", help: "admin.fileStorageHelp" },
  { id: "embedding", label: "admin.documentSearch", help: "admin.documentSearchHelp" },
  { id: "secrets", label: "admin.configurationSource", help: "admin.configurationSourceHelp" },
  { id: "health", label: "admin.systemStatus", help: "admin.systemStatusHelp" },
] as const;
type SectionId = (typeof SECTIONS)[number]["id"];

export default function AdminPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const [active, setActive] = useState<SectionId>("llm");
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [guards, setGuards] = useState<Record<string, DraftState>>({});
  const [pendingNavigation, setPendingNavigation] = useState<(() => void) | null>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const healthLock = useRef(false);
  const configGeneration = useRef(0);
  const setGuard = useCallback((id: string, state: DraftState | null) => setGuards((previous) => {
    if (!state) { const next = { ...previous }; delete next[id]; return next; }
    if (previous[id]?.dirty === state.dirty && previous[id]?.busy === state.busy) return previous;
    return { ...previous, [id]: state };
  }), []);
  const dirty = Object.values(guards).some((guard) => guard.dirty);
  const busy = Object.values(guards).some((guard) => guard.busy);
  const section = SECTIONS.find((item) => item.id === active)!;
  const fetchConfig = useCallback(async () => {
    const generation = ++configGeneration.current;
    setError(false);
    try {
      const data = await loadAdminConfig(backendUrl);
      if (generation === configGeneration.current) setConfig(data);
    } catch { if (generation === configGeneration.current) setError(true); }
    finally { if (generation === configGeneration.current) setLoading(false); }
  }, [backendUrl]);
  const publishSection = <K extends ConfigSection>(section: K, update: ConfigUpdate<NonNullable<AdminConfig[K]>>) => {
    configGeneration.current += 1;
    setConfig((previous) => previous && { ...previous, [section]: update.config, ...(update.persistence ? { persistence: update.persistence } : {}) });
  };
  const fetchHealth = useCallback(async () => {
    if (healthLock.current) return;
    healthLock.current = true;
    setHealthLoading(true); setHealthError(false);
    try {
      const data = await adminRequest<AdminSystemHealth>(backendUrl, "system/health");
      if (!data || typeof data !== "object") throw new Error("Status unavailable");
      setHealth(data); setUpdatedAt(new Date().toLocaleString());
    } catch { setHealthError(true); }
    finally { setHealthLoading(false); healthLock.current = false; }
  }, [backendUrl]);
  useEffect(() => { void fetchConfig(); }, [fetchConfig]);
  useEffect(() => { if (active === "health") void fetchHealth(); }, [active, fetchHealth]);
  useEffect(() => {
    if (!dirty && !busy) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [dirty, busy]);
  const navigate = (action: () => void) => {
    if (busy) return;
    if (dirty) setPendingNavigation(() => action);
    else action();
  };
  const selectSection = (id: SectionId) => {
    if (id === active) return;
    navigate(() => { setActive(id); requestAnimationFrame(() => titleRef.current?.focus({ preventScroll: true })); });
  };
  const persistence = parseAdminPersistence(config?.persistence);

  return <AdminDraftContext.Provider value={setGuard}>
    <div className="admin-control min-h-screen bg-app-bg">
      <a className="admin-button admin-skip" href="#configuration-content">{t("admin.skipNavigation")}</a>
      <header className="admin-header"><div className="admin-brand"><strong>NotbookLM</strong><span>{t("admin.title")}</span></div>
        <Link className="admin-button admin-quiet" href="/" aria-disabled={busy} onClick={(event) => {
          if (event.ctrlKey || event.metaKey || event.shiftKey) return;
          if (dirty || busy) { event.preventDefault(); navigate(() => router.push("/")); }
        }}>{t("admin.backToApp")}</Link>
      </header>
      <div className="admin-layout">
        <nav className="admin-nav" aria-label={t("admin.navigation")}>
          {SECTIONS.map((item) => <button type="button" key={item.id} className="admin-nav-button" aria-current={active === item.id ? "page" : undefined} onClick={() => selectSection(item.id)} disabled={busy}>{t(item.label)}</button>)}
        </nav>
        <main id="configuration-content" className="admin-main">
          <div className="admin-mobile-nav"><label htmlFor="configuration-section">{t("admin.navigation")}</label><select id="configuration-section" value={active} disabled={busy} onChange={(event) => selectSection(event.target.value as SectionId)}>{SECTIONS.map((item) => <option key={item.id} value={item.id}>{t(item.label)}</option>)}</select></div>
          <div className="admin-page-heading"><h1 ref={titleRef} tabIndex={-1}>{t(section.label)}</h1><p>{t(section.help)}</p></div>
          {loading && <p role="status">{t("admin.loadingConfiguration")}</p>}
          {error && <div role="alert" className="admin-notice"><p>{t(config ? "admin.configRefreshFailed" : "admin.loadFailed")}</p><button className="admin-button" onClick={() => { if (!config) setLoading(true); void fetchConfig(); }}>{t("admin.retry")}</button></div>}
          {config && <>
            {persistence?.mode !== "local_env" && <PersistenceNotice persistence={persistence} />}
            {active === "llm" && <LLMTab config={config.llm} backendUrl={backendUrl} onSaved={(update) => publishSection("llm", update)} />}
            {active === "storage" && <StorageTab config={config.storage} backendUrl={backendUrl} onSaved={(update) => publishSection("storage", update)} />}
            {active === "embedding" && <EmbeddingTab config={config.embedding} rerankerConfig={config.reranker} backendUrl={backendUrl} onSaved={(update) => publishSection("embedding", update)} onRerankerSaved={(update) => publishSection("reranker", update)} />}
            {active === "secrets" && <SecretsTab config={config.secrets} persistence={persistence} />}
            {persistence?.mode === "local_env" && active !== "health" && active !== "secrets" && <PersistenceNotice persistence={persistence} />}
          </>}
          {active === "health" && <SystemHealthTab health={health} onRefresh={fetchHealth} isLoading={healthLoading} error={healthError} updatedAt={updatedAt} />}
        </main>
      </div>
      {pendingNavigation && <DiscardDialog onStay={() => setPendingNavigation(null)} onDiscard={() => { const action = pendingNavigation; setPendingNavigation(null); action(); }} />}
    </div>
  </AdminDraftContext.Provider>;
}
