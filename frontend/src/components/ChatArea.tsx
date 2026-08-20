"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { 
  Sparkles, 
  FileText, 
  Check, 
  Loader2, 
  Copy, 
  Pencil, 
  Clock 
} from "lucide-react";
import { ChatMessage, Document as DocType, TargetedSource } from "@/app/ChatClient";
import { InChatMessageComponent } from "./chat/ChatMessageItem";
import { ChatInputBox } from "./chat/ChatInput";
import { CitationContext } from "./chat/CitationParser";

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
  activeCitationKey
}: ChatAreaProps) {
  const [copiedMessageIdx, setCopiedMessageIdx] = useState<number | null>(null);
  const [editingMessageIdx, setEditingMessageIdx] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const isChatEmpty = messages.length === 0;

  useEffect(() => {
    if (!isChatEmpty) {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
      }
    }
  }, [messages, isLoading, isChatEmpty]);

  const handleSendMessage = useCallback((text: string) => {
    onSendMessage(text);
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

      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 sm:px-6 pt-10 sm:pt-12 pb-6 w-full min-h-0 scroll-smooth"
      >
        <div className={`max-w-3xl mx-auto space-y-6 ${isChatEmpty ? 'min-h-full flex flex-col justify-center' : ''}`}>
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
                targetedSource={targetedSource}
                onClearTargetedSource={onClearTargetedSource}
              />
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, idx) => (
                <div key={idx} className="space-y-2 group">
                  {msg.role === "user" ? (
                    <div className="flex flex-col items-end">
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
                        <div className="flex items-center gap-2 max-w-[85%]">
                          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => handleStartEdit(msg.content, idx)}
                              className="p-1 text-gray-400 hover:text-white rounded-md hover:bg-white/10 transition-colors cursor-pointer"
                              title="Edit message"
                            >
                              <Pencil size={13} />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleCopy(msg.content, idx)}
                              className="p-1 text-gray-400 hover:text-white rounded-md hover:bg-white/10 transition-colors cursor-pointer"
                              title="Copy prompt"
                            >
                              {copiedMessageIdx === idx ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                            </button>
                          </div>
                          <div className="bg-[#2f2f2f] text-white px-4 py-2.5 rounded-2xl rounded-tr-sm text-[15px] leading-relaxed shadow-sm">
                            {msg.content}
                          </div>
                        </div>
                      )}
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
                        <div className="mt-2 flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleCopy(msg.content.replace(/<!-- SOURCES_DATA:[\s\S]*?-->/, "").trim(), idx)}
                            className="p-1.5 text-gray-400 hover:text-white rounded-md hover:bg-white/10 transition-colors cursor-pointer flex items-center gap-1 text-xs"
                            title="Copy response"
                          >
                            {copiedMessageIdx === idx ? (
                              <>
                                <Check size={13} className="text-emerald-400" />
                                <span className="text-emerald-400 text-[11px]">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy size={13} />
                                <span className="text-[11px]">Copy</span>
                              </>
                            )}
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

      {!isChatEmpty && (
        <div className="p-4 bg-gradient-to-t from-[#212121] via-[#212121] to-transparent shrink-0">
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
            targetedSource={targetedSource}
            onClearTargetedSource={onClearTargetedSource}
          />
        </div>
      )}
    </div>
  );
}
