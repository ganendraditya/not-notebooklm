"use client";

import { useState, useRef, useEffect } from "react";
import { Search, MessageSquare, Sidebar, X, ArrowUpDown, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { ChatSession } from "@/stores/chatStore";
import { useTranslation } from "@/lib/i18n";

interface SearchChatsViewProps {
  sessions: ChatSession[];
  backendUrl: string;
  isSidebarOpen: boolean;
  onOpenSidebar: () => void;
  onSelectChat: (chatId: string) => void;
}

export default function SearchChatsView({
  sessions,
  backendUrl,
  isSidebarOpen,
  onOpenSidebar,
  onSelectChat
}: SearchChatsViewProps) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus input when opened
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const formatRelativeDate = (isoStr?: string) => {
    if (!isoStr) return "-";
    try {
      const d = new Date(isoStr);
      const now = new Date();
      if (d.toDateString() === now.toDateString()) return "Today";

      const yesterday = new Date();
      yesterday.setDate(now.getDate() - 1);
      if (d.toDateString() === yesterday.toDateString()) return "Yesterday";

      return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
      return "-";
    }
  };

  // Sort sessions by updated_at / created_at desc
  const sortedSessions = [...sessions].sort((a, b) => {
    const timeA = new Date(a.updated_at || a.created_at).getTime();
    const timeB = new Date(b.updated_at || b.created_at).getTime();
    return timeB - timeA;
  });

  const filteredSessions = sortedSessions.filter(session =>
    session.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col h-full bg-app-bg text-app-text relative overflow-hidden">
      {/* Top Bar for Sidebar toggle if closed */}
      <div className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-app-divider bg-app-sidebar">
        <div className="flex items-center gap-3">
          <Tooltip content={t('ui.openSidebar')} side="bottom">
            <Button
              variant="ghost"
              size="icon"
              className={`h-8 w-8 text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer mr-1 ${isSidebarOpen ? "hidden" : "flex"}`}
              onClick={onOpenSidebar}
              aria-label={t('ui.openSidebar')}
            >
              <Sidebar size={18} />
            </Button>
          </Tooltip>
          <h1 className="text-lg sm:text-xl font-bold text-app-text tracking-tight">{t('searchView.title')}</h1>
        </div>
      </div>

      {/* Main Content Area (Gemini Style) */}
      <div className="flex-1 overflow-y-scroll [scrollbar-gutter:stable] custom-scrollbar p-6 sm:p-10 flex flex-col items-center">
        <div className="w-full max-w-2xl space-y-8">
          {/* Prominent Center Search Pill */}
          <div className="relative w-full">
            <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-app-text-dim" />
            <input
              ref={inputRef}
              type="text"
              placeholder={t('searchView.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-app-input border border-app-border rounded-full pl-12 pr-10 py-3.5 text-sm text-app-text placeholder:text-app-text-dim outline-none focus:border-blue-500/50 transition-all shadow-lg"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-app-text-dim hover:text-app-text cursor-pointer p-1 rounded-full hover:bg-app-item-hover transition-colors"
              >
                <X size={15} />
              </button>
            )}
          </div>

          {/* Section Header */}
          <div className="space-y-2">
            <div className="text-xs font-semibold text-app-text-dim tracking-wider select-none px-2">
              {searchQuery ? t('searchView.searchResults') : t('searchView.recent')}
            </div>

            {/* Conversations List */}
            {filteredSessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-app-text-dim space-y-2">
                <MessageSquare size={36} className="opacity-20" />
                <p className="text-sm font-medium">{t('searchView.noResults')}</p>
                <p className="text-xs text-app-text-dim">{t('searchView.noResultsDesc')}</p>
              </div>
            ) : (
              <div className="divide-y divide-app-divider border-t border-b border-app-divider">
                {filteredSessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => onSelectChat(session.id)}
                    className="flex items-center justify-between py-3.5 px-3 hover:bg-app-item-hover rounded-xl cursor-pointer transition-colors group"
                  >
                    <div className="flex items-center gap-3 min-w-0 pr-4">
                      <span className="text-sm text-app-text truncate font-medium">
                        {session.title}
                      </span>
                    </div>

                    <div className="text-xs text-app-text-dim font-mono shrink-0">
                      {formatRelativeDate(session.updated_at || session.created_at)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
