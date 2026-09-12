"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Sparkles, Settings } from "lucide-react";
import LeftSidebar from "@/components/LeftSidebar";
import ChatArea from "@/components/ChatArea";
import RightSidebar from "@/components/RightSidebar";
import SettingsModal from "@/components/SettingsModal";
import LibraryView from "@/components/LibraryView";
import SearchChatsView from "@/components/SearchChatsView";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Tooltip } from "@/components/ui/tooltip";
import { useTranslation } from "@/lib/i18n";
import { useChatStore } from "@/stores/chatStore";
import { useDocumentStore, type Document, type PendingSourceItem } from "@/stores/documentStore";
import { useUIStore } from "@/stores/uiStore";

import { useChatSession } from "@/hooks/chat/useChatSession";
import { useChatStream, type ChatJobState } from "@/hooks/chat/useChatStream";
import { isMatchingPaper } from "@/lib/sourceUtils";

export default function ChatClient() {
  const { t } = useTranslation();
  
  // Zustand Stores
  const { 
    sessions, setSessions, activeChatId, setActiveChatId, 
    messages, setMessages, isLoading, setIsLoading,
    activeStatus, setActiveStatus, queuedPrompts, setQueuedPrompts,
    bumpSessionToTop, updateMessagesList, updateSessionsList
  } = useChatStore();

  const {
    documents, setDocuments, pendingSources, setPendingSources,
    targetedSource, setTargetedSource, viewingDoc, setViewingDoc,
    groundingHighlight, setGroundingHighlight,
    updateDocumentsList, updatePendingSourcesList,
    cancelPendingItem
  } = useDocumentStore();

  const {
    isSettingsOpen, setIsSettingsOpen, currentView, setCurrentView,
    libraryInitialCategory, setLibraryInitialCategory
  } = useUIStore();
  
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const activeChatIdRef = useRef<string | null>(null);

  // Bridge getChatJob to useChatSession cleanly without cyclical dependency or object monkey-patching
  const getChatJobRef = useRef<(id: string) => ChatJobState>(() => ({
    controller: null,
    queue: [],
    isProcessing: false,
    status: null,
  }));

  // 1. Hook for Session DB logic
  const {
    handleEnsureChatSession,
    handleCreateChat,
    handleSelectChat,
    handleDeleteChat,
    handleRenameChat,
    handleTogglePinChat
  } = useChatSession(
    backendUrl,
    sessions,
    setSessions,
    activeChatId,
    setActiveChatId,
    setDocuments,
    setPendingSources,
    setMessages,
    setTargetedSource,
    setViewingDoc,
    setQueuedPrompts,
    setIsLoading,
    setActiveStatus,
    setCurrentView,
    updateSessionsList,
    (id) => getChatJobRef.current(id),
    activeChatIdRef
  );

  // 2. Wrap ensure function so stream hook can call it
  const handleEnsureChatSessionRef = useRef<(suggestedTitle?: string) => Promise<string>>(async () => "");
  useEffect(() => {
    handleEnsureChatSessionRef.current = handleEnsureChatSession;
  }, [handleEnsureChatSession]);

  // 3. Hook for Stream logic
  const {
    getChatJob,
    handleStopGeneration,
    handleRemoveQueuedPrompt,
    handlePromoteQueuedPrompt,
    handleSendMessage,
    handleEditMessage,
    handleRegenerateMessage,
    handleSelectVariant
  } = useChatStream(
    backendUrl,
    activeChatIdRef,
    messages,
    setMessages,
    setIsLoading,
    setActiveStatus,
    setQueuedPrompts,
    bumpSessionToTop,
    updateSessionsList,
    updateMessagesList,
    updateDocumentsList,
    handleEnsureChatSessionRef
  );

  // Keep getChatJobRef in sync with actual implementation
  useEffect(() => {
    getChatJobRef.current = getChatJob;
  }, [getChatJob]);

  const handleBulkDocumentsDeleted = useCallback((docIds: number[]) => {
    const idSet = new Set(docIds);
    updateDocumentsList(prev => {
      const remaining = prev.filter(d => !idSet.has(d.id));
      return remaining.map((doc, idx) => ({ ...doc, index: idx + 1 }));
    });
  }, [updateDocumentsList]);

  const handleDocumentAdded = useCallback((doc: Document, targetChatId?: string) => {
    // Only append to the visible documents list if the user is currently viewing the target chat
    if (!targetChatId || targetChatId === activeChatIdRef.current) {
      updateDocumentsList(prev => {
        if (prev.some(d => d.id === doc.id)) return prev;
        return [...prev, doc];
      });
      // Remove matching pending item by doi or filename matching
      updatePendingSourcesList(prev => prev.filter(p => {
        if (isMatchingPaper({ title: p.filename, filename: p.filename, doi: p.doi }, doc)) {
          return false;
        }
        return true;
      }));
    }
  }, [updateDocumentsList, updatePendingSourcesList]);

  const handleAddPendingSources = useCallback((items: PendingSourceItem[]) => {
    updatePendingSourcesList(prev => [...prev, ...items]);
  }, [updatePendingSourcesList]);

  const handleResolvePendingSource = useCallback((pendingId: string) => {
    updatePendingSourcesList(prev => prev.filter(p => p.id !== pendingId));
  }, [updatePendingSourcesList]);

  const handleCancelPendingSource = useCallback((pendingId: string) => {
    cancelPendingItem(pendingId);
  }, [cancelPendingItem]);

  const handleDocumentUpdated = useCallback((updatedDoc: Document) => {
    updateDocumentsList(prev => prev.map(d => d.id === updatedDoc.id ? { ...d, title: updatedDoc.title } : d));
    const curr = useDocumentStore.getState().viewingDoc;
    if (curr && curr.id === updatedDoc.id) {
      setViewingDoc({ ...curr, title: updatedDoc.title });
    }
  }, [updateDocumentsList, setViewingDoc]);

  // Whenever active chat changes, always reset viewingDoc and groundingHighlight
  useEffect(() => {
    setViewingDoc(null);
    setGroundingHighlight(null);
  }, [activeChatId, setViewingDoc, setGroundingHighlight]);

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);
  const [mobileTab, setMobileTab] = useState<"menu" | "chat" | "sources">("chat");

  return (
    <div className="flex flex-col h-screen w-full overflow-hidden bg-app-bg text-app-text">
      {/* Mobile/Tablet NotebookLM Top Header Bar (< lg) */}
      <div className="lg:hidden shrink-0 bg-app-sidebar border-b border-app-border z-50 flex flex-col">
        {/* Row 1: Brand / Active Chat Title + Settings Gear Icon */}
        <div className="px-4 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0 pr-2">
            <div className="p-1 rounded-md bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm flex items-center justify-center shrink-0">
              <Sparkles size={14} />
            </div>
            <span className="text-sm font-semibold text-app-text truncate">
              {currentView === "library" 
                ? "Library" 
                : currentView === "search" 
                ? "Search" 
                : (activeChatId ? (sessions.find(s => s.id === activeChatId)?.title || "NotbookLM") : "NotbookLM")}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <Tooltip content={t('settings.title') || "Settings"} side="bottom">
              <button
                onClick={() => setIsSettingsOpen(true)}
                className="p-1.5 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer"
                aria-label={t('settings.title') || "Settings"}
              >
                <Settings size={17} />
              </button>
            </Tooltip>
          </div>
        </div>

        {/* Row 2: 3 Tabs (Menu | Chat | Sources) */}
        <div className="flex items-center justify-around text-xs font-medium border-t border-app-divider">
          {/* 1. Left Tab: Menu */}
          <button
            onClick={() => {
              setMobileTab("menu");
              setIsSidebarOpen(true);
            }}
            className={`flex-1 py-2.5 text-center relative transition-colors cursor-pointer ${
              mobileTab === "menu" ? "text-app-text font-semibold" : "text-app-text-muted hover:text-app-text"
            }`}
          >
            <span>{t('nav.menu')}</span>
            {mobileTab === "menu" && (
              <div className="absolute bottom-0 inset-x-4 h-0.5 bg-blue-500 rounded-full"></div>
            )}
          </button>

          {/* 2. Middle Tab: Dynamic Label (Chat | Library | Search) */}
          <button
            onClick={() => {
              setMobileTab("chat");
            }}
            className={`flex-1 py-2.5 text-center relative transition-colors cursor-pointer ${
              mobileTab === "chat" ? "text-app-text font-semibold" : "text-app-text-muted hover:text-app-text"
            }`}
          >
            <span>
              {currentView === "library" ? t('nav.library') : currentView === "search" ? t('nav.search') : t('nav.chat')}
            </span>
            {mobileTab === "chat" && (
              <div className="absolute bottom-0 inset-x-4 h-0.5 bg-blue-500 rounded-full"></div>
            )}
          </button>

          {/* 3. Right Tab: Sources (Disabled & Dimmed when on Library / Search view) */}
          {currentView === "chat" ? (
            <button
              onClick={() => {
                setMobileTab("sources");
                setIsRightSidebarOpen(true);
              }}
              className={`flex-1 py-2.5 text-center relative transition-colors cursor-pointer ${
                mobileTab === "sources" ? "text-app-text font-semibold" : "text-app-text-muted hover:text-app-text"
              }`}
            >
              <span>{t('nav.sources')}</span>
              {mobileTab === "sources" && (
                <div className="absolute bottom-0 inset-x-4 h-0.5 bg-blue-500 rounded-full"></div>
              )}
            </button>
          ) : (
            <Tooltip content={t('nav.sourcesDisabledTooltip')} side="top">
              <div
                className="flex-1 py-2.5 text-center relative text-app-text-dim cursor-not-allowed select-none opacity-40"
                aria-label={t('nav.sourcesDisabledTooltip')}
              >
                <span>{t('nav.sources')}</span>
              </div>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex min-w-0 h-full overflow-hidden relative">
        {/* Left Sidebar: Chat Sessions (Shown on desktop if open, or when mobileTab is 'menu' on smaller screens) */}
        {(isSidebarOpen || mobileTab === "menu") && (
          <div className={`h-full min-w-0 ${mobileTab === "menu" ? "w-full z-40 lg:w-auto" : "hidden lg:block"}`}>
            <LeftSidebar 
              sessions={sessions} 
              activeChatId={activeChatId} 
              currentView={currentView}
              onSelectChat={(id) => {
                handleSelectChat(id);
                setCurrentView("chat");
                setMobileTab("chat");
              }}
              onCreateChat={() => {
                handleCreateChat();
                setCurrentView("chat");
                setMobileTab("chat");
              }}
              onOpenLibrary={(cat) => {
                setLibraryInitialCategory(cat || "all");
                setCurrentView("library");
                setMobileTab("chat");
              }}
              onOpenSearch={() => {
                setCurrentView("search");
                setMobileTab("chat");
              }}
              onDeleteChat={handleDeleteChat}
              onRenameChat={handleRenameChat}
              onTogglePinChat={handleTogglePinChat}
              onToggleSidebar={() => {
                setIsSidebarOpen(false);
                setMobileTab("chat");
              }}
              onOpenSettings={() => setIsSettingsOpen(true)}
            />
          </div>
        )}
        
        {/* Center View: Main Chat Area, Library View, or Search View */}
        {currentView === "library" ? (
          <LibraryView
            initialCategory={libraryInitialCategory}
            backendUrl={backendUrl}
            isSidebarOpen={isSidebarOpen}
            onOpenSidebar={() => setIsSidebarOpen(true)}
            onSelectChat={handleSelectChat}
          />
        ) : currentView === "search" ? (
          <SearchChatsView
            sessions={sessions}
            backendUrl={backendUrl}
            isSidebarOpen={isSidebarOpen}
            onOpenSidebar={() => setIsSidebarOpen(true)}
            onSelectChat={handleSelectChat}
          />
        ) : (
          <div className={`flex-1 flex min-w-0 h-full overflow-hidden ${mobileTab === "menu" ? "hidden lg:flex" : "flex"}`}>
            <div className={`flex-1 h-full min-w-0 ${mobileTab === "sources" ? "hidden lg:flex" : "flex"}`}>
              <ErrorBoundary fallbackTitle="Antarmuka percakapan mengalami kendala">
                <ChatArea 
                  activeChatId={activeChatId} 
                  messages={messages} 
                  isLoading={isLoading}
                  onSendMessage={handleSendMessage} 
                  onEditMessage={handleEditMessage}
                  onStopGeneration={handleStopGeneration}
                  queuedPrompts={queuedPrompts}
                  onRemoveQueuedPrompt={handleRemoveQueuedPrompt}
                  onPromoteQueuedPrompt={handlePromoteQueuedPrompt}
                  documents={documents}
                  onDocumentAdded={handleDocumentAdded}
                  onAddPendingSources={handleAddPendingSources}
                  onResolvePendingSource={handleResolvePendingSource}
                  onOpenDocument={(doc, citationContext) => {
                    setViewingDoc(doc);
                    if (citationContext) {
                      setGroundingHighlight({
                        docId: doc.id,
                        sentence: citationContext.sentence,
                        num: citationContext.num,
                        citationKey: citationContext.citationKey,
                        aiQuotes: citationContext.aiQuotes,
                        clickId: Date.now()
                      });
                    } else {
                      setGroundingHighlight(null);
                    }
                    setIsRightSidebarOpen(true);
                    setMobileTab("sources");
                  }}
                  onEnsureChatSession={handleEnsureChatSession}
                  backendUrl={backendUrl}
                  isSidebarOpen={isSidebarOpen}
                  onOpenSidebar={() => {
                    setIsSidebarOpen(true);
                    setMobileTab("menu");
                  }}
                  isRightSidebarOpen={isRightSidebarOpen}
                  onToggleRightSidebar={() => {
                    if (typeof window !== "undefined" && window.innerWidth < 1024) {
                      setMobileTab(prev => (prev === "sources" ? "chat" : "sources"));
                      setIsRightSidebarOpen(true);
                    } else {
                      setIsRightSidebarOpen(prev => !prev);
                    }
                  }}
                  targetedSource={targetedSource}
                  onClearTargetedSource={() => setTargetedSource(null)}
                  activeStatus={activeStatus}
                  activeCitationKey={groundingHighlight?.citationKey}
                  onRenameChat={handleRenameChat}
                  onDeleteChat={handleDeleteChat}
                  onTogglePinChat={handleTogglePinChat}
                  isPinned={sessions.find(s => s.id === activeChatId)?.is_pinned}
                  chatTitle={sessions.find(s => s.id === activeChatId)?.title}
                  onRegenerateMessage={handleRegenerateMessage}
                  onSelectVariant={handleSelectVariant}
                  onOpenStorage={() => setIsSettingsOpen(true)}
                />
              </ErrorBoundary>
            </div>

            {/* Right Sidebar: Sources Panel (NotebookLM Style) */}
            {(isRightSidebarOpen || mobileTab === "sources") && (
              <div className={`h-full min-w-0 ${mobileTab === "chat" ? "hidden lg:block" : "w-full lg:w-auto"}`}>
                <ErrorBoundary fallbackTitle="Panel sumber referensi mengalami kendala">
                  <RightSidebar 
                    key={activeChatId || "new-chat"}
                    activeChatId={activeChatId} 
                    documents={documents} 
                    pendingSources={pendingSources}
                    onDocumentAdded={handleDocumentAdded} 
                    onDocumentUpdated={handleDocumentUpdated}
                    onDocumentDeleted={(id) => {
                      updateDocumentsList(prev => prev.filter(d => d.id !== id));
                      if (targetedSource?.id === id) setTargetedSource(null);
                      if (viewingDoc?.id === id) setViewingDoc(null);
                    }}
                    onBulkDocumentsDeleted={(ids) => {
                      handleBulkDocumentsDeleted(ids);
                      if (targetedSource && ids.includes(targetedSource.id)) setTargetedSource(null);
                      if (viewingDoc && ids.includes(viewingDoc.id)) setViewingDoc(null);
                    }}
                    onEnsureChatSession={handleEnsureChatSession}
                    onAskAboutDocument={(doc, paperTitle) => {
                      setTargetedSource({ id: doc.id, filename: doc.filename, title: paperTitle });
                      setMobileTab("chat");
                    }}
                    externalViewingDoc={viewingDoc}
                    onViewingDocChange={setViewingDoc}
                    onCancelPendingSource={handleCancelPendingSource}
                    groundingHighlight={groundingHighlight}
                    onClearGroundingHighlight={() => setGroundingHighlight(null)}
                    onClearViewingDoc={() => {
                      setViewingDoc(null);
                      setGroundingHighlight(null);
                    }}
                    backendUrl={backendUrl}
                    onClose={() => {
                      setIsRightSidebarOpen(false);
                      setGroundingHighlight(null);
                      setMobileTab("chat");
                    }}
                  />
                </ErrorBoundary>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Global Settings & Storage Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        backendUrl={backendUrl}
        sessions={sessions}
        onNavigateToLibrary={(cat) => {
          setLibraryInitialCategory(cat);
          setCurrentView("library");
        }}
        onChatsDeleted={(deletedIds) => {
          updateSessionsList(prev => prev.filter(s => !deletedIds.includes(s.id)));
          if (activeChatId && deletedIds.includes(activeChatId)) {
            const remaining = sessions.filter(s => !deletedIds.includes(s.id));
            if (remaining.length > 0) {
              handleSelectChat(remaining[0].id);
            } else {
              handleCreateChat();
            }
          }
        }}
        onAllDataReset={() => {
          setSessions([]);
          setDocuments([]);
          setMessages([]);
          setActiveChatId(null);
          setViewingDoc(null);
          setGroundingHighlight(null);
          handleCreateChat();
        }}
      />
    </div>
  );
}
