import React from "react";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { Portal } from "@/components/ui/Portal";
import { useTranslation } from "@/lib/i18n";
import { Document } from "@/stores/documentStore";

interface BulkDeleteModalProps {
  isOpen: boolean;
  selectedCount: number;
  isBulkDeleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function BulkDeleteModal({
  isOpen,
  selectedCount,
  isBulkDeleting,
  onClose,
  onConfirm,
}: BulkDeleteModalProps) {
  const { t } = useTranslation();

  if (!isOpen) return null;

  return (
    <Portal>
      <div 
        onClick={(e) => {
          e.stopPropagation();
          if (!isBulkDeleting) onClose();
        }}
        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      >
      <div 
        onClick={(e) => e.stopPropagation()}
        className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150 text-app-text"
      >
        <div className="space-y-1.5">
          <h3 className="text-base font-semibold text-app-text">
            {t('right.deleteConfirmTitle', { count: selectedCount.toString() })}
          </h3>
          <p className="text-xs text-app-text-muted leading-relaxed">
            {t('right.deleteConfirmDesc')}
          </p>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-app-divider">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            disabled={isBulkDeleting}
            className="text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg px-3.5 h-8 cursor-pointer"
          >
            {t('action.cancel')}
          </Button>

          <Button
            size="sm"
            onClick={onConfirm}
            disabled={isBulkDeleting}
            className="text-xs bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow flex items-center gap-1.5"
          >
            {isBulkDeleting ? (
              <>
                <Loader2 size={12} className="animate-spin" />
                <span>{t('right.deleting')}</span>
              </>
            ) : (
              <span>{t('right.deleteButton', { count: selectedCount.toString() })}</span>
            )}
          </Button>
        </div>
      </div>
    </div>
    </Portal>
  );
}

interface RenameModalProps {
  isOpen: boolean;
  renamingDoc: Document | null;
  renameTitleInput: string;
  isSavingRename: boolean;
  onInputChange: (val: string) => void;
  onClose: () => void;
  onSave: (e: React.FormEvent) => void;
}

export function RenameModal({
  isOpen,
  renamingDoc,
  renameTitleInput,
  isSavingRename,
  onInputChange,
  onClose,
  onSave,
}: RenameModalProps) {
  const { t } = useTranslation();

  if (!isOpen || !renamingDoc) return null;

  return (
    <Portal>
      <div 
        onClick={(e) => {
          e.stopPropagation();
          if (!isSavingRename) onClose();
        }}
        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      >
      <div 
        onClick={(e) => e.stopPropagation()}
        className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-md p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150 text-app-text"
      >
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-app-text">{t('right.renameSource')}</h3>
          <p className="text-xs text-app-text-muted truncate" title={renamingDoc.filename}>
            {t('right.filePrefix')}{renamingDoc.filename}
          </p>
        </div>

        <form onSubmit={onSave} className="space-y-3">
          <div>
            <input
              type="text"
              value={renameTitleInput}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder={t('right.renamePlaceholder')}
              className="w-full h-10 px-3.5 rounded-xl bg-app-input-surface border border-app-border focus:border-blue-500 text-xs text-app-text placeholder:text-app-text-dim focus:outline-none transition-all"
              autoFocus
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-1 border-t border-app-divider">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onClose}
              disabled={isSavingRename}
              className="text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg px-3.5 h-8 cursor-pointer"
            >
              {t('action.cancel')}
            </Button>

            <Button
              type="submit"
              size="sm"
              disabled={!renameTitleInput.trim() || isSavingRename}
              className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow flex items-center gap-1.5"
            >
              {isSavingRename ? (
                <>
                  <Loader2 size={12} className="animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <span>{t('action.save')}</span>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
    </Portal>
  );
}
