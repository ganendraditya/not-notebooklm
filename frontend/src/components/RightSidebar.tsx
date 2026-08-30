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
        getHighlightedContent={() => getHighlightedContent((paperDetails?.content || ""), (groundingHighlight?.sentence || ""), highlightRefsMap, activeMatchIndex, groundingHighlight?.aiQuotes).nodes}
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

  // =========================================================================
  // VIEW MODE: CONSENSUS.AI STYLE ACADEMIC PAPER READER VIEW (Overview & Full Paper)
  // =========================================================================
  if (viewingDoc) {
    const filenameFallback = ((viewingDoc as any)?.filename || "paper").replace(/\.[^/.]+$/, "").replace(/_/g, " ");
    
    // Generic publisher headers that should never be displayed as paper title
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
    const landingUrl = paperDetails?.url || (doiStr ? `https://doi.org/${doiStr}` : "");

    const citations = generateCitations(
      title,
      paperDetails?.authors || [],
      paperDetails?.year || "2024",
      journalName,
      doiStr,
      landingUrl
    );

    return (
      <aside className="w-full lg:w-[460px] h-full bg-app-sidebar border-l border-app-border flex flex-col shrink-0 select-none z-10 transition-all relative text-app-text">
        {/* 1. Header Bar: â† Paper + Circular Close Button */}
        <div className="px-4 py-3 flex items-center justify-between border-b border-app-divider">
          <button
            onClick={() => {
              setViewingDoc(null);
              onClearViewingDoc?.();
            }}
            className="flex items-center gap-2 text-xs font-semibold text-app-text hover:opacity-80 transition-colors cursor-pointer group"
          >
            <ArrowLeft size={16} className="text-app-text-muted group-hover:text-app-text transition-transform group-hover:-translate-x-0.5" />
            <span className="text-sm tracking-tight font-medium">Paper</span>
          </button>

          <button 
            onClick={onClose}
            className="w-7 h-7 rounded-full bg-app-item-hover hover:bg-app-item-active text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer hidden lg:flex"
            title={t('right.close')}
          >
            <X size={14} />
          </button>
        </div>

        {/* 2. Clean 2 Navigation Tabs: Full Text & Original Document */}
        <div className="flex items-center px-4 border-b border-app-divider text-xs font-medium text-app-text-muted gap-5 shrink-0">
          <button
            onClick={() => setActiveTab("preview")}
            className={`py-2.5 transition-colors cursor-pointer border-b-2 font-medium flex items-center gap-1.5 ${
              activeTab === "preview" ? "text-app-text border-blue-500 font-semibold" : "text-app-text-muted hover:text-app-text border-transparent"
            }`}
          >
            <span>{t('right.fullText')}</span>
          </button>
          <button
            onClick={() => setActiveTab("pdf")}
            className={`py-2.5 transition-colors cursor-pointer border-b-2 font-medium flex items-center gap-1.5 ${
              activeTab === "pdf" ? "text-app-text border-blue-500 font-semibold" : "text-app-text-muted hover:text-app-text border-transparent"
            }`}
          >
            <span>{t('right.originalDoc')}</span>
          </button>
        </div>

        {/* 3. Main Body */}
        {activeTab === "preview" ? (
          /* TAB 2: FULL PAPER / IN-APP NATIVE SCROLLABLE DOCUMENT READER */
          <div className="flex-1 flex flex-col min-h-0 bg-app-bg relative overflow-hidden">
            {/* Top Preview Controls Bar */}
            <div className="px-3.5 py-2 bg-app-sidebar border-b border-app-divider flex items-center justify-between text-xs text-app-text-muted shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-2 h-2 rounded-full shrink-0 ${paperDetails?.has_full_pdf ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
                <span className="truncate max-w-[170px] font-mono text-[11px] text-app-text-muted">
                  {((viewingDoc as any)?.filename || "paper")}
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                {/* Evidence Passage Navigator (Chevron Up / Down for multiple disjoint matches) */}
                {totalMatches > 1 && (
                  <div className="flex items-center gap-1 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2 py-0.5 mr-1">
                    <span className="text-[10px] font-mono font-semibold text-amber-500">
                      {activeMatchIndex + 1}/{totalMatches}
                    </span>
                    <div className="flex items-center">
                      <button
                        type="button"
                        onClick={() => {
                          const prev = activeMatchIndex > 0 ? activeMatchIndex - 1 : totalMatches - 1;
                          setActiveMatchIndex(prev);
                        }}
                        className="p-0.5 hover:bg-amber-500/20 text-amber-500 hover:text-amber-600 rounded transition-colors"
                        title={t('right.prevEvidence')}
                      >
                        <ChevronUp size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const next = activeMatchIndex < totalMatches - 1 ? activeMatchIndex + 1 : 0;
                          setActiveMatchIndex(next);
                        }}
                        className="p-0.5 hover:bg-amber-500/20 text-amber-500 hover:text-amber-600 rounded transition-colors"
                        title={t('right.nextEvidence')}
                      >
                        <ChevronDown size={13} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* In-App Paper Document Reader Canvas (Fully Scrollable) */}
            <div className="flex-1 p-4 overflow-y-auto custom-scrollbar space-y-4 select-text">
              {isLoadingDetails ? (
                <div className="py-24 flex flex-col items-center justify-center text-center space-y-3">
                  <Loader2 size={24} className="animate-spin text-blue-500" />
                  <p className="text-xs text-app-text-dim">{t('right.loading')}</p>
                </div>
              ) : (paperDetails?.has_full_pdf === false || paperDetails?.is_abstract_only || (paperDetails?.content && (paperDetails.content.length < 3500 || paperDetails.content.includes("NOTBOOKLM SCHOLARLY ARCHIVE") || paperDetails.content.includes("OFFICIAL PUBLICATION ARCHIVE RECORD")))) ? (
                <div className="p-4 sm:p-5 rounded-xl bg-app-card border border-app-border shadow-lg space-y-4">
                  {/* Status Banner for Abstract Only */}
                  <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-2 text-xs text-amber-900 dark:text-amber-200">
                    <div className="flex items-center gap-2 font-semibold text-amber-800 dark:text-amber-100">
                      <Info size={16} className="text-amber-500 shrink-0" />
                      <span>
                        {paperDetails?.is_oa
                          ? t('right.restrictedOA')
                          : t('right.restrictedPaywall')}
                      </span>
                    </div>
                    <p className="text-[11.5px] text-amber-700 dark:text-amber-300/80 leading-relaxed">
                      {paperDetails?.is_oa
                        ? t('right.restrictedOADesc')
                        : t('right.restrictedPaywallDesc')}
                    </p>
                    {landingUrl && (
                      <div className="pt-1">
                        <a
                          href={landingUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-500/20 hover:bg-amber-500/30 text-amber-800 dark:text-amber-100 font-medium text-xs border border-amber-500/30 transition-colors"
                        >
                          <ExternalLink size={13} />
                          <span>{t('right.openOfficial')}</span>
                        </a>
                      </div>
                    )}
                  </div>

                  {/* Paper Title & Authors */}
                  <div className="pb-3 border-b border-app-divider space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold font-mono uppercase bg-amber-500/15 border border-amber-500/30 text-amber-600 dark:text-amber-400">
                        {t('right.metadataAndAbstract')}
                      </span>
                      {paperDetails?.year && (
                        <span className="text-[11px] text-app-text-dim">
                          {paperDetails.year}
                        </span>
                      )}
                    </div>

                    <h2 className="text-sm sm:text-[15px] font-bold text-app-text leading-snug">
                      {title}
                    </h2>

                    {authorsStr && (
                      <p className="text-xs text-app-text-muted">
                        {t('right.by')}{authorsStr}
                      </p>
                    )}
                  </div>

                  {/* Official Abstract Content */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold text-app-text uppercase tracking-wider">
                      {t('right.officialAbstract')}
                    </h3>
                    <div className="text-[12.5px] sm:text-[13px] text-app-text leading-relaxed font-sans whitespace-pre-wrap select-text break-words bg-app-input-surface p-3.5 rounded-lg border border-app-border">
                      {(() => {
                        const targetAbstract = cleanAbstract || paperDetails?.abstract || "No additional abstract text provided.";
                        const res = getHighlightedContent(
                          targetAbstract,
                          groundingHighlight?.sentence,
                          highlightRefsMap,
                          activeMatchIndex,
                          groundingHighlight?.aiQuotes
                        );
                        if (res.matchCount !== totalMatches) {
                          setTimeout(() => setTotalMatches(res.matchCount), 0);
                        }
                        return res.nodes;
                      })()}
                    </div>
                  </div>
                </div>
              ) : paperDetails?.content ? (
                <div className="p-4 sm:p-5 rounded-xl bg-app-card border border-app-border shadow-lg space-y-4">
                  {/* Status Banner for Full Manuscript */}
                  <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-300">
                    <Check size={14} className="text-emerald-500 shrink-0" />
                    <span className="font-medium">{t('right.fullManuscriptVerified')}</span>
                  </div>

                  {/* Paper Sheet Header */}
                  <div className="pb-3 border-b border-app-divider space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold font-mono uppercase bg-blue-500/15 border border-blue-500/30 text-blue-500">
                        {paperDetails.type?.toUpperCase() || "PDF"}
                      </span>
                      {paperDetails.year && (
                        <span className="text-[11px] text-app-text-dim">
                          {paperDetails.year}
                        </span>
                      )}
                    </div>

                    <h2 className="text-sm sm:text-[15px] font-bold text-app-text leading-snug">
                      {title}
                    </h2>

                    {authorsStr && (
                      <p className="text-xs text-app-text-muted">
                        {t('right.by')}{authorsStr}
                      </p>
                    )}
                  </div>

                  {/* Clean Formatted Document Body (Scrolls through the entire file) */}
                  <div className="text-[12.5px] sm:text-[13px] text-app-text leading-relaxed font-sans whitespace-pre-wrap select-text break-words">
                    {(() => {
                      // Strip repeated journal header/footer lines injected by PyMuPDF on every page
                      let cleanedContent = paperDetails.content
                        .replace(/^#\s+[^\n]+\n+/, "")
                        .replace(/##\s+Abstract & Overview\n+/, "");
                      // Remove repeated journal masthead blocks (ISSN, page numbers, author footers, "available online at" lines)
                      cleanedContent = cleanedContent.replace(/\n*(?:Author\s*\d*\s*\|[^\n]*\n?)+/gi, "\n");
                      cleanedContent = cleanedContent.replace(/\n*\*\*_?[A-Za-z]+:.*?Journal.*?_?\*\*[^\n]*\n(?:[^\n]*ISSN[^\n]*\n)?(?:[^\n]*Halaman[^\n]*\n)?(?:[^\n]*available online at[^\n]*\n)?/gi, "\n");
                      cleanedContent = cleanedContent.replace(/\n*_?available online at_?\s*https?:\/\/[^\n]+\n*/gi, "\n");
                      cleanedContent = cleanedContent.replace(/\n{3,}/g, "\n\n");

                      const res = getHighlightedContent(
                        cleanedContent,
                        groundingHighlight?.sentence,
                        highlightRefsMap,
                        activeMatchIndex,
                        groundingHighlight?.aiQuotes
                      );
                      if (res.matchCount !== totalMatches) {
                        setTimeout(() => setTotalMatches(res.matchCount), 0);
                      }
                      return res.nodes;
                    })()}
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-app-card border border-app-border text-center py-10 space-y-2">
                  <FileText size={28} className="text-app-text-dim mx-auto stroke-[1.5]" />
                  <p className="text-xs text-app-text font-medium">{t('right.docIndexed')}</p>
                  <p className="text-[11px] text-app-text-dim max-w-[240px] mx-auto">
                    {t('right.docIndexedDesc')}
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : activeTab === "pdf" ? (
          <div className="flex-1 w-full h-full bg-app-surface overflow-hidden relative">
            {activeChatId && viewingDoc && paperDetails?.has_full_pdf !== false ? (
              <object
                data={`${backendUrl}/chats/${activeChatId}/documents/${((viewingDoc as any)?.id || "undefined")}/stream#toolbar=1&navpanes=0`}
                type="application/pdf"
                className="w-full h-full"
              >
                <div className="flex flex-col items-center justify-center h-full text-center p-6 space-y-3">
                  <FileText size={36} className="text-blue-500 mx-auto stroke-[1.5]" />
                  <p className="text-xs text-app-text font-medium">{t('right.openInNewTab')}</p>
                  <a
                    href={`${backendUrl}/chats/${activeChatId}/documents/${((viewingDoc as any)?.id || "undefined")}/stream`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium inline-flex items-center gap-1.5 shadow-sm transition-colors"
                  >
                    <ExternalLink size={13} />
                    <span>{t('right.openInNewTab')}</span>
                  </a>
                </div>
              </object>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-6 space-y-3">
                <FileText size={36} className="text-amber-500 mx-auto stroke-[1.5]" />
                <div className="space-y-1 max-w-sm">
                  <p className="text-xs text-app-text font-medium">
                    {t('right.originalDocNotAvail')}
                  </p>
                </div>
                {landingUrl && (
                  <a
                    href={landingUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium inline-flex items-center gap-1.5 shadow-sm transition-colors mt-2"
                  >
                    <ExternalLink size={13} />
                    <span>{t('right.openOfficialPublisher')}</span>
                  </a>
                )}
              </div>
            )}
          </div>
        ) : null}

        {/* 4. Consensus-style Bottom Floating Action Toolbar */}
        <div className={`p-3 border-t border-app-divider bg-app-sidebar flex items-center justify-between gap-1.5 shrink-0 select-none transition-opacity ${
          isLoadingDetails ? "opacity-40 pointer-events-none" : "opacity-100"
        }`}>
          <div className="flex items-center gap-1.5">
            {/* Ask Button (Pill) */}
            <button
              disabled={isLoadingDetails}
              onClick={() => {
                if (viewingDoc && onAskAboutDocument) {
                  onAskAboutDocument(viewingDoc, paperDetails?.title || ((viewingDoc as any)?.filename || "paper"));
                }
                const chatInput = document.getElementById("chat-input-textarea");
                if (chatInput) {
                  chatInput.focus();
                }
              }}
              className="h-8 px-3 rounded-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-xs flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm disabled:cursor-not-allowed"
              title={t('right.askAI')}
            >
              <MessageSquare size={13} />
              <span>{t('right.ask')}</span>
            </button>

            {/* Multi-Format Cite Button (Opens Interactive Citation Modal) */}
            <button
              disabled={isLoadingDetails}
              onClick={() => setIsCiteModalOpen(true)}
              className="h-8 px-2.5 rounded-full bg-app-card hover:bg-app-card-hover disabled:opacity-50 border border-app-border text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
              title={t('right.citePaper')}
            >
              <Quote size={13} />
              <span>{t('action.cite') || 'Cite'}</span>
            </button>

            {/* Copy Link Icon Button */}
            <button
              disabled={isLoadingDetails || !landingUrl}
              onClick={() => copyToClipboard(landingUrl, "link")}
              className="w-8 h-8 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border disabled:opacity-50 text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
              title={copiedLink ? t('right.copiedLink') : t('right.copyLink')}
            >
              {copiedLink ? <Check size={14} className="text-emerald-500" /> : <LinkIcon size={14} />}
            </button>

            {/* Download Icon Button */}
            {activeChatId && (() => {
              const isDownloadable = Boolean(!isLoadingDetails && paperDetails?.has_full_pdf);
              if (!isDownloadable) {
                return (
                  <button
                    disabled
                    className="w-8 h-8 rounded-full bg-app-card border border-app-border text-app-text-dim opacity-30 flex items-center justify-center cursor-not-allowed"
                    title={t('right.downloadNotAvail')}
                  >
                    <Download size={14} />
                  </button>
                );
              }
              return (
                <a
                  href={`${backendUrl}/chats/${activeChatId}/documents/${((viewingDoc as any)?.id || "undefined")}/download`}
                  download={((viewingDoc as any)?.filename || "paper")}
                  className="w-8 h-8 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer shadow-sm"
                  title="Download original manuscript PDF"
                >
                  <Download size={14} />
                </a>
              );
            })()}
          </div>

          {/* Right Side: PDF / External Landing Page Pill - ALWAYS shown */}
          {(() => {
            const pdfLink = landingUrl || `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
            return (
              <a
                href={isLoadingDetails ? undefined : pdfLink}
                target="_blank"
                rel="noopener noreferrer"
                className={`h-8 px-2.5 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors shrink-0 shadow-sm ${
                  isLoadingDetails ? "pointer-events-none opacity-50 cursor-not-allowed" : "cursor-pointer"
                }`}
                title={landingUrl ? "Open full-text paper link in new tab" : "Search for this paper on Google Scholar"}
              >
                <ExternalLink size={12} />
                <span>{landingUrl ? "PDF â†—" : "Find â†—"}</span>
              </a>
            );
          })()}
        </div>

        {/* 5. Interactive Multi-Format Citation Modal */}

      </aside>
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
























