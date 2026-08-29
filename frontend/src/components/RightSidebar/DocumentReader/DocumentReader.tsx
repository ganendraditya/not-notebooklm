import React from "react";
import {
  ArrowLeft,
  X,
  MessageSquare,
  Quote,
  Check,
  Link as LinkIcon,
  Download,
  ExternalLink,
  ChevronUp,
  ChevronDown,
  Loader2,
  FileText,
} from "lucide-react";
import { useTranslation } from "@/lib/i18n";

export interface DocumentReaderProps {
  viewingDoc: any;
  paperDetails: any;
  isLoadingDetails: boolean;
  activeTab: "preview" | "pdf";
  setActiveTab: (tab: "preview" | "pdf") => void;
  onClose: () => void;
  setViewingDoc: (doc: any | null) => void;
  onClearViewingDoc?: () => void;
  onAskAboutDocument?: (doc: any, title?: string) => void;
  backendUrl: string;
  activeChatId: string | null;
  totalMatches: number;
  activeMatchIndex: number;
  navigateMatch: (direction: "next" | "prev") => void;
  getHighlightedContent: () => React.ReactNode;
  cleanAbstract: string;
  authorsStr: string;
  pubDateStr: string;
  journalName: string;
  citationsCount: number;
  landingUrl: string;
  title: string;
  copiedLink: boolean;
  copyToClipboard: (text: string, type: "doi" | "link" | "citation") => void;
  setIsCiteModalOpen: (isOpen: boolean) => void;
}

export const DocumentReader: React.FC<DocumentReaderProps> = ({
  viewingDoc,
  paperDetails,
  isLoadingDetails,
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
  cleanAbstract,
  authorsStr,
  pubDateStr,
  journalName,
  citationsCount,
  landingUrl,
  title,
  copiedLink,
  copyToClipboard,
  setIsCiteModalOpen,
}) => {
  const { t } = useTranslation();

  return (
    <aside className="w-full lg:w-[460px] h-full bg-app-sidebar border-l border-app-border flex flex-col shrink-0 select-none z-10 transition-all relative text-app-text">
      {/* 1. Header Bar */}
      <div className="px-4 py-3 flex items-center justify-between border-b border-app-divider">
        <button
          onClick={() => {
            setViewingDoc(null);
            if (onClearViewingDoc) onClearViewingDoc();
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
                {viewingDoc.filename}
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              {totalMatches > 1 && (
                <div className="flex items-center gap-1 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2 py-0.5 mr-1">
                  <span className="text-[10px] font-mono font-semibold text-amber-500">
                    {activeMatchIndex + 1}/{totalMatches}
                  </span>
                  <div className="flex items-center">
                    <button
                      type="button"
                      onClick={() => navigateMatch("prev")}
                      className="p-1 text-amber-500 hover:bg-amber-500/20 rounded cursor-pointer transition-colors"
                      title="Previous match"
                    >
                      <ChevronUp size={12} />
                    </button>
                    <button
                      type="button"
                      onClick={() => navigateMatch("next")}
                      className="p-1 text-amber-500 hover:bg-amber-500/20 rounded cursor-pointer transition-colors"
                      title="Next match"
                    >
                      <ChevronDown size={12} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Academic Paper Metadata Header (Scrollable) */}
          <div className="flex-1 overflow-y-auto w-full relative group">
            {isLoadingDetails ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-app-bg/50 backdrop-blur-sm z-20">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-3" />
                <p className="text-xs text-app-text font-medium">{t('right.fetchingDetails')}</p>
                <p className="text-[11px] text-app-text-dim mt-1">{t('right.fetchingDetailsDesc')}</p>
              </div>
            ) : null}

            <div className="max-w-2xl mx-auto bg-app-surface min-h-full">
              {/* Top Meta Section */}
              <div className="px-5 py-6 border-b border-app-divider space-y-4">
                <h1 className="text-xl font-bold text-app-text leading-tight tracking-tight break-words">
                  {title}
                </h1>

                <div className="space-y-3.5">
                  <div className="flex items-start gap-2 text-[13px] leading-relaxed">
                    <span className="font-semibold text-app-text shrink-0">{t('right.authors')}</span>
                    <span className="text-blue-400 break-words line-clamp-3 hover:line-clamp-none transition-all cursor-text">{authorsStr}</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs">
                    <div className="flex items-center gap-1.5 bg-app-sidebar border border-app-border px-2 py-1 rounded-md text-app-text">
                      <span className="text-app-text-muted font-medium">{t('right.date')}</span>
                      <span>{pubDateStr}</span>
                    </div>
                    <div className="flex items-center gap-1.5 bg-app-sidebar border border-app-border px-2 py-1 rounded-md text-app-text max-w-[200px]">
                      <span className="text-app-text-muted font-medium">{t('right.journal')}</span>
                      <span className="truncate" title={journalName}>{journalName}</span>
                    </div>
                    {citationsCount > 0 && (
                      <div className="flex items-center gap-1.5 bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-1 rounded-md font-medium">
                        <Quote size={12} className="text-blue-500" />
                        <span>{citationsCount} {t('right.citations')}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="space-y-1.5 pt-1">
                  <h3 className="text-sm font-bold text-app-text">{t('right.abstract')}</h3>
                  <div className="text-[13px] leading-relaxed text-app-text-muted break-words">
                    {cleanAbstract ? (
                      <p>{cleanAbstract}</p>
                    ) : (
                      <p className="italic text-app-text-dim">{t('right.noAbstractProvided')}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Document Text Body Section */}
              {paperDetails?.content ? (
                <div className="px-5 py-6">
                  <h3 className="text-sm font-bold text-app-text mb-4 uppercase tracking-wider text-app-text-muted">{t('right.fullTextBody')}</h3>
                  <div className="text-[14px] leading-[1.75] text-app-text break-words">
                    {getHighlightedContent()}
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
        </div>
      ) : activeTab === "pdf" ? (
        <div className="flex-1 w-full h-full bg-app-surface overflow-hidden relative">
          {activeChatId && viewingDoc && paperDetails?.has_full_pdf !== false ? (
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
            title={t('right.askAI')}
          >
            <MessageSquare size={13} />
            <span>{t('right.ask')}</span>
          </button>

          <button
            disabled={isLoadingDetails}
            onClick={() => setIsCiteModalOpen(true)}
            className="h-8 px-2.5 rounded-full bg-app-card hover:bg-app-card-hover disabled:opacity-50 border border-app-border text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
            title={t('right.citePaper')}
          >
            <Quote size={13} />
            <span>{t('action.cite') || 'Cite'}</span>
          </button>

          <button
            disabled={isLoadingDetails || !landingUrl}
            onClick={() => copyToClipboard(landingUrl, "link")}
            className="w-8 h-8 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border disabled:opacity-50 text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
            title={copiedLink ? t('right.copiedLink') : t('right.copyLink')}
          >
            {copiedLink ? <Check size={14} className="text-emerald-500" /> : <LinkIcon size={14} />}
          </button>

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
                href={`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/download`}
                download={viewingDoc.filename}
                className="w-8 h-8 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer shadow-sm"
                title="Download original manuscript PDF"
              >
                <Download size={14} />
              </a>
            );
          })()}
        </div>

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
              <span>{landingUrl ? "PDF ???" : "Find ???"}</span>
            </a>
          );
        })()}
      </div>
    </aside>
  );
};


