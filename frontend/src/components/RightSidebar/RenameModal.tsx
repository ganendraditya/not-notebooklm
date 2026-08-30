import React from "react";
import { Edit2, Loader2 } from "lucide-react";
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-sm rounded-2xl bg-app-card border border-app-border shadow-2xl p-5 space-y-4 animate-in zoom-in-95 duration-150 text-app-text">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-500 flex items-center justify-center shrink-0">
            <Edit2 size={18} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-app-text">
              {t('right.renameModalTitle') || "Rename document"}
            </h3>
            <p className="text-xs text-app-text-muted">
              {t('right.renameModalDesc') || "Enter a custom display title for this source"}
            </p>
          </div>
        </div>

        <form onSubmit={onSave} className="space-y-4">
          <div>
            <input
              type="text"
              value={renameTitleInput}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder="e.g. YOLOv8 Road Damage Detection"
              autoFocus
              className="w-full px-3.5 py-2 rounded-xl bg-app-input border border-app-border focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none text-xs text-app-text transition-colors placeholder:text-app-text-dim"
            />
          </div>

          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSavingRename}
              className="px-3.5 py-1.5 rounded-lg border border-app-border text-xs font-medium text-app-text hover:bg-app-item-hover transition-colors cursor-pointer disabled:opacity-50"
            >
              {t('common.cancel') || "Cancel"}
            </button>
            <button
              type="submit"
              disabled={isSavingRename || !renameTitleInput.trim()}
              className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-medium text-white transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-50 shadow-sm"
            >
              {isSavingRename && <Loader2 size={13} className="animate-spin" />}
              <span>{isSavingRename ? (t('common.saving') || "Saving...") : (t('common.save') || "Save")}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};