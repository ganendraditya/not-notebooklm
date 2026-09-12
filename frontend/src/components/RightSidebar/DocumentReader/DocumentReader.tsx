import React from "react";
import {
  ArrowLeft,
  PanelRight,
  MessageSquare,
  Quote,
  Check,
  Link as LinkIcon,
  Download,
  ExternalLink,
  ChevronUp,
  ChevronDown,
  FileText,
} from "lucide-react";
import { useTranslation } from "@/lib/i18n";
import { Document as DocType } from "@/stores/documentStore";
import { PaperDetailData } from "@/hooks/usePaperDetails";
import { Tooltip } from "@/components/ui/tooltip";
import { getFileBadgeInfo } from "../DocumentReaderUtils";

export interface DocumentReaderProps {
  viewingDoc: DocType | null;
  paperDetails: PaperDetailData | null;
  isLoadingDetails: boolean;
  isAcademicPaper?: boolean;
  activeTab: "preview" | "pdf";
  setActiveTab: (tab: "preview" | "pdf") => void;
  onClose: () => void;
  setViewingDoc: (doc: DocType | null) => void;
  onClearViewingDoc?: () => void;
  onAskAboutDocument?: (doc: DocType, title?: string) => void;
  backendUrl: string;
  activeChatId: string | null;
  totalMatches: number;
  activeMatchIndex: number;
  navigateMatch: (direction: "next" | "prev") => void;
  getHighlightedContent: () => React.ReactNode;
  authorsStr: string;
  pubDateStr: string;
  landingUrl: string;
  title: string;
  copiedLink: boolean;
  copyToClipboard: (text: string, type?: "doi" | "link" | "citation") => void;
  setIsCiteModalOpen: (isOpen: boolean) => void;
}

export const DocumentReader: React.FC<DocumentReaderProps> = ({
  viewingDoc,
  paperDetails,
  isLoadingDetails,
  isAcademicPaper = false,
  activeTab,
  setActiveTab,
  onClose,
  setViewingDoc,
  onClearViewingDoc,
  onAskAboutDocument,
  backendUrl,
  activeChatId,
  totalMatches,
  activeMatchIndex,
  navigateMatch,
  getHighlightedContent,
  authorsStr,
  pubDateStr,
  landingUrl,
  title,
  copiedLink,
  copyToClipboard,
  setIsCiteModalOpen,
}) => {
  const { t } = useTranslation();
  const badge = getFileBadgeInfo(viewingDoc?.filename || "");

  return (
    <aside className="w-full lg:w-[460px] h-full bg-app-sidebar border-l border-app-border flex flex-col shrink-0 z-10 transition-all relative text-app-text">
      {/* 1. Header Bar: Pinned Breadcrumb Header */}
      <div className="w-full h-[52px] pl-4 pr-3 flex items-center justify-between border-b border-app-border shrink-0">
        <button
          onClick={() => {
            setViewingDoc(null);
            if (onClearViewingDoc) onClearViewingDoc();
          }}
          className="flex items-center gap-1.5 text-xs font-semibold text-app-text hover:opacity-80 transition-colors cursor-pointer group"
          aria-label={t('ui.sources') || "Sources"}
        >
          <ArrowLeft size={16} className="text-app-text-muted group-hover:text-app-text transition-transform group-hover:-translate-x-0.5" />
          <span className="text-sm tracking-tight font-semibold">{t('ui.sources') || "Sources"}</span>
        </button>

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

      {/* 2. Navigation Tabs */}
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
        <div className="flex-1 flex flex-col min-h-0 bg-app-bg relative overflow-hidden">
          {/* Top Preview Controls Bar */}
          <div className="px-3.5 py-2 bg-app-sidebar border-b border-app-divider flex items-center justify-between text-xs text-app-text-muted shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <span className={`w-2 h-2 rounded-full shrink-0 ${paperDetails?.has_full_pdf ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
              <span className="truncate max-w-[170px] font-mono text-[11px] text-app-text-muted">
                {viewingDoc?.filename || ""}
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              {totalMatches > 1 && (
                <div className="flex items-center gap-1 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2 py-0.5 mr-1">
                  <span className="text-[10px] font-mono font-semibold text-amber-500">
                    {activeMatchIndex + 1}/{totalMatches}
                  </span>
                  <div className="flex items-center">
                    <Tooltip content="Previous match" side="top">
                      <button
                        type="button"
                        onClick={() => navigateMatch("prev")}
                        className="p-1 text-amber-500 hover:bg-amber-500/20 rounded cursor-pointer transition-colors"
                        aria-label="Previous match"
                      >
                        <ChevronUp size={12} />
                      </button>
                    </Tooltip>
                    <Tooltip content="Next match" side="top">
                      <button
                        type="button"
                        onClick={() => navigateMatch("next")}
                        className="p-1 text-amber-500 hover:bg-amber-500/20 rounded cursor-pointer transition-colors"
                        aria-label="Next match"
                      >
                        <ChevronDown size={12} />
                      </button>
                    </Tooltip>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Academic Paper Metadata Header (Scrollable) */}
          <div className="flex-1 overflow-y-auto w-full relative group">
            {isLoadingDetails ? (
              <div className="max-w-2xl mx-auto min-h-full p-4 space-y-4 animate-pulse">
                {/* Skeleton Paper Card */}
                <div className="p-4 sm:p-5 rounded-xl bg-app-card border border-app-border space-y-4">
                  {/* Paper Title & Badges */}
                  <div className="pb-3 border-b border-app-divider space-y-3">
                    <div className="flex items-center gap-2">
                      <div className="h-4 w-10 rounded bg-app-divider/60" />
                      <div className="h-3.5 w-16 rounded bg-app-divider/40" />
                    </div>
                    <div className="space-y-2">
                      <div className="h-5 w-11/12 rounded bg-app-divider/70" />
                      <div className="h-5 w-3/4 rounded bg-app-divider/60" />
                    </div>
                    <div className="h-3.5 w-1/2 rounded bg-app-divider/40 pt-1" />
                  </div>

                  {/* Clean Formatted Document Body Skeleton */}
                  <div className="space-y-2.5 pt-2">
                    <div className="h-3.5 w-full rounded bg-app-divider/40" />
                    <div className="h-3.5 w-full rounded bg-app-divider/40" />
                    <div className="h-3.5 w-4/5 rounded bg-app-divider/40" />
                    <div className="h-3.5 w-full rounded bg-app-divider/40 pt-2" />
                    <div className="h-3.5 w-full rounded bg-app-divider/40" />
                    <div className="h-3.5 w-3/4 rounded bg-app-divider/40" />
                    <div className="h-3.5 w-5/6 rounded bg-app-divider/40" />
                  </div>
                </div>
              </div>
            ) : (
            <div className="max-w-2xl mx-auto min-h-full p-4">
              {/* Top Meta Section */}
              <div className="bg-app-surface border border-app-border rounded-xl mb-4 overflow-hidden shadow-sm">
                <div className="px-5 py-6 space-y-4">
                  <div className="flex flex-wrap items-center gap-3 text-xs mb-3">
                    <div className="flex items-center gap-2 text-app-text-muted">
                      <span className={`text-[9.5px] font-bold uppercase px-1.5 py-0.5 rounded border ${badge.bg}`}>
                        {badge.label}
                      </span>
                      {pubDateStr && (
                        <span>{pubDateStr}</span>
                      )}
                    </div>
                  </div>
                  
                  <h1 className="text-xl font-bold text-app-text leading-tight tracking-tight break-words">
                    {title}
                  </h1>
                  
                  {authorsStr && (
                    <p className="text-sm text-app-text-muted mt-2">
                      By {authorsStr}
                    </p>
                  )}
                  
                  {/* Document Text Body Section */}
                  {paperDetails?.content || viewingDoc?.content ? (
                    <div className="pt-6 mt-6 border-t border-app-border text-[14px] leading-[1.75] text-app-text break-words whitespace-pre-wrap document-content-view">
                      {(() => {
                        const contentToRender = paperDetails?.content || viewingDoc?.content;
                        if (!contentToRender) return null;
                        
                        if (getHighlightedContent) {
                          const highlighted = getHighlightedContent();
                          if (highlighted && (!Array.isArray(highlighted) || highlighted.length > 0)) {
                            return highlighted;
                          }
                        }
                        return contentToRender;
                      })()}
                    </div>
                  ) : null}
                </div>
              </div>

              {!paperDetails?.content && !viewingDoc?.content && (
                <div className="px-5 py-6">
                  <div className="p-4 rounded-xl bg-app-card border border-app-border text-center py-10 space-y-2">
                    <Check size={28} className="text-emerald-500 mx-auto stroke-[2]" />
                    <p className="text-xs text-app-text font-medium">{t('right.docIndexed')}</p>
                    <p className="text-[11px] text-app-text-dim max-w-[240px] mx-auto">
                      {t('right.docIndexedDesc')}
                    </p>
                  </div>
                </div>
              )}
            </div>
            )}
          </div>
        </div>
      ) : activeTab === "pdf" ? (
        <div className="flex-1 w-full h-full bg-app-surface overflow-hidden relative">
          {isLoadingDetails ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-6 space-y-4">
               <div className="w-8 h-8 rounded-full border-2 border-app-border border-t-blue-500 animate-spin" />
               <p className="text-xs text-app-text-muted font-medium animate-pulse">{t('right.loading')}</p>
            </div>
          ) : activeChatId && viewingDoc && paperDetails?.has_full_pdf !== false && !viewingDoc.filename?.toLowerCase().endsWith('.txt') ? (
            <object
              data={`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/stream#toolbar=1&navpanes=0`}
              type="application/pdf"
              className="w-full h-full"
            >
              <div className="flex flex-col items-center justify-center h-full text-center p-6 space-y-3">
                <FileText size={36} className="text-blue-500 mx-auto stroke-[1.5]" />
                <p className="text-xs text-app-text font-medium">{t('right.openInNewTab')}</p>
                <a
                  href={`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/stream`}
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

      {/* 4. Action Toolbar */}
      <div className={`p-3 border-t border-app-divider bg-app-sidebar flex items-center justify-between gap-1.5 shrink-0 select-none transition-opacity ${
        isLoadingDetails ? "opacity-40 pointer-events-none" : "opacity-100"
      }`}>
        <div className="flex items-center gap-1.5">
          <Tooltip content={t('right.askAI')} side="top">
            <button
              disabled={isLoadingDetails}
              onClick={() => {
                if (viewingDoc && onAskAboutDocument) {
                  onAskAboutDocument(viewingDoc, paperDetails?.title || viewingDoc.filename);
                }
                const chatInput = document.getElementById("chat-input-textarea");
                if (chatInput) {
                  chatInput.focus();
                }
              }}
              className="h-8 px-3 rounded-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-xs flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm disabled:cursor-not-allowed"
              aria-label={t('right.askAI')}
            >
              <MessageSquare size={13} />
              <span>{t('right.ask')}</span>
            </button>
          </Tooltip>

          <Tooltip content={t('right.citePaper')} side="top">
            <button
              disabled={isLoadingDetails}
              onClick={() => setIsCiteModalOpen(true)}
              className="h-8 px-2.5 rounded-full bg-app-card hover:bg-app-card-hover disabled:opacity-50 border border-app-border text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
              aria-label={t('right.citePaper')}
            >
              <Quote size={13} />
              <span>{t('action.cite') || 'Cite'}</span>
            </button>
          </Tooltip>

          <Tooltip content={copiedLink ? t('right.copiedLink') : t('right.copyLink')} side="top">
            <button
              disabled={isLoadingDetails || !landingUrl}
              onClick={() => copyToClipboard(landingUrl, "link")}
              className="w-8 h-8 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border disabled:opacity-50 text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
              aria-label={copiedLink ? t('right.copiedLink') : t('right.copyLink')}
            >
              {copiedLink ? <Check size={14} className="text-emerald-500" /> : <LinkIcon size={14} />}
            </button>
          </Tooltip>

          {activeChatId && viewingDoc && (() => {
            const isDownloadable = Boolean(!isLoadingDetails);
            const downloadTooltip = isDownloadable
              ? (paperDetails?.has_full_pdf !== false 
                  ? (t('right.downloadPdf') || "Download manuscript PDF") 
                  : (t('right.downloadFile') || "Download document text"))
              : (t('right.downloadNotAvail') || "Document is not available for download");

            const handleDownload = () => {
              if (!isDownloadable) return;
              const link = document.createElement("a");
              link.href = `${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/download`;
              link.download = viewingDoc.filename;
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
            };

            return (
              <Tooltip content={downloadTooltip} side="top">
                <button
                  type="button"
                  onClick={handleDownload}
                  aria-disabled={!isDownloadable}
                  className={`w-8 h-8 rounded-full bg-app-card border border-app-border flex items-center justify-center transition-colors shadow-sm ${
                    isDownloadable
                      ? "hover:bg-app-card-hover text-app-text-muted hover:text-app-text cursor-pointer"
                      : "text-app-text-dim opacity-30 cursor-not-allowed"
                  }`}
                  aria-label={downloadTooltip}
                >
                  <Download size={14} />
                </button>
              </Tooltip>
            );
          })()}
        </div>

        {(landingUrl || isAcademicPaper) && (() => {
          const pdfLink = landingUrl || `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
          return (
            <Tooltip content={landingUrl ? "Open full-text paper link in new tab" : "Search for this paper on Google Scholar"} side="top">
              <a
                href={isLoadingDetails ? undefined : pdfLink}
                target="_blank"
                rel="noopener noreferrer"
                className={`h-8 px-2.5 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors shrink-0 shadow-sm ${
                  isLoadingDetails ? "pointer-events-none opacity-50 cursor-not-allowed" : "cursor-pointer"
                }`}
                aria-label={landingUrl ? "Open full-text paper link in new tab" : "Search for this paper on Google Scholar"}
              >
                <ExternalLink size={12} />
                <span>PDF ↗</span>
              </a>
            </Tooltip>
          );
        })()}
      </div>
    </aside>
  );
};


