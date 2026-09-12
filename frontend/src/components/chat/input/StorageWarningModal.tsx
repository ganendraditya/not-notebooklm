"use client";

import React from "react";
import { FileText, X } from "lucide-react";
import { Portal } from "@/components/ui/Portal";
import { Tooltip } from "@/components/ui/tooltip";
import { formatFileSize } from "./fileUtils";

interface StorageWarningModalProps {
  file: { filename: string; size: number } | null;
  onClose: () => void;
  onOpenStorage?: () => void;
}

export function StorageWarningModal({
  file,
  onClose,
  onOpenStorage
}: StorageWarningModalProps) {
  if (!file) return null;

  return (
    <Portal>
      <div 
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      >
        <div 
          onClick={(e) => e.stopPropagation()}
          className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-md p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150 relative text-left text-app-text"
        >
          <div className="flex items-start justify-between">
            <h3 className="text-base font-semibold text-app-text">File added to chat only</h3>
            <Tooltip content="Close" side="bottom">
              <button
                type="button"
                onClick={onClose}
                className="text-app-text-muted hover:text-app-text p-1 rounded-lg hover:bg-app-item-hover transition-colors cursor-pointer"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </Tooltip>
          </div>

          <p className="text-sm text-app-text-muted leading-relaxed">
            You don&apos;t have enough storage space left to save this file. Remove files to create space.
          </p>

          <div className="flex items-center justify-between p-3 rounded-xl bg-app-input-surface border border-app-border">
            <div className="flex items-center gap-3 min-w-0 pr-3">
              <div className="p-2 rounded-lg bg-app-item-hover border border-app-border shrink-0">
                <FileText size={18} className="text-app-text-muted" />
              </div>
              <span className="text-sm font-medium text-app-text truncate">
                {file.filename}
              </span>
            </div>
            <span className="text-xs text-app-text-dim font-mono shrink-0">
              {formatFileSize(file.size)}
            </span>
          </div>

          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={() => {
                onClose();
                onOpenStorage?.();
              }}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition-all"
            >
              Open Storage
            </button>
          </div>
        </div>
      </div>
    </Portal>
  );
}
