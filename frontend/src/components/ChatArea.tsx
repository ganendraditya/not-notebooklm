"use client";

import { useState, useRef, useEffect, useCallback, useMemo, memo } from "react";
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
import { ChatMessage, Document as DocType } from "@/app/ChatClient";
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
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  backendUrl: string;
  isSidebarOpen?: boolean;
  onOpenSidebar?: () => void;
  isRightSidebarOpen?: boolean;
  onToggleRightSidebar?: () => void;
}

interface InChatMessageProps {
  msg: ChatMessage;
  activeChatId: string | null;
  backendUrl: string;
  onDocumentAdded?: (doc: DocType) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
}

// Memoized In-Chat Message Component with Markdown parsing & Interactive Source Cards
const InChatMessageComponent = memo(function InChatMessageComponent({ 
  msg, 
  activeChatId, 
  backendUrl, 
  onDocumentAdded, 
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

  const [selectedSources, setSelectedSources] = useState<Record<number, boolean>>({});
  const [isImporting, setIsImporting] = useState(false);
  const [isImported, setIsImported] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Initialize all selected by default
  useEffect(() => {
    if (sources.length > 0) {
      const init: Record<number, boolean> = {};
      sources.forEach((_, i) => { init[i] = true; });
      setSelectedSources(init);
    }
  }, [sources.length]);

  const toggleSelectAll = () => {
    const all = sources.every((_, i) => selectedSources[i]);
    const next = !all;
    const updated: Record<number, boolean> = {};
    sources.forEach((_, i) => { updated[i] = next; });
    setSelectedSources(updated);
  };

  const handleImport = async () => {
    const toImport = sources.filter((_, i) => selectedSources[i]);
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
        createdDocs.forEach((d: DocType) => onDocumentAdded?.(d));
        setIsImported(true);
      }
    } catch (e) {
      console.error("Import sources failed:", e);
    } finally {
      setIsImporting(false);
    }
  };

  const selectedCount = sources.filter((_, i) => selectedSources[i]).length;

  return (
    <div className="w-full space-y-3">
      {/* 1. Main Markdown Text Content */}
      <div className="prose prose-invert max-w-none text-[16px] leading-[1.65] space-y-3">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <p className="mb-2.5 last:mb-0 text-gray-100 leading-[1.65]">{children}</p>,
            h1: ({ children }) => <h1 className="text-2xl font-bold text-white mt-5 mb-2.5 tracking-tight">{children}</h1>,
            h2: ({ children }) => <h2 className="text-xl font-bold text-white mt-4 mb-2 tracking-tight">{children}</h2>,
            h3: ({ children }) => <h3 className="text-lg font-semibold text-white mt-3 mb-1.5">{children}</h3>,
            ul: ({ children }) => <ul className="list-disc pl-5 my-2.5 space-y-1.5 text-gray-100">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal pl-5 my-2.5 space-y-1.5 text-gray-100">{children}</ol>,
            li: ({ children }) => <li className="leading-[1.65]">{children}</li>,
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
            code: ({ className, children, ...props }) => {
              const isInline = !className?.includes("language-");
              return isInline ? (
                <code className="bg-white/10 text-blue-300 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
                  {children}
                </code>
              ) : (
                <pre className="bg-[#1e1e1e] p-3.5 rounded-xl overflow-x-auto text-sm my-3 border border-white/10 font-mono">
                  <code className={className} {...props}>{children}</code>
                </pre>
              );
            },
            table: ({ children }) => (
              <div className="overflow-x-auto my-4 rounded-xl border border-white/10 bg-[#1e1e1e]/60 shadow-md">
                <table className="w-full text-left text-sm border-collapse">{children}</table>
              </div>
            ),
            th: ({ children }) => (
              <th className="bg-white/5 border-b border-white/10 px-4 py-2.5 font-semibold text-white text-xs uppercase tracking-wider">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border-b border-white/5 px-4 py-2.5 text-gray-200 text-sm leading-normal">
                {children}
              </td>
            ),
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-blue-500/80 bg-blue-500/10 pl-4 py-2 my-2.5 rounded-r-lg italic text-gray-200">
                {children}
              </blockquote>
            ),
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
                <button 
                  onClick={(e) => { e.stopPropagation(); toggleSelectAll(); }}
                  className="hover:text-white font-medium cursor-pointer transition-colors text-blue-400"
                >
                  {sources.every((_, i) => selectedSources[i]) ? "Deselect All" : "Select All"}
                </button>
              </div>

              {/* Scrollable Paper Cards List */}
              <div className="max-h-[360px] overflow-y-auto divide-y divide-white/5 p-1 custom-scrollbar">
                {sources.map((src, i) => {
                  const isChecked = !!selectedSources[i];
                  return (
                    <div 
                      key={i} 
                      onClick={() => {
                        setSelectedSources(prev => ({ ...prev, [i]: !prev[i] }));
                      }}
                      className={`p-3 px-3.5 flex items-start justify-between gap-3 hover:bg-white/5 transition-colors cursor-pointer rounded-xl m-1 ${
                        isChecked ? "bg-white/[0.03]" : ""
                      }`}
                    >
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 shrink-0 mt-0.5">
                          <BookOpen size={16} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline gap-2">
                            <h4 className="text-xs font-semibold text-white leading-snug line-clamp-2">
                              {src.title}
                            </h4>
                            {src.year && src.year !== "N/A" && (
                              <span className="text-[11px] text-gray-400 shrink-0">
                                ({src.year})
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

                      <div className={`w-3.5 h-3.5 rounded border mt-1 flex items-center justify-center shrink-0 transition-colors ${
                        isChecked ? "bg-blue-600 border-blue-600 text-white" : "border-gray-500 bg-transparent"
                      }`}>
                        {isChecked && <Check size={10} strokeWidth={3} />}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Sticky Bottom Actions Bar */}
              <div className="p-3 px-4 bg-[#18191a] border-t border-white/5 flex items-center justify-between">
                <span className="text-xs text-gray-400 font-medium">
                  {selectedCount}/{sources.length} selected
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
  backendUrl
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
    onSubmit(query);
    setInput("");
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
        {/* Top Textarea */}
        <textarea 
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
          placeholder={isLoading ? "Type your next message (automatically queued)..." : "Ask NotbookLM anything"}
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
  onEnsureChatSession,
  backendUrl,
  isSidebarOpen = true,
  onOpenSidebar,
  isRightSidebarOpen = true,
  onToggleRightSidebar
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
                        <div className="bg-[#2f2f2f] text-white rounded-2xl px-4 py-2.5 shadow-sm">
                          <p className="whitespace-pre-wrap leading-relaxed text-[16px] break-words">{msg.content}</p>
                        </div>

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
                          onDocumentAdded={onDocumentAdded}
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
                <div className="flex justify-start">
                  <div className="bg-transparent text-gray-400 px-5 py-3 flex items-center gap-3">
                    <div className="flex space-x-1.5">
                      <div className="w-2.5 h-2.5 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                      <div className="w-2.5 h-2.5 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                      <div className="w-2.5 h-2.5 bg-blue-400 rounded-full animate-bounce"></div>
                    </div>
                    <span className="text-xs font-medium text-gray-400 animate-pulse">Searching sources & generating response...</span>
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
          />
        </div>
      )}
    </div>
  );
}
