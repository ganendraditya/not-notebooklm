"use client";

import { useRef, useState } from "react";
import { ArrowLeft, ChevronRight } from "lucide-react";
import type { AdminConfig, GatewayProfile } from "@/types/admin";
import { loadAdminConfig, llmPayload, profilesFromConfig, routingFromConfig, saveAdminSection, type LlmRouting } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n";
import { AdminDialog, DiscardDialog, FeedbackMessage, useDraftGuard, usePersistenceFeedback, type Feedback } from "./AdminForms";
import ConnectionEditor from "./ConnectionEditor";
import ConnectionModels from "./ConnectionModels";
import ModelRoutingForm from "./ModelRoutingForm";

interface LLMTabProps { config: AdminConfig["llm"]; backendUrl: string; onSaved: () => void }

export default function LLMTab({ config, backendUrl, onSaved }: LLMTabProps) {
  const { t } = useTranslation();
  const persistenceFeedback = usePersistenceFeedback();
  const [saved, setSaved] = useState(config);
  const [routing, setRouting] = useState(() => routingFromConfig(config));
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [uncertain, setUncertain] = useState(false);
  const [editor, setEditor] = useState<{ profile?: GatewayProfile } | null>(null);
  const [removing, setRemoving] = useState<GatewayProfile | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [feedbackProfileId, setFeedbackProfileId] = useState<string | null>(null);
  const [routingFeedback, setRoutingFeedback] = useState<Feedback | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [modelDirty, setModelDirty] = useState(false);
  const [discardModels, setDiscardModels] = useState(false);
  const providerButtons = useRef<Record<string, HTMLButtonElement | null>>({});
  const listHeading = useRef<HTMLHeadingElement>(null);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const removeReturnFocus = useRef<HTMLElement | null>(null);
  const profiles = profilesFromConfig(saved);
  const selected = profiles.find((profile) => profile.id === selectedId);
  const dirty = JSON.stringify(routing) !== JSON.stringify(routingFromConfig(saved));
  useDraftGuard(dirty, busy);
  const showProviders = () => {
    setSelectedId(null); setModelDirty(false); setDiscardModels(false);
    requestAnimationFrame(() => providerButtons.current[selectedId || ""]?.focus());
  };
  const reloadSaved = async () => {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    setFeedbackProfileId(null);
    try {
      const current = await loadAdminConfig(backendUrl);
      setSaved(current.llm);
      if (!dirty) setRouting(routingFromConfig(current.llm));
      setUncertain(false);
      setFeedback({ text: t("admin.reconciled") });
    } catch { setFeedback({ text: t("admin.loadFailed"), error: true }); }
    finally { lock.current = false; setBusy(false); }
  };

  const write = async (nextProfiles: GatewayProfile[], nextRouting?: LlmRouting, credentials?: Record<string, string>) => {
    if (lock.current || uncertain) return false;
    lock.current = true;
    setBusy(true);
    setFeedback(null);
    try {
      const result = await saveAdminSection(backendUrl, "llm", llmPayload(saved, nextProfiles, nextRouting, credentials));
      setSaved(result.config);
      if (nextRouting) setRouting(routingFromConfig(result.config));
      else if (!dirty) setRouting(routingFromConfig(result.config));
      const message = { text: persistenceFeedback(result.persistence) };
      if (nextRouting && !removing) setRoutingFeedback(message);
      else setFeedback(message);
      onSaved();
      return true;
    } catch {
      setFeedback({ text: t("admin.saveUnconfirmed"), error: true });
      if (nextRouting && !removing) setRoutingFeedback({ text: t("admin.saveUnconfirmed"), error: true });
      setUncertain(true);
      return false;
    } finally { lock.current = false; setBusy(false); }
  };

  return <>
    {uncertain && <div className="admin-notice">
      <p>{t("admin.reconcileHelp")}</p>
      <button className="admin-button" disabled={busy} onClick={reloadSaved}>{t("admin.reloadSaved")}</button>
    </div>}
    <div hidden={!!selected}>
    <section aria-labelledby="connections-heading">
      <div className="admin-section-heading admin-task-heading">
        <h2 ref={listHeading} tabIndex={-1} id="connections-heading">{t("admin.connections")}</h2>
        <button className="admin-button admin-primary" type="button" disabled={busy || uncertain} onClick={() => { setFeedbackProfileId(null); setEditor({}); }}>{t("admin.addConnection")}</button>
        <p className="admin-help">{t("admin.connectionsHelp")}</p>
      </div>
      {!profiles.length && <div className="admin-empty"><h3>{t("admin.noConnections")}</h3><p>{t("admin.noConnectionsHelp")}</p></div>}
      {!!profiles.length && <ul className="admin-provider-list">{profiles.map((profile) => <li key={profile.id}>
        <button ref={(node) => { providerButtons.current[profile.id] = node; }} className="admin-provider-row" type="button" disabled={busy} aria-label={profile.name} aria-describedby={`provider-${profile.id}-summary`} onClick={() => {
          setSelectedId(profile.id);
          requestAnimationFrame(() => detailHeading.current?.focus());
        }}>
          <span><span className="admin-provider-name">{profile.name}</span><span id={`provider-${profile.id}-summary`} className="admin-provider-meta"><span>{profile.protocol === "anthropic" ? "Anthropic" : "OpenAI-compatible"}</span><code>{profile.base_url}</code></span></span>
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </li>)}</ul>}
    </section>
    {!!profiles.length && <details className="admin-disclosure admin-routing-settings">
      <summary>{t("admin.advancedRouting")}{dirty && <span className="admin-help">{t("admin.unsaved")}</span>}</summary>
      <div className="admin-disclosure-content"><ModelRoutingForm profiles={profiles} draft={routing} onChange={(draft) => { setRouting(draft); setRoutingFeedback(null); }} onSave={() => { setFeedbackProfileId(null); void write(profiles, routing); }} onCancel={() => { setRouting(routingFromConfig(saved)); setRoutingFeedback(null); }} busy={busy} uncertain={uncertain} dirty={dirty} feedback={routingFeedback} /></div>
    </details>}
    </div>
    {selected && <section aria-labelledby="provider-detail-heading">
      <button className="admin-button admin-quiet admin-back" type="button" disabled={busy} onClick={() => modelDirty ? setDiscardModels(true) : showProviders()}><ArrowLeft size={16} aria-hidden="true" />{t("admin.allProviders")}</button>
      <div className="admin-section-heading admin-provider-heading">
        <div><h2 ref={detailHeading} tabIndex={-1} id="provider-detail-heading">{selected.name}</h2><p className="admin-help">{selected.protocol === "anthropic" ? "Anthropic" : "OpenAI-compatible"}</p></div>
        <button className="admin-button" type="button" disabled={busy || uncertain} onClick={() => { setFeedbackProfileId(selected.id); setEditor({ profile: selected }); }}>{t("admin.editConnection")}</button>
      </div>
      <dl className="admin-definition-list admin-provider-connection"><dt>{t("admin.baseUrl")}</dt><dd><code>{selected.base_url}</code></dd><dt>{t("admin.apiKey")}</dt><dd>{t(selected.has_api_key ? "admin.keyConfigured" : "admin.keyNotConfigured")}</dd></dl>
      <ConnectionModels key={selected.id} profile={selected} busy={busy} blocked={uncertain} onDraftChange={setModelDirty} onSave={(models) => { setFeedbackProfileId(selected.id); return write(profiles.map((item) => item.id === selected.id ? { ...item, models } : item)); }} />
      {feedbackProfileId === selected.id && <FeedbackMessage feedback={feedback} />}
      {profiles.length > 1 && <div className="admin-provider-removal">
        <button className="admin-button admin-quiet admin-danger" type="button" disabled={busy || uncertain || dirty || modelDirty} onClick={(event) => { removeReturnFocus.current = event.currentTarget; setFeedbackProfileId(null); setRemoving(selected); }}>{t("admin.removeProvider")}</button>
        {dirty && <p className="admin-help">{t("admin.resolveRoutingFirst")}</p>}
      </div>}
    </section>}
    {!feedbackProfileId && <FeedbackMessage feedback={feedback} />}
    {editor && <ConnectionEditor profile={editor.profile} backendUrl={backendUrl} busy={busy} uncertain={uncertain} onReload={reloadSaved} onClose={() => setEditor(null)} onSave={(profile, key) => write(profiles.some((item) => item.id === profile.id) ? profiles.map((item) => item.id === profile.id ? profile : item) : [...profiles, profile], undefined, key ? { [profile.id]: key } : undefined)} />}
    {discardModels && <DiscardDialog onStay={() => setDiscardModels(false)} onDiscard={showProviders} />}
    {removing && <AdminDialog returnFocusRef={removeReturnFocus} title={t("admin.removeConnectionTitle")} description={t("admin.removeConnectionHelp", { name: removing.name, replacement: profiles.find((profile) => profile.id !== removing.id)?.name || "" })} onClose={() => setRemoving(null)} busy={busy}>
      <p className="admin-help">{t("admin.removeConnectionRoles", { roles: [saved.primary_profile_id === removing.id ? t("admin.mainRole") : "", saved.fast_profile_id === removing.id ? t("admin.quickRole") : "", saved.fallback_profile_id === removing.id ? t("admin.backupRole") : ""].filter(Boolean).join(", ") || t("admin.none") })}</p>
      <div className="admin-actions admin-dialog-actions">
        <button className="admin-button" disabled={busy} onClick={() => setRemoving(null)}>{t("admin.cancel")}</button>
        <button className="admin-button admin-danger" disabled={busy || uncertain} onClick={async () => {
          const remaining = profiles.filter((profile) => profile.id !== removing.id);
          const next = routingFromConfig(saved);
          if (next.primary_profile_id === removing.id) next.primary_profile_id = remaining[0].id;
          if (next.fast_profile_id === removing.id) next.fast_profile_id = next.primary_profile_id;
          if (next.fallback_profile_id === removing.id) next.fallback_profile_id = next.primary_profile_id;
          if (await write(remaining, next)) { removeReturnFocus.current = listHeading.current; setSelectedId(null); setModelDirty(false); setRemoving(null); }
        }}>{t("admin.remove")}</button>
      </div>
      <FeedbackMessage feedback={feedback} />
      {uncertain && <button className="admin-button" disabled={busy} onClick={reloadSaved}>{t("admin.reloadSaved")}</button>}
    </AdminDialog>}
  </>;
}
