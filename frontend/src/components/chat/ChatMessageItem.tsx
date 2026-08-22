"use client";

import React, { useState, useMemo, useCallback, memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  ChevronDown, 
  Check, 
  Plus, 
  Loader2, 
  ExternalLink, 
  BookOpen, 
  Copy, 
  Pencil, 
  Clock, 
  Trash2 
} from "lucide-react";
import { ChatMessage, Document as DocType } from "@/app/ChatClient";
import { parseCitationsInReactNode, CitationContext } from "./CitationParser";
import { FileText, Image as ImageIcon } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

export interface InChatMessageProps {
  msg: ChatMessage;
  activeChatId: string | null;
  backendUrl: string;
  documents?: DocType[];
  onDocumentAdded?: (doc: DocType, targetChatId?: string) => void;
  onAddPendingSources?: (items: { id: string; filename: string; type: "file" | "doi"; status: "uploading" }[]) => void;
  onResolvePendingSource?: (pendingId: string) => void;
  onOpenDocument?: (doc: DocType, citationContext?: CitationContext) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  activeCitationKey?: string | null;
}

export const InChatMessageComponent = memo(function InChatMessageComponent({ 
  msg, 
  activeChatId, 
  backendUrl, 
  documents = [],
  onDocumentAdded,
  onAddPendingSources,
  onResolvePendingSource,
  onOpenDocument,
  onEnsureChatSession,
  activeCitationKey
}: InChatMessageProps) {
  const { t } = useTranslation();
  const isUser = msg.role === "user";
  const { cleanContent, sources, citationMap } = useMemo(() => {
    const sourcesMatch = msg.content.match(/<!-- SOURCES_DATA:\s*([\s\S]*?)\s*-->/);
    const citationMapMatch = msg.content.match(/<!-- CITATION_MAP:\s*([\s\S]*?)\s*-->/);

    let clean = msg.content;
    let parsedSources: any[] = [];
    let parsedCitationMap: Record<string, string[]> = {};
    
    if (sourcesMatch) {
      clean = clean.replace(/<!-- SOURCES_DATA:[\s\S]*?-->/, "").trim();
      try {
        parsedSources = JSON.parse(sourcesMatch[1]);
      } catch (e) {
        console.error("Failed to parse sources data:", e);
      }
    }

    if (citationMapMatch) {
      clean = clean.replace(/<!-- CITATION_MAP:[\s\S]*?-->/, "").trim();
      try {
        // Robust JSON parse: strip markdown code fences, trailing commas
        let rawJson = citationMapMatch[1].trim();
        rawJson = rawJson.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
        rawJson = rawJson.replace(/,\s*([\]}])/g, "$1"); // trailing commas
        parsedCitationMap = JSON.parse(rawJson);
      } catch (e) {
        console.error("Failed to parse citation map data:", e);
      }
    }

    // Clean any internal actions tag
    clean = clean.replace(/<!-- SOURCES_ACTION:[\s\S]*?-->/, "").trim();
    return { cleanContent: clean, sources: parsedSources, citationMap: parsedCitationMap };
  }, [msg.content]);

  const isDuplicateSource = useCallback((src: any) => {
    if (!documents || documents.length === 0) return false;
    const normalize = (s: string) => s.replace(/\.pdf$/i, "").replace(/[^a-zA-Z0-9\s]/g, " ").toLowerCase().trim().replace(/\s+/g, " ");
    const srcNorm = normalize(src.title || "");
    if (!srcNorm) return false;
    const srcTokens = new Set(srcNorm.split(" "));

    for (const doc of documents) {
      const docNorm = normalize(doc.filename || "");
      if (!docNorm) continue;
      if (srcNorm === docNorm) return true;
      if (docNorm.length >= 20 && (srcNorm.startsWith(docNorm) || docNorm.startsWith(srcNorm))) return true;

      const docTokens = new Set(docNorm.split(" "));
      let intersection = 0;
      for (const t of srcTokens) {
        if (docTokens.has(t)) intersection++;
      }
      const minLen = Math.min(srcTokens.size, docTokens.size);
      if (minLen > 0 && intersection / minLen >= 0.75 && intersection >= 3) return true;
    }
    return false;
  }, [documents]);

  const [userSelectionOverrides, setUserSelectionOverrides] = useState<Record<number, boolean>>({});
  const [isImporting, setIsImporting] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const isSourceChecked = useCallback((src: any, index: number) => {
    if (isDuplicateSource(src)) return false;
    if (userSelectionOverrides[index] !== undefined) {
      return userSelectionOverrides[index];
    }
    return true;
  }, [userSelectionOverrides, isDuplicateSource]);

  const toggleSelectAll = () => {
    const novelIndices = sources.map((s, i) => (!isDuplicateSource(s) ? i : -1)).filter(i => i !== -1);
    const areAllNovelSelected = novelIndices.length > 0 && novelIndices.every(i => isSourceChecked(sources[i], i));
    const nextState = !areAllNovelSelected;
    
    const updated = { ...userSelectionOverrides };
    novelIndices.forEach(i => {
      updated[i] = nextState;
    });
    setUserSelectionOverrides(updated);
  };

  const [importProgress, setImportProgress] = useState<{ current: number; total: number } | null>(null);

  const handleImport = async () => {
    const toImport = sources.filter((src, i) => !isDuplicateSource(src) && isSourceChecked(src, i));
    if (toImport.length === 0) return;

    setIsImporting(true);
    setImportProgress({ current: 0, total: toImport.length });

    // Register pending placeholder sources immediately in the sidebar so circular spinners appear
    const pendingItems = toImport.map((src, idx) => ({
      id: `pending-import-${Date.now()}-${idx}-${Math.random().toString(36).slice(2, 6)}`,
      filename: `${(src.title || src.doi || "Research Paper").trim()}.pdf`,
      type: "doi" as const,
      doi: src.doi,
      status: "uploading" as const,
    }));
    onAddPendingSources?.(pendingItems);

    try {
      let currentChatId = activeChatId;
      if (!currentChatId && onEnsureChatSession) {
        currentChatId = await onEnsureChatSession(toImport[0]?.title || "Research Paper");
      }
      if (!currentChatId) return;

      // Client-side granular batch ingestion (Chunked by 4 items)
      // Guarantees real-time progress update (1/44 -> 4/44 -> 8/44) and instant sidebar append
      const CHUNK_SIZE = 4;
      let totalSuccessfullyAdded = 0;

      for (let i = 0; i < toImport.length; i += CHUNK_SIZE) {
        const chunk = toImport.slice(i, i + CHUNK_SIZE);
        const chunkPendingIds = pendingItems.slice(i, i + CHUNK_SIZE).map(p => p.id);
        try {
          const res = await fetch(`${backendUrl}/chats/${currentChatId}/import_sources`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sources: chunk })
          });

          if (res.ok) {
            const createdDocs = await res.json();
            if (createdDocs && createdDocs.length > 0) {
              createdDocs.forEach((d: DocType) => onDocumentAdded?.(d, currentChatId));
              totalSuccessfullyAdded += createdDocs.length;
            }
          }
        } catch (chunkErr) {
          console.error("Chunk import error:", chunkErr);
        } finally {
          chunkPendingIds.forEach(id => onResolvePendingSource?.(id));
        }

        const currentProgress = Math.min(i + chunk.length, toImport.length);
        setImportProgress({ current: currentProgress, total: toImport.length });
      }

      setUserSelectionOverrides({});
    } catch (e) {
      console.error("Import sources failed:", e);
    } finally {
      setIsImporting(false);
      setImportProgress(null);
    }
  };

  const novelSourcesCount = useMemo(() => sources.filter(s => !isDuplicateSource(s)).length, [sources, isDuplicateSource]);
  const selectedCount = useMemo(() => sources.filter((s, i) => !isDuplicateSource(s) && isSourceChecked(s, i)).length, [sources, isDuplicateSource, isSourceChecked]);
  const allNovelSelected = useMemo(() => {
    const novelIndices = sources.map((s, i) => (!isDuplicateSource(s) ? i : -1)).filter(i => i !== -1);
    return novelIndices.length > 0 && novelIndices.every(i => isSourceChecked(sources[i], i));
  }, [sources, isDuplicateSource, isSourceChecked]);

  return (
    <div className={`mb-5 flex ${isUser ? "justify-end" : "justify-start"} font-sans group`}>
      <div 
        className={`relative inline-block max-w-[95%] sm:max-w-[85%] leading-relaxed tracking-wide ${
          isUser 
            ? "bg-[#18181b] border border-white/5 text-gray-200 px-5 py-3.5 rounded-[1.5rem] rounded-tr-sm shadow-md"
            : "text-gray-300 w-full"
        }`}
      >
        {isUser && msg.attachments && msg.attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2 pb-2 border-b border-white/10">
            {msg.attachments.map((att, idx) => {
              const fileHref = att.url?.startsWith("http") ? att.url : `${backendUrl}${att.url || ""}`;
              return (
                <a 
                  key={idx} 
                  href={fileHref} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-1.5 pr-3 rounded-lg bg-black/40 border border-white/5 hover:border-white/20 transition-colors"
                >
                  {att.type === "image" ? (
                    <div className="w-10 h-10 rounded shrink-0 overflow-hidden bg-black/60">
                      <img src={fileHref} alt={att.filename} className="w-full h-full object-cover" />
                    </div>
                  ) : (
                    <div className="w-10 h-10 rounded shrink-0 bg-white/5 flex items-center justify-center">
                      <FileText size={18} className="text-gray-400" />
                    </div>
                  )}
                  <span className="text-[11px] text-gray-300 font-medium truncate max-w-[150px]">{att.filename}</span>
                </a>
              );
            })}
          </div>
        )}

    <div className="w-full space-y-2">
      {/* 1. Main Markdown Text Content */}
      <div className="prose prose-invert max-w-none text-[16px] leading-[1.65]">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <p className="mb-2 last:mb-0 text-gray-100 leading-[1.65]">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "p")}</p>,
            h1: ({ children }) => <h1 className="text-2xl font-bold text-white mt-5 mb-2.5 tracking-tight">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "h1")}</h1>,
            h2: ({ children }) => <h2 className="text-xl font-bold text-white mt-4 mb-2 tracking-tight">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "h2")}</h2>,
            h3: ({ children }) => <h3 className="text-lg font-semibold text-white mt-3 mb-1.5">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "h3")}</h3>,
            ul: ({ children }) => <ul className="list-disc pl-5 my-2.5 space-y-1.5 text-gray-100">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal pl-5 my-2.5 space-y-1.5 text-gray-100">{children}</ol>,
            li: ({ children }) => <li className="leading-[1.65]">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "li")}</li>,
            em: ({ children }) => <em className="italic">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "em")}</em>,
            strong: ({ children }) => <strong className="font-semibold text-white">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "strong")}</strong>,
            a: ({ href, children }) => (
              <a 
                href={href} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-blue-400 hover:text-blue-300 underline font-medium break-all"
              >
                {children}
              </a>
            ),
            table: ({ children }) => (
              <div className="overflow-x-auto my-4 rounded-xl border border-white/10 shadow-md">
                <table className="w-full text-left text-sm border-collapse bg-[#1a1b1e]">
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => <thead className="bg-[#24262b] text-gray-200 border-b border-white/10 font-semibold">{children}</thead>,
            tbody: ({ children }) => <tbody className="divide-y divide-white/5">{children}</tbody>,
            tr: ({ children }) => <tr className="hover:bg-white/[0.02] transition-colors">{children}</tr>,
            th: ({ children }) => <th className="py-2.5 px-3 font-semibold text-gray-200 text-xs tracking-wider uppercase">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "th")}</th>,
            td: ({ children }) => <td className="py-2.5 px-3 text-gray-300 text-xs leading-relaxed">{parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "td")}</td>,
            blockquote: ({ children }) => (
              <blockquote className="border-l-2 border-blue-500 pl-4 py-1.5 my-3 text-gray-300 bg-blue-500/5 rounded-r-lg italic">
                {parseCitationsInReactNode(children, documents, onOpenDocument, activeCitationKey, undefined, citationMap, "blockquote")}
              </blockquote>
            ),
            pre: ({ children }) => (
              <div className="relative group my-3">
                <pre className="bg-[#16171a] p-3.5 rounded-xl overflow-x-auto text-xs text-gray-200 font-mono border border-white/10">
                  {children}
                </pre>
              </div>
            ),
            code: ({ inline, className, children, ...props }: any) => {
              if (inline) {
                return (
                  <code className="bg-white/10 text-blue-300 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
                    {children}
                  </code>
                );
              }
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            }
          }}
        >
          {cleanContent}
        </ReactMarkdown>
      </div>

      {/* 2. Embedded Interactive Paper Source Cards */}
      {sources.length > 0 && (
        <div className="mt-4 rounded-2xl bg-[#1e1f20] border border-white/10 overflow-hidden shadow-lg animate-in fade-in duration-200">
          <div 
            className="p-3.5 px-4 bg-[#28292c] flex items-center justify-between cursor-pointer select-none hover:bg-[#2d2e32] transition-colors border-b border-white/5"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-white">
                Report &amp; Outside sources ({sources.length})
              </span>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <ChevronDown size={16} className={`transition-transform duration-200 ${isCollapsed ? "-rotate-90" : ""}`} />
            </div>
          </div>

          {!isCollapsed && (
            <>
              <div className="px-4 py-2 bg-[#222325] border-b border-white/5 flex items-center justify-between text-xs text-gray-300">
                <span className="text-gray-400">{t('chat.researchFound')}</span>
                {novelSourcesCount > 0 && (
                  <button 
                    onClick={(e) => { e.stopPropagation(); toggleSelectAll(); }}
                    className="hover:text-white font-medium cursor-pointer transition-colors text-blue-400"
                  >
                    {allNovelSelected ? "Deselect All" : "Select All"}
                  </button>
                )}
              </div>

              <div className="max-h-[360px] overflow-y-auto divide-y divide-white/5 p-1 custom-scrollbar">
                {sources.map((src, i) => {
                  const isAlreadyAdded = isDuplicateSource(src);
                  const isChecked = isAlreadyAdded || isSourceChecked(src, i);
                  return (
                    <div 
                      key={i} 
                      onClick={() => {
                        if (!isAlreadyAdded) {
                          setUserSelectionOverrides(prev => ({ ...prev, [i]: !isSourceChecked(src, i) }));
                        }
                      }}
                      className={`p-3 px-3.5 flex items-start justify-between gap-3 transition-colors rounded-xl m-1 ${
                        isAlreadyAdded 
                          ? "bg-emerald-500/[0.04] border border-emerald-500/10 cursor-default" 
                          : isChecked 
                            ? "bg-white/[0.04] hover:bg-white/5 cursor-pointer" 
                            : "hover:bg-white/5 cursor-pointer"
                      }`}
                    >
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className={`p-2 rounded-lg shrink-0 mt-0.5 ${
                          isAlreadyAdded ? "bg-emerald-500/10 text-emerald-400" : "bg-blue-500/10 text-blue-400"
                        }`}>
                          <BookOpen size={16} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline gap-2 flex-wrap">
                            <h4 className="text-xs font-semibold text-white leading-snug line-clamp-2">
                              {src.title}
                            </h4>
                            {src.year && src.year !== "N/A" && (
                              <span className="text-[11px] text-gray-400 shrink-0">
                                ({src.year})
                              </span>
                            )}
                            {isAlreadyAdded && (
                              <span className="text-[10px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded-full shrink-0">
                                In Sources
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            {src.url ? (
                              <a 
                                href={src.url} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                onClick={(e) => e.stopPropagation()}
                                className="text-[11px] text-blue-400 hover:text-blue-300 hover:underline flex items-center gap-1 shrink-0"
                              >
                                <span>{src.doi ? `DOI: ${src.doi}` : "Journal Link"}</span>
                                <ExternalLink size={10} />
                              </a>
                            ) : src.doi ? (
                              <span className="text-[11px] text-gray-400 font-mono">
                                DOI: {src.doi}
                              </span>
                            ) : null}
                          </div>
                          {src.snippet && (
                            <p className="text-[11px] text-gray-400 line-clamp-1 leading-normal mt-0.5">
                              {src.snippet}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className={`w-4 h-4 rounded border mt-1 flex items-center justify-center shrink-0 transition-colors ${
                        isAlreadyAdded 
                          ? "bg-emerald-600/30 border-emerald-500/40 text-emerald-300"
                          : isChecked 
                            ? "bg-blue-600 border-blue-600 text-white" 
                            : "border-gray-500 bg-transparent"
                      }`}>
                        {(isAlreadyAdded || isChecked) && <Check size={11} strokeWidth={3} />}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="p-3 px-4 bg-[#18191a] border-t border-white/5 flex items-center justify-between">
                <span className="text-xs text-gray-400 font-medium">
                  {selectedCount}/{novelSourcesCount} new selected
                </span>

                <button
                  type="button"
                  onClick={handleImport}
                  disabled={isImporting || selectedCount === 0}
                  className="h-8 px-4 rounded-full bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed border-0 outline-none transition-colors"
                >
                  {isImporting ? (
                    <>
                      <Loader2 size={12} className="animate-spin" />
                      <span>
                        {importProgress ? `Adding ${importProgress.current}/${importProgress.total}...` : "Adding sources..."}
                      </span>
                    </>
                  ) : (
                    <>
                      <Plus size={13} />
                      <span>{t('chat.addToSources').replace('{count}', selectedCount > 0 ? `${selectedCount} ` : "")}</span>
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
    </div>
    </div>
  );
});
