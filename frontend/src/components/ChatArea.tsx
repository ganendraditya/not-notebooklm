"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { 
  Sparkles, 
  FileText, 
  Check, 
  Loader2, 
  Copy, 
  Pencil, 
  Clock,
  MoreHorizontal,
  Pin,
  PinOff,
  Trash2,
  X,
  RotateCw,
  ChevronLeft,
  ChevronRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/stores/chatStore";
import { Document as DocType, TargetedSource } from "@/stores/documentStore";
import { InChatMessageComponent } from "./chat/ChatMessageItem";
import { ChatInputBox, Attachment } from "./chat/ChatInput";
import { CitationContext } from "./chat/CitationParser";
import { useTranslation } from "@/lib/i18n";

interface ChatAreaProps {
  activeChatId: string | null;
  messages: ChatMessage[];
  isLoading?: boolean;
  onSendMessage: (message: string, attachments?: Attachment[]) => void;
  onEditMessage?: (messageIndex: number, newContent: string) => void;
  onStopGeneration?: () => void;
  queuedPrompts?: string[];
  onRemoveQueuedPrompt?: (index: number) => void;
  onPromoteQueuedPrompt?: (index: number) => void;
  documents: DocType[];
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
  onAddPendingSources,
  onResolvePendingSource,
  onOpenDocument, 
  onEnsureChatSession,
  backendUrl,
  isSidebarOpen = true,
  onOpenSidebar,
  isRightSidebarOpen = true,
  onToggleRightSidebar,
  targetedSource,
  onClearTargetedSource,
  activeStatus,
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
  const [copiedMessageIdx, setCopiedMessageIdx] = useState<number | null>(null);
  const [editingMessageIdx, setEditingMessageIdx] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");
  const [isTopMenuOpen, setIsTopMenuOpen] = useState(false);
  const [isRenameOpen, setIsRenameOpen] = useState(false);
  const [renameInput, setRenameInput] = useState("");
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  const topMenuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const isChatEmpty = messages.length === 0;

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
      setTimeout(() => {
        renameInputRef.current?.focus();
        renameInputRef.current?.select();
      }, 50);
    }
  }, [isRenameOpen]);

  useEffect(() => {
    if (!isChatEmpty) {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
      }
    }
  }, [messages, isLoading, isChatEmpty]);

  const handleSendMessage = useCallback((text: string, attachments?: Attachment[]) => {
    onSendMessage(text, attachments);
  }, [onSendMessage]);

  const handleCopy = useCallback((text: string, idx: number) => {
    // Convert bracket or parenthesis citations into clean academic brackets e.g. [2], [13]
    let cleanText = text
      .replace(/<!-- SOURCES_DATA:[\s\S]*?-->/g, "")
      .replace(/<!-- SOURCES_ACTION:[\s\S]*?-->/g, "")
      .trim();
    navigator.clipboard.writeText(cleanText);
    setCopiedMessageIdx(idx);
    setTimeout(() => setCopiedMessageIdx(null), 2000);
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
      {/* Top Floating Action Controls (Transparent, no solid bar / height) */}
      <div className="absolute top-3 inset-x-0 px-4 sm:px-6 md:px-8 hidden lg:flex items-center justify-between z-20 pointer-events-none">
        {/* Left: Open Sidebar Button */}
        <div className="flex items-center gap-2 pointer-events-auto">
          {!isSidebarOpen && onOpenSidebar && (
            <button 
              type="button"
              onClick={onOpenSidebar}
              className="h-8 w-8 text-gray-400 hover:text-white bg-[#282828] hover:bg-[#333333] border border-white/10 rounded-lg shadow-md cursor-pointer flex items-center justify-center transition-colors"
              title={t('chat.openSidebar')}
            >
              <Sparkles size={16} />
            </button>
          )}
        </div>

        {/* Right: Context Menu & Sources Controls */}
        <div className="flex items-center gap-2 pointer-events-auto">
          {/* Three Dots Context Menu (Only when chat is not empty & activeChatId exists) */}
          {!isChatEmpty && activeChatId && (
            <div className="relative" ref={topMenuRef}>
              <button
                type="button"
                onClick={() => setIsTopMenuOpen(prev => !prev)}
                className="h-8 w-8 rounded-lg bg-[#28292c]/90 hover:bg-[#333] border border-white/10 text-gray-300 hover:text-white flex items-center justify-center cursor-pointer shadow-md backdrop-blur transition-colors"
                title={t('left.options')}
              >
                <MoreHorizontal size={16} />
              </button>

              {/* Dropdown Menu */}
              {isTopMenuOpen && (
                <div 
                  className="absolute right-0 top-9 z-50 w-44 rounded-xl bg-[#222222] border border-white/10 shadow-2xl p-1 text-xs text-gray-200 animate-in fade-in zoom-in-95 duration-100 space-y-0.5"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Rename */}
                  <button
                    onClick={() => {
                      setIsTopMenuOpen(false);
                      setRenameInput(chatTitle || "");
                      setIsRenameOpen(true);
                    }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
                  >
                    <Pencil size={13} className="text-gray-400" />
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
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
                  >
                    {isPinned ? (
                      <>
                        <PinOff size={13} className="text-amber-400" />
                        <span>{t('action.unpin')}</span>
                      </>
                    ) : (
                      <>
                        <Pin size={13} className="text-gray-400" />
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
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors cursor-pointer"
                  >
                    <Trash2 size={13} />
                    <span>{t('action.delete')}</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Open Sources Toggle (when right sidebar is closed) */}
          {!isRightSidebarOpen && onToggleRightSidebar && (
            <button 
              type="button"
              onClick={onToggleRightSidebar}
              className="relative h-8 w-8 rounded-lg bg-[#28292c]/90 hover:bg-[#333] border border-white/10 text-gray-300 hover:text-white flex items-center justify-center cursor-pointer shadow-md backdrop-blur transition-colors"
              title={t('chat.openSources') || "Open sources"}
            >
              <FileText size={15} className="text-blue-400" />
              {documents.length > 0 && (
                <span className="absolute -top-1 -right-1 px-1 min-w-4 h-4 rounded-full bg-blue-600 text-white text-[9px] font-mono flex items-center justify-center border border-[#1e1f20] leading-none shadow">
                  {documents.length}
                </span>
              )}
            </button>
          )}
        </div>
      </div>

      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 sm:px-6 md:px-8 pt-12 lg:pt-14 pb-36 w-full min-h-0 scroll-smooth custom-scrollbar"
      >
          <div className={`w-full lg:max-w-3xl mx-auto space-y-6 ${isChatEmpty ? 'min-h-full flex flex-col justify-center' : ''}`}>
          {isChatEmpty ? (
            <div className="flex flex-col items-center justify-center py-12 text-center px-4 w-full max-w-2xl mx-auto my-auto">
              <div className="p-3.5 rounded-full bg-white/5 border border-white/10 mb-4 shadow-sm">
                <Sparkles size={28} className="text-white" />
              </div>
              <h2 className="text-3xl font-bold tracking-tight text-white mb-6">NotbookLM</h2>

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
                      <div className="flex flex-col items-end w-full max-w-[85%] -mr-[7px]">
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
                                  className="flex flex-col p-3 rounded-2xl bg-[#1e1f20] border border-white/10 hover:border-white/20 transition-all text-left w-36 shadow-md group/att"
                                >
                                  <div className="flex items-center justify-between mb-2">
                                    {att.type === "image" ? (
                                      <div className="w-8 h-8 rounded-lg overflow-hidden bg-black/40">
                                        <img src={fileHref} alt={att.filename} className="w-full h-full object-cover" />
                                      </div>
                                    ) : isWord ? (
                                      <div className="w-7 h-7 rounded bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-[11px]">
                                        W
                                      </div>
                                    ) : isPdf ? (
                                      <div className="w-7 h-7 rounded bg-red-600/20 border border-red-500/30 flex items-center justify-center text-red-400 font-bold text-[10px]">
                                        PDF
                                      </div>
                                    ) : (
                                      <div className="w-7 h-7 rounded bg-white/5 border border-white/10 flex items-center justify-center text-gray-300">
                                        <FileText size={15} />
                                      </div>
                                    )}
                                  </div>
                                  <span className="text-xs font-medium text-gray-200 line-clamp-2 leading-tight group-hover/att:text-white">
                                    {att.filename}
                                  </span>
                                </a>
                              );
                            })}
                          </div>
                        )}

                        {editingMessageIdx === idx ? (
                          <div className="w-full max-w-xl bg-[#2a2a2a] p-3 rounded-2xl border border-white/10 space-y-2 shadow-xl">
                            <textarea
                              value={editContent}
                              onChange={(e) => setEditContent(e.target.value)}
                              className="w-full bg-[#1e1e1e] text-white p-3 rounded-xl border border-white/10 focus:outline-none focus:border-blue-500 text-sm resize-none"
                              rows={3}
                              autoFocus
                            />
                            <div className="flex justify-end gap-2">
                              <button
                                type="button"
                                onClick={() => setEditingMessageIdx(null)}
                                className="px-3 py-1.5 text-xs text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
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
                              <div className="bg-[#2f2f2f] text-white px-4 py-2.5 rounded-2xl rounded-tr-sm text-[15px] leading-relaxed shadow-sm">
                                {msg.content}
                              </div>
                            )}
                            <div className="flex items-center gap-1 mt-1 mr-0.5">
                              <button
                                type="button"
                                onClick={() => handleStartEdit(msg.content || "", idx)}
                                className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-center"
                                title={t('chat.editMessage')}
                              >
                                <Pencil size={15} />
                              </button>
                              {msg.content?.trim() && (
                                <button
                                  type="button"
                                  onClick={() => handleCopy(msg.content, idx)}
                                  className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-center"
                                  title={t('chat.copyPrompt')}
                                >
                                  {copiedMessageIdx === idx ? <Check size={15} className="text-emerald-400" /> : <Copy size={15} />}
                                </button>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start">
                      <div className="flex-1 min-w-0">
                        <InChatMessageComponent 
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
                        <div className="mt-1 flex items-center gap-1.5">
                          {/* Pagination for response variants (e.g. 1/2, 2/2) */}
                          {msg.variants && msg.variants.length > 1 && (
                            <div className="flex items-center gap-0.5 text-xs text-gray-400 font-mono select-none bg-white/5 px-2 py-0.5 rounded-lg border border-white/5 mr-1">
                              <button
                                type="button"
                                onClick={() => onSelectVariant?.(idx, (msg.active_variant_index || 0) - 1)}
                                disabled={(msg.active_variant_index || 0) <= 0 || isLoading}
                                className="p-0.5 hover:text-white disabled:opacity-25 transition-colors cursor-pointer disabled:cursor-not-allowed"
                                title={t('chat.previousResponse')}
                              >
                                <ChevronLeft size={14} />
                              </button>
                              <span className="px-1 text-gray-300 text-xs">
                                {(msg.active_variant_index || 0) + 1}/{msg.variants.length}
                              </span>
                              <button
                                type="button"
                                onClick={() => onSelectVariant?.(idx, (msg.active_variant_index || 0) + 1)}
                                disabled={(msg.active_variant_index || 0) >= msg.variants.length - 1 || isLoading}
                                className="p-0.5 hover:text-white disabled:opacity-25 transition-colors cursor-pointer disabled:cursor-not-allowed"
                                title={t('chat.nextResponse')}
                              >
                                <ChevronRight size={14} />
                              </button>
                            </div>
                          )}

                          {/* Copy Button */}
                          <button
                            type="button"
                            onClick={() => handleCopy(msg.content.replace(/<!-- SOURCES_DATA:[\s\S]*?-->/g, "").trim(), idx)}
                            className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-center"
                            title={t('chat.copyResponse')}
                          >
                            {copiedMessageIdx === idx ? (
                              <Check size={15} className="text-emerald-400" />
                            ) : (
                              <Copy size={15} />
                            )}
                          </button>

                          {/* Retry / Regenerate Button */}
                          <button
                            type="button"
                            onClick={() => onRegenerateMessage?.(idx)}
                            disabled={isLoading}
                            className="p-1.5 text-gray-400 hover:text-white disabled:opacity-30 rounded-lg hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-center"
                            title={t('chat.regenerateResponse')}
                          >
                            <RotateCw size={15} />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="flex items-center gap-2.5 text-gray-400 text-sm py-1.5 animate-in fade-in duration-200">
                  <Loader2 size={16} className="text-blue-400 animate-spin shrink-0" />
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
        <div className="absolute bottom-0 inset-x-0 pb-3 pt-6 pointer-events-none z-20 flex justify-center px-4 sm:px-6 md:px-8">
          <div className="w-full lg:max-w-3xl pointer-events-auto min-w-0 relative">
            <div className="absolute -inset-x-4 -top-6 -bottom-3 bg-gradient-to-t from-[#212121] via-[#212121]/95 to-transparent -z-10 pointer-events-none rounded-3xl" />
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
      )}

      {/* Modal for Rename Chat */}
      {isRenameOpen && activeChatId && (
        <div 
          onClick={() => setIsRenameOpen(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-[#28292c] border border-white/10 rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150"
          >
            <div className="space-y-1.5">
              <h3 className="text-base font-semibold text-white">{t('left.renameConversation')}</h3>
              <p className="text-xs text-gray-400">
                {t('left.renameDesc')}
              </p>
            </div>

            <form 
              onSubmit={(e) => {
                e.preventDefault();
                if (renameInput.trim() && onRenameChat && activeChatId) {
                  onRenameChat(activeChatId, renameInput.trim());
                }
                setIsRenameOpen(false);
              }} 
              className="space-y-4"
            >
              <input
                ref={renameInputRef}
                type="text"
                value={renameInput}
                onChange={(e) => setRenameInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setIsRenameOpen(false);
                }}
                placeholder={t('left.renamePlaceholder')}
                className="w-full bg-[#1b1c1e] border border-white/15 focus:border-blue-500 rounded-xl px-3 py-2 text-xs text-white outline-none transition-colors"
              />

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsRenameOpen(false)}
                  className="text-xs text-gray-300 hover:text-white hover:bg-white/10 rounded-lg px-3.5 h-8 cursor-pointer"
                >
                  {t('action.cancel')}
                </Button>

                <Button
                  type="submit"
                  size="sm"
                  disabled={!renameInput.trim()}
                  className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow"
                >
                  {t('action.save')}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmation Modal for Delete Chat */}
      {isDeleteConfirmOpen && activeChatId && (
        <div 
          onClick={() => setIsDeleteConfirmOpen(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-[#28292c] border border-white/10 rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150"
          >
            <div className="space-y-1.5">
              <h3 className="text-base font-semibold text-white">{t('ui.deleteConfirmTitle')}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {t('ui.deleteConfirmDesc').replace('{title}', chatTitle || "conversation")}
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setIsDeleteConfirmOpen(false)}
                className="text-xs text-gray-300 hover:text-white hover:bg-white/10 rounded-lg px-3.5 h-8 cursor-pointer"
              >
                {t('action.cancel')}
              </Button>

              <Button
                type="button"
                size="sm"
                onClick={() => {
                  if (onDeleteChat && activeChatId) {
                    onDeleteChat(activeChatId);
                  }
                  setIsDeleteConfirmOpen(false);
                }}
                className="text-xs bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow"
              >
                {t('action.delete')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
