"use client";

import React, { useEffect } from "react";
import { Trash2, AlertTriangle } from "lucide-react";
import { Portal } from "./Portal";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  isDestructive?: boolean;
  isLoading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  isDestructive = true,
  isLoading = false,
  onConfirm,
  onClose,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <Portal>
      <div 
        className="fixed inset-0 z-[99999] bg-black/60 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
        onClick={onClose}
      >
        <div 
          className="bg-app-card border border-app-border rounded-xl max-w-sm w-full p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start gap-3">
            <div className={`p-2.5 rounded-full shrink-0 ${isDestructive ? "bg-red-500/10 text-red-500" : "bg-amber-500/10 text-amber-500"}`}>
              {isDestructive ? <Trash2 size={20} /> : <AlertTriangle size={20} />}
            </div>
            <div>
              <h3 className="font-semibold text-app-text text-base leading-tight">
                {title}
              </h3>
              <div className="text-xs text-app-text-muted mt-1.5 leading-relaxed">
                {description}
              </div>
            </div>
          </div>
          
          <div className="flex justify-end gap-2.5 pt-2 border-t border-app-border/40">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-3.5 py-1.5 text-xs font-medium rounded-lg text-app-text-dim hover:bg-app-item-hover hover:text-app-text transition-colors disabled:opacity-50"
            >
              {cancelLabel}
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={isLoading}
              className={`px-3.5 py-1.5 text-xs font-medium rounded-lg text-white transition-colors flex items-center gap-1.5 disabled:opacity-50 shadow-sm ${
                isDestructive 
                  ? "bg-red-600 hover:bg-red-700" 
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {isLoading ? (
                <>
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                confirmLabel
              )}
            </button>
          </div>
        </div>
      </div>
    </Portal>
  );
};
