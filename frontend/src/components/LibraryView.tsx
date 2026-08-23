"use client";

import { useState, useEffect, useRef } from "react";
import { 
  X, Search, Trash2, Image as ImageIcon, 
  FileText, LayoutGrid, List as ListIcon, Download, Box,
  Sidebar, MessageSquare
} from "lucide-react";
import { Button } from "@/components/ui/button";

export interface LibraryItem {
  id: string;
  type: "file" | "image" | "document" | "other";
  name: string;
  raw_filename: string;
  size_bytes: number;
  modified: string;
  path: string;
  chat_id?: string | null;
  chat_title?: string | null;
}

interface LibraryViewProps {
  initialCategory?: "all" | "documents" | "images";
  backendUrl: string;
  isSidebarOpen: boolean;
  onOpenSidebar: () => void;
  onSelectChat?: (chatId: string) => void;
}

export default function LibraryView({
  initialCategory = "all",
  backendUrl,
  isSidebarOpen,
  onOpenSidebar,
  onSelectChat
}: LibraryViewProps) {
  const [category, setCategory] = useState<"all" | "documents" | "images">(initialCategory);
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"date" | "size" | "name" | "chat">("date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const headerCheckboxRef = useRef<HTMLInputElement>(null);

  const isIndeterminate = selectedIds.size > 0 && selectedIds.size < items.length;
  const isAllSelected = items.length > 0 && selectedIds.size === items.length;

  useEffect(() => {
    if (headerCheckboxRef.current) {
      headerCheckboxRef.current.indeterminate = isIndeterminate;
    }
  }, [isIndeterminate]);

  useEffect(() => {
    setCategory(initialCategory);
  }, [initialCategory]);

  useEffect(() => {
    fetchItems(category, search, sort, sortOrder);
  }, [category, search, sort, sortOrder]);

  const fetchItems = async (
    cat: string, 
    q: string, 
    sortBy: "date" | "size" | "name" | "chat", 
    order: "asc" | "desc"
  ) => {
    setIsLoading(true);
    try {
      const backendCat = cat === 'all' ? '' : cat;
      const res = await fetch(`${backendUrl}/storage/files?category=${backendCat}`);
      if (res.ok) {
        const data = await res.json();
        let filtered = data.filter((item: any) => 
          (item.filename || "").toLowerCase().includes(q.toLowerCase()) ||
          (item.chat_title || "").toLowerCase().includes(q.toLowerCase())
        );

        if (sortBy === 'name') {
          filtered.sort((a: any, b: any) => 
            order === 'asc' 
              ? (a.filename || "").localeCompare(b.filename || "") 
              : (b.filename || "").localeCompare(a.filename || "")
          );
        } else if (sortBy === 'chat') {
          filtered.sort((a: any, b: any) => {
            const titleA = a.chat_title || "";
            const titleB = b.chat_title || "";
            return order === 'asc' ? titleA.localeCompare(titleB) : titleB.localeCompare(titleA);
          });
        } else if (sortBy === 'size') {
          filtered.sort((a: any, b: any) => 
            order === 'asc' ? a.size - b.size : b.size - a.size
          );
        } else {
          // Date
          filtered.sort((a: any, b: any) => {
            const timeA = new Date(a.uploaded_at).getTime();
            const timeB = new Date(b.uploaded_at).getTime();
            return order === 'asc' ? timeA - timeB : timeB - timeA;
          });
        }
        
        const mappedItems: LibraryItem[] = filtered.map((item: any) => ({
          id: item.id,
          type: item.category === 'images' ? 'image' : 'document',
          name: item.filename,
          raw_filename: item.raw_filename || item.filename,
          size_bytes: item.size,
          modified: item.uploaded_at,
          path: item.id,
          chat_id: item.chat_id || null,
          chat_title: item.chat_title || null
        }));
        setItems(mappedItems);
      }
    } catch (e) {
      console.error("Failed to fetch library:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    if (selectedIds.size === 0 || isDeleting) return;
    setIsDeleting(true);
    try {
      const res = await fetch(`${backendUrl}/storage/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_ids: Array.from(selectedIds) })
      });
      if (res.ok) {
        setSelectedIds(new Set());
        fetchItems(category, search, sort, sortOrder);
      }
    } catch (e) {
      console.error("Failed to delete items:", e);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDownload = async () => {
    if (selectedIds.size === 0 || isDownloading) return;
    setIsDownloading(true);
    try {
      const res = await fetch(`${backendUrl}/storage/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_ids: Array.from(selectedIds) })
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const disposition = res.headers.get("content-disposition");
        let filename = selectedIds.size > 1 ? `Library_Export_${selectedIds.size}_files.zip` : "download";
        if (disposition && disposition.includes("filename=")) {
          const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
          if (match && match[1]) filename = decodeURIComponent(match[1]);
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (e) {
      console.error("Failed to download files:", e);
    } finally {
      setIsDownloading(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (isoStr: string) => {
    if (!isoStr) return "-";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
      return "-";
    }
  };

  const toggleSelect = (id: string) => {
    const newSel = new Set(selectedIds);
    if (newSel.has(id)) newSel.delete(id);
    else newSel.add(id);
    setSelectedIds(newSel);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map(i => i.id)));
    }
  };

  const renderFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    if (ext === 'pdf') {
      return (
        <div className="w-8 h-8 rounded-lg bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 font-bold text-[10px] shrink-0 select-none">
          PDF
        </div>
      );
    }
    if (['docx', 'doc'].includes(ext)) {
      return (
        <div className="w-8 h-8 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-[10px] shrink-0 select-none">
          DOC
        </div>
      );
    }
    if (['glb', 'gltf', 'obj', '3d'].includes(ext)) {
      return (
        <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0 select-none">
          <Box size={15} />
        </div>
      );
    }
    if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'].includes(ext)) {
      return (
        <div className="w-8 h-8 rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0 select-none">
          <ImageIcon size={15} />
        </div>
      );
    }
    if (['txt', 'md', 'json', 'csv', 'xlsx', 'pptx'].includes(ext)) {
      return (
        <div className="w-8 h-8 rounded-lg bg-slate-500/15 border border-slate-500/30 flex items-center justify-center text-slate-300 font-bold text-[10px] shrink-0 select-none">
          {ext.toUpperCase().slice(0, 3)}
        </div>
      );
    }
    return (
      <div className="w-8 h-8 rounded-lg bg-gray-500/15 border border-gray-500/30 flex items-center justify-center text-gray-300 shrink-0 select-none">
        <FileText size={15} />
      </div>
    );
  };

  const renderGridFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    if (ext === 'pdf') {
      return (
        <div className="w-14 h-14 rounded-2xl bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 font-bold text-sm shadow-sm select-none">
          PDF
        </div>
      );
    }
    if (['docx', 'doc'].includes(ext)) {
      return (
        <div className="w-14 h-14 rounded-2xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-sm shadow-sm select-none">
          DOC
        </div>
      );
    }
    if (['glb', 'gltf', 'obj', '3d'].includes(ext)) {
      return (
        <div className="w-14 h-14 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-sm select-none">
          <Box size={24} />
        </div>
      );
    }
    if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'].includes(ext)) {
      return (
        <div className="w-14 h-14 rounded-2xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shadow-sm select-none">
          <ImageIcon size={24} />
        </div>
      );
    }
    if (['txt', 'md', 'json', 'csv', 'xlsx', 'pptx'].includes(ext)) {
      return (
        <div className="w-14 h-14 rounded-2xl bg-slate-500/15 border border-slate-500/30 flex items-center justify-center text-slate-300 font-bold text-xs shadow-sm select-none">
          {ext.toUpperCase().slice(0, 4)}
        </div>
      );
    }
    return (
      <div className="w-14 h-14 rounded-2xl bg-gray-500/15 border border-gray-500/30 flex items-center justify-center text-gray-300 shadow-sm select-none">
        <FileText size={24} />
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#212121] text-white relative overflow-hidden">
      {/* Top Header */}
      <div className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-white/5 bg-[#1e1e1e]">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className={`h-8 w-8 text-gray-400 hover:text-white hover:bg-white/10 cursor-pointer mr-1 ${isSidebarOpen ? "hidden" : "flex"}`}
            onClick={onOpenSidebar}
            title="Open sidebar"
          >
            <Sidebar size={18} />
          </Button>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">Library</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* Search Box */}
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input 
              type="text" 
              placeholder="Search files or chats..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-[#282828] border border-white/10 rounded-full pl-9 pr-4 py-1.5 text-xs text-white w-40 sm:w-72 focus:border-white/20 outline-none transition-all placeholder:text-gray-500"
            />
          </div>
        </div>
      </div>

      {/* Filter Tabs & Selection Actions Toolbar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-white/5 bg-[#1c1c1c]">
        {/* Left Side: Category Tabs & Inline Selection Action Bar */}
        <div className="flex items-center gap-3">
          {/* Pill Category Tabs */}
          <div className="flex items-center gap-1.5 bg-[#262626] p-1 rounded-full border border-white/10">
            <button 
              onClick={() => setCategory("all")}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                category === "all" ? "bg-[#383838] text-white shadow-sm" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              All
            </button>
            <button 
              onClick={() => setCategory("images")}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                category === "images" ? "bg-[#383838] text-white shadow-sm" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Images
            </button>
            <button 
              onClick={() => setCategory("documents")}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                category === "documents" ? "bg-[#383838] text-white shadow-sm" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Documents
            </button>
          </div>

          {/* Inline Selection Action Bar (Adjacent to category tabs) */}
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 bg-[#28292c] px-3 py-1 rounded-full border border-blue-500/30 animate-in fade-in slide-in-from-left-2 duration-150 shadow-sm">
              <span className="text-xs font-semibold text-blue-400 pl-1 select-none">
                {selectedIds.size} selected
              </span>
              <div className="h-3.5 w-px bg-white/20"></div>
              
              {/* Download Button */}
              <button 
                onClick={handleDownload}
                disabled={isDownloading}
                className="flex items-center gap-1.5 text-xs text-gray-300 hover:text-white font-medium cursor-pointer transition-colors px-1 disabled:opacity-50"
                title="Download"
              >
                <Download size={13} />
                <span>{isDownloading ? "Downloading..." : "Download"}</span>
              </button>

              <div className="h-3.5 w-px bg-white/20"></div>

              {/* Delete Button */}
              <button 
                onClick={handleDelete}
                disabled={isDeleting}
                className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 font-medium cursor-pointer transition-colors px-1 disabled:opacity-50"
                title="Delete"
              >
                <Trash2 size={13} />
                <span>{isDeleting ? "Deleting..." : "Delete"}</span>
              </button>
            </div>
          )}
        </div>

        {/* Right Side: View Mode Toggle */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center bg-[#262626] border border-white/10 rounded-lg p-0.5">
            <button 
              onClick={() => setViewMode("list")}
              className={`p-1.5 rounded-md transition-colors cursor-pointer ${viewMode === "list" ? "bg-white/10 text-white" : "text-gray-400 hover:text-gray-200"}`}
              title="List view"
            >
              <ListIcon size={14} />
            </button>
            <button 
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded-md transition-colors cursor-pointer ${viewMode === "grid" ? "bg-white/10 text-white" : "text-gray-400 hover:text-gray-200"}`}
              title="Grid view"
            >
              <LayoutGrid size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-scroll [scrollbar-gutter:stable] custom-scrollbar p-6 relative">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400 space-y-2">
            <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
            <p className="text-xs text-gray-500">Loading library items...</p>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-500 space-y-3">
            <LayoutGrid size={40} className="opacity-25" />
            <p className="text-sm font-medium">No items found.</p>
            <p className="text-xs text-gray-600">Uploaded documents and images will show up here.</p>
          </div>
        ) : viewMode === "list" ? (
          <div className="w-full space-y-1">
            {/* Table Header */}
            <div className="flex items-center px-3 py-2 text-xs font-semibold text-gray-500 border-b border-white/5 select-none">
              <div className="w-9 shrink-0 flex items-center">
                <input 
                  ref={headerCheckboxRef}
                  type="checkbox"
                  checked={isAllSelected}
                  onChange={toggleSelectAll}
                  className="rounded border-white/20 bg-black/40 cursor-pointer"
                />
              </div>
              
              {/* Name Column */}
              <div 
                onClick={() => {
                  if (sort === "name") {
                    setSortOrder(prev => prev === "desc" ? "asc" : "desc");
                  } else {
                    setSort("name");
                    setSortOrder("asc");
                  }
                }}
                className="flex-1 min-w-0 pr-4 pl-1 cursor-pointer hover:text-gray-300 transition-colors select-none truncate"
              >
                Name {sort === "name" && (sortOrder === "desc" ? "↓" : "↑")}
              </div>

              {/* Conversation / Chat Column */}
              <div 
                onClick={() => {
                  if (sort === "chat") {
                    setSortOrder(prev => prev === "desc" ? "asc" : "desc");
                  } else {
                    setSort("chat");
                    setSortOrder("asc");
                  }
                }}
                className="w-44 sm:w-48 md:w-56 shrink-0 text-left pr-4 cursor-pointer hover:text-gray-300 transition-colors select-none truncate"
              >
                Conversation {sort === "chat" && (sortOrder === "desc" ? "↓" : "↑")}
              </div>

              {/* Modified Date Column */}
              <div 
                onClick={() => {
                  if (sort === "date") {
                    setSortOrder(prev => prev === "desc" ? "asc" : "desc");
                  } else {
                    setSort("date");
                    setSortOrder("desc");
                  }
                }}
                className="w-28 shrink-0 text-left cursor-pointer hover:text-gray-300 select-none"
              >
                Modified {sort === "date" && (sortOrder === "desc" ? "↓" : "↑")}
              </div>

              {/* Size Column */}
              <div 
                onClick={() => {
                  if (sort === "size") {
                    setSortOrder(prev => prev === "desc" ? "asc" : "desc");
                  } else {
                    setSort("size");
                    setSortOrder("desc");
                  }
                }}
                className="w-24 shrink-0 text-right cursor-pointer hover:text-gray-300 pr-2 select-none"
              >
                Size {sort === "size" && (sortOrder === "desc" ? "↓" : "↑")}
              </div>
            </div>

            {/* Rows */}
            {items.map(item => (
              <div 
                key={item.id} 
                className={`flex items-center px-3 py-2.5 hover:bg-white/5 rounded-xl cursor-pointer transition-colors group ${
                  selectedIds.has(item.id) ? "bg-white/5" : ""
                }`}
                onClick={() => toggleSelect(item.id)}
              >
                {/* Checkbox */}
                <div className="w-9 shrink-0 flex items-center" onClick={(e) => e.stopPropagation()}>
                  <input 
                    type="checkbox" 
                    checked={selectedIds.has(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    className="rounded border-white/20 bg-black/40 cursor-pointer"
                  />
                </div>

                {/* Name */}
                <div className="flex-1 min-w-0 pr-4 flex items-center gap-3">
                  {renderFileIcon(item.name)}
                  <span className="text-sm text-gray-200 group-hover:text-white truncate font-medium">
                    {item.name}
                  </span>
                </div>

                {/* Conversation */}
                <div className="w-44 sm:w-48 md:w-56 shrink-0 pr-4 text-xs truncate">
                  {item.chat_id && item.chat_title ? (
                    <span 
                      onClick={(e) => {
                        if (onSelectChat && item.chat_id) {
                          e.stopPropagation();
                          onSelectChat(item.chat_id);
                        }
                      }}
                      title={`Go to conversation: ${item.chat_title}`}
                      className="text-gray-400 group-hover:text-gray-200 hover:!text-blue-400 transition-colors inline-flex items-center gap-1.5 truncate max-w-full"
                    >
                      <MessageSquare size={13} className="shrink-0 opacity-70" />
                      <span className="truncate">{item.chat_title}</span>
                    </span>
                  ) : (
                    <span className="text-gray-600 font-mono text-[11px]">-</span>
                  )}
                </div>

                {/* Modified */}
                <div className="w-28 shrink-0 text-xs text-gray-400 font-mono">
                  {formatDate(item.modified)}
                </div>

                {/* Size */}
                <div className="w-24 shrink-0 text-xs text-gray-400 text-right font-mono pr-2">
                  {formatBytes(item.size_bytes)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* Grid View */
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {items.map(item => (
              <div 
                key={item.id} 
                onClick={() => toggleSelect(item.id)}
                className={`relative group cursor-pointer aspect-square rounded-2xl border bg-[#18181a] overflow-hidden hover:border-white/20 transition-all flex flex-col justify-between p-3.5 ${
                  selectedIds.has(item.id) ? "border-blue-500 ring-1 ring-blue-500 bg-blue-500/5" : "border-white/10"
                }`}
              >
                {/* Checkbox Top Left */}
                <div 
                  className="absolute top-3 left-3 z-10"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input 
                    type="checkbox" 
                    checked={selectedIds.has(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    className="w-4 h-4 rounded border-white/20 bg-black/40 cursor-pointer"
                  />
                </div>

                {/* Center Icon Area (True geometric center) */}
                <div className="flex-1 w-full flex items-center justify-center pt-2">
                  {renderGridFileIcon(item.name)}
                </div>

                {/* Bottom Info Bar */}
                <div className="w-full text-left pt-1">
                  <p className="text-xs font-medium text-gray-200 group-hover:text-white truncate">{item.name}</p>
                  <p className="text-[11px] text-gray-500 mt-0.5 truncate font-mono">
                    {item.chat_title ? item.chat_title : formatBytes(item.size_bytes)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
