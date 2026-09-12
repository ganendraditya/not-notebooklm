"use client";

import React, { useState, useEffect, useRef } from "react";
import { Edit2 } from "lucide-react";
import { Portal } from "./Portal";

interface RenameDialogProps {
  isOpen: boolean;
  title: string;
  initialValue: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isLoading?: boolean;
  onConfirm: (newValue: string) => void;
  onClose: () => void;
}

export const RenameDialog: React.FC<RenameDialogProps> = ({
  isOpen,
  title,
  initialValue,
  placeholder = "Enter new name...",
  confirmLabel = "Save",
  cancelLabel = "Cancel",
  isLoading = false,
  onConfirm,
  onClose,
}) => {
  const [value, setValue] = useState(initialValue);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setValue(initialValue);
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 50);
    }
  }, [isOpen, initialValue]);

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed && trimmed !== initialValue) {
      onConfirm(trimmed);
    } else {
      onClose();
    }
  };

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
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500 shrink-0">
              <Edit2 size={18} />
            </div>
            <h3 className="font-semibold text-app-text text-base leading-tight">
              {title}
            </h3>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              ref={inputRef}
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={placeholder}
              className="w-full px-3 py-2 bg-app-item rounded-lg border border-app-border text-sm text-app-text placeholder:text-app-text-muted focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
            />

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
                type="submit"
                disabled={isLoading || !value.trim()}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-50 shadow-sm"
              >
                {confirmLabel}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Portal>
  );
};
