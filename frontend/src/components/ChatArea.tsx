"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo, memo, Fragment, cloneElement, isValidElement } from "react";
import { 
  ArrowUp, 
  ArrowRight,
  Sparkles, 
  FileText, 
  ChevronDown, 
  Check, 
  Plus, 
  Loader2, 
  ExternalLink, 
  BookOpen, 
  Copy, 
  Pencil,
  Square,
  Clock,
  X,
  Trash2,
  SlidersHorizontal
} from "lucide-react";
import { ChatMessage, Document as DocType, TargetedSource } from "@/app/ChatClient";
import ModelSelector from "@/components/ModelSelector";
import SearchFilterPopover, { SearchFilterState, DEFAULT_SEARCH_FILTER } from "@/components/SearchFilterPopover";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatAreaProps {
  activeChatId: string | null;
  messages: ChatMessage[];
  isLoading?: boolean;
  onSendMessage: (message: string) => void;
  onEditMessage?: (messageIndex: number, newContent: string) => void;
  onStopGeneration?: () => void;
  queuedPrompts?: string[];
  onRemoveQueuedPrompt?: (index: number) => void;
  onPromoteQueuedPrompt?: (index: number) => void;
  documents: DocType[];
  onDocumentAdded?: (doc: DocType) => void;
  onOpenDocument?: (doc: DocType) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  backendUrl: string;
  isSidebarOpen?: boolean;
  onOpenSidebar?: () => void;
  isRightSidebarOpen?: boolean;
  onToggleRightSidebar?: () => void;
  targetedSource?: TargetedSource | null;
  onClearTargetedSource?: () => void;
  activeStatus?: string | null;
}

interface InChatMessageProps {
  msg: ChatMessage;
  activeChatId: string | null;
  backendUrl: string;
  documents?: DocType[];
  onDocumentAdded?: (doc: DocType) => void;
  onOpenDocument?: (doc: DocType) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
}

// Helper to recursively parse IEEE-style citation brackets [1], [2], [1, 2], [1-3] into interactive clickable pills
function parseCitationsInReactNode(
  node: React.ReactNode, 
  documents?: DocType[], 
  onOpenDocument?: (doc: DocType) => void
): React.ReactNode {
  if (typeof node === "string") {
    // Regex matching [1], [2], [1, 2], [1-3], [1, 3, 5]
    const regex = /\[(\d+(?:\s*,\s*\d+|\s*-\s*\d+)*)\]/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(node)) !== null) {
      const matchIndex = match.index;
      if (matchIndex > lastIndex) {
        parts.push(node.substring(lastIndex, matchIndex));
      }

      const rawNumbers = match[1];
      const nums: number[] = [];
      if (rawNumbers.includes("-")) {
        const [startStr, endStr] = rawNumbers.split("-");
        const start = parseInt(startStr.trim(), 10);
        const end = parseInt(endStr.trim(), 10);
        if (!isNaN(start) && !isNaN(end) && start <= end && end - start <= 10) {
          for (let i = start; i <= end; i++) nums.push(i);
        } else if (!isNaN(start)) {
          nums.push(start);
        }
      } else {
        rawNumbers.split(",").forEach(nStr => {
          const n = parseInt(nStr.trim(), 10);
          if (!isNaN(n)) nums.push(n);
        });
      }

      if (nums.length > 0) {
        parts.push(
          <span key={`cite-group-${matchIndex}`} className="inline-flex items-center gap-0.5 mx-0.5 align-baseline">
            {nums.map((num, i) => {
              const doc = documents?.find(d => (d.index ? d.index === num : false)) || documents?.[num - 1];
              const docTitle = doc?.filename.replace(/\.pdf$/i, "") || `Referenced Source [${num}]`;

              return (
                <button
                  key={`pill-${num}-${i}`}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (doc && onOpenDocument) {
                      onOpenDocument(doc);
                    }
                  }}
                  className="inline-flex items-center justify-center px-1.5 py-0 min-w-[20px] h-[19px] text-[10.5px] font-mono font-bold text-blue-300 hover:text-blue-100 bg-blue-500/15 hover:bg-blue-500/35 border border-blue-500/30 hover:border-blue-400/70 rounded-full cursor-pointer transition-all duration-150 transform hover:scale-110 active:scale-95 select-none shadow-sm"
                  title={`[${num}] ${docTitle}\nClick to open paper details in panel`}
                >
                  {num}
                </button>
              );
            })}
          </span>
        );
      } else {
        parts.push(match[0]);
      }

      lastIndex = regex.lastIndex;
    }

    if (lastIndex < node.length) {
      parts.push(node.substring(lastIndex));
    }

    return parts.length === 1 ? parts[0] : parts;
  }

  if (Array.isArray(node)) {
    return node.map((child, idx) => (
      <React.Fragment key={idx}>{parseCitationsInReactNode(child, documents, onOpenDocument)}</React.Fragment>
    ));
  }

  if (React.isValidElement(node) && (node.props as any)?.children) {
    return React.cloneElement(node as React.ReactElement<any>, {
      children: parseCitationsInReactNode((node.props as any).children, documents, onOpenDocument)
    });
  }

  return node;
}

// Memoized In-Chat Message Component with Markdown parsing & Interactive Source Cards
const InChatMessageComponent = memo(function InChatMessageComponent({ 
  msg, 
  activeChatId, 
  backendUrl, 
  documents = [],
  onDocumentAdded, 
  onOpenDocument,
  onEnsureChatSession 
}: InChatMessageProps) {
  // Parse any embedded SOURCES_DATA with useMemo
  const { cleanContent, sources } = useMemo(() => {
    const sourcesMatch = msg.content.match(/<!-- SOURCES_DATA:\s*([\s\S]*?)\s*-->/);
    let clean = msg.content;
    let parsedSources: any[] = [];
    
    if (sourcesMatch) {
      clean = msg.content.replace(/<!-- SOURCES_DATA:[\s\S]*?-->/, "").trim();
      try {
        parsedSources = JSON.parse(sourcesMatch[1]);
      } catch (e) {
        console.error("Failed to parse sources data:", e);
      }
    }
    return { cleanContent: clean, sources: parsedSources };
  }, [msg.content]);

  // Smart fuzzy & DOI duplicate detection against current notebook documents
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
  const [isImported, setIsImported] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const isSourceChecked = useCallback((src: any, index: number) => {
    if (userSelectionOverrides[index] !== undefined) {
      return userSelectionOverrides[index];
    }
    return !isDuplicateSource(src);
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

  const handleImport = async () => {
    const toImport = sources.filter((src, i) => isSourceChecked(src, i));
    if (toImport.length === 0) return;

    setIsImporting(true);
    try {
      let currentChatId = activeChatId;
      if (!currentChatId && onEnsureChatSession) {
        currentChatId = await onEnsureChatSession(toImport[0]?.title || "Research Paper");
      }
      if (!currentChatId) return;

      const res = await fetch(`${backendUrl}/chats/${currentChatId}/import_sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: toImport })
      });
      if (res.ok) {
        const createdDocs = await res.json();
        if (createdDocs && createdDocs.length > 0) {
          createdDocs.forEach((d: DocType) => onDocumentAdded?.(d));
        }
        setIsImported(true);
      }
    } catch (e) {
      console.error("Import sources failed:", e);
    } finally {
      setIsImporting(false);
    }
  };

  const novelSourcesCount = useMemo(() => sources.filter(s => !isDuplicateSource(s)).length, [sources, isDuplicateSource]);
  const selectedCount = useMemo(() => sources.filter((s, i) => isSourceChecked(s, i)).length, [sources, isSourceChecked]);
  const allNovelSelected = useMemo(() => {
    const novelIndices = sources.map((s, i) => (!isDuplicateSource(s) ? i : -1)).filter(i => i !== -1);
    return novelIndices.length > 0 && novelIndices.every(i => isSourceChecked(sources[i], i));
  }, [sources, isDuplicateSource, isSourceChecked]);

  return (
    <div className="w-full space-y-3">
      {/* 1. Main Markdown Text Content */}
      <div className="prose prose-invert max-w-none text-[16px] leading-[1.65] space-y-3">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <p className="mb-2.5 last:mb-0 text-gray-100 leading-[1.65]">{parseCitationsInReactNode(children, documents, onOpenDocument)}</p>,
            h1: ({ children }) => <h1 className="text-2xl font-bold text-white mt-5 mb-2.5 tracking-tight">{children}</h1>,
            h2: ({ children }) => <h2 className="text-xl font-bold text-white mt-4 mb-2 tracking-tight">{children}</h2>,
            h3: ({ children }) => <h3 className="text-lg font-semibold text-white mt-3 mb-1.5">{children}</h3>,
            ul: ({ children }) => <ul className="list-disc pl-5 my-2.5 space-y-1.5 text-gray-100">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal pl-5 my-2.5 space-y-1.5 text-gray-100">{children}</ol>,
            li: ({ children }) => <li className="leading-[1.65]">{parseCitationsInReactNode(children, documents, onOpenDocument)}</li>,
            strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
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
            th: ({ children }) => <th className="py-2.5 px-3 font-semibold text-gray-200 text-xs tracking-wider uppercase">{children}</th>,
            td: ({ children }) => <td className="py-2.5 px-3 text-gray-300 text-xs leading-relaxed">{parseCitationsInReactNode(children, documents, onOpenDocument)}</td>,
            blockquote: ({ children }) => (
              <blockquote className="border-l-2 border-blue-500 pl-4 py-1.5 my-3 text-gray-300 bg-blue-500/5 rounded-r-lg italic">
                {parseCitationsInReactNode(children, documents, onOpenDocument)}
              </blockquote>
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
                <div className="relative group my-3">
                  <pre className="bg-[#16171a] p-3.5 rounded-xl overflow-x-auto text-xs text-gray-200 font-mono border border-white/10">
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                </div>
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
          
          {/* Header Bar */}
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

          {/* Collapsible Body */}
          {!isCollapsed && (
            <>
              {/* Select All Subheader Bar */}
              <div className="px-4 py-2 bg-[#222325] border-b border-white/5 flex items-center justify-between text-xs text-gray-300">
                <span className="text-gray-400">Research papers and articles found</span>
                {novelSourcesCount > 0 && (
                  <button 
                    onClick={(e) => { e.stopPropagation(); toggleSelectAll(); }}
                    className="hover:text-white font-medium cursor-pointer transition-colors text-blue-400"
                  >
                    {allNovelSelected ? "Deselect All" : "Select All"}
                  </button>
                )}
              </div>

              {/* Scrollable Paper Cards List */}
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

              {/* Sticky Bottom Actions Bar */}
              <div className="p-3 px-4 bg-[#18191a] border-t border-white/5 flex items-center justify-between">
                <span className="text-xs text-gray-400 font-medium">
                  {selectedCount}/{novelSourcesCount} new selected
                </span>

                <button
                  type="button"
                  onClick={handleImport}
                  disabled={isImporting || selectedCount === 0 || isImported}
                  className="h-8 px-4 rounded-full bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed border-0 outline-none transition-colors"
                >
                  {isImporting ? (
                    <>
                      <Loader2 size={12} className="animate-spin" />
                      <span>Adding...</span>
                    </>
                  ) : isImported ? (
                    <>
                      <Check size={12} />
                      <span>Added to sources</span>
                    </>
                  ) : (
                    <>
                      <Plus size={13} />
                      <span>Add to sources</span>
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
});

// Memoized Isolated Input Box (Zero-latency typing without re-rendering parent message tree)
interface ChatInputBoxProps {
  isCentered?: boolean;
  isLoading?: boolean;
  documentsCount: number;
  onToggleRightSidebar?: () => void;
  onSubmit: (text: string) => void;
  onStopGeneration?: () => void;
  queuedPrompts?: string[];
  onRemoveQueuedPrompt?: (index: number) => void;
  onPromoteQueuedPrompt?: (index: number) => void;
  backendUrl: string;
  targetedSource?: TargetedSource | null;
  onClearTargetedSource?: () => void;
}

const ChatInputBox = memo(function ChatInputBox({
  isCentered = false,
  isLoading = false,
  documentsCount,
  onToggleRightSidebar,
  onSubmit,
  onStopGeneration,
  queuedPrompts = [],
  onRemoveQueuedPrompt,
  onPromoteQueuedPrompt,
  backendUrl,
  targetedSource,
  onClearTargetedSource
}: ChatInputBoxProps) {
  const [input, setInput] = useState("");
  const [filter, setFilter] = useState<SearchFilterState>(DEFAULT_SEARCH_FILTER);
  const [isFilterOpen, setIsFilterOpen] = useState<boolean>(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height smoothly as text wraps/expands
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleSend = () => {
    const query = input.trim();
    if (!query) return;

    // Check if any academic search filters are active
    const filterClauses: string[] = [];
    if (filter.yearFrom && filter.yearTo) {
      filterClauses.push(`years ${filter.yearFrom}-${filter.yearTo}`);
    } else if (filter.yearFrom) {
      filterClauses.push(`from ${filter.yearFrom} onwards`);
    } else if (filter.yearTo) {
      filterClauses.push(`up to ${filter.yearTo}`);
    }

    if (filter.minCitations && Number(filter.minCitations) > 0) {
      filterClauses.push(`minimum ${filter.minCitations} citations`);
    }

    if (filter.scopusQuartiles && filter.scopusQuartiles.length > 0) {
      filterClauses.push(`Scopus ${filter.scopusQuartiles.join("/")}`);
    }

    if (filter.sintaTiers && filter.sintaTiers.length > 0) {
      filterClauses.push(`SINTA ${filter.sintaTiers.join("/")}`);
    }

    if (filter.excludePreprints) {
      filterClauses.push("exclude preprints");
    }

    if (filter.openAccessOnly) {
      filterClauses.push("open access only");
    }

    if (filter.language && filter.language !== "all") {
      filterClauses.push(`language: ${filter.language}`);
    }

    if (filter.fieldsOfStudy && filter.fieldsOfStudy.length > 0) {
      filterClauses.push(`discipline: ${filter.fieldsOfStudy.join(", ")}`);
    }

    let finalMessage = query;
    if (targetedSource) {
      finalMessage = `[Focused Document: "${targetedSource.title || targetedSource.filename}"]\n${query}`;
    }
    if (filterClauses.length > 0) {
      finalMessage = `${finalMessage}\n[Filter Preferences: ${filterClauses.join(", ")}]`;
    }

    onSubmit(finalMessage);
    setInput("");
    onClearTargetedSource?.();
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  return (
    <div className={`w-full ${isCentered ? "max-w-2xl mx-auto my-4" : "max-w-3xl mx-auto"}`}>
      {/* Floating Queued Prompts Container (Antigravity Style) */}
      {queuedPrompts && queuedPrompts.length > 0 && (
        <div className="mb-2.5 rounded-2xl bg-[#1e1f22] border border-white/10 shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200">
          {/* Header */}
          <div className="flex items-center justify-between px-3.5 py-2 border-b border-white/5 bg-[#25262a]">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-semibold text-gray-200">Queued Messages</span>
              <span className="px-1.5 py-0.2 rounded-full bg-white/10 text-gray-300 text-[11px] font-mono font-medium">
                {queuedPrompts.length}
              </span>
              <span className="text-[11px] text-gray-400 font-normal hidden sm:inline">
                Sends after agent finishes working
              </span>
            </div>
          </div>

          {/* List of Queued Items */}
          <div className="p-2 space-y-1 divide-y divide-white/5">
            {queuedPrompts.map((qText, qIdx) => (
              <div 
                key={qIdx}
                className="flex items-center justify-between gap-3 px-2 py-1.5 group rounded-lg hover:bg-white/[0.03] transition-colors"
              >
                <p className="text-xs text-gray-200 truncate flex-1 font-normal select-text">
                  {qText}
                </p>

                {/* Actions: Send Now (Switch/Promote), Edit, Delete */}
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => onPromoteQueuedPrompt?.(qIdx)}
                    className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                    title="Switch & process now (stop current task)"
                  >
                    <ArrowRight size={14} className="text-blue-400" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setInput(qText);
                      onRemoveQueuedPrompt?.(qIdx);
                      textareaRef.current?.focus();
                    }}
                    className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
                    title="Edit queued message"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemoveQueuedPrompt?.(qIdx)}
                    className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
                    title="Remove from queue"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Input Box (Antigravity Style Card) */}
      <div className="bg-[#1e1f22] rounded-2xl p-2.5 sm:p-3 border border-white/10 shadow-2xl focus-within:border-white/20 transition-all flex flex-col gap-2">
        {/* Active Dedicated Source Reference Card (Dismissible) */}
        {targetedSource && (
          <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-xl bg-blue-950/50 border border-blue-800/70 text-xs animate-in fade-in slide-in-from-top-1 duration-150 shadow-sm">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1 rounded-md bg-blue-500/20 text-blue-400 shrink-0">
                <FileText size={12} />
              </div>
              <span className="text-blue-300 font-medium text-[11.5px] shrink-0">Focused on:</span>
              <span className="font-semibold text-white text-[12px] truncate max-w-[240px] sm:max-w-[420px]">
                {targetedSource.title || targetedSource.filename}
              </span>
            </div>
            <button
              type="button"
              onClick={onClearTargetedSource}
              className="p-1 rounded-md hover:bg-white/10 text-gray-400 hover:text-white transition-colors cursor-pointer shrink-0 flex items-center gap-1 text-[11px]"
              title="Cancel focus on this document"
            >
              <X size={13} />
              <span className="hidden sm:inline">Cancel</span>
            </button>
          </div>
        )}

        {/* Top Textarea */}
        <textarea 
          id="chat-input-textarea"
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={
            targetedSource 
              ? "Ask a question about this source..."
              : (isLoading ? "Type your next message (automatically queued)..." : "Ask NotbookLM anything")
          }
          style={{ wordBreak: "break-word", overflowWrap: "break-word", whiteSpace: "pre-wrap" }}
          className="w-full bg-transparent border-0 focus:outline-none resize-none px-2 py-1 text-[15px] text-white placeholder:text-gray-500 max-h-[180px] min-h-[32px] overflow-y-auto overflow-x-hidden leading-relaxed shadow-none box-border"
        />

        {/* Bottom Actions Row (Clean seamlessly integrated row without divider) */}
        <div className="flex items-center justify-between gap-2 pt-0.5">
          {/* Left: ModelSelector */}
          <div className="flex items-center">
            <ModelSelector backendUrl={backendUrl} />
          </div>

          {/* Right: Filter, Sources Badge and Send/Stop Button */}
          <div className="flex items-center gap-2">
            <SearchFilterPopover 
              filter={filter}
              onApplyFilter={(newFilter) => setFilter(newFilter)}
              isOpen={isFilterOpen}
              onClose={() => setIsFilterOpen(false)}
              onToggle={() => setIsFilterOpen(prev => !prev)}
            />

            <button
              type="button"
              onClick={onToggleRightSidebar}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] text-gray-300 hover:text-white transition-colors cursor-pointer shrink-0"
              title="Manage sources"
            >
              <FileText size={11} className="text-blue-400" />
              <span className="font-medium">{documentsCount} sources</span>
            </button>

            {/* Send / Stop Button (Consistent rounded-full circular wrapper) */}
            {isLoading && !input.trim() ? (
              <button 
                type="button"
                className="rounded-full h-7 w-7 bg-[#eb5757] hover:bg-[#ff6b6b] text-white transition-all shrink-0 cursor-pointer shadow-sm flex items-center justify-center animate-in fade-in duration-150 border-0 outline-none"
                onClick={onStopGeneration}
                title="Stop generating"
              >
                <Square size={10} className="fill-white" />
              </button>
            ) : (
              <button 
                type="button"
                disabled={!input.trim()}
                className={`rounded-full h-7 w-7 transition-all shrink-0 flex items-center justify-center border-0 outline-none ${
                  input.trim() 
                    ? "bg-[#0091ff] text-white hover:bg-[#0080e6] cursor-pointer shadow-sm" 
                    : "bg-white/10 text-gray-500 cursor-not-allowed"
                }`}
                onClick={handleSend}
                title={isLoading ? "Add to queue" : "Send message"}
              >
                <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>
      </div>

      <p className="text-center text-[11px] text-gray-500 mt-2">
        NotbookLM can make mistakes. Verify important info.
      </p>
    </div>
  );
});

export default function ChatArea({ 
  activeChatId, 
  messages, 
  isLoading, 
  onSendMessage, 
  onEditMessage,
  onStopGeneration,
  queuedPrompts = [],
  onRemoveQueuedPrompt,
  onPromoteQueuedPrompt,
  documents, 
  onDocumentAdded, 
  onOpenDocument,
  onEnsureChatSession,
  backendUrl,
  isSidebarOpen = true,
  onOpenSidebar,
  isRightSidebarOpen = true,
  onToggleRightSidebar,
  targetedSource,
  onClearTargetedSource,
  activeStatus
}: ChatAreaProps) {
  const [copiedMessageIdx, setCopiedMessageIdx] = useState<number | null>(null);
  const [editingMessageIdx, setEditingMessageIdx] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const isChatEmpty = messages.length === 0;

  // Auto-scroll to bottom on new message or when loading
  useEffect(() => {
    if (!isChatEmpty) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading, isChatEmpty]);

  const handleSendMessage = useCallback((text: string) => {
    onSendMessage(text);
  }, [onSendMessage]);

  const handleCopy = useCallback((text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedMessageIdx(idx);
    setTimeout(() => setCopiedMessageIdx(null), 1500);
  }, []);

  const handleStartEdit = useCallback((text: string, idx: number) => {
    setEditingMessageIdx(idx);
    setEditContent(text);
  }, []);

  const handleSaveEdit = (idx: number) => {
    if (editContent.trim() && !isLoading) {
      if (onEditMessage) {
        onEditMessage(idx, editContent.trim());
      } else {
        onSendMessage(editContent.trim());
      }
      setEditingMessageIdx(null);
      setEditContent("");
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#212121] overflow-hidden relative">
      
      {/* Top Floating Reopen Left Sidebar Button */}
      {!isSidebarOpen && onOpenSidebar && (
        <div className="absolute top-3.5 left-3.5 z-20">
          <button 
            type="button"
            onClick={onOpenSidebar}
            className="h-8 w-8 text-gray-400 hover:text-white bg-[#282828] hover:bg-[#333333] border border-white/10 rounded-lg shadow-md cursor-pointer flex items-center justify-center transition-colors"
            title="Open sidebar"
          >
            <Sparkles size={16} />
          </button>
        </div>
      )}

      {/* Top Floating Toggle Sources Button */}
      {!isRightSidebarOpen && onToggleRightSidebar && (
        <div className="absolute top-3.5 right-3.5 z-20">
          <button 
            type="button"
            onClick={onToggleRightSidebar}
            className="h-8 px-2.5 rounded-lg bg-[#28292c]/90 hover:bg-[#333] border border-white/10 text-xs text-gray-300 hover:text-white flex items-center gap-1.5 cursor-pointer shadow-md backdrop-blur transition-colors"
            title="Open sources"
          >
            <FileText size={13} className="text-blue-400" />
            <span>Sources</span>
            {documents.length > 0 && (
              <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-blue-600/30 text-blue-300 text-[10px] font-mono">
                {documents.length}
              </span>
            )}
          </button>
        </div>
      )}

      {/* Scrollable Container */}
      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 sm:px-6 pt-10 sm:pt-12 pb-6 w-full min-h-0 scroll-smooth"
      >
        <div className="max-w-3xl mx-auto space-y-6">
          {isChatEmpty ? (
            /* Centered Hero View for New Chat */
            <div className="flex flex-col items-center justify-center min-h-[75vh] text-center px-4 w-full max-w-2xl mx-auto">
              <div className="p-3.5 rounded-full bg-white/5 border border-white/10 mb-4 shadow-sm">
                <Sparkles size={28} className="text-white" />
              </div>
              <h2 className="text-3xl font-bold tracking-tight text-white mb-6">NotbookLM</h2>

              {/* Centered Input Box */}
              <ChatInputBox 
                isCentered={true}
                isLoading={isLoading}
                documentsCount={documents.length}
                onToggleRightSidebar={onToggleRightSidebar}
                onSubmit={handleSendMessage}
                onStopGeneration={onStopGeneration}
                queuedPrompts={queuedPrompts}
                onRemoveQueuedPrompt={onRemoveQueuedPrompt}
                onPromoteQueuedPrompt={onPromoteQueuedPrompt}
                backendUrl={backendUrl}
                targetedSource={targetedSource}
                onClearTargetedSource={onClearTargetedSource}
              />
            </div>
          ) : (
            /* Message History */
            <>
              {messages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`flex flex-col ${msg.role === 'user' ? (editingMessageIdx === idx ? 'w-full items-stretch' : 'items-end') : 'items-start'}`}
                >
                  {msg.role === 'user' ? (
                    editingMessageIdx === idx ? (
                      /* Full Width Edit Box (Matching normal input box width) */
                      <div className="w-full bg-[#2f2f2f] rounded-2xl sm:rounded-3xl p-3 sm:p-4 border border-white/20 space-y-2.5 shadow-xl animate-in fade-in duration-150">
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          className="w-full bg-transparent border-0 focus:outline-none resize-none text-[16px] text-white leading-relaxed min-h-[60px] custom-scrollbar"
                          autoFocus
                          style={{ wordBreak: "break-word", overflowWrap: "break-word", whiteSpace: "pre-wrap" }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                              e.preventDefault();
                              handleSaveEdit(idx);
                            }
                          }}
                        />
                        <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/10">
                          <button
                            type="button"
                            onClick={() => setEditingMessageIdx(null)}
                            className="h-7 px-3 text-xs text-gray-300 hover:text-white hover:bg-white/10 rounded-lg cursor-pointer transition-colors"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => handleSaveEdit(idx)}
                            disabled={!editContent.trim() || isLoading}
                            className="h-7 px-3.5 text-xs bg-white text-black hover:bg-gray-200 font-medium rounded-lg cursor-pointer shadow transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Send
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-end max-w-[85%] sm:max-w-[80%] space-y-1">
                        {(() => {
                          const matchFocus = msg.content.match(/^\[(?:Focused Document|Fokus Dokumen|Fokus Sumber):\s*"(.*?)"\]\n?/i);
                          const focusTitle = matchFocus ? matchFocus[1] : null;
                          const cleanText = matchFocus ? msg.content.replace(matchFocus[0], "").trim() : msg.content;

                          return (
                            <div className="bg-[#2f2f2f] text-white rounded-2xl px-4 py-2.5 shadow-sm space-y-1.5">
                              {focusTitle && (
                                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-blue-950/80 border border-blue-800/90 text-[11px] text-blue-300 font-medium">
                                  <FileText size={11} className="text-blue-400" />
                                  <span className="truncate max-w-[260px] sm:max-w-[380px]">Focus: {focusTitle}</span>
                                </div>
                              )}
                              <p className="whitespace-pre-wrap leading-relaxed text-[15px] sm:text-[16px] break-words">{cleanText}</p>
                            </div>
                          );
                        })()}

                        {/* User Action Buttons (Align Right flush with bubble edge) */}
                        <div className="flex items-center gap-1 text-gray-400 self-end pr-0 pt-0.5">
                          <button
                            onClick={() => handleCopy(msg.content, idx)}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer flex items-center gap-1"
                            title={copiedMessageIdx === idx ? "Copied!" : "Copy text"}
                          >
                            {copiedMessageIdx === idx ? (
                              <Check size={16} className="text-green-400" />
                            ) : (
                              <Copy size={16} />
                            )}
                          </button>
                          <button
                            onClick={() => handleStartEdit(msg.content, idx)}
                            className="p-1.5 -mr-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                            title="Edit message"
                          >
                            <Pencil size={16} />
                          </button>
                        </div>
                      </div>
                    )
                  ) : (
                    /* AI Message */
                    <div className="flex flex-col items-start max-w-full space-y-1">
                      <div className="text-gray-100 w-full">
                        <InChatMessageComponent 
                          msg={msg}
                          activeChatId={activeChatId}
                          backendUrl={backendUrl}
                          documents={documents}
                          onDocumentAdded={onDocumentAdded}
                          onOpenDocument={onOpenDocument}
                          onEnsureChatSession={onEnsureChatSession}
                        />
                      </div>

                      {/* AI Action Buttons (Align Left flush with text) */}
                      <div className="flex items-center gap-1 text-gray-400 pl-0 pt-1">
                        <button
                          onClick={() => handleCopy(msg.content.replace(/<!-- SOURCES_DATA:[\s\S]*?-->/, "").trim(), idx)}
                          className="p-1.5 -ml-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer flex items-center gap-1.5 text-xs"
                          title={copiedMessageIdx === idx ? "Copied!" : "Copy response"}
                        >
                          {copiedMessageIdx === idx ? (
                            <>
                              <Check size={16} className="text-green-400" />
                              <span className="text-xs text-green-400 font-medium">Copied</span>
                            </>
                          ) : (
                            <Copy size={16} />
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start animate-in fade-in duration-200">
                  <div className="bg-[#242528]/90 border border-blue-500/20 text-gray-200 px-4 py-2.5 rounded-2xl flex items-center gap-3 shadow-md backdrop-blur-sm">
                    <div className="relative flex items-center justify-center">
                      <Sparkles size={14} className="text-blue-400 animate-spin" style={{ animationDuration: '3s' }} />
                    </div>
                    <span className="text-xs font-medium text-blue-200/90 transition-all duration-300">
                      {activeStatus || "Analyzing query & reasoning..."}
                    </span>
                  </div>
                </div>
              )}
            </>
          )}
          
          <div ref={messagesEndRef} className="h-4" />
        </div>
      </div>

      {/* Fixed Bottom Input Area (Only rendered when there are active messages in conversation) */}
      {!isChatEmpty && (
        <div className="w-full shrink-0 px-4 pb-4 pt-1 bg-[#212121]">
          <ChatInputBox 
            isCentered={false}
            isLoading={isLoading}
            documentsCount={documents.length}
            onToggleRightSidebar={onToggleRightSidebar}
            onSubmit={handleSendMessage}
            onStopGeneration={onStopGeneration}
            queuedPrompts={queuedPrompts}
            onRemoveQueuedPrompt={onRemoveQueuedPrompt}
            onPromoteQueuedPrompt={onPromoteQueuedPrompt}
            backendUrl={backendUrl}
            targetedSource={targetedSource}
            onClearTargetedSource={onClearTargetedSource}
          />
        </div>
      )}
    </div>
  );
}
