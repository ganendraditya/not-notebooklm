"use client";

import { DocumentReader } from "./RightSidebar/DocumentReader";
import { DocumentListPanel } from "./RightSidebar/DocumentListPanel";
import { usePaperDetails } from "@/hooks/usePaperDetails";
import { getHighlightedContent, formatReadableDate } from "./RightSidebar/DocumentReaderUtils";
import { useDocumentManager } from "@/hooks/useDocumentManager";

import { useState, useRef, useEffect, useMemo } from "react";
import { Plus, Check, AlertCircle, PanelRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Document, CitationGroundingHighlight, PendingSourceItem } from "@/stores/documentStore";
import { useTranslation } from "@/lib/i18n";
import { SourcesToolbar } from "./RightSidebar/SourcesToolbar";
import { RightSidebarModals } from "./RightSidebar/RightSidebarModals";
import { DownloadManager } from "@/components/DownloadManager";
import { Tooltip } from "@/components/ui/tooltip";

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
  onViewingDocChange?: (doc: Document | null) => void;
  onCancelPendingSource?: (pendingId: string) => void;
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
  onViewingDocChange,
  onCancelPendingSource,
  groundingHighlight,
  onClearViewingDoc, 
  backendUrl, 
  onClose 
}: RightSidebarProps) {
  const { t } = useTranslation();
  const { viewingDoc, setViewingDoc, paperDetails, isLoadingDetails, activeTab, setActiveTab } = usePaperDetails({ 
    activeChatId, 
    backendUrl, 
    externalViewingDoc, 
    onViewingDocChange,
    groundingHighlight 
  });
  const {
    selectedDocs,
    sortBy, setSortBy,
    sortDirection, setSortDirection,
    isSortMenuOpen, setIsSortMenuOpen,
    activeMenuId, setActiveMenuId,
    isCleaningDuplicates,
    cleanFeedback,
    isAddSourcesModalOpen, setIsAddSourcesModalOpen,
    doiInput, setDoiInput,
    setInternalPendingSources,
    pendingSources,
    isDraggingOver, setIsDraggingOver,
    isRenameModalOpen, setIsRenameModalOpen,
    renamingDoc, setRenamingDoc,
    renameTitleInput, setRenameTitleInput,
    isSavingRename,
    setRenameError,
    docToDelete, setDocToDelete,
    showBulkDeleteConfirm, setShowBulkDeleteConfirm,
    isBulkDeleting,
    isBulkDownloading,
    downloadTask, setDownloadTask,
    selectedDocList, selectedCount,
    isAllSelected, isPartiallySelected,
    sortedDocuments,
    toggleDocSelection, handleToggleSelectAll,
    getFileBadgeInfo, handleOpenRename, handleSaveRename,
    handleCleanDuplicates, handleBulkDownload, handleConfirmBulkDelete,
    handleUploadBatch, handleImportDoi,
    cancelPendingSource
  } = useDocumentManager({
    documents,
    externalPendingSources,
    activeChatId,
    backendUrl,
    onDocumentAdded,
    onDocumentUpdated,
    onDocumentDeleted,
    onBulkDocumentsDeleted,
    onEnsureChatSession,
    onCancelPendingSource,
    viewingDoc,
    setViewingDoc,
    t
  });
  const sortMenuRef = useRef<HTMLDivElement>(null);


  // Citation Modal State
  const [isCiteModalOpen, setIsCiteModalOpen] = useState<boolean>(false);
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
      } else {
        setActiveMatchIndex(prev => (prev >= highlightResult.matchCount ? 0 : prev));
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
  }, [isSortMenuOpen, activeMenuId, setActiveMenuId, setIsSortMenuOpen]);





















  const copyToClipboard = (text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
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

    const isUserUpload = Boolean(
      paperDetails?.is_uploaded ||
      paperDetails?.journal_metric === "Uploaded Document" ||
      paperDetails?.access_status === "Uploaded Document"
    );

    const isAcademicPaper = !isUserUpload && Boolean(
      paperDetails?.doi || 
      viewingDoc?.doi ||
      (paperDetails?.journal && !["uploaded document", "scholarly publication"].includes(paperDetails.journal.trim().toLowerCase())) ||
      (paperDetails?.authors && paperDetails.authors.length > 0) ||
      (paperDetails?.citations && paperDetails.citations > 0)
    );

    const authorsStr = paperDetails?.authors && paperDetails.authors.length > 0
      ? paperDetails.authors.join(", ")
      : "";

    const rawUploadDate = viewingDoc?.created_at || paperDetails?.created_at;
    const pubDateStr = isAcademicPaper
      ? (formatReadableDate(paperDetails?.publication_date, paperDetails?.year) || "")
      : (rawUploadDate ? `Uploaded ${formatReadableDate(rawUploadDate)}` : "");

    const doiStr = paperDetails?.doi || "";
    const landingUrl = paperDetails?.url || (doiStr ? `https://doi.org/${doiStr}` : "");

    return (
      <>
        <DocumentReader
          viewingDoc={viewingDoc}
          paperDetails={paperDetails}
          isLoadingDetails={isLoadingDetails}
          isAcademicPaper={isAcademicPaper}
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
          authorsStr={authorsStr}
          pubDateStr={pubDateStr}
          landingUrl={landingUrl}
          title={title}
          copiedLink={copiedLink}
          copyToClipboard={copyToClipboard}
          setIsCiteModalOpen={setIsCiteModalOpen}
        />

        {/* Modals Composition - Mounted in Reader Mode as well */}
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
      </>
    );
  }

  // ==========================================
  // VIEW MODE: STANDARD SOURCES LIST PANEL
  // ==========================================
  return (
    <aside className="w-full lg:w-[460px] h-full bg-app-sidebar border-l border-app-border flex flex-col shrink-0 z-10 transition-all relative text-app-text">
      {/* 1. Header Bar: Top Fixed Header */}
      <div className="w-full h-[52px] pl-4 pr-3 flex items-center justify-between border-b border-app-border shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-app-text tracking-tight">{t('ui.sources') || "Sources"}</span>
        </div>
        <Tooltip content={t('ui.closeSidebar') || "Close sidebar"} side="left">
          <button 
            onClick={onClose}
            className="w-7 h-7 rounded-lg hover:bg-app-item-hover text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer"
            aria-label={t('ui.closeSidebar') || "Close sidebar"}
          >
            <PanelRight size={15} />
          </button>
        </Tooltip>
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
      <div className="pl-2 pr-[18px] pt-3 pb-2.5 space-y-2.5 shrink-0 bg-app-sidebar z-10 border-b border-app-divider shadow-sm">
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
        {cleanFeedback && (() => {
          const isError = cleanFeedback.toLowerCase().includes("fail") || cleanFeedback.toLowerCase().includes("error");
          return (
            <div className={`w-full px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 animate-in fade-in zoom-in-95 duration-150 ${
              isError
                ? "bg-rose-500/10 border border-rose-500/20 text-rose-300"
                : "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300"
            }`}>
              {isError ? (
                <AlertCircle size={13} className="text-rose-400 shrink-0" />
              ) : (
                <Check size={13} className="text-emerald-400 shrink-0" />
              )}
              <span className="text-[12px]">{cleanFeedback}</span>
            </div>
          );
        })()}

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
        cancelPendingSource={cancelPendingSource}
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

      <DownloadManager 
        task={downloadTask} 
        onClose={() => setDownloadTask(null)} 
      />
    </aside>
  );
}