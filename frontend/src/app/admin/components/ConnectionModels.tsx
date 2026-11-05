"use client";

import { useEffect, useRef, useState } from "react";
import { Menu } from "@base-ui/react/menu";
import { Ellipsis } from "lucide-react";
import type { GatewayProfile, ProfileModelItem } from "@/types/admin";
import { useTranslation } from "@/lib/i18n";
import { AdminDialog, useDraftGuard } from "./AdminForms";

const MAX_DISPLAY_NAME_LENGTH = 64;

export default function ConnectionModels({ profile, busy, blocked = false, onDraftChange, onSave }: { profile: GatewayProfile; busy: boolean; blocked?: boolean; onDraftChange: (dirty: boolean) => void; onSave: (models: ProfileModelItem[]) => Promise<boolean> }) {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<ProfileModelItem | null>(null);
  const [modelId, setModelId] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [removing, setRemoving] = useState<ProfileModelItem | null>(null);
  const actionTriggers = useRef<Record<string, HTMLButtonElement | null>>({});
  const returnFocusRef = useRef<HTMLButtonElement | null>(null);
  const registerButtonRef = useRef<HTMLButtonElement | null>(null);
  const models = profile.models || [];
  const dirty = editing ? name !== (editing.name || editing.id) : adding && (!!modelId || !!name);
  const labelTooLong = name.length > MAX_DISPLAY_NAME_LENGTH;
  useDraftGuard(dirty, busy);
  useEffect(() => onDraftChange(!!dirty), [dirty, onDraftChange]);
  return <div className="admin-model-list">
    <div className="admin-section-heading admin-task-heading"><h2>{t("admin.pickerModels")}</h2>
      <button ref={registerButtonRef} type="button" className="admin-button admin-primary" disabled={busy || blocked || adding || !!editing} onClick={() => setAdding(true)}>{t("admin.registerModel")}</button>
      <p className="admin-help">{t("admin.providerModelsHelp", { name: profile.name })}</p>
    </div>
    {!models.length && <p className="admin-help">{t("admin.noRegisteredModels")}</p>}
    {models.map((model) => <div className="admin-model-row" key={model.id}>
      <div className="admin-model-name"><span>{model.name || model.id}</span>{model.name && model.name !== model.id && <small><code>{model.id}</code></small>}</div>
      <div className="admin-actions">
        <label className="admin-checkbox"><input type="checkbox" checked={model.enabled} disabled={busy || blocked} aria-label={t("admin.showModel", { model: model.id })} onChange={() => onSave(models.map((item) => item.id === model.id ? { ...item, enabled: !item.enabled } : item))} />{t("admin.showInPicker")}</label>
        <Menu.Root>
          <Menu.Trigger ref={(node: HTMLButtonElement | null) => { if (node) actionTriggers.current[model.id] = node; else delete actionTriggers.current[model.id]; }} className="admin-button admin-icon-button admin-quiet" disabled={busy || blocked} aria-label={t("admin.modelActions", { model: model.id })}><Ellipsis size={18} aria-hidden="true" /></Menu.Trigger>
          <Menu.Portal><Menu.Positioner align="end" sideOffset={6} collisionPadding={12} className="admin-popover-positioner"><Menu.Popup className="admin-control admin-row-menu">
            <Menu.Item className="admin-menu-item" disabled={adding || !!editing} aria-label={t("admin.editModelLabel", { model: model.id })} onClick={() => { setEditing(model); setModelId(model.id); setName(model.name || model.id); }}>{t("admin.editLabel")}</Menu.Item>
            <Menu.Item className="admin-menu-item admin-danger" aria-label={t("admin.removeModelNamed", { model: model.id })} onClick={() => { returnFocusRef.current = actionTriggers.current[model.id]; setRemoving(model); }}>{t("admin.remove")}</Menu.Item>
          </Menu.Popup></Menu.Positioner></Menu.Portal>
        </Menu.Root>
      </div>
    </div>)}
    {!models.some((model) => model.enabled) && <p className="admin-notice">{t("admin.emptyPickerFallback")}</p>}
    {(adding || editing) && <form className="admin-inline-form" onSubmit={async (event) => {
      event.preventDefault();
      const identifier = modelId.trim();
      if (!identifier || busy || blocked || labelTooLong) return;
      if (!editing && models.some((model) => model.id === identifier)) { setError(t("admin.duplicateModel")); return; }
      const next = editing ? models.map((model) => model.id === editing.id ? { ...model, name: name.trim() || model.id } : model) : [...models, { id: identifier, name: name.trim() || identifier, enabled: true }];
      if (await onSave(next)) { const target = editing ? actionTriggers.current[editing.id] : registerButtonRef.current; setModelId(""); setName(""); setError(""); setAdding(false); setEditing(null); requestAnimationFrame(() => target?.focus()); }
    }}>
      <h3 className="admin-inline-form-title">{t(editing ? "admin.editLabel" : "admin.addModelTo", { name: profile.name })}</h3>
      <fieldset disabled={busy || blocked}><div className="admin-grid">
        <div className="admin-field"><label htmlFor={`${profile.id}-model-id`}>{t("admin.modelId")}</label><input id={`${profile.id}-model-id`} autoFocus={!editing} readOnly={!!editing} value={modelId} required onChange={(event) => { setError(""); setModelId(event.target.value); }} /></div>
        <div className="admin-field"><label htmlFor={`${profile.id}-model-name`}>{t("admin.displayName")}</label><input id={`${profile.id}-model-name`} autoFocus={!!editing} value={name} maxLength={MAX_DISPLAY_NAME_LENGTH} aria-describedby={`${profile.id}-model-name-limit`} aria-invalid={labelTooLong || undefined} onChange={(event) => setName(event.target.value)} /><small id={`${profile.id}-model-name-limit`}>{t("admin.modelLabelLimit", { max: String(MAX_DISPLAY_NAME_LENGTH) })} ({name.length}/{MAX_DISPLAY_NAME_LENGTH})</small></div>
      </div></fieldset>
      {(labelTooLong || error) && <p role="alert" className="admin-error">{labelTooLong ? t("admin.modelLabelTooLong", { max: String(MAX_DISPLAY_NAME_LENGTH) }) : error}</p>}
      <div className="admin-actions"><button className="admin-button" type="button" disabled={busy} onClick={() => { const target = editing ? actionTriggers.current[editing.id] : registerButtonRef.current; setAdding(false); setEditing(null); setModelId(""); setName(""); setError(""); requestAnimationFrame(() => target?.focus()); }}>{t("admin.cancel")}</button><button className="admin-button admin-primary" disabled={busy || blocked || !modelId.trim() || !dirty || labelTooLong} type="submit">{t(editing ? "admin.saveLabel" : "admin.registerModel")}</button></div>
      <p className="admin-help">{t("admin.registrationNotTest")}</p>
    </form>}
    {removing && <AdminDialog returnFocusRef={returnFocusRef} title={t("admin.removeModelTitle")} description={t("admin.removeModelHelp", { model: removing.id })} busy={busy} onClose={() => setRemoving(null)}>
      <div className="admin-actions admin-dialog-actions"><button className="admin-button" disabled={busy} onClick={() => { setError(""); setRemoving(null); }}>{t("admin.cancel")}</button><button className="admin-button admin-danger" disabled={busy || blocked} onClick={async () => { if (await onSave(models.filter((model) => model.id !== removing.id))) { returnFocusRef.current = registerButtonRef.current; setError(""); setRemoving(null); } else setError(t("admin.operationUnconfirmed")); }}>{t("admin.remove")}</button></div>
      {error && <p role="alert" className="admin-error">{error}</p>}
    </AdminDialog>}
  </div>;
}
