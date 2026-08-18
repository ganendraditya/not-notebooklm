"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Sidebar, 
  MessageSquare, 
  MoreHorizontal, 
  Pencil, 
  Trash2, 
  Share2, 
  Check, 
  X,
  SquarePen,
  Search,
  Sparkles
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatSession } from "@/app/ChatClient";

interface LeftSidebarProps {
  sessions: ChatSession[];
  activeChatId: string | null;
  onSelectChat: (id: string) => void;
  onCreateChat: () => void;
  onDeleteChat: (id: string) => void;
  onRenameChat: (id: string, newTitle: string) => void;
  onToggleSidebar?: () => void;
}

export default function LeftSidebar({ 
  sessions, 
  activeChatId, 
  onSelectChat, 
  onCreateChat,
  onDeleteChat,
  onRenameChat,
  onToggleSidebar
}: LeftSidebarProps) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<ChatSession | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const editInputRef = useRef<HTMLInputElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

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

  // Focus input when editing starts
  useEffect(() => {
    if (editingId) {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }
  }, [editingId]);

  // Focus search input when search is opened
  useEffect(() => {
    if (isSearching) {
      searchInputRef.current?.focus();
    }
  }, [isSearching]);

  const handleStartRename = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(session.id);
    setEditTitle(session.title);
    setOpenMenuId(null);
  };

  const handleSaveRename = (id: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (editTitle.trim()) {
      onRenameChat(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelRename = () => {
    setEditingId(null);
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

  const handleCopyLink = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const url = `${window.location.origin}/?chat=${id}`;
    navigator.clipboard.writeText(url);
    setCopiedId(id);
    setTimeout(() => {
      setCopiedId(null);
      setOpenMenuId(null);
    }, 1200);
  };

  const filteredSessions = sessions.filter(session => 
    session.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="w-[260px] bg-[#171717] flex flex-col h-full text-sm border-r border-white/5 select-none shrink-0">
      {/* Top Header with NotbookLM Logo and Sidebar Toggle */}
      <div className="p-3.5 flex items-center justify-between">
        {/* Logo NotbookLM */}
        <div className="flex items-center gap-2 font-bold text-white tracking-tight">
          <div className="p-1 rounded-md bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm flex items-center justify-center">
            <Sparkles size={14} />
          </div>
          <span className="text-sm font-bold text-white">NotbookLM</span>
        </div>

        {/* Hide Sidebar Button (Moved to far right) */}
        <Button 
          variant="ghost" 
          size="icon" 
          className="h-8 w-8 text-gray-400 hover:text-white hover:bg-white/10 cursor-pointer"
          onClick={onToggleSidebar}
          title="Tutup Sidebar"
        >
          <Sidebar size={17} />
        </Button>
      </div>

      {/* Top Action Items: New chat & Search chat */}
      <div className="px-3 py-1 space-y-1">
        <Button 
          variant="ghost" 
          className="w-full justify-start text-gray-300 hover:text-white hover:bg-white/10 h-9 text-xs font-medium cursor-pointer"
          onClick={() => {
            onCreateChat();
            setIsSearching(false);
          }}
        >
          <SquarePen className="mr-2.5 text-gray-400" size={16} /> New chat
        </Button>

        <Button 
          variant="ghost" 
          className={`w-full justify-start h-9 text-xs font-medium cursor-pointer transition-colors ${
            isSearching 
              ? "bg-white/10 text-white" 
              : "text-gray-300 hover:text-white hover:bg-white/10"
          }`}
          onClick={() => setIsSearching(prev => !prev)}
        >
          <Search className="mr-2.5 text-gray-400" size={16} /> Search chat
        </Button>

        {/* Inline Search Input */}
        {isSearching && (
          <div className="pt-1">
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#252525] border border-white/10 text-xs">
              <Search size={13} className="text-gray-400 shrink-0" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Cari percakapan..."
                className="flex-1 bg-transparent text-white outline-none text-xs placeholder:text-gray-500"
              />
              {searchQuery && (
                <button 
                  onClick={() => setSearchQuery("")}
                  className="text-gray-400 hover:text-white cursor-pointer"
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Chat History Header */}
      <div className="mt-3 px-4 text-xs font-medium text-gray-400">
        Recent chats
      </div>

      {/* History List */}
      <div className="flex-1 overflow-y-auto px-2 mt-1.5 space-y-0.5 min-h-0">
        {filteredSessions.length === 0 ? (
          <div className="text-center text-xs text-gray-500 py-8 px-4">
            {searchQuery ? "Tidak ditemukan" : "Belum ada riwayat chat"}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = activeChatId === session.id;
            const isMenuOpen = openMenuId === session.id;
            const isEditing = editingId === session.id;

            return (
              <div 
                key={session.id}
                className="relative group"
              >
                {isEditing ? (
                  <form 
                    onSubmit={(e) => handleSaveRename(session.id, e)}
                    className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-[#2a2a2a] border border-white/10"
                  >
                    <input
                      ref={editInputRef}
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") handleCancelRename();
                      }}
                      className="flex-1 bg-transparent text-xs text-white outline-none px-1"
                    />
                    <button
                      type="submit"
                      className="p-1 text-green-400 hover:text-green-300 hover:bg-white/10 rounded cursor-pointer"
                      title="Simpan"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={handleCancelRename}
                      className="p-1 text-gray-400 hover:text-gray-200 hover:bg-white/10 rounded cursor-pointer"
                      title="Batal"
                    >
                      <X size={14} />
                    </button>
                  </form>
                ) : (
                  <div
                    onClick={() => onSelectChat(session.id)}
                    className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg transition-all cursor-pointer text-xs ${
                      isActive 
                        ? "bg-[#2a2a2a] text-white font-medium shadow-sm" 
                        : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 truncate mr-1">
                      <MessageSquare size={14} className="shrink-0 text-gray-400" />
                      <span className="truncate">{session.title}</span>
                    </div>

                    {/* Three-dots button on hover */}
                    <div className="shrink-0 flex items-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(isMenuOpen ? null : session.id);
                        }}
                        className={`p-1 rounded-md text-gray-400 hover:text-white hover:bg-white/10 transition-opacity cursor-pointer ${
                          isMenuOpen || isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                        }`}
                        title="Opsi"
                      >
                        <MoreHorizontal size={14} />
                      </button>
                    </div>
                  </div>
                )}

                {/* Dropdown Menu */}
                {isMenuOpen && (
                  <div
                    ref={menuRef}
                    className="absolute right-1 top-9 z-50 w-44 rounded-xl bg-[#222222] border border-white/10 shadow-2xl py-1 text-xs text-gray-200 animate-in fade-in zoom-in-95 duration-100"
                  >
                    {/* Rename */}
                    <button
                      onClick={(e) => handleStartRename(session, e)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
                    >
                      <Pencil size={13} className="text-gray-400" />
                      <span>Ubah nama</span>
                    </button>

                    {/* Share / Copy Link */}
                    <button
                      onClick={(e) => handleCopyLink(session.id, e)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
                    >
                      <Share2 size={13} className="text-gray-400" />
                      <span>{copiedId === session.id ? "Tersalin! ✅" : "Salin tautan"}</span>
                    </button>

                    <div className="h-px bg-white/10 my-1" />

                    {/* Delete */}
                    <button
                      onClick={(e) => handleRequestDelete(session, e)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors cursor-pointer"
                    >
                      <Trash2 size={13} />
                      <span>Hapus percakapan</span>
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* User Footer / Info */}
      <div className="p-3 border-t border-white/5 text-[11px] text-gray-500 text-center">
        NotbookLM v0.1
      </div>

      {/* Centered Confirmation Modal for Delete Chat */}
      {chatToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div className="bg-[#28292c] border border-white/10 rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150">
            <div className="space-y-1.5">
              <h3 className="text-base font-semibold text-white">Hapus percakapan?</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Tindakan ini akan menghapus percakapan <span className="text-white font-medium">"{chatToDelete.title}"</span> beserta seluruh riwayat dan dokumennya secara permanen.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setChatToDelete(null)}
                className="text-xs text-gray-300 hover:text-white hover:bg-white/10 rounded-lg px-3.5 h-8 cursor-pointer"
              >
                Batal
              </Button>

              <Button
                size="sm"
                onClick={handleConfirmDelete}
                className="text-xs bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow"
              >
                Hapus
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
