"use client";

import React, { useState, useRef, useEffect, useLayoutEffect, useCallback, useMemo } from "react";
import { 
  Sparkles, 
  Sidebar,
  FileText, 
  Check, 
  Loader2, 
  Copy, 
  Pencil, 
  MoreHorizontal, 
  Pin, 
  PinOff, 
  Trash2, 
  RotateCw, 
  ChevronLeft, 
  ChevronRight, 
  ChevronDown
} from "lucide-react";
import { Portal } from "@/components/ui/Portal";
import { Button } from "@/components/ui/button";
import { ChatMessage, useChatStore } from "@/stores/chatStore";
import { Document as DocType, TargetedSource, useDocumentStore } from "@/stores/documentStore";
import { InChatMessageComponent } from "./chat/ChatMessageItem";
import { UserMessageBubble } from "./chat/UserMessageBubble";
import { ChatInputBox, Attachment } from "./chat/ChatInput";
import { CitationContext } from "./chat/CitationParser";
import { useTranslation } from "@/lib/i18n";
import { Tooltip } from "@/components/ui/tooltip";

interface ChatAreaProps {
  activeChatId: string | null;
  messages?: ChatMessage[];
  isLoading?: boolean;
  onSendMessage: (message: string, attachments?: Attachment[]) => void;
  onEditMessage?: (messageIndex: number, newContent: string) => void;
  onStopGeneration?: () => void;
  queuedPrompts?: string[];
  onRemoveQueuedPrompt?: (index: number) => void;
  onPromoteQueuedPrompt?: (index: number) => void;
  documents?: DocType[];
  onDocumentAdded?: (doc: DocType, targetChatId?: string) => void;
  onAddPendingSources?: (items: { id: string; filename: string; type: "file" | "doi"; status: "uploading" }[]) => void;
  onResolvePendingSource?: (pendingId: string) => void;
  onOpenDocument?: (doc: DocType, citationContext?: CitationContext) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  backendUrl: string;
  isSidebarOpen?: boolean;
  onOpenSidebar?: () => void;
  isRightSidebarOpen?: boolean;
  onToggleRightSidebar?: () => void;
  targetedSource?: TargetedSource | null;
  onClearTargetedSource?: () => void;
  activeStatus?: string | null;
  activeCitationKey?: string | null;
  onRenameChat?: (id: string, newTitle: string) => void;
  onDeleteChat?: (id: string) => void;
  onTogglePinChat?: (id: string) => void;
  isPinned?: boolean;
  chatTitle?: string;
  onRegenerateMessage?: (messageIndex: number) => void;
  onSelectVariant?: (messageIndex: number, variantIndex: number) => void;
  onOpenStorage?: () => void;
}

function isInsideInnerScrollContainer(
  target: EventTarget | null,
  rootContainer: HTMLElement | null
): boolean {
  if (!target || !rootContainer || !(target instanceof Element) || typeof window === "undefined") {
    return false;
  }
  let curr: Element | null = target;
  while (curr && curr !== rootContainer) {
    if (curr instanceof HTMLElement && curr.scrollHeight > curr.clientHeight) {
      const style = window.getComputedStyle(curr);
      const overflowY = style.overflowY;
      if (overflowY === "auto" || overflowY === "scroll") {
        return true;
      }
    }
    curr = curr.parentElement;
  }
  return false;
}

export default function ChatArea({ 
  activeChatId, 
  messages: propMessages, 
  isLoading: propIsLoading, 
  onSendMessage, 
  onEditMessage,
  onStopGeneration,
  queuedPrompts: propQueuedPrompts,
  onRemoveQueuedPrompt,
  onPromoteQueuedPrompt,
  documents: propDocuments, 
  onDocumentAdded, 
  onAddPendingSources,
  onResolvePendingSource,
  onOpenDocument, 
  onEnsureChatSession,
  backendUrl,
  isSidebarOpen = true,
  onOpenSidebar,
  isRightSidebarOpen = true,
  onToggleRightSidebar,
  targetedSource: propTargetedSource,
  onClearTargetedSource,
  activeStatus: propActiveStatus,
  activeCitationKey,
  onRenameChat,
  onDeleteChat,
  onTogglePinChat,
  isPinned = false,
  chatTitle = "",
  onRegenerateMessage,
  onSelectVariant,
  onOpenStorage
}: ChatAreaProps) {
  const { t } = useTranslation();
  
  // Zustand Store Selectors (Eliminate Prop Drilling)
  const storeMessages = useChatStore((s) => s.messages);
  const storeIsLoading = useChatStore((s) => s.isLoading);
  const storeActiveStatus = useChatStore((s) => s.activeStatus);
  const storeQueuedPrompts = useChatStore((s) => s.queuedPrompts);
  const storeDocuments = useDocumentStore((s) => s.documents);
  const storeTargetedSource = useDocumentStore((s) => s.targetedSource);

  const messages = propMessages ?? storeMessages;
  const isLoading = propIsLoading ?? storeIsLoading;
  const activeStatus = propActiveStatus ?? storeActiveStatus;
  const queuedPrompts = propQueuedPrompts ?? storeQueuedPrompts;
  const documents = propDocuments ?? storeDocuments;
  const targetedSource = propTargetedSource ?? storeTargetedSource;

  const [copiedMessageIdx, setCopiedMessageIdx] = useState<number | null>(null);
  const [editingMessageIdx, setEditingMessageIdx] = useState<number | null>(null);
  const [regeneratingMessageIdx, setRegeneratingMessageIdx] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");
  const [isTopMenuOpen, setIsTopMenuOpen] = useState(false);
  const [isRenameOpen, setIsRenameOpen] = useState(false);
  const [renameTitleInput, setRenameTitleInput] = useState("");
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  // Clear regenerating indicator once global loading stops
  useEffect(() => {
    if (!isLoading) {
      setRegeneratingMessageIdx(null);
    }
  }, [isLoading]);

  const topMenuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const inputWrapperRef = useRef<HTMLDivElement>(null);
  const isAtBottomRef = useRef<boolean>(true);
  const isAutoScrollingRef = useRef<boolean>(false);
  const autoScrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [showScrollBottom, setShowScrollBottom] = useState<boolean>(false);
  const [inputHeight, setInputHeight] = useState<number>(144);

  const isChatEmpty = messages.length === 0;

  // Clean up programmatic scroll timer on unmount
  useEffect(() => {
    return () => {
      if (autoScrollTimeoutRef.current) {
        clearTimeout(autoScrollTimeoutRef.current);
      }
    };
  }, []);

  // Dynamically observe input bar height changes (e.g. multi-row prompt expansions, attachments, or collapses)
  // Ensures messages are NEVER obscured by the floating input bar at the bottom, just like ChatGPT/Claude.
  useEffect(() => {
    const el = inputWrapperRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const h = entry.borderBoxSize?.[0]?.blockSize ?? entry.target.getBoundingClientRect().height;
        if (h > 0) {
          setInputHeight((prevH) => {
            const newH = Math.round(h);
            if (newH !== prevH) {
              const diff = newH - prevH;
              const container = scrollContainerRef.current;
              if (container && isAtBottomRef.current && !isAutoScrollingRef.current && diff > 0) {
                requestAnimationFrame(() => {
                  if (container && isAtBottomRef.current && !isAutoScrollingRef.current) {
                    container.scrollTop += diff;
                  }
                });
              }
              return newH;
            }
            return prevH;
          });
        }
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, [isChatEmpty]);

  // Once the assistant has started generating tokens, hide the bottom thinking text
  const isGeneratingContent = useMemo(() => {
    if (!isLoading || messages.length === 0) return false;
    const lastMsg = messages[messages.length - 1];
    return lastMsg.role === "assistant" && Boolean(lastMsg.content?.trim());
  }, [isLoading, messages]);

  // Immediate wheel interception (Crucial for Mac trackpads & mouse wheels):
  // As soon as the user gestures UP on the main canvas, immediately release scroll lock
  // BEFORE the fast streaming token updates can yank the user back down!
  const handleWheel = useCallback((e: React.WheelEvent) => {
    // Ignore wheel interactions on nested scrollable elements (e.g. report sources list, markdown tables, code blocks)
    if (isInsideInnerScrollContainer(e.target, scrollContainerRef.current)) {
      return;
    }
    isAutoScrollingRef.current = false;
    if (autoScrollTimeoutRef.current) clearTimeout(autoScrollTimeoutRef.current);
    if (e.deltaY < 0) {
      // User is scrolling up on the main canvas
      isAtBottomRef.current = false;
      const container = scrollContainerRef.current;
      if (container) {
        const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        if (distanceFromBottom > 30) {
          setShowScrollBottom(!isChatEmpty);
        }
      }
    } else if (e.deltaY > 0) {
      // User is scrolling down
      const container = scrollContainerRef.current;
      if (container) {
        const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        if (distanceFromBottom <= 30) {
          isAtBottomRef.current = true;
          setShowScrollBottom(false);
        }
      }
    }
  }, [isChatEmpty]);

  // Track touch gestures on mobile/tablets
  const touchStartYRef = useRef<number | null>(null);
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (isInsideInnerScrollContainer(e.target, scrollContainerRef.current)) return;
    isAutoScrollingRef.current = false;
    if (autoScrollTimeoutRef.current) clearTimeout(autoScrollTimeoutRef.current);
    touchStartYRef.current = e.touches[0].clientY;
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (touchStartYRef.current === null) return;
    if (isInsideInnerScrollContainer(e.target, scrollContainerRef.current)) return;
    const currentY = e.touches[0].clientY;
    const deltaY = touchStartYRef.current - currentY;
    if (deltaY < 0) {
      // Swiping down to scroll content up on the main canvas
      isAtBottomRef.current = false;
      const container = scrollContainerRef.current;
      if (container) {
        const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        if (distanceFromBottom > 30) {
          setShowScrollBottom(!isChatEmpty);
        }
      }
    }
  }, [isChatEmpty]);

  // General scroll handler for scrollbar dragging, momentum finish, and keyboard nav
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    // Only respond to scroll events directly originating on the main canvas container itself
    if (e.target !== e.currentTarget) return;

    const container = scrollContainerRef.current;
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;

    // During programmatic smooth scrolling to bottom, suppress button re-appearance
    if (isAutoScrollingRef.current) {
      if (distanceFromBottom <= 30) {
        isAutoScrollingRef.current = false;
        isAtBottomRef.current = true;
        setShowScrollBottom(false);
      }
      return;
    }

    if (distanceFromBottom > 30) {
      isAtBottomRef.current = false;
      setShowScrollBottom(!isChatEmpty);
    } else {
      isAtBottomRef.current = true;
      setShowScrollBottom(false);
    }
  }, [isChatEmpty]);

  const scrollToBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    isAutoScrollingRef.current = true;
    setShowScrollBottom(false);

    if (autoScrollTimeoutRef.current) {
      clearTimeout(autoScrollTimeoutRef.current);
    }
    // Safety release after smooth scrolling finishes
    autoScrollTimeoutRef.current = setTimeout(() => {
      isAutoScrollingRef.current = false;
      if (scrollContainerRef.current) {
        const c = scrollContainerRef.current;
        isAtBottomRef.current = (c.scrollHeight - c.scrollTop - c.clientHeight) <= 30;
      }
    }, 800);

    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth"
    });
  }, []);

  // Close top menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (topMenuRef.current && !topMenuRef.current.contains(e.target as Node)) {
        setIsTopMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Focus rename input
  useEffect(() => {
    if (isRenameOpen) {
      setRenameTitleInput(chatTitle || "");
      setTimeout(() => {
        renameInputRef.current?.focus();
        renameInputRef.current?.select();
      }, 50);
    }
  }, [isRenameOpen, chatTitle]);

  const handleSaveRename = (e: React.FormEvent) => {
    e.preventDefault();
    if (onRenameChat && activeChatId && renameTitleInput.trim()) {
      onRenameChat(activeChatId, renameTitleInput.trim());
      setIsRenameOpen(false);
      setRenameTitleInput("");
    }
  };

  const handleCancelRename = () => {
    setIsRenameOpen(false);
    setRenameTitleInput("");
  };

  const handleConfirmDelete = () => {
    if (onDeleteChat && activeChatId) {
      onDeleteChat(activeChatId);
    }
    setIsDeleteConfirmOpen(false);
  };

  // Reset scroll to bottom on chat switch
  useEffect(() => {
    isAtBottomRef.current = true;
    setShowScrollBottom(false);
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [activeChatId]);

  // Smart auto-scroll: only follow stream if the user has NOT intentionally scrolled up
  useLayoutEffect(() => {
    if (!isChatEmpty && scrollContainerRef.current) {
      if (isAtBottomRef.current) {
        scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
      }
    }
  }, [messages, isLoading, isChatEmpty]);

  const handleSendMessage = useCallback((text: string, attachments?: Attachment[]) => {
    isAtBottomRef.current = true;
    setShowScrollBottom(false);
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
    onSendMessage(text, attachments);
  }, [onSendMessage]);

  const handleCopy = useCallback((text: string, idx: number) => {
    // Convert bracket or parenthesis citations into clean academic brackets e.g. [2], [13]
    const cleanText = text
      .replace(/<!-- SOURCES_DATA:[\s\S]*?-->/g, "")
      .replace(/<!-- SOURCES_ACTION:[\s\S]*?-->/g, "")
      .trim();
    navigator.clipboard.writeText(cleanText);
    setCopiedMessageIdx(idx);
    setTimeout(() => setCopiedMessageIdx(null), 2000);
  }, []);

  const handleStartEdit = useCallback((text: string, idx: number) => {
    // If AI is currently thinking or generating, immediately interrupt/abort
    if (isLoading && onStopGeneration) {
      onStopGeneration();
    }
    setEditingMessageIdx(idx);
    setEditContent(text);
  }, [isLoading, onStopGeneration]);

  const handleSaveEdit = (idx: number) => {
    if (editContent.trim()) {
      if (isLoading && onStopGeneration) {
        onStopGeneration();
      }
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
    <div className="flex-1 flex flex-col h-full bg-app-bg text-app-text overflow-hidden relative">
      {/* 1. Top Fixed Pane Header (NotebookLM Split-Pane Architecture) */}
      <div className="w-full h-[52px] px-4 flex items-center justify-between border-b border-app-border bg-app-sidebar shrink-0 z-20 select-none">
        {/* Left: Open Sidebar Button + "Chat" Title */}
        <div className="flex items-center gap-2.5">
          {!isSidebarOpen && onOpenSidebar && (
            <Tooltip content={t('chat.openSidebar')} side="bottom">
              <button 
                type="button"
                onClick={onOpenSidebar}
                className="w-7 h-7 text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg cursor-pointer flex items-center justify-center transition-colors hidden lg:flex"
                aria-label={t('chat.openSidebar')}
              >
                <Sidebar size={15} />
              </button>
            </Tooltip>
          )}
          <span className="font-semibold text-sm text-app-text tracking-tight">
            {t('nav.chat') || "Chat"}
          </span>
        </div>

        {/* Right: Context Menu & Sources Controls */}
        <div className="flex items-center gap-1.5">
          {/* Three Dots Context Menu (When activeChatId exists) */}
          {activeChatId && (
            <div className="relative" ref={topMenuRef}>
              <Tooltip content={t('left.options')} side="bottom">
                <button
                  type="button"
                  onClick={() => setIsTopMenuOpen(prev => !prev)}
                  className={`w-7 h-7 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover flex items-center justify-center cursor-pointer transition-colors ${
                    isTopMenuOpen ? "bg-app-item-hover text-app-text" : ""
                  }`}
                  aria-label={t('left.options')}
                >
                  <MoreHorizontal size={15} />
                </button>
              </Tooltip>

              {/* Dropdown Menu */}
              {isTopMenuOpen && (
                <div 
                  className="absolute right-0 top-9 z-50 w-44 rounded-xl bg-app-dropdown border border-app-border-strong shadow-2xl p-1 text-xs text-app-text animate-in fade-in zoom-in-95 duration-100 space-y-0.5"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Rename */}
                  <button
                    onClick={() => {
                      setIsTopMenuOpen(false);
                      setRenameTitleInput(chatTitle || "");
                      setIsRenameOpen(true);
                    }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-app-item-hover hover:text-app-text transition-colors cursor-pointer"
                  >
                    <Pencil size={13} className="text-app-text-dim" />
                    <span>{t('action.rename')}</span>
                  </button>

                  {/* Pin / Unpin */}
                  <button
                    onClick={() => {
                      setIsTopMenuOpen(false);
                      if (onTogglePinChat && activeChatId) {
                        onTogglePinChat(activeChatId);
                      }
                    }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-app-item-hover hover:text-app-text transition-colors cursor-pointer"
                  >
                    {isPinned ? (
                      <>
                        <PinOff size={13} className="text-amber-500" />
                        <span>{t('action.unpin')}</span>
                      </>
                    ) : (
                      <>
                        <Pin size={13} className="text-app-text-dim" />
                        <span>{t('action.pin')}</span>
                      </>
                    )}
                  </button>

                  {/* Delete */}
                  <button
                    onClick={() => {
                      setIsTopMenuOpen(false);
                      setIsDeleteConfirmOpen(true);
                    }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-red-500 hover:bg-red-500/10 hover:text-red-600 transition-colors cursor-pointer"
                  >
                    <Trash2 size={13} />
                    <span>{t('action.deleteChat')}</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Open Sources Toggle (when right sidebar is closed) */}
          {!isRightSidebarOpen && onToggleRightSidebar && (
            <Tooltip content={t('chat.openSources') || "Open sources"} side="bottom">
              <button 
                type="button"
                onClick={onToggleRightSidebar}
                className="relative h-7 px-2 rounded-lg hover:bg-app-item-hover text-app-text-muted hover:text-app-text flex items-center gap-1.5 cursor-pointer transition-colors text-xs font-medium"
                aria-label={t('chat.openSources') || "Open sources"}
              >
                <FileText size={14} className="text-blue-500" />
                <span className="hidden sm:inline text-xs">{t('ui.sources') || "Sources"}</span>
                {documents.length > 0 && (
                  <span className="px-1 min-w-4 h-4 rounded-full bg-blue-600 text-white text-[9px] font-mono flex items-center justify-center leading-none">
                    {documents.length}
                  </span>
                )}
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      <div 
        ref={scrollContainerRef}
        onScroll={handleScroll}
        onWheel={handleWheel}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        className={`flex-1 overflow-y-auto w-full min-h-0 custom-scrollbar overflow-x-hidden ${
          isChatEmpty ? "flex items-center justify-center py-4" : "py-6"
        }`}
        style={!isChatEmpty ? { paddingBottom: `${Math.max(120, inputHeight + 16)}px` } : undefined}
      >
        <div className="w-full px-4 space-y-6">
          {isChatEmpty ? (
            <div className="flex flex-col items-center justify-center py-6 text-center w-full">
              <div className="p-3.5 rounded-full bg-app-surface border border-app-border mb-4 shadow-sm">
                <Sparkles size={28} className="text-blue-500" />
              </div>
              <h2 className="text-3xl font-bold tracking-tight text-app-text mb-6">NotbookLM</h2>

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
                chatId={activeChatId}
                onEnsureChatSession={onEnsureChatSession}
                targetedSource={targetedSource}
                onClearTargetedSource={onClearTargetedSource}
                onOpenStorage={onOpenStorage}
              />
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, idx) => (
                <div key={idx} className="space-y-2 group">
                  {msg.role === "user" ? (
                    <div className="flex flex-col items-end">
                      <div className="flex flex-col items-end w-full max-w-[85%]">
                        {/* Always display attachments above, even during edit */}
                        {msg.attachments && msg.attachments.length > 0 && (
                          <div className="flex flex-wrap justify-end gap-2 mb-2">
                            {msg.attachments.map((att, attIdx) => {
                              const fileHref = att.url?.startsWith("http") ? att.url : `${backendUrl}${att.url || ""}`;
                              const isWord = att.filename.endsWith(".docx") || att.filename.endsWith(".doc");
                              const isPdf = att.filename.endsWith(".pdf");
                              return (
                                <a
                                  key={attIdx}
                                  href={fileHref}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex flex-col p-3 rounded-2xl bg-app-card border border-app-border hover:border-app-border-strong transition-all text-left w-36 shadow-md group/att"
                                >
                                  <div className="flex items-center justify-between mb-2">
                                    {att.type === "image" ? (
                                      <div className="w-8 h-8 rounded-lg overflow-hidden bg-black/10 dark:bg-black/40">
                                        {/* eslint-disable-next-line @next/next/no-img-element */}
                                        <img src={fileHref} alt={att.filename} className="w-full h-full object-cover" />
                                      </div>
                                    ) : isWord ? (
                                      <div className="w-7 h-7 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-500 font-bold text-[11px]">
                                        W
                                      </div>
                                    ) : isPdf ? (
                                      <div className="w-7 h-7 rounded-lg bg-red-600/20 border border-red-500/30 flex items-center justify-center text-red-500 font-bold text-[10px]">
                                        PDF
                                      </div>
                                    ) : (
                                      <div className="w-7 h-7 rounded-lg bg-app-item-hover border border-app-border flex items-center justify-center text-app-text-muted">
                                        <FileText size={15} />
                                      </div>
                                    )}
                                  </div>
                                  <span className="text-xs font-medium text-app-text line-clamp-2 leading-tight">
                                    {att.filename}
                                  </span>
                                </a>
                              );
                            })}
                          </div>
                        )}

                        {editingMessageIdx === idx ? (
                          <div className="w-full max-w-xl bg-app-card p-3 rounded-2xl border border-app-border-strong space-y-2 shadow-xl">
                            <textarea
                              value={editContent}
                              onChange={(e) => setEditContent(e.target.value)}
                              className="w-full bg-app-input-surface text-app-text p-3 rounded-xl border border-app-border focus:outline-none focus:border-blue-500 text-sm resize-none"
                              rows={3}
                              autoFocus
                            />
                            <div className="flex justify-end gap-2">
                              <button
                                type="button"
                                onClick={() => setEditingMessageIdx(null)}
                                className="px-3 py-1.5 text-xs text-app-text-muted hover:text-app-text rounded-lg hover:bg-app-item-hover transition-colors cursor-pointer"
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                onClick={() => handleSaveEdit(idx)}
                                className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors cursor-pointer shadow-sm"
                              >
                                Save &amp; Submit
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            {msg.content?.trim() && (
                              <UserMessageBubble content={msg.content} maxCollapsedHeight={180} />
                            )}
                            <div className="flex items-center gap-1 mt-1 mr-0.5">
                              <Tooltip content={t('chat.editMessage')} side="top">
                                <button
                                  type="button"
                                  onClick={() => handleStartEdit(msg.content || "", idx)}
                                  className="p-1.5 text-app-text-muted hover:text-app-text rounded-lg hover:bg-app-item-hover transition-colors cursor-pointer flex items-center justify-center"
                                  aria-label={t('chat.editMessage')}
                                >
                                  <Pencil size={15} />
                                </button>
                              </Tooltip>
                              {msg.content?.trim() && (
                                <Tooltip content={copiedMessageIdx === idx ? "Copied!" : t('chat.copyPrompt')} side="top">
                                  <button
                                    type="button"
                                    onClick={() => handleCopy(msg.content, idx)}
                                    className="p-1.5 text-app-text-muted hover:text-app-text rounded-lg hover:bg-app-item-hover transition-colors cursor-pointer flex items-center justify-center"
                                    aria-label={t('chat.copyPrompt')}
                                  >
                                    {copiedMessageIdx === idx ? <Check size={15} className="text-emerald-500" /> : <Copy size={15} />}
                                  </button>
                                </Tooltip>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start">
                      <div className="flex-1 min-w-0">
                        {isLoading && regeneratingMessageIdx === idx && !msg.content ? (
                          <div className="flex items-center gap-2.5 text-app-text-muted text-sm py-2 px-1 animate-in fade-in duration-200">
                            <Loader2 size={16} className="text-blue-500 animate-spin shrink-0" />
                            <span>{activeStatus || "Regenerating response..."}</span>
                          </div>
                        ) : msg.content ? (
                          <InChatMessageComponent 
                            key={`assistant-msg-${idx}-v-${msg.active_variant_index ?? 0}`}
                            msg={msg}
                            activeChatId={activeChatId}
                            backendUrl={backendUrl}
                            documents={documents}
                            onDocumentAdded={onDocumentAdded}
                            onAddPendingSources={onAddPendingSources}
                            onResolvePendingSource={onResolvePendingSource}
                            onOpenDocument={onOpenDocument}
                            onEnsureChatSession={onEnsureChatSession}
                            activeCitationKey={activeCitationKey}
                          />
                        ) : null}
                        {!msg.isStreaming && msg.content && (
                          <div className="mt-1 flex items-center gap-1.5 animate-in fade-in duration-200">
                            {/* Pagination for response variants (e.g. 1/2, 2/2) */}
                            {msg.variants && msg.variants.length > 1 && (
                              <div className="flex items-center gap-0.5 text-xs text-gray-400 font-mono select-none bg-white/5 px-2 py-0.5 rounded-lg border border-white/5 mr-1">
                                <Tooltip content={t('chat.previousResponse')} side="top">
                                  <button
                                    type="button"
                                    onClick={() => onSelectVariant?.(idx, (msg.active_variant_index || 0) - 1)}
                                    disabled={(msg.active_variant_index || 0) <= 0 || isLoading}
                                    className="p-0.5 hover:text-app-text disabled:opacity-25 transition-colors cursor-pointer disabled:cursor-not-allowed"
                                    aria-label={t('chat.previousResponse')}
                                  >
                                    <ChevronLeft size={14} />
                                  </button>
                                </Tooltip>
                                <span className="px-1 text-app-text text-xs">
                                  {(msg.active_variant_index || 0) + 1}/{msg.variants.length}
                                </span>
                                <Tooltip content={t('chat.nextResponse')} side="top">
                                  <button
                                    type="button"
                                    onClick={() => onSelectVariant?.(idx, (msg.active_variant_index || 0) + 1)}
                                    disabled={(msg.active_variant_index || 0) >= msg.variants.length - 1 || isLoading}
                                    className="p-0.5 hover:text-app-text disabled:opacity-25 transition-colors cursor-pointer disabled:cursor-not-allowed"
                                    aria-label={t('chat.nextResponse')}
                                  >
                                    <ChevronRight size={14} />
                                  </button>
                                </Tooltip>
                              </div>
                            )}

                            {/* Copy Button */}
                            <Tooltip content={copiedMessageIdx === idx ? "Copied!" : t('chat.copyResponse')} side="top">
                              <button
                                type="button"
                                onClick={() => handleCopy(msg.content.replace(/<!-- SOURCES_DATA:[\s\S]*?-->/g, "").trim(), idx)}
                                className="p-1.5 text-app-text-muted hover:text-app-text rounded-lg hover:bg-app-item-hover transition-colors cursor-pointer flex items-center justify-center"
                                aria-label={t('chat.copyResponse')}
                              >
                                {copiedMessageIdx === idx ? (
                                  <Check size={15} className="text-emerald-500" />
                                ) : (
                                  <Copy size={15} />
                                )}
                              </button>
                            </Tooltip>

                            {/* Retry / Regenerate Button */}
                            <Tooltip content={t('chat.regenerateResponse')} side="top">
                              <button
                                type="button"
                                onClick={() => {
                                  setRegeneratingMessageIdx(idx);
                                  onRegenerateMessage?.(idx);
                                }}
                                disabled={isLoading}
                                className="p-1.5 text-app-text-muted hover:text-app-text disabled:opacity-30 rounded-lg hover:bg-app-item-hover transition-colors cursor-pointer flex items-center justify-center"
                                aria-label={t('chat.regenerateResponse')}
                              >
                                <RotateCw size={15} />
                              </button>
                            </Tooltip>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {isLoading && regeneratingMessageIdx === null && !isGeneratingContent && (
                <div className="flex items-center gap-2.5 text-app-text-muted text-sm py-1.5 animate-in fade-in duration-200">
                  <Loader2 size={16} className="text-blue-500 animate-spin shrink-0" />
                  <span>{activeStatus || "Analyzing and generating response..."}</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Floating Gradient Backdrop for Input (width capped to input box width only, zero side overflow) */}
      {!isChatEmpty && (
        <div className="absolute bottom-0 inset-x-0 pb-3 pt-6 pointer-events-none z-10">
          <div className="w-full px-4 pointer-events-none min-w-0 relative">
            <div className="absolute left-4 right-4 -top-6 -bottom-3 bg-gradient-to-t from-app-bg from-60% via-app-bg to-transparent -z-10 pointer-events-none rounded-t-3xl rounded-b-none" />
            {showScrollBottom && (
              <div className="flex justify-center mb-2 pointer-events-none animate-in fade-in slide-in-from-bottom-2 duration-200">
                <button
                  type="button"
                  onClick={scrollToBottom}
                  className="pointer-events-auto px-3 py-1.5 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text-muted hover:text-app-text text-xs font-medium flex items-center gap-1.5 shadow-md cursor-pointer transition-colors"
                >
                  <ChevronDown size={13} className="text-blue-500" />
                  <span>Scroll to bottom</span>
                </button>
              </div>
            )}
            <div ref={inputWrapperRef} className="pointer-events-auto">
              <ChatInputBox 
                isLoading={isLoading}
                documentsCount={documents.length}
                onToggleRightSidebar={onToggleRightSidebar}
                onSubmit={handleSendMessage}
                onStopGeneration={onStopGeneration}
                queuedPrompts={queuedPrompts}
                onRemoveQueuedPrompt={onRemoveQueuedPrompt}
                onPromoteQueuedPrompt={onPromoteQueuedPrompt}
                backendUrl={backendUrl}
                chatId={activeChatId}
                onEnsureChatSession={onEnsureChatSession}
                targetedSource={targetedSource}
                onClearTargetedSource={onClearTargetedSource}
                onOpenStorage={onOpenStorage}
              />
            </div>
          </div>
        </div>
      )}

      {/* Centered Modal for Rename Chat */}
      {isRenameOpen && activeChatId && (
        <Portal>
          <div 
            onClick={(e) => {
              e.stopPropagation();
              handleCancelRename();
            }}
            className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
          >
            <div 
              onClick={(e) => e.stopPropagation()}
              className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150 text-app-text"
            >
              <div className="space-y-1.5">
                <h3 className="text-base font-semibold text-app-text">{t('left.renameConversation')}</h3>
                <p className="text-xs text-app-text-muted">
                  {t('left.renameDesc')}
                </p>
              </div>

              <form onSubmit={handleSaveRename} className="space-y-4">
                <input
                  ref={renameInputRef}
                  type="text"
                  value={renameTitleInput}
                  onChange={(e) => setRenameTitleInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") handleCancelRename();
                  }}
                  placeholder={t('left.renamePlaceholder')}
                  className="w-full bg-app-input-surface border border-app-border focus:border-blue-500 rounded-xl px-3 py-2 text-xs text-app-text outline-none transition-colors"
                />

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-app-divider">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleCancelRename}
                    className="text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg px-3.5 h-8 cursor-pointer"
                  >
                    {t('action.cancel')}
                  </Button>

                  <Button
                    type="submit"
                    size="sm"
                    disabled={!renameTitleInput.trim()}
                    className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow"
                  >
                    {t('action.save')}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </Portal>
      )}

      {/* Centered Confirmation Modal for Delete Chat */}
      {isDeleteConfirmOpen && activeChatId && (
        <Portal>
          <div 
            onClick={(e) => {
              e.stopPropagation();
              setIsDeleteConfirmOpen(false);
            }}
            className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
          >
            <div 
              onClick={(e) => e.stopPropagation()}
              className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150 text-app-text"
            >
              <div className="space-y-1.5">
                <h3 className="text-base font-semibold text-app-text">{t('ui.deleteConfirmTitle')}</h3>
                <p className="text-xs text-app-text-muted leading-relaxed">
                  {t('ui.deleteConfirmDesc').replace('{title}', chatTitle || "conversation")}
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-app-divider">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsDeleteConfirmOpen(false)}
                  className="text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg px-3.5 h-8 cursor-pointer"
                >
                  {t('action.cancel')}
                </Button>

                <Button
                  size="sm"
                  onClick={handleConfirmDelete}
                  className="text-xs bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow"
                >
                  {t('action.delete')}
                </Button>
              </div>
            </div>
          </div>
        </Portal>
      )}
    </div>
  );
}
