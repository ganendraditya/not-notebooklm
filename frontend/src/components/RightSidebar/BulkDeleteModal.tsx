import React, { useId } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Portal } from "@/components/ui/Portal";
import { useTranslation } from "@/lib/i18n";

interface BulkDeleteModalProps {
  isOpen: boolean;
  selectedCount: number;
  isBulkDeleting: boolean;
  sourceNames?: string[];
  description?: string;
  errorMessage?: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export const BulkDeleteModal: React.FC<BulkDeleteModalProps> = ({
  isOpen,
  selectedCount,
  isBulkDeleting,
  sourceNames,
  description,
  errorMessage,
  onClose,
  onConfirm
}) => {
  const { t } = useTranslation();
  const dialogId = useId();

  if (!isOpen) return null;

  return (
    <Portal>
      <div 
        onClick={(e) => {
          e.stopPropagation();
          if (!isBulkDeleting) onClose();
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape" && !isBulkDeleting) {
            e.stopPropagation();
            onClose();
          }
        }}
        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150 text-app-text"
      >
      <div 
        onClick={(e) => e.stopPropagation()}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${dialogId}-title`}
        aria-describedby={[
          `${dialogId}-description`,
          sourceNames?.length ? `${dialogId}-sources` : null,
          errorMessage ? `${dialogId}-error` : null,
        ].filter(Boolean).join(" ")}
        className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150 text-app-text"
      >
        <div className="flex items-center gap-2.5 font-semibold text-sm">
          <AlertTriangle size={18} className="text-red-500" />
          <span id={`${dialogId}-title`}>{t('right.deleteConfirmTitle')?.replace('{count}', selectedCount.toString()) || `Delete ${selectedCount} selected source(s)?`}</span>
        </div>
        
        <p id={`${dialogId}-description`} className="text-xs text-app-text-muted leading-relaxed">
          {description || t('right.deleteConfirmDesc') ||
            `Deleted documents will no longer be used by the AI to answer questions in this chat session.`}
        </p>

        {sourceNames && sourceNames.length > 0 && (
          <ul id={`${dialogId}-sources`} className="max-h-36 space-y-1 overflow-y-auto rounded-lg border border-app-divider px-3 py-2 text-xs text-app-text">
            {sourceNames.map((name, index) => (
              <li key={`${index}-${name}`} className="break-words">{name}</li>
            ))}
          </ul>
        )}

        {errorMessage && (
          <p id={`${dialogId}-error`} role="alert" className="text-xs text-red-500 leading-relaxed">{errorMessage}</p>
        )}

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-app-divider">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            autoFocus
            disabled={isBulkDeleting}
            className="text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg px-3.5 h-8 cursor-pointer"
          >
            {t('action.cancel') || "Cancel"}
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
                <span>{t('right.deleting') || "Deleting..."}</span>
              </>
            ) : (
              <span>{t('right.deleteButton')?.replace('{count}', selectedCount.toString()) || `Delete (${selectedCount})`}</span>
            )}
          </Button>
        </div>
      </div>
    </div>
    </Portal>
  );
};
