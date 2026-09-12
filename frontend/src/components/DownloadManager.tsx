"use client";

import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, X, CheckCircle2, AlertCircle, FileArchive, ArrowDownToLine, Loader2 } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { useTranslation } from "@/lib/i18n";

export interface DownloadTask {
  status: "idle" | "preparing" | "zipping" | "complete" | "error";
  total: number;
  current: number;
  percent: number;
  currentFile: string;
  downloadedCount?: number;
  skippedCount?: number;
  totalSizeMb?: number;
  errorMsg?: string;
}

interface DownloadManagerProps {
  task: DownloadTask | null;
  onClose: () => void;
}

export const DownloadManager: React.FC<DownloadManagerProps> = ({ task, onClose }) => {
  const { t } = useTranslation();
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Auto-dismiss on complete after 8 seconds
  useEffect(() => {
    if (task?.status === "complete") {
      const timer = setTimeout(() => {
        onClose();
      }, 8000);
      return () => clearTimeout(timer);
    }
  }, [task?.status, onClose]);

  if (!task || task.status === "idle") return null;

  const displayPercent = typeof task.percent === "number" && !isNaN(task.percent) 
    ? Math.min(100, Math.max(0, Math.round(task.percent))) 
    : (task.total > 0 ? Math.min(100, Math.max(0, Math.round((task.current / task.total) * 100))) : 0);

  return (
    <div className="absolute bottom-0 left-0 right-0 z-40 w-full animate-in fade-in slide-in-from-bottom-2 duration-200 text-app-text">
      <div className="bg-app-card border-t border-app-border shadow-2xl overflow-hidden transition-all duration-200">
        {/* Header Bar */}
        <div className="flex items-center justify-between px-3.5 py-2 bg-app-surface border-b border-app-divider">
          <div className="flex items-center gap-2">
            {task.status === "complete" ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 animate-in zoom-in-50" />
            ) : task.status === "error" ? (
              <AlertCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />
            ) : (
              <Loader2 className="w-3.5 h-3.5 text-blue-500 shrink-0 animate-spin" />
            )}
            <span className="text-xs font-semibold text-app-text">
              {task.status === "complete"
                ? t('download.complete')
                : task.status === "error"
                ? t('download.failed')
                : t('download.preparing')}
            </span>
          </div>

          <div className="flex items-center gap-0.5">
            <Tooltip content={isCollapsed ? t('download.expand') : t('download.collapse')} side="bottom">
              <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className="p-1 text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded transition-colors cursor-pointer"
                aria-label={isCollapsed ? t('download.expand') : t('download.collapse')}
              >
                {isCollapsed ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            </Tooltip>
            <Tooltip content={t('download.close')} side="bottom">
              <button
                onClick={onClose}
                className="p-1 text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded transition-colors cursor-pointer"
                aria-label={t('download.close')}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </Tooltip>
          </div>
        </div>

        {/* Content Body (Collapsible) */}
        {!isCollapsed && (
          <div className="p-3 space-y-2">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-500 shrink-0">
                <FileArchive className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="font-medium text-app-text truncate">
                    {task.status === "complete"
                      ? task.skippedCount && task.skippedCount > 0
                        ? `Zipped ${task.downloadedCount ?? task.total} of ${task.total} files (${task.skippedCount} skipped)`
                        : `Zipped ${task.total} files (${task.totalSizeMb ? `${task.totalSizeMb} MB` : "Ready"})`
                      : task.status === "error"
                      ? (task.errorMsg || "An error occurred")
                      : `Processing ${task.total} files...`}
                  </span>
                  <span className="font-bold text-blue-500 shrink-0 ml-2">
                    {task.status === "complete" ? "100%" : `${displayPercent}%`}
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="w-full h-1.5 bg-app-input-surface rounded-full overflow-hidden border border-app-border">
                  <div
                    className={`h-full transition-all duration-300 rounded-full ${
                      task.status === "complete"
                        ? task.skippedCount && task.skippedCount > 0
                          ? "bg-gradient-to-r from-teal-500 to-amber-400"
                          : "bg-gradient-to-r from-emerald-500 to-teal-400"
                        : task.status === "error"
                        ? "bg-red-500"
                        : "bg-gradient-to-r from-blue-500 to-cyan-400 animate-pulse"
                    }`}
                    style={{ width: `${Math.max(4, displayPercent)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Current Item / Subtitle Status */}
            <div className="flex items-center justify-between text-[10.5px] text-app-text-dim pt-0.5">
              {task.status === "complete" ? (
                <div className="flex items-center justify-between w-full">
                  <span className="text-emerald-500 flex items-center gap-1.5 truncate">
                    <ArrowDownToLine className="w-3 h-3 shrink-0" />
                    {task.skippedCount && task.skippedCount > 0
                      ? t('download.zippedWithSkip').replace('{downloaded}', (task.downloadedCount ?? task.total).toString()).replace('{total}', task.total.toString()).replace('{skipped}', task.skippedCount.toString())
                      : `${t('download.zippedCount').replace('{total}', task.total.toString())} (${task.totalSizeMb ? `${task.totalSizeMb} MB` : t('download.ready')})`}
                  </span>
                  {task.totalSizeMb && (
                    <span className="text-app-text-dim font-mono text-[10px] shrink-0 ml-2">
                      {task.totalSizeMb} MB
                    </span>
                  )}
                </div>
              ) : task.status === "error" ? (
                <span className="text-red-500 truncate">{task.errorMsg || "Please try again"}</span>
              ) : (
                <>
                  <span className="truncate pr-2 text-app-text-muted">
                    {task.currentFile ? `Checking: ${task.currentFile}` : "Fetching sources..."}
                  </span>
                  <span className="shrink-0 font-medium text-app-text-dim">
                    {task.current} of {task.total}
                  </span>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
