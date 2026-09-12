import React from "react";
import { useTranslation } from "@/lib/i18n";
import { Document, PendingSourceItem } from "@/stores/documentStore";
import { Tooltip } from "@/components/ui/tooltip";
import { 
  FileText, 
  MoreHorizontal, 
  Pencil, 
  Download, 
  Trash2, 
  Check, 
  AlertCircle, 
  X 
} from "lucide-react";

export interface DocumentListPanelProps {
  documents: Document[];
  sortedDocuments: Document[];
  pendingSources: PendingSourceItem[];
  selectedDocs: Record<number, boolean>;
  activeMenuId: number | null;
  setActiveMenuId: (id: number | null) => void;
  setViewingDoc: (doc: Document) => void;
  toggleDocSelection: (docId: number) => void;
  getFileBadgeInfo: (filename: string) => { label: string; bg: string };
  setRenamingDoc: (doc: Document | null) => void;
  setRenameTitleInput: (title: string) => void;
  setRenameError: (err: string | null) => void;
  setIsRenameModalOpen: (isOpen: boolean) => void;
  setDocToDelete: (id: number | null) => void;
  setShowBulkDeleteConfirm: (isOpen: boolean) => void;
  setInternalPendingSources: React.Dispatch<React.SetStateAction<PendingSourceItem[]>>;
  cancelPendingSource?: (id: string) => void;
  activeChatId: string | null;
  backendUrl: string;
}

export const DocumentListPanel: React.FC<DocumentListPanelProps> = ({
  documents,
  sortedDocuments,
  pendingSources,
  selectedDocs,
  activeMenuId,
  setActiveMenuId,
  setViewingDoc,
  toggleDocSelection,
  getFileBadgeInfo,
  setRenamingDoc,
  setRenameTitleInput,
  setRenameError,
  setIsRenameModalOpen,
  setDocToDelete,
  setShowBulkDeleteConfirm,
  setInternalPendingSources,
  cancelPendingSource,
  activeChatId,
  backendUrl,
}) => {
  const { t } = useTranslation();

  return (
    <div className="px-2 pb-3 flex-1 flex flex-col overflow-y-auto custom-scrollbar min-h-0 relative">
      <div className="w-full flex-1 space-y-0.5 pt-0.5">
        {sortedDocuments.length === 0 && pendingSources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center text-app-text-muted px-3">
            <FileText size={30} className="text-app-text-dim mb-2 stroke-[1.5]" />
            <h4 className="text-xs font-semibold text-app-text">{t('ui.noSources')}</h4>
            <p className="text-[11px] text-app-text-dim mt-1 max-w-[220px] leading-relaxed">
              {t('ui.noSourcesDesc')}
            </p>
          </div>
        ) : (
          <>
            {/* Existing indexed documents */}
            {sortedDocuments.map((doc) => {
              const isChecked = selectedDocs[doc.id] !== undefined ? selectedDocs[doc.id] : true;
              const badge = getFileBadgeInfo(doc.filename);
              const docIndex = (documents.findIndex(d => d.id === doc.id) + 1) || doc.index || 1;

              return (
                <div
                  key={doc.id}
                  onClick={() => setViewingDoc(doc)}
                  className="flex items-center justify-between py-2 px-2.5 rounded-lg bg-transparent hover:bg-app-item-hover transition-colors cursor-pointer group"
                >
                  {/* Left: Clean Monospace Index + Compact Format Badge + File Name */}
                  <div className="flex items-center gap-2 min-w-0 flex-1 mr-1.5">
                    {/* Clean Minimalist Index */}
                    <Tooltip content={`Permanent Reference Index [${docIndex}]`} side="top">
                      <span 
                        className="w-6 text-left text-[11px] font-mono font-medium text-app-text-dim group-hover:text-app-text transition-colors shrink-0 select-none tabular-nums"
                      >
                        {docIndex}.
                      </span>
                    </Tooltip>

                    <div className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 ${badge.bg}`}>
                      <span className="text-[7.5px] font-bold tracking-tighter uppercase font-mono">{badge.label}</span>
                    </div>

                    {(() => {
                      let displayTitle = (doc.title || doc.filename.replace(/\.[^/.]+$/, "").replace(/_/g, " ")).replace(/<[^>]+>/g, "").trim();
                      if (displayTitle.length > 8 && displayTitle === displayTitle.toUpperCase()) {
                        displayTitle = displayTitle.toLowerCase().replace(/\b\w/g, (c: string) => c.toUpperCase());
                      }
                      return (
                        <span className="text-[11.5px] text-app-text truncate group-hover:text-blue-500 font-medium transition-colors" title={displayTitle}>
                          {displayTitle}
                        </span>
                      );
                    })()}
                  </div>

                  {/* 3 dots action menu */}
                  <div className="shrink-0 flex items-center relative mr-1 document-action-menu-container">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (activeMenuId === doc.id) {
                          setActiveMenuId(null);
                        } else {
                          setActiveMenuId(doc.id);
                        }
                      }}
                      className={`p-1 rounded-md transition-colors z-20 hover:bg-app-item-active group-hover:opacity-100 ${
                        activeMenuId === doc.id ? "opacity-100 text-app-text bg-app-item-active" : "opacity-0 text-app-text-muted"
                      }`}
                    >
                      <MoreHorizontal size={14} />
                    </button>
                    {/* Dropdown Menu */}
                    {activeMenuId === doc.id && (
                      <div 
                        className="absolute right-0 mt-1 w-36 bg-app-dropdown border border-app-border-strong rounded-xl shadow-xl z-[60] overflow-hidden py-1 animate-in fade-in zoom-in-95 duration-100"
                        ref={(el) => {
                          if (el) {
                              const rect = el.getBoundingClientRect();
                              const windowHeight = window.innerHeight;
                              if (rect.top > windowHeight / 2) {
                                el.style.top = 'auto';
                                el.style.bottom = '100%';
                                el.style.marginBottom = '4px';
                                el.style.marginTop = '0px';
                              } else {
                                el.style.top = '100%';
                                el.style.bottom = 'auto';
                                el.style.marginBottom = '0px';
                                el.style.marginTop = '4px';
                              }
                          }
                        }}
                      >
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveMenuId(null);
                            setRenamingDoc(doc);
                            setRenameTitleInput(doc.title || doc.filename.replace(/\.[^/.]+$/, "").replace(/_/g, " "));
                            setRenameError(null);
                            setIsRenameModalOpen(true);
                          }}
                          className="w-full text-left px-3 py-1.5 text-xs text-app-text hover:bg-app-item-hover transition-colors flex items-center gap-2"
                        >
                          <Pencil size={13} className="shrink-0" /> {t('action.rename')}
                        </button>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            setActiveMenuId(null);
                            if (!activeChatId) return;
                            try {
                              const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/${doc.id}/download`);
                              if (res.ok) {
                                const blob = await res.blob();
                                const url = window.URL.createObjectURL(blob);
                                const link = document.createElement("a");
                                link.href = url;
                                link.download = doc.filename.endsWith(".pdf") ? doc.filename : `${doc.filename}.pdf`;
                                document.body.appendChild(link);
                                link.click();
                                document.body.removeChild(link);
                                window.URL.revokeObjectURL(url);
                              } else {
                                console.error("Failed to download document: status", res.status);
                              }
                            } catch (err) {
                              console.error("Download error:", err);
                            }
                          }}
                          className="w-full text-left px-3 py-1.5 text-xs text-app-text hover:bg-app-item-hover transition-colors flex items-center gap-2"
                        >
                          <Download size={13} className="shrink-0" /> {t('action.download') || "Download"}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveMenuId(null);
                            setDocToDelete(doc.id);
                            setShowBulkDeleteConfirm(true);
                          }}
                          className="w-full text-left px-3 py-1.5 text-xs text-red-500 hover:bg-red-500/10 transition-colors flex items-center gap-2"
                        >
                          <Trash2 size={13} className="shrink-0" /> {t('action.delete')}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Right: Checkbox ONLY toggles selection */}
                  <Tooltip content={isChecked ? "Exclude from AI context" : "Include in AI context"} side="left">
                    <div 
                      className="flex items-center shrink-0 p-1 -m-1 cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleDocSelection(doc.id);
                      }}
                      aria-label={isChecked ? "Exclude from AI context" : "Include in AI context"}
                    >
                      <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
                        isChecked ? "bg-blue-600 border-blue-600 text-white" : "border-app-border-strong bg-transparent"
                      }`}>
                        {isChecked && <Check size={9} strokeWidth={3} />}
                      </div>
                    </div>
                  </Tooltip>
                </div>
              );
            })}

            {/* Pending Uploading & Resolving Sources */}
            {pendingSources.map((item: PendingSourceItem, pIdx: number) => {
              const itemNumber = documents.length + pIdx + 1;

              return (
                <div
                  key={item.id}
                  className="flex items-center justify-between py-2 px-2.5 rounded-lg bg-transparent hover:bg-app-item-hover transition-colors select-none group"
                >
                  {/* Left: Monospace Number + Badge + File / DOI Name */}
                  <div className="flex items-center gap-2 min-w-0 flex-1 mr-1.5">
                    <span 
                      className="w-6 text-left text-[11px] font-mono font-medium text-app-text-dim shrink-0 select-none tabular-nums"
                    >
                      {itemNumber}.
                    </span>

                    {/* Placeholder Silhouette Badge for Pending Sources */}
                    <div className="w-5 h-5 rounded border border-app-border-strong border-dashed flex items-center justify-center shrink-0 bg-app-item-hover/50 opacity-50">
                      <div className="w-2.5 h-1 bg-app-text-dim rounded-full animate-pulse" />
                    </div>

                    <span 
                      className={`text-[11.5px] truncate font-normal ${
                        item.status === "error" ? "text-red-500 line-through opacity-80" : "text-app-text-muted"
                      }`} 
                      title={item.filename}
                    >
                      {item.filename}
                    </span>
                  </div>

                  {/* Right: Circular Spinner (with Hover Cancel 'X') or Error Icon */}
                  <div className="flex items-center shrink-0 p-1 -m-1">
                    {item.status === "uploading" ? (
                      <div className="relative w-3.5 h-3.5 flex items-center justify-center group/spinner">
                        {/* Normal Spinning Circle (Hides on hover) */}
                        <div className="flex items-center justify-center group-hover/spinner:hidden" title={t('right.uploading')}>
                          <svg className="animate-spin w-3.5 h-3.5 text-blue-400" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                            <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                        </div>
                        {/* Hover Cancel 'X' Button */}
                        <Tooltip content={t('right.cancelUpload') || "Cancel upload"} side="left">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (cancelPendingSource) {
                                cancelPendingSource(item.id);
                              } else {
                                setInternalPendingSources(prev => prev.filter(p => p.id !== item.id));
                              }
                            }}
                            className="hidden group-hover/spinner:flex items-center justify-center w-3.5 h-3.5 text-app-text-muted hover:text-red-500 rounded transition-colors cursor-pointer"
                            aria-label={t('right.cancelUpload') || "Cancel upload"}
                          >
                            <X size={12} strokeWidth={2.5} />
                          </button>
                        </Tooltip>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1">
                        <span title={item.error || t('right.uploadFailed')} className="text-red-400 cursor-help">
                          <AlertCircle size={13} />
                        </span>
                        <Tooltip content={t('right.dismiss')} side="top">
                          <button
                            type="button"
                            onClick={() => {
                              if (cancelPendingSource) {
                                cancelPendingSource(item.id);
                              } else {
                                setInternalPendingSources(prev => prev.filter(p => p.id !== item.id));
                              }
                            }}
                            className="text-app-text-dim hover:text-app-text p-0.5 rounded cursor-pointer"
                            aria-label={t('right.dismiss')}
                          >
                            <X size={12} />
                          </button>
                        </Tooltip>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
};
