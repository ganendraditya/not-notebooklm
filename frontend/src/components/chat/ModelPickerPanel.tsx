"use client";

import React, { useId, useMemo, useRef, useState } from "react";
import { Popover } from "@base-ui/react/popover";
import { Check, ChevronRight, ExternalLink, History, Plus, RefreshCw, Search, Star } from "lucide-react";
import type { WorkspaceModel } from "@/stores/chatStore";
import { modelKey } from "@/hooks/chat/useModelPreferences";
import { useTranslation } from "@/lib/i18n";

interface ModelPickerPanelProps {
  models: WorkspaceModel[];
  activeModel: WorkspaceModel;
  favorites: string[];
  recent: string[];
  isSaving: boolean;
  error: string | null;
  onSelect: (model: WorkspaceModel) => void;
  onToggleFavorite: (model: WorkspaceModel) => void;
  refreshing: boolean;
  refreshMessage: string;
  onRefresh: () => void;
}

export function ModelPickerPanel({
  models, activeModel, favorites, recent, isSaving, error, onSelect, onToggleFavorite,
  refreshing, refreshMessage, onRefresh,
}: ModelPickerPanelProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [collapsedProviders, setCollapsedProviders] = useState<Set<string>>(new Set());
  const searchRef = useRef<HTMLInputElement>(null);
  const panelId = useId();
  const search = query.trim().toLocaleLowerCase();

  const matchingModels = useMemo(() => models.filter((model) =>
    `${model.name} ${model.id} ${model.profile_name}`.toLocaleLowerCase().includes(search)
  ), [models, search]);

  const { providers, recentModels, favoriteModels } = useMemo(() => {
    const byKey = new Map(matchingModels.map((model) => [modelKey(model), model]));
    const providers = new Map<string, { name: string; models: WorkspaceModel[] }>();
    for (const model of matchingModels) {
      const provider = providers.get(model.profile_id);
      if (provider) provider.models.push(model);
      else providers.set(model.profile_id, { name: model.profile_name, models: [model] });
    }
    const resolve = (keys: string[]) => keys.flatMap((key) => {
      const model = byKey.get(key);
      return model ? [model] : [];
    });
    return { providers, recentModels: resolve(recent), favoriteModels: resolve(favorites) };
  }, [matchingModels, recent, favorites]);

  const handleNavigation = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target !== searchRef.current && !target.hasAttribute("data-model-option")) return;
    const options = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("[data-model-option]:not(:disabled)"));
    if (options.length === 0) return;
    const index = options.indexOf(target as HTMLButtonElement);
    let next: HTMLElement | undefined;
    if (event.key === "ArrowDown") next = options[Math.min(index + 1, options.length - 1)];
    else if (event.key === "ArrowUp") next = index === 0 ? searchRef.current! : options[index < 0 ? options.length - 1 : index - 1];
    else if (index >= 0 && event.key === "Home") next = options[0];
    else if (index >= 0 && event.key === "End") next = options[options.length - 1];
    if (next) {
      event.preventDefault();
      next.focus();
      next.scrollIntoView?.({ block: "nearest" });
    }
  };

  const renderModel = (model: WorkspaceModel, showProvider = false) => {
    const key = modelKey(model);
    const selected = key === modelKey(activeModel);
    const favorite = favorites.includes(key);
    const name = model.name || model.id;
    const label = `${name} (${model.profile_name})`;
    return (
      <div key={key} className={`group flex items-center gap-1 rounded-lg ${selected ? "bg-app-item-active" : "hover:bg-app-item-hover focus-within:bg-app-item-hover"}`}>
        <button
          type="button"
          data-model-option
          disabled={isSaving}
          aria-label={t("chat.useModel", { model: label })}
          aria-pressed={selected}
          onClick={() => onSelect(model)}
          title={model.id}
          className="flex min-h-11 sm:min-h-9 min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] text-app-text cursor-pointer disabled:cursor-wait focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-app-text"
        >
          <span className="min-w-0 flex-1 break-words [overflow-wrap:anywhere]">
            <span className={selected ? "font-medium" : ""}>{name}</span>
            {showProvider && <span className="ml-2 text-[11px] text-app-text-muted">{model.profile_name}</span>}
            {name !== model.id && <span className="block font-mono text-[10px] text-app-text-muted">{model.id}</span>}
          </span>
          {selected && <Check size={14} aria-hidden="true" className="shrink-0 text-blue-600 dark:text-blue-400" />}
        </button>
        <button
          type="button"
          aria-label={t("chat.favoriteModel", { model: label })}
          aria-pressed={favorite}
          title={t(favorite ? "chat.removeFavorite" : "chat.addFavorite")}
          onClick={() => onToggleFavorite(model)}
          className="flex h-11 w-11 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-app-text"
        >
          <Star size={14} aria-hidden="true" fill={favorite ? "currentColor" : "none"} />
        </button>
      </div>
    );
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col" onKeyDown={handleNavigation}>
      <Popover.Title className="sr-only">{t("chat.selectModel")}</Popover.Title>
      <div className="flex shrink-0 items-center gap-2 border-b border-app-border px-3 py-1.5">
        <Search size={16} aria-hidden="true" className="shrink-0 text-app-text-muted" />
        <input
          ref={searchRef}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label={t("chat.searchModels")}
          placeholder={t("chat.searchModels")}
          className="h-11 sm:h-9 min-w-0 flex-1 rounded-sm bg-transparent text-base sm:text-[13px] text-app-text placeholder:text-app-text-muted outline-none caret-app-text"
        />
      </div>

      <div className="min-h-0 overflow-y-auto overscroll-contain custom-scrollbar p-1.5" aria-busy={isSaving || refreshing}>
        {recentModels.length > 0 && (
          <section aria-label={t("chat.recentModels")} className="mb-2">
            <h3 className="flex items-center gap-2 px-2.5 py-2 text-xs font-medium text-app-text-muted">
              <History size={14} aria-hidden="true" />{t("chat.recentModels")}
            </h3>
            {recentModels.map((model) => renderModel(model, true))}
          </section>
        )}
        {favoriteModels.length > 0 && (
          <section aria-label={t("chat.favoriteModels")} className="mb-2">
            <h3 className="flex items-center gap-2 px-2.5 py-2 text-xs font-medium text-app-text-muted">
              <Star size={14} aria-hidden="true" />{t("chat.favoriteModels")}
            </h3>
            {favoriteModels.map((model) => renderModel(model, true))}
          </section>
        )}
        {Array.from(providers, ([id, provider], index) => {
          const expanded = search.length > 0 || !collapsedProviders.has(id);
          const contentId = `${panelId}-provider-${index}`;
          return (
            <section key={id} aria-label={provider.name} className="mb-1 last:mb-0">
              <button
                type="button"
                aria-label={provider.name}
                aria-expanded={expanded}
                aria-controls={contentId}
                onClick={() => setCollapsedProviders((previous) => {
                  const next = new Set(previous);
                  if (expanded) next.add(id);
                  else next.delete(id);
                  return next;
                })}
                disabled={search.length > 0}
                className="flex min-h-11 sm:min-h-9 w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs font-medium text-app-text-muted hover:bg-app-item-hover cursor-pointer disabled:cursor-default focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-app-text"
              >
                <ChevronRight size={14} aria-hidden="true" className={`shrink-0 ${expanded ? "rotate-90" : ""}`} />
                <span className="min-w-0 flex-1 break-words [overflow-wrap:anywhere]">{provider.name}</span>
                <span className="text-[11px] tabular-nums">{provider.models.length}</span>
              </button>
              <div id={contentId} hidden={!expanded}>{expanded && provider.models.map((model) => renderModel(model))}</div>
            </section>
          );
        })}
        {matchingModels.length === 0 && (
          <p role="status" className="px-3 py-6 text-center text-[13px] text-app-text-muted">
            {t(models.length === 0 ? "chat.noModels" : "chat.noMatchingModels")}
          </p>
        )}
      </div>

      <div className="shrink-0 border-t border-app-border p-1.5">
        {(isSaving || error) && (
          <p role={error ? "alert" : "status"} className="px-2.5 py-2 text-xs text-app-text">
            {error || t("chat.savingModel")}
          </p>
        )}
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          aria-busy={refreshing}
          className="flex min-h-11 sm:min-h-9 w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer disabled:opacity-50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-app-text"
        >
          <RefreshCw size={14} aria-hidden="true" />{t("admin.refreshModels")}
        </button>
        {refreshMessage && <p role="status" className="px-2.5 py-2 text-xs text-app-text-muted">{refreshMessage}</p>}
        <a
          href="/admin"
          target="_blank"
          rel="noopener noreferrer"
          aria-label={t("admin.openNewTab")}
          title={t("admin.openNewTab")}
          className="flex min-h-11 sm:min-h-9 w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-app-text"
        >
          <Plus size={15} aria-hidden="true" />{t("admin.title")}
          <ExternalLink size={13} aria-hidden="true" className="ml-auto shrink-0" />
        </a>
      </div>
    </div>
  );
}
