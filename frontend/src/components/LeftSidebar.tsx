"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Sidebar, 
  MessageSquare, 
  MoreHorizontal, 
  Pencil, 
  Trash2, 
  Pin, 
  PinOff, 
  SquarePen, 
  Search, 
  Sparkles, 
  Settings, 
  FolderArchive 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { ChatSession } from "@/stores/chatStore";
import { useTranslation } from "@/lib/i18n";

interface LeftSidebarProps {
  sessions: ChatSession[];
  activeChatId: string | null;
  currentView?: "chat" | "library" | "search";
  onSelectChat: (id: string) => void;
  onCreateChat: () => void;
  onOpenLibrary?: (category?: "all" | "documents" | "images") => void;
  onOpenSearch?: () => void;
  onDeleteChat: (id: string) => void;
  onRenameChat: (id: string, newTitle: string) => void;
  onTogglePinChat?: (id: string) => void;
  onToggleSidebar?: () => void;
  onOpenSettings?: () => void;
}

export default function LeftSidebar({ 
  sessions, 
  activeChatId, 
  currentView = "chat",
  onSelectChat, 
  onCreateChat,
  onOpenLibrary,
  onOpenSearch,
  onDeleteChat,
  onTogglePinChat,
  onRenameChat,
  onOpenSettings,
  onToggleSidebar
}: LeftSidebarProps) {
  const { t } = useTranslation();
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [chatToRename, setChatToRename] = useState<ChatSession | null>(null);
  const [renameTitleInput, setRenameTitleInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [chatToDelete, setChatToDelete] = useState<ChatSession | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Focus input when rename modal opens
  useEffect(() => {
    if (chatToRename) {
      setTimeout(() => {
        renameInputRef.current?.focus();
        renameInputRef.current?.select();
      }, 50);
    }
  }, [chatToRename]);

  const handleStartRename = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setChatToRename(session);
    setRenameTitleInput(session.title);
    setOpenMenuId(null);
  };

  const handleSaveRename = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (chatToRename && renameTitleInput.trim()) {
      onRenameChat(chatToRename.id, renameTitleInput.trim());
    }
    setChatToRename(null);
  };

  const handleCancelRename = () => {
    setChatToRename(null);
  };

  const handleRequestDelete = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setChatToDelete(session);
    setOpenMenuId(null);
  };

  const handleConfirmDelete = () => {
    if (chatToDelete) {
      onDeleteChat(chatToDelete.id);
      setChatToDelete(null);
    }
  };

  const handleTogglePin = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    onTogglePinChat?.(session.id);
    setOpenMenuId(null);
  };

  // Sort sessions: pinned first, then by updated_at / created_at desc
  const sortedSessions = [...sessions].sort((a, b) => {
    if (Boolean(a.is_pinned) !== Boolean(b.is_pinned)) {
      return a.is_pinned ? -1 : 1;
    }
    const timeA = new Date(a.updated_at || a.created_at).getTime();
    const timeB = new Date(b.updated_at || b.created_at).getTime();
    return timeB - timeA;
  });

  const filteredSessions = sortedSessions.filter(session => 
    session.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="w-full lg:w-[260px] bg-app-sidebar flex flex-col h-full text-sm border-r border-app-divider select-none shrink-0">
      {/* Top Header with NotbookLM Logo and Sidebar Toggle (Desktop Only) */}
      <div className="w-full h-[52px] px-4 items-center justify-between border-b border-app-border shrink-0 hidden lg:flex">
        {/* Logo NotbookLM (Clickable -> New Chat) */}
        <div 
          onClick={onCreateChat}
          className="flex items-center gap-2 font-semibold text-app-text tracking-tight cursor-pointer hover:opacity-90 transition-opacity"
        >
          <div className="p-1 rounded-md bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm flex items-center justify-center">
            <Sparkles size={14} />
          </div>
          <span className="text-sm font-semibold text-app-text tracking-tight">NotbookLM</span>
        </div>

        {/* Hide Sidebar Button (Only visible on desktop) */}
        <Tooltip content={t('left.closeSidebar')} side="right">
          <button 
            type="button"
            className="w-7 h-7 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer flex items-center justify-center transition-colors"
            onClick={onToggleSidebar}
            aria-label={t('left.closeSidebar')}
          >
            <Sidebar size={15} />
          </button>
        </Tooltip>
      </div>

      {/* Top Action Items: New chat, Search, & Library */}
      <div className="w-full px-2 pt-2 pb-2.5 space-y-0.5 border-b border-app-divider">
        <Button 
          variant="ghost" 
          className={`w-full justify-start h-9 px-2 text-xs font-medium cursor-pointer transition-colors ${
            currentView === "chat" && !activeChatId
              ? "bg-app-item-active text-app-text font-semibold"
              : "text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
          }`}
          onClick={() => {
            setSearchQuery("");
            onCreateChat();
          }}
        >
          <SquarePen className="mr-2.5 text-app-text-dim shrink-0" size={16} /> 
          <span>{t('ui.newChat')}</span>
        </Button>

        <Button 
          variant="ghost" 
          className={`w-full justify-start h-9 px-2 text-xs font-medium cursor-pointer transition-colors ${
            currentView === "library"
              ? "bg-app-item-active text-app-text font-semibold"
              : "text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
          }`}
          onClick={() => onOpenLibrary?.("all")}
        >
          <FolderArchive className="mr-2.5 text-app-text-dim shrink-0" size={16} /> 
          <span>{t('ui.library')}</span>
        </Button>

        <Button 
          variant="ghost" 
          className={`w-full justify-start h-9 px-2 text-xs font-medium cursor-pointer transition-colors ${
            currentView === "search" 
              ? "bg-app-item-active text-app-text font-semibold" 
              : "text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
          }`}
          onClick={() => onOpenSearch?.()}
        >
          <Search className="mr-2.5 text-app-text-dim shrink-0" size={16} /> 
          <span>{t('ui.searchChat')}</span>
        </Button>
      </div>

      {/* History List */}
      <div className="w-full flex-1 overflow-y-auto px-2 pt-3 space-y-4 min-h-0 custom-scrollbar">
        {filteredSessions.length === 0 ? (
          <div className="text-center text-xs text-app-text-dim py-8 px-4">
            {searchQuery ? t('ui.noConversationsFound') : t('ui.noChatHistory')}
          </div>
        ) : (
          (() => {
            const pinnedList = filteredSessions.filter(s => s.is_pinned);
            const recentList = filteredSessions.filter(s => !s.is_pinned);

            const renderSessionItem = (session: ChatSession) => {
              const isActive = currentView === "chat" && activeChatId === session.id;
              const isMenuOpen = openMenuId === session.id;

              return (
                <div key={session.id} className="relative group">
                  <div
                    onClick={() => onSelectChat(session.id)}
                    className={`w-full flex items-center justify-between px-2 py-2 rounded-lg transition-all cursor-pointer text-xs ${
                      isActive 
                        ? "bg-app-item-active text-app-text font-medium shadow-sm" 
                        : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 truncate mr-1">
                      {session.is_pinned ? (
                        <Pin size={16} className="shrink-0 text-amber-500 fill-amber-500/20" />
                      ) : (
                        <MessageSquare size={16} className="shrink-0 text-app-text-dim" />
                      )}
                      <span className="truncate">{session.title}</span>
                    </div>

                    {/* Three-dots button on hover */}
                    <div className="shrink-0 flex items-center">
                      <Tooltip content={t('left.options')} side="top">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenMenuId(isMenuOpen ? null : session.id);
                          }}
                          className={`p-1 rounded-md text-app-text-dim hover:text-app-text hover:bg-app-item-hover transition-opacity cursor-pointer ${
                            isMenuOpen || isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                          }`}
                          aria-label={t('left.options')}
                        >
                          <MoreHorizontal size={14} />
                        </button>
                      </Tooltip>
                    </div>
                  </div>

                  {/* Dropdown Menu */}
                  {isMenuOpen && (
                    <div
                      ref={menuRef}
                      className="absolute right-1 top-9 z-50 w-44 rounded-xl bg-app-dropdown border border-app-border-strong shadow-2xl p-1 text-xs text-app-text animate-in fade-in zoom-in-95 duration-100 space-y-0.5"
                    >
                      {/* Rename */}
                      <button
                        onClick={(e) => handleStartRename(session, e)}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-app-item-hover hover:text-app-text transition-colors cursor-pointer"
                      >
                        <Pencil size={13} className="text-app-text-dim" />
                        <span>{t('action.rename')}</span>
                      </button>

                      {/* Pin / Unpin */}
                      <button
                        onClick={(e) => handleTogglePin(session, e)}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-app-item-hover hover:text-app-text transition-colors cursor-pointer"
                      >
                        {session.is_pinned ? (
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
                        onClick={(e) => handleRequestDelete(session, e)}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-red-500 hover:bg-red-500/10 hover:text-red-600 transition-colors cursor-pointer"
                      >
                        <Trash2 size={13} />
                        <span>{t('action.deleteChat')}</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            };

            return (
              <div className="space-y-4">
                {/* Pinned Section */}
                {pinnedList.length > 0 && (
                  <div className="space-y-1">
                    <div className="px-2 text-xs font-semibold text-app-text-dim">
                      {t('ui.pinned')}
                    </div>
                    {pinnedList.map(renderSessionItem)}
                  </div>
                )}

                {/* Recent Section */}
                {recentList.length > 0 && (
                  <div className="space-y-1">
                    <div className="px-2 text-xs font-medium text-gray-400">
                      {t('ui.recentChats')}
                    </div>
                    <div className="space-y-0.5">
                      {recentList.map(renderSessionItem)}
                    </div>
                  </div>
                )}
              </div>
            );
          })()
        )}
      </div>

      {/* Desktop-only Footer: App Version & Settings Gear Button */}
      <div className="hidden lg:flex items-center justify-between px-4 py-3 border-t border-app-divider text-xs text-app-text-muted shrink-0">
        <span className="font-medium tracking-wide text-app-text-muted select-none">
          NotbookLM <span className="text-[11px] text-app-text-dim font-mono">v1.0.0</span>
        </span>
        <Tooltip content={t('ui.settings') || "Settings"} side="top">
          <button
            type="button"
            onClick={onOpenSettings}
            aria-label={t('ui.settings') || "Settings"}
            className="p-1.5 text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg transition-colors cursor-pointer"
          >
            <Settings size={15} />
          </button>
        </Tooltip>
      </div>

      {/* Centered Modal for Rename Chat */}
        {chatToRename && (
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
      )}

      {/* Centered Confirmation Modal for Delete Chat */}
        {chatToDelete && (
          <div 
            onClick={(e) => {
              e.stopPropagation();
              setChatToDelete(null);
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
                {t('ui.deleteConfirmDesc').replace('{title}', chatToDelete.title)}
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-app-divider">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setChatToDelete(null)}
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
      )}
    </div>
  );
}
