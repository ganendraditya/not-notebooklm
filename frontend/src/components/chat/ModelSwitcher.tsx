"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import { Cpu, ChevronDown, Check, Settings, Sparkles } from "lucide-react";
import { useChatStore, WorkspaceModel } from "@/stores/chatStore";
import { useTranslation } from "@/lib/i18n";
import { readModelPreferences, recordModelSelection } from "@/lib/model-preferences";
import { resolveNewChatModel } from "@/lib/workspace-models";

interface ModelSwitcherProps {
  backendUrl: string;
  activeChatId: string | null;
  onOpenSettings?: () => void;
}

export function ModelSwitcher({
  backendUrl,
  activeChatId,
}: ModelSwitcherProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const availableModels = useChatStore((state) => state.availableModels);
  const modelCatalogStatus = useChatStore((state) => state.modelCatalogStatus);
  const lastSelectedModelKey = useChatStore((state) => state.lastSelectedModelKey);
  const sessions = useChatStore((state) => state.sessions);
  const pendingNewChatModel = useChatStore((state) => state.pendingNewChatModel);
  const updateSessionModel = useChatStore((state) => state.updateSessionModel);
  const setPendingNewChatModel = useChatStore((state) => state.setPendingNewChatModel);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  // Keyboard accessibility: Escape closes dropdown
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  // Determine currently active model for this session
  const currentSession = useMemo(() => {
    if (!activeChatId) return null;
    return sessions.find((s) => s.id === activeChatId) || null;
  }, [activeChatId, sessions]);

  const activeModel = useMemo(() => {
    if (currentSession?.model) {
      return availableModels.find((model) => model.id === currentSession.model && (!currentSession.profile_id || model.profile_id === currentSession.profile_id))
        || { id: currentSession.model, name: currentSession.model, profile_id: currentSession.profile_id || "", profile_name: currentSession.profile_id || "" };
    }
    if (activeChatId) return availableModels.find((model) => model.is_default) || availableModels[0];
    return resolveNewChatModel(availableModels, lastSelectedModelKey || readModelPreferences().recent[0], pendingNewChatModel);
  }, [currentSession, activeChatId, availableModels, lastSelectedModelKey, pendingNewChatModel]);

  const catalogMessage = t(modelCatalogStatus === "loading" ? "chat.loadingModels" : modelCatalogStatus === "error" ? "chat.modelLoadError" : "chat.noModels");

  // Group models by gateway provider
  const groupedModels = useMemo(() => {
    const groups: Record<string, WorkspaceModel[]> = {};
    for (const m of availableModels) {
      const groupName = m.profile_name || "Default Gateway";
      if (!groups[groupName]) {
        groups[groupName] = [];
      }
      groups[groupName].push(m);
    }
    return groups;
  }, [availableModels]);

  const handleSelectModel = async (m: WorkspaceModel) => {
    setIsOpen(false);
    if (activeChatId) {
      const prevModel = currentSession?.model ?? null;
      const prevProfileId = currentSession?.profile_id ?? null;

      // 1. Optimistically update store
      updateSessionModel(activeChatId, m.id, m.profile_id);

      // 2. Persist to backend database with rollback on failure
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
          updateSessionModel(activeChatId, prevModel, prevProfileId);
          console.error("Failed to update session model:", res.statusText);
          return;
        }
        recordModelSelection(m);
      } catch (err) {
        updateSessionModel(activeChatId, prevModel, prevProfileId);
        console.error("Failed to update session model:", err);
      }
    } else {
      // For new unsaved chat, set pending model
      setPendingNewChatModel({
        model: m.id,
        profile_id: m.profile_id,
      });
      recordModelSelection(m);
    }
  };

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-app-surface border border-app-border hover:border-app-border-strong text-xs text-app-text transition-all cursor-pointer group shadow-xs focus:outline-hidden"
        title={t("chat.selectModel") || "Select synthesis model"}
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <Sparkles size={12} className="text-blue-500 shrink-0" />
        {activeModel?.profile_name && <span className="text-[10px] font-mono px-1 py-0.5 rounded bg-app-card text-app-text-muted border border-app-border max-w-[80px] truncate">
          {activeModel.profile_name}
        </span>}
        <span className="font-medium text-app-text max-w-[110px] sm:max-w-[150px] truncate">
          {activeModel ? activeModel.name || activeModel.id : catalogMessage}
        </span>
        <ChevronDown
          size={11}
          className={`text-app-text-muted group-hover:text-app-text transition-transform duration-150 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className="absolute left-0 mt-1.5 z-50 w-64 rounded-xl bg-app-dropdown border border-app-border-strong shadow-2xl p-1.5 text-xs text-app-text animate-in fade-in zoom-in-95 duration-100 max-h-80 overflow-y-auto custom-scrollbar"
          role="menu"
        >
          <div className="px-2 py-1 text-[10px] font-semibold text-app-text-dim uppercase tracking-wider">
            {t("chat.model") || "Synthesis Models"}
          </div>

          {Object.keys(groupedModels).length === 0 ? (
            <div className="px-3 py-2 text-xs text-app-text-muted text-center">
              {catalogMessage}
            </div>
          ) : (
            Object.entries(groupedModels).map(([groupName, models]) => (
              <div key={groupName} className="mb-2 last:mb-0">
                <div className="px-2 py-1 text-[10px] font-medium text-app-text-muted/80 flex items-center gap-1.5">
                  <Cpu size={10} className="text-blue-500/70" />
                  <span className="truncate">{groupName}</span>
                </div>
                <div className="space-y-0.5">
                  {models.map((m) => {
                    const isSelected = m.id === activeModel?.id && m.profile_id === activeModel?.profile_id;
                    return (
                      <button
                        key={`${m.profile_id}_${m.id}`}
                        type="button"
                        onClick={() => handleSelectModel(m)}
                        className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left transition-colors cursor-pointer ${
                          isSelected
                            ? "bg-blue-600/15 text-blue-500 font-medium"
                            : "hover:bg-app-item-hover text-app-text"
                        }`}
                        role="menuitem"
                      >
                        <div className="min-w-0 pr-2">
                          <div className="truncate text-xs">{m.name || m.id}</div>
                          <div className="text-[10px] font-mono text-app-text-dim truncate">
                            {m.id}
                          </div>
                        </div>
                        {isSelected && (
                          <Check size={13} className="text-blue-500 shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          )}

          <>
              <div className="my-1 border-t border-app-border" />
              <a
                href="/admin"
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setIsOpen(false)}
                className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer text-xs"
              >
                <Settings size={12} className="text-app-text-dim" />
                <span className="truncate">
                  {t("chat.manageModels") || "Manage models in Settings"}
                </span>
              </a>
            </>
        </div>
      )}
    </div>
  );
}
