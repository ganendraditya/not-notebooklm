"use client";

import { useId, useRef } from "react";
import type { GatewayProfile } from "@/types/admin";
import type { LlmRouting } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n";
import { FormActions, type Feedback } from "./AdminForms";
import RoutingModelPicker from "./RoutingModelPicker";

export default function ModelRoutingForm({ profiles, draft, onChange, onSave, onCancel, busy, uncertain, dirty, feedback }: {
  profiles: GatewayProfile[];
  draft: LlmRouting;
  onChange: (draft: LlmRouting) => void;
  onSave: () => void;
  onCancel: () => void;
  busy: boolean;
  uncertain: boolean;
  dirty: boolean;
  feedback: Feedback | null;
}) {
  const { t } = useTranslation();
  const id = useId();
  const manualEntries = useRef<Partial<Record<"fast" | "fallback", HTMLDetailsElement>>>({});
  const pair = (role: "fast" | "fallback", label: string) => {
    const modelKey = role === "fast" ? "fast_model" : "fallback_model";
    const profileKey = `${role}_profile_id` as const;
    const modelList = profiles.find((profile) => profile.id === draft[profileKey])?.models || [];
    return <div className="admin-routing-choice">
      <h3>{label}</h3>
      <RoutingModelPicker profiles={profiles} profileId={draft[profileKey]} modelId={draft[modelKey] || ""} label={label} disabled={busy || !profiles.length} onSelect={(profileId, modelId) => onChange({ ...draft, [profileKey]: profileId, [modelKey]: modelId })} onManualEntry={() => {
        const entry = manualEntries.current[role];
        if (entry) { entry.open = true; requestAnimationFrame(() => entry.querySelector<HTMLInputElement>("input")?.focus()); }
      }} />
      <details className="admin-manual-entry" ref={(node) => { if (node) manualEntries.current[role] = node; else delete manualEntries.current[role]; }}>
        <summary>{t("admin.manualModelEntry")}</summary>
        <div className="admin-grid">
      <div className="admin-field">
        <label htmlFor={`${id}-${role}-connection`}>{t("admin.connectionFor", { role: label })}</label>
        <select id={`${id}-${role}-connection`} value={draft[profileKey]} onChange={(event) => onChange({ ...draft, [profileKey]: event.target.value })}>
          {!profiles.some((profile) => profile.id === draft[profileKey]) && <option value={draft[profileKey]}>{draft[profileKey] || t("admin.noConnections")}</option>}
          {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
        </select>
      </div>
      <div className="admin-field">
        <label htmlFor={`${id}-${role}-model`}>{t("admin.modelFor", { role: label })}</label>
        <input id={`${id}-${role}-model`} value={draft[modelKey] || ""} list={`${id}-${role}-models`} onChange={(event) => onChange({ ...draft, [modelKey]: event.target.value })} />
        <datalist id={`${id}-${role}-models`}>{modelList.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}</datalist>
      </div>
        </div>
      </details>
    </div>;
  };
  return <form onSubmit={(event) => { event.preventDefault(); onSave(); }} className="admin-routing-panel" aria-label={t("admin.advancedRouting")}>
    <p className="admin-help admin-defaults-help">{t("admin.routingHelp")}</p>
    <fieldset disabled={busy || !profiles.length}>
      {pair("fast", t("admin.quickRole"))}
      <div style={{ marginTop: 18 }}>{pair("fallback", t("admin.backupRole"))}</div>
      <div className="admin-field" style={{ marginTop: 18 }}>
        <label htmlFor={`${id}-temperature`}>{t("admin.temperature")}</label>
        <input id={`${id}-temperature`} type="number" min="0" max="2" step="any" value={draft.temperature} onChange={(event) => onChange({ ...draft, temperature: Number(event.target.value) })} required />
        <small>{t("admin.temperatureHelp")}</small>
      </div>
    </fieldset>
    <FormActions dirty={dirty && !!profiles.length} busy={busy} saveDisabled={uncertain} onCancel={onCancel} saveLabel={t("admin.saveRouting")} feedback={feedback} />
  </form>;
}
