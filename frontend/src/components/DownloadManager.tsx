"use client";

import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, X, CheckCircle2, AlertCircle, FileArchive, ArrowDownToLine, Loader2 } from "lucide-react";

export interface DownloadTask {
  status: "idle" | "preparing" | "zipping" | "complete" | "error";
  total: number;
  current: number;
  percent: number;
  currentFile: string;
  totalSizeMb?: number;
  errorMsg?: string;
}

interface DownloadManagerProps {
  task: DownloadTask | null;
  onClose: () => void;
}

export const DownloadManager: React.FC<DownloadManagerProps> = ({ task, onClose }) => {
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

  return (
    <div className="fixed bottom-6 right-6 z-50 w-88 max-w-[calc(100vw-2rem)] animate-in fade-in slide-in-from-bottom-4 duration-300">
      <div className="bg-[#1e1f20]/95 backdrop-blur-xl border border-[#333538] rounded-2xl shadow-2xl shadow-black/80 overflow-hidden transition-all duration-300">
        {/* Header Bar */}
        <div className="flex items-center justify-between px-4 py-3 bg-[#282a2c]/70 border-b border-[#383a3d]">
          <div className="flex items-center gap-2.5">
            {task.status === "complete" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 animate-in zoom-in-50" />
            ) : task.status === "error" ? (
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
            ) : (
              <Loader2 className="w-4 h-4 text-blue-400 shrink-0 animate-spin" />
            )}
            <span className="text-sm font-semibold text-gray-200">
              {task.status === "complete"
                ? "Download ready"
                : task.status === "error"
                ? "Download failed"
                : "Preparing download"}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="p-1 text-gray-400 hover:text-gray-200 hover:bg-[#383a3d] rounded-lg transition-colors"
              title={isCollapsed ? "Expand" : "Collapse"}
            >
              {isCollapsed ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            <button
              onClick={onClose}
              className="p-1 text-gray-400 hover:text-gray-200 hover:bg-[#383a3d] rounded-lg transition-colors"
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content Body (Collapsible) */}
        {!isCollapsed && (
          <div className="p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
                <FileArchive className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-gray-300 truncate">
                    {task.status === "complete"
                      ? `Zipped ${task.total} files (${task.totalSizeMb ? `${task.totalSizeMb} MB` : "Ready"})`
                      : task.status === "error"
                      ? (task.errorMsg || "An error occurred")
                      : `Zipping ${task.total} files...`}
                  </span>
                  <span className="font-bold text-blue-400 shrink-0 ml-2">
                    {task.status === "complete" ? "100%" : `${task.percent}%`}
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="w-full h-2 bg-[#2c2d30] rounded-full overflow-hidden border border-[#383a3d]">
                  <div
                    className={`h-full transition-all duration-300 rounded-full ${
                      task.status === "complete"
                        ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                        : task.status === "error"
                        ? "bg-red-500"
                        : "bg-gradient-to-r from-blue-500 to-cyan-400 animate-pulse"
                    }`}
                    style={{ width: `${Math.max(4, task.percent)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Current Item / Subtitle Status */}
            <div className="flex items-center justify-between text-[11px] text-gray-400 pt-0.5">
              {task.status === "complete" ? (
                <span className="text-emerald-400 flex items-center gap-1.5">
                  <ArrowDownToLine className="w-3.5 h-3.5" />
                  Your archive is downloading automatically
                </span>
              ) : task.status === "error" ? (
                <span className="text-red-400">{task.errorMsg || "Please try again"}</span>
              ) : (
                <>
                  <span className="truncate pr-2">
                    {task.currentFile ? `Zipping: ${task.currentFile}` : "Fetching sources from journals..."}
                  </span>
                  <span className="shrink-0 font-medium text-gray-400">
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
