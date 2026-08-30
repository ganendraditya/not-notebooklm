import React from "react";
import { Trash2, AlertCircle, Loader2 } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

interface BulkDeleteModalProps {
  isOpen: boolean;
  selectedCount: number;
  isBulkDeleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export const BulkDeleteModal: React.FC<BulkDeleteModalProps> = ({
  isOpen,
  selectedCount,
  isBulkDeleting,
  onClose,
  onConfirm
}) => {
  const { t } = useTranslation();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-sm rounded-2xl bg-app-card border border-app-border shadow-2xl p-5 space-y-4 animate-in zoom-in-95 duration-150 text-app-text">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/20 text-red-500 flex items-center justify-center shrink-0">
            <Trash2 size={20} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-app-text">
              {t('right.deleteModalTitle') || "Delete sources"}
            </h3>
            <p className="text-xs text-app-text-muted">
              {t('right.deleteModalDesc')?.replace('{n}', selectedCount.toString()) || 
                `Are you sure you want to delete ${selectedCount} selected document${selectedCount > 1 ? 's' : ''}? This action cannot be undone.`}
            </p>
          </div>
        </div>

        <div className="p-3 rounded-xl bg-app-item-hover/50 border border-app-border flex items-start gap-2.5 text-xs text-app-text-muted">
          <AlertCircle size={15} className="text-amber-500 shrink-0 mt-0.5" />
          <span>{t('right.deleteModalWarning') || "Removed sources will no longer be available for AI context or references."}</span>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isBulkDeleting}
            className="px-3.5 py-1.5 rounded-lg border border-app-border text-xs font-medium text-app-text hover:bg-app-item-hover transition-colors cursor-pointer disabled:opacity-50"
          >
            {t('common.cancel') || "Cancel"}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isBulkDeleting}
            className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-medium text-white transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-50 shadow-sm"
          >
            {isBulkDeleting && <Loader2 size={13} className="animate-spin" />}
            <span>{isBulkDeleting ? (t('right.deleting') || "Deleting...") : (t('common.delete') || "Delete")}</span>
          </button>
        </div>
      </div>
    </div>
  );
};