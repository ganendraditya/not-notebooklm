"use client";

import React from "react";
import { ArrowRight, Pencil, Trash2 } from "lucide-react";
import { useTranslation } from "@/lib/i18n";
import { Tooltip } from "@/components/ui/tooltip";

interface QueuedPromptsListProps {
  queuedPrompts: string[];
  onPromoteQueuedPrompt?: (index: number) => void;
  onRemoveQueuedPrompt?: (index: number) => void;
  onEditQueuedPrompt?: (text: string, index: number) => void;
}

export function QueuedPromptsList({
  queuedPrompts,
  onPromoteQueuedPrompt,
  onRemoveQueuedPrompt,
  onEditQueuedPrompt
}: QueuedPromptsListProps) {
  const { t } = useTranslation();

  if (!queuedPrompts || queuedPrompts.length === 0) return null;

  return (
    <div className="mb-2.5 rounded-2xl bg-app-card border border-app-border shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200 text-app-text">
      <div className="flex items-center justify-between px-3.5 py-2 border-b border-app-divider bg-app-surface">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-semibold text-app-text">{t("chat.queuedMessages")}</span>
          <span className="px-1.5 py-0.2 rounded-full bg-app-item-active text-app-text text-[11px] font-mono font-medium">
            {queuedPrompts.length}
          </span>
          <span className="text-[11px] text-app-text-muted font-normal hidden sm:inline">
            Sends after agent finishes working
          </span>
        </div>
      </div>

      <div className="p-2 space-y-1 divide-y divide-app-divider">
        {queuedPrompts.map((qText, qIdx) => (
          <div 
            key={qIdx}
            className="flex items-center justify-between gap-3 px-2 py-1.5 group rounded-lg hover:bg-app-item-hover transition-colors"
          >
            <p className="text-xs text-app-text truncate flex-1 font-normal select-text">
              {qText}
            </p>

            <div className="flex items-center gap-1 shrink-0">
              <Tooltip content={t("chat.switchProcess")} side="top">
                <button
                  type="button"
                  onClick={() => onPromoteQueuedPrompt?.(qIdx)}
                  className="p-1.5 text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                  aria-label={t("chat.switchProcess")}
                >
                  <ArrowRight size={14} className="text-blue-500" />
                </button>
              </Tooltip>
              <Tooltip content={t("chat.editQueued")} side="top">
                <button
                  type="button"
                  onClick={() => onEditQueuedPrompt?.(qText, qIdx)}
                  className="p-1.5 text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg transition-colors cursor-pointer"
                  aria-label={t("chat.editQueued")}
                >
                  <Pencil size={13} />
                </button>
              </Tooltip>
              <Tooltip content={t("chat.removeQueued")} side="top">
                <button
                  type="button"
                  onClick={() => onRemoveQueuedPrompt?.(qIdx)}
                  className="p-1.5 text-app-text-muted hover:text-red-500 hover:bg-app-item-hover rounded-lg transition-colors cursor-pointer"
                  aria-label={t("chat.removeQueued")}
                >
                  <Trash2 size={13} />
                </button>
              </Tooltip>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
