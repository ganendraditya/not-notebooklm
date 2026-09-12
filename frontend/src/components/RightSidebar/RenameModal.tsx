import React from "react";
import { Loader2 } from "lucide-react";
import { Portal } from "@/components/ui/Portal";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n";
import { Document } from "@/stores/documentStore";

interface RenameModalProps {
  isOpen: boolean;
  renamingDoc: Document | null;
  renameTitleInput: string;
  isSavingRename: boolean;
  onInputChange: (title: string) => void;
  onClose: () => void;
  onSave: (e?: React.FormEvent) => void;
}

export const RenameModal: React.FC<RenameModalProps> = ({
  isOpen,
  renamingDoc,
  renameTitleInput,
  isSavingRename,
  onInputChange,
  onClose,
  onSave
}) => {
  const { t } = useTranslation();

  if (!isOpen || !renamingDoc) return null;

  return (
    <Portal>
      <div 
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150"
      >
        <div 
          onClick={(e) => e.stopPropagation()}
          className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150 text-app-text"
        >
          <div className="space-y-1.5">
            <h3 className="text-base font-semibold text-app-text">
              {t('right.renameSource') || "Rename source"}
            </h3>
            <p className="text-xs text-app-text-muted">
              {t('right.renameSourceDesc') || "Enter a custom display title for this document."}
            </p>
          </div>

          <form onSubmit={onSave} className="space-y-4">
            <input
              type="text"
              value={renameTitleInput}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") onClose();
              }}
              placeholder={renamingDoc.title || renamingDoc.filename || "Document title"}
              autoFocus
              className="w-full bg-app-input-surface border border-app-border focus:border-blue-500 rounded-xl px-3 py-2 text-xs text-app-text outline-none transition-colors placeholder:text-app-text-dim"
            />

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-app-divider">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onClose}
                disabled={isSavingRename}
                className="text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg px-3.5 h-8 cursor-pointer"
              >
                {t('action.cancel') || "Cancel"}
              </Button>

              <Button
                type="submit"
                size="sm"
                disabled={isSavingRename || !renameTitleInput.trim()}
                className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow flex items-center gap-1.5"
              >
                {isSavingRename && <Loader2 size={13} className="animate-spin" />}
                <span>{t('action.save') || "Save"}</span>
              </Button>
            </div>
          </form>
        </div>
      </div>
    </Portal>
  );
};