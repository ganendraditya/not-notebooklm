import React from "react";
import { Check, Sparkles, Edit2, Loader2, Download, Trash2, Minus } from "lucide-react";
import { useTranslation } from "@/lib/i18n";
import { Document } from "@/stores/documentStore";
import { Tooltip } from "@/components/ui/tooltip";

interface SourcesToolbarProps {
  documents: Document[];
  selectedCount: number;
  isSortMenuOpen: boolean;
  setIsSortMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  sortMenuRef: React.RefObject<HTMLDivElement | null>;
  sortBy: "date" | "title";
  setSortBy: (sort: "date" | "title") => void;
  sortDirection: "asc" | "desc";
  setSortDirection: (dir: "asc" | "desc") => void;
  isCleaningDuplicates: boolean;
  handleCleanDuplicates: () => void;
  handleOpenRename: () => void;
  handleBulkDownload: () => void;
  isBulkDownloading: boolean;
  isBulkDeleting: boolean;
  setDocToDelete: (id: number | null) => void;
  setShowBulkDeleteConfirm: (show: boolean) => void;
  handleToggleSelectAll: () => void;
  isAllSelected: boolean;
  isPartiallySelected: boolean;
  selectedDocList: Document[];
}

export const SourcesToolbar: React.FC<SourcesToolbarProps> = ({
  documents,
  selectedCount,
  isSortMenuOpen,
  setIsSortMenuOpen,
  sortMenuRef,
  sortBy,
  setSortBy,
  sortDirection,
  setSortDirection,
  isCleaningDuplicates,
  handleCleanDuplicates,
  handleOpenRename,
  handleBulkDownload,
  isBulkDownloading,
  isBulkDeleting,
  setDocToDelete,
  setShowBulkDeleteConfirm,
  handleToggleSelectAll,
  isAllSelected,
  isPartiallySelected,
  selectedDocList
}) => {
  const { t } = useTranslation();

  return (
    <div className="w-full flex items-center justify-between pt-1 px-0 text-xs text-app-text-muted relative">
      <div className="flex items-center gap-1">
        {/* Sort Button & Dropdown (Disabled if <= 1 document) */}
        <div className="relative" ref={sortMenuRef}>
          <Tooltip content={documents.length > 1 ? t('right.sortSources') : t('right.addMoreSort')} side="bottom">
            <button 
              onClick={() => {
                if (documents.length > 1) {
                  setIsSortMenuOpen(prev => !prev);
                }
              }}
              disabled={documents.length <= 1}
              className={`w-7 h-7 rounded-lg transition-colors flex items-center justify-center ${
                documents.length > 1
                  ? "text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer"
                  : "text-app-text-dim opacity-30 cursor-not-allowed"
              }`}
              aria-label={documents.length > 1 ? t('right.sortSources') : t('right.addMoreSort')}
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" className="opacity-90">
                <rect x="2" y="3" width="12" height="1.6" rx="0.8" />
                <rect x="2" y="7.2" width="8" height="1.6" rx="0.8" />
                <rect x="2" y="11.4" width="4.5" height="1.6" rx="0.8" />
              </svg>
            </button>
          </Tooltip>

          {/* Sort Dropdown Menu */}
          {isSortMenuOpen && (
            <div className="absolute left-0 top-8 z-30 w-36 rounded-xl bg-app-dropdown border border-app-border-strong shadow-2xl p-1 text-xs animate-in fade-in zoom-in-95 duration-100 text-app-text">
              {/* Section 1: Sort Criteria */}
              <div className="space-y-0.5 pb-0.5">
                <button
                  onClick={() => { setSortBy("title"); setIsSortMenuOpen(false); }}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
                >
                  <span className={sortBy === "title" ? "text-app-text font-medium" : "text-app-text-muted"}>Title</span>
                  {sortBy === "title" && <Check size={13} className="text-blue-500" strokeWidth={2.5} />}
                </button>
                <button
                  onClick={() => { setSortBy("date"); setIsSortMenuOpen(false); }}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
                >
                  <span className={sortBy === "date" ? "text-app-text font-medium" : "text-app-text-muted"}>Date added</span>
                  {sortBy === "date" && <Check size={13} className="text-blue-500" strokeWidth={2.5} />}
                </button>
              </div>

              {/* Section Divider Line */}
              <div className="border-t border-app-divider my-1" />

              {/* Section 2: Sort Direction */}
              <div className="space-y-0.5 pt-0.5">
                <button
                  onClick={() => { setSortDirection("asc"); setIsSortMenuOpen(false); }}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
                >
                  <span className={sortDirection === "asc" ? "text-app-text font-medium" : "text-app-text-muted"}>Ascending</span>
                  {sortDirection === "asc" && <Check size={13} className="text-blue-500" strokeWidth={2.5} />}
                </button>
                <button
                  onClick={() => { setSortDirection("desc"); setIsSortMenuOpen(false); }}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
                >
                  <span className={sortDirection === "desc" ? "text-app-text font-medium" : "text-app-text-muted"}>Descending</span>
                  {sortDirection === "desc" && <Check size={13} className="text-blue-500" strokeWidth={2.5} />}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Action Icon Buttons */}
        <div className="flex items-center gap-0.5">
          {/* Clean Duplicates */}
          <Tooltip content={t('right.cleanDup')} side="bottom">
            <button
              onClick={handleCleanDuplicates}
              disabled={documents.length <= 1 || isCleaningDuplicates}
              className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors ${
                documents.length > 1 && !isCleaningDuplicates
                  ? "text-app-text-muted hover:text-emerald-500 hover:bg-emerald-500/15 cursor-pointer"
                  : "text-app-text-dim opacity-30 cursor-not-allowed"
              }`}
              aria-label={t('right.cleanDup')}
            >
              {isCleaningDuplicates ? (
                <Loader2 size={14} className="animate-spin text-emerald-500" />
              ) : (
                <Sparkles size={14} />
              )}
            </button>
          </Tooltip>

          {/* Rename Button */}
          <Tooltip
            content={
              selectedCount === 1
                ? t('right.renameSelected')
                : selectedCount > 1
                ? t('right.selectOneRename')
                : t('right.selectToRename')
            }
            side="bottom"
          >
            <button
              onClick={handleOpenRename}
              disabled={selectedCount !== 1}
              className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors ${
                selectedCount === 1
                  ? "text-app-text-muted hover:text-blue-500 hover:bg-blue-500/15 cursor-pointer"
                  : selectedCount > 1
                  ? "text-app-text-dim opacity-25 cursor-not-allowed"
                  : "text-app-text-dim opacity-30 cursor-not-allowed"
              }`}
              aria-label={
                selectedCount === 1
                  ? t('right.renameSelected')
                  : selectedCount > 1
                  ? t('right.selectOneRename')
                  : t('right.selectToRename')
              }
            >
              <Edit2 size={14} />
            </button>
          </Tooltip>

          {/* Bulk Download Button */}
          {(() => {
            const hasSelection = selectedCount > 0;
            const canDownload = hasSelection && !isBulkDownloading;
            const tooltipText = isBulkDownloading
              ? (t('download.preparing') || "Downloading...")
              : selectedCount === 0
              ? (t('right.selectToDownload') || "Select sources to download")
              : selectedCount === 1
              ? (selectedDocList[0]?.has_full_pdf !== false 
                  ? (t('right.downloadPdf') || "Download manuscript PDF") 
                  : (t('right.downloadFile') || "Download document text"))
              : (t('right.downloadSelected')?.replace('{n}', selectedCount.toString()) || `Download ${selectedCount} selected files`);

            return (
              <Tooltip content={tooltipText} side="bottom">
                <button
                  onClick={handleBulkDownload}
                  disabled={!canDownload}
                  className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors ${
                    canDownload
                      ? "text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer"
                      : "text-app-text-dim opacity-30 cursor-not-allowed"
                  }`}
                  aria-label={tooltipText}
                >
                  {isBulkDownloading ? (
                    <Loader2 size={15} className="animate-spin text-blue-500" />
                  ) : (
                    <Download size={15} />
                  )}
                </button>
              </Tooltip>
            );
          })()}

          {/* Delete Button */}
          <Tooltip
            content={selectedCount > 0 ? t('right.deleteSelected').replace('{n}', selectedCount.toString()) : t('right.selectToDelete')}
            side="bottom"
          >
            <button
              onClick={() => {
                setDocToDelete(null);
                setShowBulkDeleteConfirm(true);
              }}
              disabled={selectedCount === 0 || isBulkDeleting}
              className={`w-7 h-7 rounded-lg flex items-center justify-center transition-colors ${
                selectedCount > 0
                  ? "text-app-text-muted hover:text-red-500 hover:bg-red-500/15 cursor-pointer"
                  : "text-app-text-dim opacity-30 cursor-not-allowed"
              }`}
              aria-label={selectedCount > 0 ? t('right.deleteSelected').replace('{n}', selectedCount.toString()) : t('right.selectToDelete')}
            >
              <Trash2 size={15} />
            </button>
          </Tooltip>
        </div>
      </div>

      {/* Select all label and checkbox */}
      <div 
        onClick={() => {
          if (documents.length > 0) {
            handleToggleSelectAll();
          }
        }}
        className={`flex items-center gap-2 pr-0 whitespace-nowrap select-none ${
          documents.length === 0 ? "opacity-30 pointer-events-none" : "cursor-pointer group/selectall"
        }`}
      >
        <span className="text-[11px] font-medium text-app-text-muted group-hover/selectall:text-app-text transition-colors select-none">
          {(isAllSelected || isPartiallySelected) ? t('right.unselectAll') : t('right.selectAll')}
        </span>
        <Tooltip
          content={documents.length === 0 ? t('right.noSourcesAvail') : (isAllSelected || isPartiallySelected) ? t('right.unselectAll') : t('right.selectAll')}
          side="left"
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleToggleSelectAll();
            }}
            disabled={documents.length === 0}
            className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
              documents.length === 0 
                ? "border-app-border-strong bg-transparent cursor-not-allowed"
                : isAllSelected || isPartiallySelected
                ? "bg-blue-600 border-blue-600 text-white cursor-pointer hover:bg-blue-700" 
                : "border-app-border-strong bg-transparent cursor-pointer group-hover/selectall:border-gray-500"
            }`}
            aria-label={documents.length === 0 ? t('right.noSourcesAvail') : (isAllSelected || isPartiallySelected) ? t('right.unselectAll') : t('right.selectAll')}
          >
            {isAllSelected && documents.length > 0 ? (
              <Check size={9} strokeWidth={3} />
            ) : isPartiallySelected ? (
              <Minus size={9} strokeWidth={3} />
            ) : null}
          </button>
        </Tooltip>
      </div>
    </div>
  );
};