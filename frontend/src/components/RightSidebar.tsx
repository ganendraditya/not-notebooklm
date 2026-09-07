import { DocumentReader } from "./RightSidebar/DocumentReader";
import { DocumentListPanel } from "./RightSidebar/DocumentListPanel";
import { usePaperDetails } from "@/hooks/usePaperDetails";
import { cleanHtmlAbstract, getHighlightedContent, formatReadableDate } from "./RightSidebar/DocumentReaderUtils";
"use client";
import { useDocumentManager } from "@/hooks/useDocumentManager";

import { useState, useRef, useEffect, useMemo } from "react";
import { Plus, X, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Document, CitationGroundingHighlight, PendingSourceItem } from "@/stores/documentStore";
import { useTranslation } from "@/lib/i18n";
import { SourcesToolbar } from "./RightSidebar/SourcesToolbar";
import { RightSidebarModals } from "./RightSidebar/RightSidebarModals";

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

  const currentContent = paperDetails?.content || (viewingDoc as any)?.content || "";

  const highlightResult = useMemo(() => {
    return getHighlightedContent(
      currentContent,
      groundingHighlight?.sentence || "",
      // eslint-disable-next-line react-hooks/refs
      highlightRefsMap,
      activeMatchIndex,
      groundingHighlight?.aiQuotes
    );
  }, [currentContent, groundingHighlight?.sentence, groundingHighlight?.aiQuotes, activeMatchIndex]);

  useEffect(() => {
    setTotalMatches(highlightResult.matchCount);
    if (highlightResult.matchCount > 0) {
      if (highlightResult.initialActiveIndex !== undefined) {
        setActiveMatchIndex(highlightResult.initialActiveIndex);
      } else if (activeMatchIndex >= highlightResult.matchCount) {
        setActiveMatchIndex(0);
      }
    }
  }, [highlightResult.matchCount, highlightResult.initialActiveIndex]);

  // Reset highlight refs when highlighted target changes (or same citation re-clicked)
  useEffect(() => {
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
        getHighlightedContent={() => highlightResult.nodes}
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
    <aside className="w-full lg:w-80 h-full bg-app-sidebar border-l border-app-border flex flex-col shrink-0 z-10 transition-all relative text-app-text">
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

        <SourcesToolbar
          documents={documents}
          selectedCount={selectedCount}
          isSortMenuOpen={isSortMenuOpen}
          setIsSortMenuOpen={setIsSortMenuOpen}
          sortMenuRef={sortMenuRef}
          sortBy={sortBy}
          setSortBy={setSortBy}
          sortDirection={sortDirection}
          setSortDirection={setSortDirection}
          isCleaningDuplicates={isCleaningDuplicates}
          handleCleanDuplicates={handleCleanDuplicates}
          handleOpenRename={handleOpenRename}
          handleBulkDownload={handleBulkDownload}
          isBulkDownloading={isBulkDownloading}
          isBulkDeleting={isBulkDeleting}
          setDocToDelete={setDocToDelete}
          setShowBulkDeleteConfirm={setShowBulkDeleteConfirm}
          handleToggleSelectAll={handleToggleSelectAll}
          isAllSelected={isAllSelected}
          isPartiallySelected={isPartiallySelected}
          selectedDocList={selectedDocList}
        />
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

      {/* Modals Composition */}
      <RightSidebarModals
        isAddSourcesModalOpen={isAddSourcesModalOpen}
        setIsAddSourcesModalOpen={setIsAddSourcesModalOpen}
        doiInput={doiInput}
        setDoiInput={setDoiInput}
        handleImportDoi={handleImportDoi}
        fileInputRef={fileInputRef}
        isDraggingOver={isDraggingOver}
        setIsDraggingOver={setIsDraggingOver}
        handleUploadBatch={handleUploadBatch}
        documentsLength={documents.length}
        pendingSourcesLength={pendingSources.length}
        isCiteModalOpen={isCiteModalOpen}
        setIsCiteModalOpen={setIsCiteModalOpen}
        paperDetails={paperDetails}
        viewingDoc={viewingDoc}
        showBulkDeleteConfirm={showBulkDeleteConfirm}
        docToDelete={docToDelete}
        selectedCount={selectedCount}
        isBulkDeleting={isBulkDeleting}
        setShowBulkDeleteConfirm={setShowBulkDeleteConfirm}
        setDocToDelete={setDocToDelete}
        handleConfirmBulkDelete={handleConfirmBulkDelete}
        isRenameModalOpen={isRenameModalOpen}
        renamingDoc={renamingDoc}
        renameTitleInput={renameTitleInput}
        isSavingRename={isSavingRename}
        setRenameTitleInput={setRenameTitleInput}
        setIsRenameModalOpen={setIsRenameModalOpen}
        handleSaveRename={handleSaveRename}
      />
    </aside>
  );
}