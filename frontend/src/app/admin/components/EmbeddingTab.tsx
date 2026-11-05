"use client";

import { useState } from "react";
import type { AdminConfig } from "@/types/admin";
import { saveAdminSection } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n";
import { FormActions, SecretField, TestFeedback, useDraftGuard, useExplicitTest, usePersistenceFeedback, type Feedback } from "./AdminForms";

const LOCAL_MODELS = ["sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "intfloat/multilingual-e5-large"];
const RERANKER_MODELS = ["ms-marco-TinyBERT-L-2-v2", "ms-marco-MiniLM-L-12-v2", "ms-marco-MultiBERT-L-12", "rank-T5-flan"];
const embeddingDraft = (config: AdminConfig["embedding"]) => ({
  provider: config.provider,
  local_model: config.local_model,
  gemini_model: config.gemini_model,
  custom_base_url: config.custom_base_url || "",
  custom_model_name: config.custom_model_name || "",
  custom_local_path: config.custom_local_path || "",
  gemini_key: "",
  custom_key: "",
});

function EmbeddingForm({ config, backendUrl, onSaved }: { config: AdminConfig["embedding"]; backendUrl: string; onSaved: () => void }) {
  const { t } = useTranslation();
  const describePersistence = usePersistenceFeedback();
  const [saved, setSaved] = useState(config);
  const [draft, setDraft] = useState(() => embeddingDraft(config));
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const test = useExplicitTest(backendUrl, "embeddings");
  const dirty = JSON.stringify(draft) !== JSON.stringify(embeddingDraft(saved));
  useDraftGuard(dirty, busy || test.pending);
  const update = <K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) => { test.invalidate(); setFeedback(null); setDraft({ ...draft, [key]: value }); };
  return <form className="admin-form-panel" aria-label={t("admin.embeddings")} onSubmit={async (event) => {
    event.preventDefault(); if (busy) return;
    setBusy(true); setFeedback(null);
    try {
      const result = await saveAdminSection(backendUrl, "embedding", { ...draft, custom_key: draft.custom_key.trim() || undefined, gemini_key: draft.gemini_key.trim() || undefined });
      setSaved(result.config); setDraft(embeddingDraft(result.config)); test.invalidate();
      setFeedback({ text: `${t("admin.embeddings")}: ${describePersistence(result.persistence)}` }); onSaved();
    } catch { setFeedback({ text: `${t("admin.embeddings")}: ${t("admin.saveUnconfirmed")}`, error: true }); }
    finally { setBusy(false); }
  }}>
    <div className="admin-section-heading"><div><h2>{t("admin.embeddings")}</h2><p className="admin-help">{t("admin.embeddingsHelp")}</p></div></div>
    <fieldset disabled={busy}>
      <div className="admin-field admin-service-choice"><label htmlFor="embedding-provider">{t("admin.embeddingProvider")}</label><select id="embedding-provider" value={draft.provider} onChange={(event) => update("provider", event.target.value as typeof draft.provider)}>
        <option value="local">{t("admin.localEmbeddings")}</option><option value="openai">OpenAI-compatible</option><option value="gemini">Google Gemini</option><option value="custom">{t("admin.customPath")}</option>
      </select></div>
      {draft.provider === "local" && <div className="admin-field admin-field-group"><label htmlFor="embedding-local-model">{t("admin.embeddingModel")}</label><select id="embedding-local-model" value={draft.local_model} onChange={(event) => update("local_model", event.target.value)}>
        {[...new Set([draft.local_model, ...LOCAL_MODELS])].filter(Boolean).map((model) => <option key={model}>{model}</option>)}
      </select><small>{t("admin.localDownloadHelp")}</small></div>}
      {draft.provider === "openai" && <>
        <div className="admin-grid admin-field-group">
          <div className="admin-field admin-wide"><label htmlFor="embedding-url">{t("admin.baseUrl")}</label><input id="embedding-url" type="url" required value={draft.custom_base_url} onChange={(event) => update("custom_base_url", event.target.value)} /></div>
          <div className="admin-field"><label htmlFor="embedding-model">{t("admin.embeddingModel")}</label><input id="embedding-model" required value={draft.custom_model_name} onChange={(event) => update("custom_model_name", event.target.value)} /></div>
          <SecretField id="embedding-key" label={t("admin.apiKey")} value={draft.custom_key} onChange={(value) => update("custom_key", value)} configured={saved.has_custom_key} />
        </div>
        <details className="admin-disclosure admin-test-disclosure"><summary>{t("admin.optionalEmbeddingTest")}</summary><div className="admin-disclosure-content">
          <p className="admin-help">{t("admin.embeddingTestHelp")}</p>
          <div className="admin-actions"><button type="button" className="admin-button" disabled={test.pending || !draft.custom_base_url || !draft.custom_model_name || (draft.custom_base_url !== saved.custom_base_url && !draft.custom_key.trim())} onClick={() => test.run({ base_url: draft.custom_base_url, model_name: draft.custom_model_name, api_key: draft.custom_key.trim() || undefined })}>{t("admin.testEmbeddings")}</button></div>
          <TestFeedback result={test.result} pending={test.pending} />
        </div></details>
      </>}
      {draft.provider === "gemini" && <div className="admin-grid admin-field-group">
        <div className="admin-field"><label htmlFor="embedding-gemini-model">{t("admin.embeddingModel")}</label><input id="embedding-gemini-model" required value={draft.gemini_model} onChange={(event) => update("gemini_model", event.target.value)} /></div>
        <SecretField id="embedding-gemini-key" label={t("admin.apiKey")} value={draft.gemini_key} onChange={(value) => update("gemini_key", value)} configured={saved.has_gemini_key} />
      </div>}
      {draft.provider === "custom" && <div className="admin-field admin-field-group"><label htmlFor="embedding-path">{t("admin.modelPath")}</label><input id="embedding-path" required value={draft.custom_local_path} onChange={(event) => update("custom_local_path", event.target.value)} /><small>{t("admin.modelPathHelp")}</small></div>}
      <p className="admin-notice admin-warning">{t("admin.embeddingChangeWarning")}</p>
    </fieldset>
    <FormActions dirty={dirty} busy={busy} pending={test.pending} onCancel={() => { setDraft(embeddingDraft(saved)); test.invalidate(); setFeedback(null); }} saveLabel={t("admin.saveEmbeddings")} feedback={feedback} />
  </form>;
}

function RerankerForm({ config, backendUrl, onSaved }: { config?: AdminConfig["reranker"]; backendUrl: string; onSaved: () => void }) {
  const { t } = useTranslation();
  const describePersistence = usePersistenceFeedback();
  const [saved, setSaved] = useState(config);
  const [draft, setDraft] = useState({ model: config?.model || "", top_n: config?.top_n ?? 12 });
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const test = useExplicitTest(backendUrl, "reranker");
  const dirty = draft.model !== (saved?.model || "") || draft.top_n !== (saved?.top_n ?? 12);
  useDraftGuard(dirty, busy || test.pending);
  return <form className="admin-form-panel" aria-label={t("admin.reranker")} onSubmit={async (event) => {
    event.preventDefault(); if (busy) return;
    setBusy(true); setFeedback(null);
    try {
      const result = await saveAdminSection(backendUrl, "reranker", draft);
      setSaved(result.config); setDraft(result.config); test.invalidate();
      setFeedback({ text: `${t("admin.reranker")}: ${describePersistence(result.persistence)}` }); onSaved();
    } catch { setFeedback({ text: `${t("admin.reranker")}: ${t("admin.saveUnconfirmed")}`, error: true }); }
    finally { setBusy(false); }
  }}>
    <div className="admin-section-heading"><div><h2>{t("admin.reranker")}</h2><p className="admin-help">{t("admin.rerankerHelp")}</p></div></div>
    <fieldset disabled={busy}><div className="admin-grid">
      <div className="admin-field"><label htmlFor="reranker-model">{t("admin.rerankerModel")}</label><select id="reranker-model" required value={draft.model} onChange={(event) => { test.invalidate(); setFeedback(null); setDraft({ ...draft, model: event.target.value }); }}>
        {!draft.model && <option value="">{t("admin.chooseModel")}</option>}
        {[...new Set([draft.model, ...RERANKER_MODELS])].filter(Boolean).map((model) => <option key={model}>{model}</option>)}
      </select></div>
      <div className="admin-field"><label htmlFor="reranker-count">{t("admin.contextCount")}</label><input id="reranker-count" type="number" min="3" max="30" step="1" required value={draft.top_n} onChange={(event) => { setFeedback(null); setDraft({ ...draft, top_n: Number(event.target.value) }); }} /><small>{t("admin.contextCountHelp")}</small></div>
    </div>
    <details className="admin-disclosure admin-test-disclosure"><summary>{t("admin.optionalRerankerTest")}</summary><div className="admin-disclosure-content">
      <p className="admin-help">{t("admin.rerankerDownloadHelp")}</p>
      <div className="admin-actions"><button className="admin-button" type="button" disabled={test.pending || !draft.model} onClick={() => test.run({ model: draft.model })}>{t("admin.testReranker")}</button></div>
      <TestFeedback result={test.result} pending={test.pending} />
    </div></details></fieldset>
    <FormActions dirty={dirty} busy={busy} pending={test.pending} onCancel={() => { setDraft({ model: saved?.model || "", top_n: saved?.top_n ?? 12 }); test.invalidate(); setFeedback(null); }} saveLabel={t("admin.saveReranker")} feedback={feedback} />
  </form>;
}

export default function EmbeddingTab({ config, rerankerConfig, backendUrl, onSaved }: { config: AdminConfig["embedding"]; rerankerConfig?: AdminConfig["reranker"]; backendUrl: string; onSaved: () => void }) {
  const { t } = useTranslation();
  return <><EmbeddingForm config={config} backendUrl={backendUrl} onSaved={onSaved} /><RerankerForm config={rerankerConfig} backendUrl={backendUrl} onSaved={onSaved} /><p className="admin-help admin-policy-note">{t(config.hybrid_bm25_enabled ? "admin.hybridEnabled" : "admin.hybridNotReported")}</p></>;
}
