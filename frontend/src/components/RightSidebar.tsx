import { CitationModal } from "./RightSidebar/CitationModal";
import { DocumentReader } from "./RightSidebar/DocumentReader";
import { AddSourcesModal } from "./RightSidebar/AddSourcesModal";
import { DocumentListPanel } from "./RightSidebar/DocumentListPanel";
import { usePaperDetails } from "@/hooks/usePaperDetails";
import { cleanHtmlAbstract, getHighlightedContent, formatReadableDate } from "./RightSidebar/DocumentReaderUtils";
import { generateCitations, CitationFormats } from "@/hooks/useCitationGenerator";
"use client";
import { useDocumentManager } from "@/hooks/useDocumentManager";

import { useState, useRef, useEffect, useMemo } from "react";
import { 
  Plus, 
  Check, 
  Minus,
  Trash2, 
  Download,
  Sidebar, 
  FileText, 
  Loader2,
  ArrowLeft,
  X,
  Copy,
  MessageSquare,
  Quote,
  Link as LinkIcon,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Sparkles,
  Info,
  Search,
  UploadCloud,
  AlertCircle,
  Pencil,
  MoreHorizontal
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Document, CitationGroundingHighlight, PendingSourceItem } from "@/stores/documentStore";
import { useTranslation } from "@/lib/i18n";
import { consumeSSEStream } from "@/lib/sse";
import { DownloadManager, DownloadTask } from "./DownloadManager";
import { BulkDeleteModal, RenameModal } from "./sidebar/SidebarModals";

interface RightSidebarProps {
  activeChatId: string | null;
  documents: Document[];
  pendingSources?: PendingSourceItem[];
  onDocumentAdded: (doc: Document, targetChatId?: string) => void;
  onDocumentUpdated?: (doc: Document) => void;
  onDocumentDeleted?: (id: number) => void;
  onBulkDocumentsDeleted?: (ids: number[]) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  onAskAboutDocument?: (doc: Document, paperTitle?: string) => void;
  externalViewingDoc?: Document | null;
  groundingHighlight?: CitationGroundingHighlight | null;
  onClearGroundingHighlight?: () => void;
  onClearViewingDoc?: () => void;
  backendUrl: string;
  onClose: () => void;
}

// export interface PendingSourceItem {
//   id: string;
//   filename: string;
//   type: "file" | "doi";
//   doi?: string;
//   status: "uploading" | "error";
//   error?: string;
// }

interface PaperDetailData {
  id: number;
  filename: string;
  created_at?: string;
  type: string;
  title: string;
  authors: string[];
  publication_date: string;
  year: string;
  journal: string;
  journal_metric: string;
  quality_tier?: number;
  citations: number;
  doi: string;
  url: string;
  pdf_url: string;
  abstract: string;
  abstract_type?: "official" | "ai_summary";
  is_oa?: boolean;
  access_status?: string;
  has_full_pdf?: boolean;
  is_abstract_only?: boolean;
  content: string;
}

export default function RightSidebar({ 
  activeChatId, 
  documents, 
  pendingSources: externalPendingSources = [],
  onDocumentAdded, 
  onDocumentUpdated,
  onDocumentDeleted, 
  onBulkDocumentsDeleted, 
  onEnsureChatSession, 
  onAskAboutDocument, 
  externalViewingDoc, 
  groundingHighlight,
  onClearGroundingHighlight,
  onClearViewingDoc, 
  backendUrl, 
  onClose 
}: RightSidebarProps) {
  const { t } = useTranslation();
  const { viewingDoc, setViewingDoc, paperDetails, isLoadingDetails, activeTab, setActiveTab } = usePaperDetails({ activeChatId, backendUrl, externalViewingDoc, groundingHighlight });
  const {
    selectedDocs, setSelectedDocs,
    sortBy, setSortBy,
    sortDirection, setSortDirection,
    isSortMenuOpen, setIsSortMenuOpen,
    activeMenuId, setActiveMenuId,
    isCleaningDuplicates, setIsCleaningDuplicates,
    cleanFeedback, setCleanFeedback,
    isAddSourcesModalOpen, setIsAddSourcesModalOpen,
    doiInput, setDoiInput,
    internalPendingSources, setInternalPendingSources,
    pendingSources,
    isDraggingOver, setIsDraggingOver,
    isRenameModalOpen, setIsRenameModalOpen,
    renamingDoc, setRenamingDoc,
    renameTitleInput, setRenameTitleInput,
    isSavingRename, setIsSavingRename,
    renameError, setRenameError,
    docToDelete, setDocToDelete,
    showBulkDeleteConfirm, setShowBulkDeleteConfirm,
    isBulkDeleting, setIsBulkDeleting,
    isBulkDownloading, setIsBulkDownloading,
    downloadTask, setDownloadTask,
    selectedDocList, selectedCount,
    isAllSelected, isPartiallySelected,
    sortedDocuments,
    toggleDocSelection, handleToggleSelectAll,
    getFileBadgeInfo, handleOpenRename, handleSaveRename,
    handleCleanDuplicates, handleBulkDownload, handleConfirmBulkDelete,
    handleUploadBatch, handleImportDoi, downloadFileText
  } = useDocumentManager({
    documents,
    externalPendingSources,
    activeChatId,
    backendUrl,
    onDocumentAdded,
    onDocumentUpdated,
    onBulkDocumentsDeleted,
    onEnsureChatSession,
    viewingDoc,
    setViewingDoc,
    t
  });
  const sortMenuRef = useRef<HTMLDivElement>(null);


  // Citation Modal State
  const [isCiteModalOpen, setIsCiteModalOpen] = useState<boolean>(false);
  const [selectedCitationStyle, setSelectedCitationStyle] = useState<"apa" | "ieee" | "harvard" | "mla" | "chicago" | "bibtex" | "ris">("apa");
  const [copiedCitationKey, setCopiedCitationKey] = useState<string | null>(null);

  const [copiedDoi, setCopiedDoi] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeMatchIndex, setActiveMatchIndex] = useState<number>(0);
  const [totalMatches, setTotalMatches] = useState<number>(0);
  const highlightRefsMap = useRef<Map<number, HTMLElement>>(new Map());

  // Reset active highlight match index when highlighted target changes (or same citation re-clicked)
  useEffect(() => {
    setActiveMatchIndex(0);
    highlightRefsMap.current.clear();
  }, [groundingHighlight?.clickId, groundingHighlight?.sentence, viewingDoc?.id]);

  // Auto-scroll to current active highlighted cluster
  useEffect(() => {
    if (!isLoadingDetails) {
      const timer = setTimeout(() => {
        const targetEl = highlightRefsMap.current.get(activeMatchIndex);
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [isLoadingDetails, activeMatchIndex, groundingHighlight, activeTab, paperDetails?.content]);

  // Local memory cache for instant viewer loading without repeated network/parsing overhead
  // Close sort menu on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // Logic for main sort menu
      if (isSortMenuOpen && sortMenuRef.current && !sortMenuRef.current.contains(event.target as Node)) {
        setIsSortMenuOpen(false);
      }
      
      // Logic for 3 dots menu
      // Check if click is outside of any document action menu (which we assume has a specific data attribute to avoid conflicts)
      const target = event.target as HTMLElement;
      if (activeMenuId !== null && !target.closest('.document-action-menu-container')) {
        setActiveMenuId(null);
      }
    };
    
    if (isSortMenuOpen || activeMenuId !== null) {
      window.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isSortMenuOpen, activeMenuId]);





















  const copyToClipboard = (text: string, type: "doi" | "link" | "citation") => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    if (type === "doi") {
      setCopiedDoi(true);
      setTimeout(() => setCopiedDoi(false), 2000);
    } else if (type === "link") {
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };


  if (viewingDoc) {
    const filenameFallback = ((viewingDoc as any)?.filename || "paper").replace(/\.[^/.]+$/, "").replace(/_/g, " ");
    const GENERIC_HEADERS = new Set([
      "abstract", "abstrak", "overview", "paper", "document", "introduction", "keywords",
      "article in press", "in press", "journal pre-proof", "uncorrected proof",
      "corrected proof", "original article", "research article", "full length article",
      "short communication", "review article", "full paper", "research paper",
      "accepted manuscript", "author's copy",
    ]);
    let title = (paperDetails?.title || filenameFallback).replace(/<[^>]+>/g, "");
    if (!title || GENERIC_HEADERS.has(title.trim().toLowerCase())) {
      title = filenameFallback;
    }
    const authorsStr = paperDetails?.authors && paperDetails.authors.length > 0
      ? paperDetails.authors.join(", ")
      : t('right.academicResearchers');
    const pubDateStr = formatReadableDate(paperDetails?.publication_date, paperDetails?.year);
    const journalName = paperDetails?.journal || t('right.scholarlyPublication');
    const citationsCount = paperDetails?.citations !== undefined ? paperDetails.citations : 0;
    const doiStr = paperDetails?.doi || "";
    const cleanAbstract = cleanHtmlAbstract(paperDetails?.abstract) || (isLoadingDetails ? "" : t('right.noAbstractProvided'));
    const landingUrl = paperDetails?.url || (doiStr ? "https://doi.org/$" : "");

    return (
      <DocumentReader
        viewingDoc={viewingDoc}
        paperDetails={paperDetails}
        isLoadingDetails={isLoadingDetails}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onClose={onClose}
        setViewingDoc={setViewingDoc}
        onClearViewingDoc={onClearViewingDoc}
        onAskAboutDocument={onAskAboutDocument}
        backendUrl={backendUrl}
        activeChatId={activeChatId}
        totalMatches={totalMatches}
        activeMatchIndex={activeMatchIndex}
        navigateMatch={(dir) => {
          if (dir === "next") {
            setActiveMatchIndex(prev => prev < totalMatches - 1 ? prev + 1 : 0);
          } else {
            setActiveMatchIndex(prev => prev > 0 ? prev - 1 : totalMatches - 1);
          }
        }}
        getHighlightedContent={() => getHighlightedContent((paperDetails?.content || (viewingDoc as any)?.content || ""), (groundingHighlight?.sentence || ""), highlightRefsMap, activeMatchIndex, groundingHighlight?.aiQuotes).nodes}
        cleanAbstract={cleanAbstract}
        authorsStr={authorsStr}
        pubDateStr={pubDateStr}
        journalName={journalName}
        citationsCount={citationsCount}
        landingUrl={landingUrl}
        title={title}
        copiedLink={copiedLink}
        copyToClipboard={copyToClipboard}
        setIsCiteModalOpen={setIsCiteModalOpen}
      />
    );
  }

  // ==========================================
  // VIEW MODE: STANDARD SOURCES LIST PANEL
  // ==========================================
  return (
    <aside className="w-full lg:w-80 h-full bg-app-sidebar border-l border-app-border flex flex-col shrink-0 select-none z-10 transition-all relative text-app-text">
      {/* 1. Header Bar: Top Fixed Header */}
      <div className="px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-app-text tracking-tight">{t('ui.sources') || "Sources"}</span>
          <span className="px-1.5 py-0.5 rounded-full text-[10.5px] font-mono font-medium bg-app-item-hover text-app-text-muted">
            {documents.length}
          </span>
        </div>
        <button 
          onClick={onClose}
          className="w-7 h-7 rounded-lg bg-app-item-hover hover:bg-app-item-active text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer"
          title={t('right.close') || "Hide sidebar"}
        >
          <X size={15} />
        </button>
      </div>

      {/* Hidden File Input for Multi-format Document Upload */}
      <input
        ref={fileInputRef}
        type="file"
        id="sources-file-upload"
        className="hidden"
        accept=".pdf,.docx,.doc,.txt,.md,.bib,.bibtex,.ris"
        multiple
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleUploadBatch(Array.from(e.target.files));
          }
          if (e.target) e.target.value = "";
        }}
      />

      {/* 2 & 3. Fixed Controls Area (Add Sources + Toolbar) */}
      <div className="p-3.5 pb-2.5 space-y-2.5 shrink-0 bg-app-sidebar z-10 border-b border-app-divider shadow-sm">
        {/* Prominent '+ Add sources' Button (NotebookLM Style) */}
        <div className="w-full">
          <Button
            variant="outline"
            className="w-full h-11 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text font-medium text-sm flex items-center justify-center gap-2 cursor-pointer shadow-sm transition-colors"
            onClick={() => setIsAddSourcesModalOpen(true)}
          >
            <Plus size={18} className="text-app-text-muted" />
            <span>{t('ui.addSources')}</span>
          </Button>
        </div>

        {/* Dynamic Clean Feedback Notification */}
        {cleanFeedback && (
          <div className="w-full px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-medium flex items-center gap-2 animate-in fade-in zoom-in-95 duration-150">
            <Check size={13} className="text-emerald-400 shrink-0" />
            <span className="text-[12px]">{cleanFeedback}</span>
          </div>
        )}

        {/* Action Toolbar (Always-rendered icons with dynamic disabled states) */}
        <div className="w-full flex items-center justify-between pt-1 px-0 text-xs text-app-text-muted relative">
          <div className="flex items-center gap-1">
            {/* Sort Button & Dropdown (Disabled if <= 1 document) */}
            <div className="relative" ref={sortMenuRef}>
              <button 
                onClick={() => {
                  if (documents.length > 1) {
                    setIsSortMenuOpen(prev => !prev);
                  }
                }}
                disabled={documents.length <= 1}
                className={`w-6 h-6 -ml-1 rounded transition-colors flex items-center justify-center ${
                  documents.length > 1
                    ? "text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer"
                    : "text-app-text-dim opacity-30 cursor-not-allowed"
                }`}
                title={documents.length > 1 ? t('right.sortSources') : t('right.addMoreSort')}
              >
                <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" className="opacity-90">
                  <rect x="2" y="3" width="12" height="1.6" rx="0.8" />
                  <rect x="2" y="7.2" width="8" height="1.6" rx="0.8" />
                  <rect x="2" y="11.4" width="4.5" height="1.6" rx="0.8" />
                </svg>
              </button>

              {/* Sort Dropdown Menu (2 Sections with Divider: Criteria & Direction) */}
              {isSortMenuOpen && (
                <div className="absolute left-0 top-7 z-30 w-36 rounded-xl bg-app-dropdown border border-app-border-strong shadow-2xl p-1 text-xs animate-in fade-in zoom-in-95 duration-100 text-app-text">
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

                  {/* Section 2: Sort Direction (Ascending / Descending) */}
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

            {/* Always Rendered Action Icon Buttons with Clean Disabled State */}
            <div className="flex items-center gap-1">
              {/* Clean Duplicates Button */}
              <button
                onClick={handleCleanDuplicates}
                disabled={documents.length <= 1 || isCleaningDuplicates}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  documents.length > 1 && !isCleaningDuplicates
                    ? "text-app-text-muted hover:text-emerald-500 hover:bg-emerald-500/10 cursor-pointer"
                    : "text-app-text-dim opacity-30 cursor-not-allowed"
                }`}
                title={t('right.cleanDup')}
              >
                {isCleaningDuplicates ? (
                  <Loader2 size={14} className="animate-spin text-emerald-500" />
                ) : (
                  <Sparkles size={14} />
                )}
              </button>

              {/* Rename Button (Enabled strictly when exactly 1 source is selected) */}
              <button
                onClick={handleOpenRename}
                disabled={selectedCount !== 1}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  selectedCount === 1
                    ? "text-app-text-muted hover:text-blue-500 hover:bg-blue-500/10 cursor-pointer"
                    : selectedCount > 1
                    ? "text-app-text-dim opacity-25 cursor-not-allowed"
                    : "text-app-text-dim opacity-30 cursor-not-allowed"
                }`}
                title={
                  selectedCount === 1
                    ? t('right.renameSelected')
                    : selectedCount > 1
                    ? t('right.renameMultiError').replace('{n}', selectedCount.toString())
                    : t('right.renameSelectOne')
                }
              >
                <Pencil size={14} />
              </button>

              {/* Download Button */}
              {(() => {
                const downloadableSelectedCount = selectedDocList.filter(d => d.has_full_pdf !== false).length;
                const canDownload = selectedCount > 0 && downloadableSelectedCount > 0 && !isBulkDownloading;
                const tooltipText = selectedCount === 0 
                  ? t('right.selectToDownload')
                  : downloadableSelectedCount === 0
                  ? t('right.downloadNotAvail')
                  : selectedCount === 1
                  ? t('right.downloadPdf')
                  : downloadableSelectedCount === selectedCount
                  ? t('right.downloadSelected').replace('{n}', selectedCount.toString())
                  : t('right.downloadSelectedSkip').replace('{n}', downloadableSelectedCount.toString()).replace('{m}', (selectedCount - downloadableSelectedCount).toString());

                return (
                  <button
                    onClick={handleBulkDownload}
                    disabled={!canDownload}
                    className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                      canDownload
                        ? "text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer"
                        : "text-app-text-dim opacity-30 cursor-not-allowed"
                    }`}
                    title={tooltipText}
                  >
                    {isBulkDownloading ? (
                      <Loader2 size={15} className="animate-spin text-blue-500" />
                    ) : (
                      <Download size={15} />
                    )}
                  </button>
                );
              })()}

              {/* Delete Button */}
              <button
                onClick={() => {
                  setDocToDelete(null); // Ensure bulk delete mode uses selected checkboxes
                  setShowBulkDeleteConfirm(true);
                }}
                disabled={selectedCount === 0 || isBulkDeleting}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  selectedCount > 0
                    ? "text-app-text-muted hover:text-red-500 hover:bg-red-500/10 cursor-pointer"
                    : "text-app-text-dim opacity-30 cursor-not-allowed"
                }`}
                title={selectedCount > 0 ? t('right.deleteSelected').replace('{n}', selectedCount.toString()) : t('right.selectToDelete')}
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>

          {/* Select all label and checkbox (Disabled when 0 documents) */}
          <div className={`flex items-center gap-2 pr-0.5 whitespace-nowrap select-none ${
            documents.length === 0 ? "opacity-30 pointer-events-none" : ""
          }`}>
            <span className="text-[11px] font-medium text-app-text-muted select-none">{t('right.selectAll')}</span>
            <button
              type="button"
              onClick={handleToggleSelectAll}
              disabled={documents.length === 0}
              className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
                documents.length === 0 
                  ? "border-app-border-strong bg-transparent cursor-not-allowed"
                  : isAllSelected || isPartiallySelected 
                  ? "bg-blue-600 border-blue-600 text-white cursor-pointer hover:border-gray-300" 
                  : "border-app-border-strong bg-transparent cursor-pointer hover:border-blue-500"
              }`}
              title={documents.length === 0 ? t('right.noSourcesAvail') : isAllSelected ? t('right.unselectAll') : t('right.selectAll')}
            >
              {isAllSelected && documents.length > 0 ? (
                <Check size={10} strokeWidth={3} />
              ) : isPartiallySelected ? (
                <Minus size={10} strokeWidth={3} />
              ) : null}
            </button>
          </div>
        </div>
      </div>

      {/* 4. Scrollable Document List Area ONLY */}
      <DocumentListPanel
        documents={documents}
        sortedDocuments={sortedDocuments}
        pendingSources={pendingSources}
        selectedDocs={selectedDocs}
        activeMenuId={activeMenuId}
        setActiveMenuId={setActiveMenuId}
        setViewingDoc={setViewingDoc}
        toggleDocSelection={toggleDocSelection}
        getFileBadgeInfo={getFileBadgeInfo}
        setRenamingDoc={setRenamingDoc}
        setRenameTitleInput={setRenameTitleInput}
        setRenameError={setRenameError}
        setIsRenameModalOpen={setIsRenameModalOpen}
        setDocToDelete={setDocToDelete}
        setShowBulkDeleteConfirm={setShowBulkDeleteConfirm}
        setInternalPendingSources={setInternalPendingSources}
        activeChatId={activeChatId}
        backendUrl={backendUrl}
      />

      {/* Google NotebookLM Style 'Add Sources' Centered Modal Dialog */}
      <AddSourcesModal
        isOpen={isAddSourcesModalOpen}
        onClose={() => setIsAddSourcesModalOpen(false)}
        doiInput={doiInput}
        setDoiInput={setDoiInput}
        handleImportDoi={handleImportDoi}
        fileInputRef={fileInputRef}
        isDraggingOver={isDraggingOver}
        setIsDraggingOver={setIsDraggingOver}
        handleUploadBatch={handleUploadBatch}
        documentsLength={documents.length}
        pendingSourcesLength={pendingSources.length}
      />

      <CitationModal
        isOpen={isCiteModalOpen}
        onClose={() => setIsCiteModalOpen(false)}
        citations={generateCitations(
            paperDetails?.title || ((viewingDoc as any)?.filename || "paper") || "",
            paperDetails?.authors || [],
            paperDetails?.year || "2024",
            paperDetails?.journal || "",
            paperDetails?.doi || "",
            paperDetails?.url || (paperDetails?.doi ? "https://doi.org/$" : "")
        )}
        doiStr={paperDetails?.doi || ""}
      />

      {/* Centered Modal for Bulk Delete Confirmation */}
      <BulkDeleteModal
        isOpen={showBulkDeleteConfirm}
        selectedCount={docToDelete !== null ? 1 : selectedCount}
        isBulkDeleting={isBulkDeleting}
        onClose={() => {
          setShowBulkDeleteConfirm(false);
          setDocToDelete(null);
        }}
        onConfirm={handleConfirmBulkDelete}
      />

      {/* Centered Modal for Renaming Single Document */}
      <RenameModal
        isOpen={isRenameModalOpen}
        renamingDoc={renamingDoc}
        renameTitleInput={renameTitleInput}
        isSavingRename={isSavingRename}
        onInputChange={setRenameTitleInput}
        onClose={() => setIsRenameModalOpen(false)}
        onSave={handleSaveRename}
      />
    </aside>
  );
}
























