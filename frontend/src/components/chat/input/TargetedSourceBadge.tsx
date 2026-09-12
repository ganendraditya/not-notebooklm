"use client";

import React from "react";
import { FileText, X } from "lucide-react";
import { TargetedSource } from "@/stores/documentStore";
import { useTranslation } from "@/lib/i18n";
import { Tooltip } from "@/components/ui/tooltip";

interface TargetedSourceBadgeProps {
  targetedSource: TargetedSource | null;
  onClearTargetedSource?: () => void;
}

export function TargetedSourceBadge({
  targetedSource,
  onClearTargetedSource
}: TargetedSourceBadgeProps) {
  const { t } = useTranslation();

  if (!targetedSource) return null;

  return (
    <div className="mb-2 px-3 py-1.5 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-between gap-2 animate-in fade-in duration-200">
      <div className="flex items-center gap-2 min-w-0">
        <FileText size={14} className="text-blue-400 shrink-0" />
        <span className="text-xs text-blue-200 truncate">
          Focusing on: <strong className="font-semibold text-white">{targetedSource.title || targetedSource.filename}</strong>
        </span>
      </div>
      <Tooltip content={t("chat.clearTargeted")} side="top">
        <button
          type="button"
          onClick={onClearTargetedSource}
          className="p-1 text-app-text-muted hover:text-app-text rounded-md hover:bg-app-item-hover transition-colors shrink-0 cursor-pointer"
          aria-label={t("chat.clearTargeted")}
        >
          <X size={14} />
        </button>
      </Tooltip>
    </div>
  );
}
