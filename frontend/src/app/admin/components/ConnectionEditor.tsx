"use client";

import { useState } from "react";
import type { GatewayProfile } from "@/types/admin";
import { useTranslation } from "@/lib/i18n";
import { AdminDialog, DiscardDialog, FeedbackMessage, SecretField, TestFeedback, useDraftGuard, useExplicitTest, type Feedback } from "./AdminForms";

interface ConnectionEditorProps {
  profile?: GatewayProfile;
  backendUrl: string;
  busy: boolean;
  uncertain?: boolean;
  onReload: () => Promise<void>;
  onSave: (profile: GatewayProfile, key: string) => Promise<boolean>;
  onClose: () => void;
}

const PRESETS = [
  { name: "OpenAI", protocol: "openai", url: "https://api.openai.com/v1" },
  { name: "Anthropic", protocol: "anthropic", url: "https://api.anthropic.com/v1" },
  { name: "DeepSeek", protocol: "openai", url: "https://api.deepseek.com/v1" },
  { name: "Groq", protocol: "openai", url: "https://api.groq.com/openai/v1" },
  { name: "OpenRouter", protocol: "openai", url: "https://openrouter.ai/api/v1" },
  { name: "xAI", protocol: "openai", url: "https://api.x.ai/v1" },
  { name: "Ollama", protocol: "openai", url: "http://localhost:11434/v1" },
] as const;

export default function ConnectionEditor({ profile, backendUrl, busy, uncertain, onReload, onSave, onClose }: ConnectionEditorProps) {
  const { t } = useTranslation();
  const [profileId] = useState(() => profile?.id || `profile_${crypto.randomUUID()}`);
  const [name, setName] = useState(profile?.name || "");
  const [protocol, setProtocol] = useState<"openai" | "anthropic">(profile?.protocol || "openai");
  const [url, setUrl] = useState(profile?.base_url || "");
  const [key, setKey] = useState("");
  const [model, setModel] = useState("");
  const [presetName, setPresetName] = useState("");
  const [discard, setDiscard] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const test = useExplicitTest(backendUrl, "llm");
  const dirty = name !== (profile?.name || "") || protocol !== (profile?.protocol || "openai") || url !== (profile?.base_url || "") || !!key || !!model;
  useDraftGuard(dirty, busy || test.pending);
  const sameDestination = !!profile && url.trim().replace(/\/$/, "") === profile.base_url.replace(/\/$/, "") && protocol === (profile.protocol || "openai");
  const storedKeyAvailable = sameDestination && profile.has_api_key;
  const nativeModelSupported = protocol !== "anthropic" || (model.toLowerCase().includes("claude") && !model.startsWith("gpt-"));
  const canTest = !!url.trim() && !!model.trim() && (!!key.trim() || storedKeyAvailable) && nativeModelSupported;
  const close = () => { if (!busy && !test.pending) { if (dirty) setDiscard(true); else onClose(); } };
  const changeTestInput = (update: () => void) => { test.invalidate(); setFeedback(null); update(); };

  return <>
    <AdminDialog className="admin-connection-dialog" title={t(profile ? "admin.editConnection" : "admin.addConnection")} description={t("admin.connectionFormHelp")} onClose={close} busy={busy || test.pending}>
      <form className="admin-editor-form" onSubmit={async (event) => {
        event.preventDefault();
        if (busy) return;
        setFeedback(null);
        const saved = await onSave({
          ...profile,
          id: profileId,
          name: name.trim(),
          base_url: url.trim(),
          protocol,
          api_key_masked: profile?.api_key_masked || "",
          has_api_key: profile?.has_api_key || !!key.trim(),
          models: profile?.models || [],
        }, key.trim());
        if (saved) { setKey(""); onClose(); }
        else setFeedback({ text: t("admin.saveUnconfirmed"), error: true });
      }}>
        <div className="admin-editor-body">
        <fieldset disabled={busy}>
          <div className="admin-grid">
            <div className="admin-field admin-wide">
              <label htmlFor="connection-preset">{t("admin.preset")}</label>
              <select id="connection-preset" value={presetName} onChange={(event) => {
                const preset = PRESETS.find((item) => item.name === event.target.value);
                setPresetName(event.target.value);
                if (preset) changeTestInput(() => { setUrl(preset.url); setProtocol(preset.protocol); if (!name.trim() || name === presetName) setName(preset.name); });
              }}><option value="">{t("admin.customEndpoint")}</option>{PRESETS.map((preset) => <option key={preset.name}>{preset.name}</option>)}</select>
            </div>
            <div className="admin-field">
              <label htmlFor="connection-name">{t("admin.connectionName")}</label>
              <input id="connection-name" value={name} onChange={(event) => setName(event.target.value)} required autoFocus autoComplete="off" />
            </div>
            <div className="admin-field">
              <label htmlFor="connection-protocol">{t("admin.protocol")}</label>
              <select id="connection-protocol" value={protocol} onChange={(event) => changeTestInput(() => setProtocol(event.target.value as typeof protocol))}>
                <option value="openai">OpenAI-compatible</option><option value="anthropic">Anthropic</option>
              </select>
            </div>
            <div className="admin-field admin-wide">
              <label htmlFor="connection-url">{t("admin.baseUrl")}</label>
              <input id="connection-url" type="url" value={url} onChange={(event) => changeTestInput(() => setUrl(event.target.value))} placeholder="https://api.example.com/v1" required aria-describedby="connection-url-help" />
              <small id="connection-url-help">{t("admin.endpointHelp")}</small>
            </div>
            <div className="admin-wide"><SecretField id="connection-key" label={t("admin.apiKey")} value={key} onChange={(value) => changeTestInput(() => setKey(value))} configured={storedKeyAvailable} /></div>
          </div>
          {!sameDestination && profile?.has_api_key && <p className="admin-notice">{t("admin.newDestinationKey")}</p>}
          <details className="admin-disclosure admin-test-disclosure">
            <summary>{t("admin.verifyConnection")}</summary>
            <div className="admin-disclosure-content">
            <p className="admin-help">{t("admin.testCost")}</p>
            <div className="admin-field" style={{ marginTop: 14 }}>
              <label htmlFor="connection-test-model">{t("admin.testModel")}</label>
              <input id="connection-test-model" value={model} onChange={(event) => changeTestInput(() => setModel(event.target.value))} list="connection-test-models" aria-describedby="connection-test-help" />
              <datalist id="connection-test-models">{profile?.models?.map((item) => <option key={item.id} value={item.id} />)}</datalist>
              <small id="connection-test-help">{t("admin.testModelHelp")}</small>
              {protocol === "anthropic" && <small>{t("admin.nativeTestHelp")}</small>}
            </div>
            <div className="admin-actions" style={{ marginTop: 14 }}>
              <button className="admin-button" type="button" disabled={!canTest || test.pending} onClick={() => test.run({ base_url: url.trim(), protocol, model: model.trim(), ...(key.trim() ? { api_key: key.trim() } : {}), ...(storedKeyAvailable ? { profile_id: profile.id } : {}) })}>{t("admin.testConnection")}</button>
            </div>
            <TestFeedback result={test.result} pending={test.pending} />
            </div>
          </details>
        </fieldset>
        {uncertain && <div className="admin-notice"><p>{t("admin.reconcileHelp")}</p><button className="admin-button" type="button" disabled={busy} onClick={onReload}>{t("admin.reloadSaved")}</button></div>}
        </div>
        <div className="admin-editor-footer">
        <div className="admin-editor-status">{feedback ? <FeedbackMessage feedback={feedback} /> : <p className="admin-help">{t("admin.saveIsNotTest")}</p>}</div>
        <div className="admin-actions admin-dialog-actions">
          <button className="admin-button admin-quiet" type="button" disabled={busy || test.pending} onClick={close}>{t("admin.cancel")}</button>
          <button className="admin-button admin-primary" type="submit" aria-busy={busy} disabled={busy || uncertain || test.pending || !name.trim() || !url.trim()}><span style={{ visibility: busy ? "hidden" : undefined }}>{t("admin.saveConnection")}</span>{busy && <span className="admin-busy-label">{t("admin.saving")}</span>}</button>
        </div>
        </div>
      </form>
    </AdminDialog>
    {discard && <DiscardDialog onStay={() => setDiscard(false)} onDiscard={() => { setKey(""); onClose(); }} />}
  </>;
}
