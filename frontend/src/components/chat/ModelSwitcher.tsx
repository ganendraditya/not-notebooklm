"use client";

import React, { useState, useMemo } from "react";
import { Popover } from "@base-ui/react/popover";
import { ChevronDown } from "lucide-react";
import { useChatStore, WorkspaceModel } from "@/stores/chatStore";
import { useTranslation } from "@/lib/i18n";
import { fetchWorkspaceModels } from "@/lib/workspace-models";
import { useModelPreferences } from "@/hooks/chat/useModelPreferences";
import { ModelPickerPanel } from "./ModelPickerPanel";

interface ModelSwitcherProps {
  backendUrl: string;
  activeChatId: string | null;
}

export function ModelSwitcher({
  backendUrl,
  activeChatId,
}: ModelSwitcherProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState("");
  const { favorites, recent, toggleFavorite, recordRecent } = useModelPreferences();

  const availableModels = useChatStore((state) => state.availableModels);
  const sessions = useChatStore((state) => state.sessions);
  const pendingNewChatModel = useChatStore((state) => state.pendingNewChatModel);
  const updateSessionModel = useChatStore((state) => state.updateSessionModel);
  const setPendingNewChatModel = useChatStore((state) => state.setPendingNewChatModel);
  const setAvailableModels = useChatStore((state) => state.setAvailableModels);

  const refreshModels = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setRefreshMessage("");
    try {
      setAvailableModels(await fetchWorkspaceModels(backendUrl));
      setRefreshMessage(t("admin.modelsRefreshed"));
    } catch { setRefreshMessage(t("admin.modelsRefreshFailed")); }
    finally { setRefreshing(false); }
  };

  // Determine currently active model for this session
  const currentSession = useMemo(() => {
    if (!activeChatId) return null;
    return sessions.find((s) => s.id === activeChatId) || null;
  }, [activeChatId, sessions]);

  const activeModelId = useMemo(() => {
    if (currentSession && currentSession.model) {
      return currentSession.model;
    }
    if (!activeChatId && pendingNewChatModel) {
      return pendingNewChatModel.model;
    }
    // Default model
    const def = availableModels.find((m) => m.is_default);
    if (def) return def.id;
    return availableModels[0]?.id || "";
  }, [currentSession, activeChatId, pendingNewChatModel, availableModels]);

  const activeProfileId = useMemo(() => {
    if (currentSession?.profile_id) return currentSession.profile_id;
    if (!activeChatId && pendingNewChatModel?.profile_id) return pendingNewChatModel.profile_id;
    const def = availableModels.find((m) => m.is_default);
    if (def) return def.profile_id;
    return availableModels[0]?.profile_id || "";
  }, [currentSession, activeChatId, pendingNewChatModel, availableModels]);

  const activeModel = useMemo<WorkspaceModel>(() => {
    const matched =
      availableModels.find(
        (m) => m.id === activeModelId && m.profile_id === activeProfileId
      ) || availableModels.find((m) => m.id === activeModelId);

    return (
      matched || {
        id: activeModelId,
        name: activeModelId,
        profile_id: activeProfileId,
        profile_name: activeProfileId,
      }
    );
  }, [availableModels, activeModelId, activeProfileId]);

  const handleSelectModel = async (m: WorkspaceModel) => {
    if (isSaving) return;
    setSelectionError(null);
    if (activeChatId) {
      const prevModel = currentSession?.model ?? null;
      const prevProfileId = currentSession?.profile_id ?? null;

      setIsSaving(true);
      updateSessionModel(activeChatId, m.id, m.profile_id);

      try {
        const res = await fetch(`${backendUrl}/chats/${activeChatId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: m.id,
            profile_id: m.profile_id,
          }),
        });
        if (!res.ok) {
          throw new Error(res.statusText || `HTTP ${res.status}`);
        }
        recordRecent(m);
        setIsOpen(false);
      } catch (err) {
        updateSessionModel(activeChatId, prevModel, prevProfileId);
        setSelectionError(t("chat.modelSaveError"));
        console.error("Failed to update session model:", err);
      } finally {
        setIsSaving(false);
      }
    } else {
      setPendingNewChatModel({
        model: m.id,
        profile_id: m.profile_id,
      });
      recordRecent(m);
      setIsOpen(false);
    }
  };

  return (
    <div className="min-w-0 max-w-[16rem] text-left">
      <Popover.Root open={isOpen} onOpenChange={setIsOpen}>
        <Popover.Trigger
          className="flex h-11 sm:h-8 min-w-11 sm:min-w-0 pointer-coarse:h-11 pointer-coarse:min-w-11 w-max max-w-full items-center justify-center gap-1 sm:gap-1.5 px-1.5 sm:px-3 rounded-full text-xs font-medium text-app-text-muted hover:text-app-text hover:bg-app-item-hover data-popup-open:bg-app-item-hover transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-text"
          title={activeModel.id ? `${activeModel.profile_name}: ${activeModel.name || activeModel.id}` : t("chat.selectModel")}
          aria-label={activeModel.id ? `${t("chat.selectModel")}: ${activeModel.name || activeModel.id}` : t("chat.selectModel")}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              setIsOpen(true);
            }
          }}
        >
          <span className="min-w-0 truncate">{activeModel.name || activeModel.id || t("chat.selectModel")}</span>
          <ChevronDown size={12} aria-hidden="true" className="shrink-0" />
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Positioner side="top" align="start" sideOffset={8} collisionPadding={12} className="z-50">
            <Popover.Popup
              initialFocus={(interactionType) => !["mouse", "touch", "pen"].includes(interactionType)}
              className="flex w-96 max-w-[calc(100vw-24px)] max-h-[min(520px,var(--available-height))] flex-col rounded-xl bg-app-dropdown border border-app-border-strong shadow-lg text-app-text focus-visible:outline-2 focus-visible:outline-app-text"
            >
              <ModelPickerPanel
                models={availableModels}
                activeModel={activeModel}
                favorites={favorites}
                recent={recent}
                isSaving={isSaving}
                error={selectionError}
                onSelect={handleSelectModel}
                onToggleFavorite={toggleFavorite}
                refreshing={refreshing}
                refreshMessage={refreshMessage}
                onRefresh={refreshModels}
              />
            </Popover.Popup>
          </Popover.Positioner>
        </Popover.Portal>
      </Popover.Root>
    </div>
  );
}
