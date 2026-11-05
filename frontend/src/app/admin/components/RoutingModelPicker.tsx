"use client";

import { useId, useRef, useState } from "react";
import { Popover } from "@base-ui/react/popover";
import { Check, ChevronDown } from "lucide-react";
import type { GatewayProfile } from "@/types/admin";
import { useTranslation } from "@/lib/i18n";

interface RoutingModelPickerProps {
  profiles: GatewayProfile[];
  profileId: string;
  modelId: string;
  label: string;
  disabled: boolean;
  onSelect: (profileId: string, modelId: string) => void;
  onManualEntry: () => void;
}

export default function RoutingModelPicker({ profiles, profileId, modelId, label, disabled, onSelect, onManualEntry }: RoutingModelPickerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const id = useId();
  const profile = profiles.find((item) => item.id === profileId);
  const selected = profile?.models?.find((item) => item.id === modelId);
  const name = selected?.name || modelId || t("admin.chooseModel");
  const term = query.trim().toLocaleLowerCase();
  const groups = profiles.map((connection) => ({
    connection,
    models: (connection.models || []).filter((model) => `${model.name || ""} ${model.id} ${connection.name}`.toLocaleLowerCase().includes(term)),
  })).filter((group) => group.models.length);

  return <Popover.Root open={open && !disabled} onOpenChange={(next) => { setOpen(next); if (!next) setQuery(""); }}>
    <Popover.Trigger className="admin-model-trigger" disabled={disabled} aria-label={t("admin.chooseRoleModel", { role: label, model: name })}>
      <span className="admin-model-selection"><strong>{name}</strong><span>{profile?.name || profileId || t("admin.noConnections")}{selected?.name && selected.name !== modelId && <> · <code>{modelId}</code></>}</span></span>
      <ChevronDown size={18} aria-hidden="true" />
    </Popover.Trigger>
    <Popover.Portal>
      <Popover.Positioner side="bottom" align="start" sideOffset={8} collisionPadding={16} className="admin-popover-positioner">
        <Popover.Popup className="admin-control admin-model-picker" initialFocus={searchRef} aria-label={t("admin.chooseRoleModel", { role: label, model: name })}>
          <div className="admin-picker-search admin-field"><label htmlFor={id}>{t("admin.searchModels")}</label><input ref={searchRef} id={id} type="search" value={query} onChange={(event) => setQuery(event.target.value)} autoComplete="off" /></div>
          <div className="admin-picker-results">
            {!groups.length && <p className="admin-help admin-picker-empty" role="status">{t("admin.noMatchingModels")}</p>}
            {groups.map(({ connection, models }) => <section key={connection.id} aria-label={connection.name}>
              <h3>{connection.name}</h3>
              {models.map((model) => <button type="button" className="admin-picker-option" key={model.id} aria-pressed={connection.id === profileId && model.id === modelId} onClick={() => { onSelect(connection.id, model.id); setOpen(false); setQuery(""); }}>
                <span><strong>{model.name || model.id}</strong>{model.name && model.name !== model.id && <> <code>{model.id}</code></>}</span>
                {connection.id === profileId && model.id === modelId && <Check size={16} aria-hidden="true" />}
              </button>)}
            </section>)}
          </div>
          <Popover.Close className="admin-picker-manual" onClick={onManualEntry}>{t("admin.manualModelEntry")}</Popover.Close>
        </Popover.Popup>
      </Popover.Positioner>
    </Popover.Portal>
  </Popover.Root>;
}
