import React from "react";
import {
  X,
  Search,
  UploadCloud,
} from "lucide-react";
import { Portal } from "@/components/ui/Portal";
import { Tooltip } from "@/components/ui/tooltip";
import { useTranslation } from "@/lib/i18n";

export interface AddSourcesModalProps {
  isOpen: boolean;
  onClose: () => void;
  doiInput: string;
  setDoiInput: (value: string) => void;
  handleImportDoi: (e?: React.FormEvent) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  isDraggingOver: boolean;
  setIsDraggingOver: (val: boolean) => void;
  handleUploadBatch: (files: File[]) => void;
  documentsLength: number;
  pendingSourcesLength: number;
}

export const AddSourcesModal: React.FC<AddSourcesModalProps> = ({
  isOpen,
  onClose,
  doiInput,
  setDoiInput,
  handleImportDoi,
  fileInputRef,
  isDraggingOver,
  setIsDraggingOver,
  handleUploadBatch,
  documentsLength,
  pendingSourcesLength,
}) => {
  const { t } = useTranslation();

  if (!isOpen) return null;

  return (
    <Portal>
      <div 
        onClick={(e) => {
          e.stopPropagation();
          onClose();
          setDoiInput("");
        }}
        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      >
      <div 
        onClick={(e) => e.stopPropagation()}
        className="bg-app-modal border border-app-border-strong rounded-3xl w-full max-w-xl p-6 sm:p-7 shadow-2xl space-y-6 animate-in zoom-in-95 duration-150 relative text-app-text"
      >
        {/* Close Button */}
        <Tooltip content={t('right.close') || "Close"} side="bottom">
          <button
            onClick={() => {
              onClose();
              setDoiInput("");
            }}
            className="absolute top-5 right-5 p-1.5 rounded-full hover:bg-app-item-hover text-app-text-muted hover:text-app-text transition-colors cursor-pointer"
            aria-label={t('right.close') || "Close"}
          >
            <X size={18} />
          </button>
        </Tooltip>

        {/* Modal Header */}
        <div className="space-y-1.5 pr-8">
          <h2 className="text-xl font-bold text-app-text tracking-tight leading-snug">
            {t('ui.addSources')}
          </h2>
          <p className="text-xs text-app-text-muted">
            {t('right.addSourcesModalDesc')}
          </p>
        </div>

        {/* Section 1: Fast DOI Input Bar */}
        <div className="space-y-2">
          <form onSubmit={handleImportDoi} className="relative flex items-center">
            <div className="relative w-full">
              <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-app-text-dim pointer-events-none">
                <Search size={15} />
              </div>
              <input
                type="text"
                value={doiInput}
                onChange={(e) => setDoiInput(e.target.value)}
                placeholder={t('right.enterDoi')}
                className="w-full h-11 pl-10 pr-24 rounded-full bg-app-input-surface border border-app-border focus:border-blue-500 text-xs text-app-text placeholder:text-app-text-dim focus:outline-none transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={!doiInput.trim()}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 h-8 px-3.5 rounded-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
            >
              <span>{t('right.import')}</span>
            </button>
          </form>
        </div>

        {/* Section 2: Drag and Drop Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDraggingOver(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDraggingOver(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDraggingOver(false);
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
              handleUploadBatch(Array.from(e.dataTransfer.files));
            }
          }}
          onClick={() => {
            fileInputRef.current?.click();
          }}
          className={`p-8 sm:p-10 rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center text-center space-y-3 ${
            isDraggingOver
              ? "border-blue-500 bg-blue-500/10 scale-[1.01]"
              : "border-app-border-strong hover:border-blue-500/50 bg-app-card hover:bg-app-card-hover"
          }`}
        >
          <div className="w-12 h-12 rounded-full bg-app-surface border border-app-border flex items-center justify-center text-app-text-muted">
            <UploadCloud size={24} className="text-app-text-muted" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold text-app-text">
              {t('right.dropFiles')}
            </p>
            <p className="text-xs text-app-text-dim">
              {t('right.supportedFormats')}
            </p>
          </div>
        </div>

        {/* Section 3: Capacity Progress Bar (300 Sources Max) */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-xs text-app-text-muted">
            <span>{t('right.sourcesCapacity')}</span>
            <span className="font-medium text-app-text font-mono">
              {documentsLength + pendingSourcesLength} / 300
            </span>
          </div>
          <div className="w-full h-1.5 bg-app-input-surface rounded-full overflow-hidden border border-app-border">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, ((documentsLength + pendingSourcesLength) / 300) * 100)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
    </Portal>
  );
};
