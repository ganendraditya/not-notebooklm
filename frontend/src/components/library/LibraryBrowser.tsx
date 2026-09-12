"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { 
  Search, Trash2, Image as ImageIcon, 
  FileText, LayoutGrid, List as ListIcon, Download, Box,
  MessageSquare
} from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { useTranslation } from "@/lib/i18n";

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

export interface LibraryBrowserProps {
  initialCategory?: "all" | "documents" | "images";
  backendUrl: string;
  onSelectChat?: (chatId: string) => void;
  onItemChatSelect?: () => void;
  headerLeading?: React.ReactNode;
  headerTrailing?: React.ReactNode;
  containerClassName?: string;
}

export default function LibraryBrowser({
  initialCategory = "all",
  backendUrl,
  onSelectChat,
  onItemChatSelect,
  headerLeading,
  headerTrailing,
  containerClassName = "flex-1 flex flex-col h-full bg-app-bg text-app-text relative overflow-hidden"
}: LibraryBrowserProps) {
  const { t } = useTranslation();
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

  const fetchItems = useCallback(async (
    cat: string, 
    q: string, 
    sortBy: "date" | "size" | "name" | "chat", 
    order: "asc" | "desc"
  ) => {
    setIsLoading(true);
    try {
      const backendCat = cat === "all" ? "" : cat;
      const res = await fetch(`${backendUrl}/storage/files?category=${backendCat}`);
      if (res.ok) {
        const data = await res.json();
        const mappedItems: LibraryItem[] = (Array.isArray(data) ? data : []).map((raw: any) => ({
          id: raw.id || "",
          type: raw.category === "images" ? "image" : raw.category === "documents" ? "document" : "file",
          name: raw.filename || raw.raw_filename || "Untitled",
          raw_filename: raw.raw_filename || raw.filename || "",
          size_bytes: raw.size ?? raw.size_bytes ?? 0,
          modified: raw.uploaded_at || raw.modified || new Date().toISOString(),
          path: raw.id || raw.path || "",
          chat_id: raw.chat_id || null,
          chat_title: raw.chat_title || null,
        }));

        const filtered = mappedItems.filter((item) => 
          item.name.toLowerCase().includes(q.toLowerCase()) ||
          (item.chat_title || "").toLowerCase().includes(q.toLowerCase())
        );

        if (sortBy === "name") {
          filtered.sort((a, b) => 
            order === "asc" 
              ? a.name.localeCompare(b.name) 
              : b.name.localeCompare(a.name)
          );
        } else if (sortBy === "chat") {
          filtered.sort((a, b) => {
            const titleA = a.chat_title || "";
            const titleB = b.chat_title || "";
            return order === "asc" ? titleA.localeCompare(titleB) : titleB.localeCompare(titleA);
          });
        } else if (sortBy === "size") {
          filtered.sort((a, b) => 
            order === "asc" ? a.size_bytes - b.size_bytes : b.size_bytes - a.size_bytes
          );
        } else {
          filtered.sort((a, b) => {
            const timeA = new Date(a.modified).getTime();
            const timeB = new Date(b.modified).getTime();
            return order === "asc" ? timeA - timeB : timeB - timeA;
          });
        }

        setItems(filtered);
      }
    } catch (e) {
      console.error("Failed to load library items:", e);
    } finally {
      setIsLoading(false);
    }
  }, [backendUrl]);

  useEffect(() => {
    fetchItems(category, search, sort, sortOrder);
  }, [category, search, sort, sortOrder, fetchItems]);

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

  const renderFileIcon = (filename?: string) => {
    const ext = (filename || "").split(".").pop()?.toLowerCase() || "";
    if (ext === "pdf") {
      return (
        <div className="w-8 h-8 rounded-lg bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 font-bold text-[10px] shrink-0 select-none">
          PDF
        </div>
      );
    }
    if (["docx", "doc"].includes(ext)) {
      return (
        <div className="w-8 h-8 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-[10px] shrink-0 select-none">
          DOC
        </div>
      );
    }
    if (["glb", "gltf", "obj", "3d"].includes(ext)) {
      return (
        <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0 select-none">
          <Box size={15} />
        </div>
      );
    }
    if (["png", "jpg", "jpeg", "webp", "gif", "svg"].includes(ext)) {
      return (
        <div className="w-8 h-8 rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0 select-none">
          <ImageIcon size={15} />
        </div>
      );
    }
    if (["txt", "md", "json", "csv", "xlsx", "pptx"].includes(ext)) {
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

  const renderGridFileIcon = (filename?: string) => {
    const ext = (filename || "").split(".").pop()?.toLowerCase() || "";
    if (ext === "pdf") {
      return (
        <div className="w-14 h-14 rounded-2xl bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 font-bold text-sm shadow-sm select-none">
          PDF
        </div>
      );
    }
    if (["docx", "doc"].includes(ext)) {
      return (
        <div className="w-14 h-14 rounded-2xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-sm shadow-sm select-none">
          DOC
        </div>
      );
    }
    if (["glb", "gltf", "obj", "3d"].includes(ext)) {
      return (
        <div className="w-14 h-14 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-sm select-none">
          <Box size={24} />
        </div>
      );
    }
    if (["png", "jpg", "jpeg", "webp", "gif", "svg"].includes(ext)) {
      return (
        <div className="w-14 h-14 rounded-2xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shadow-sm select-none">
          <ImageIcon size={24} />
        </div>
      );
    }
    if (["txt", "md", "json", "csv", "xlsx", "pptx"].includes(ext)) {
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
    <div className={containerClassName}>
      {/* Top Header */}
      <div className="w-full h-[52px] px-4 flex items-center justify-between border-b border-app-border bg-app-sidebar shrink-0 z-20 select-none">
        <div className="flex items-center gap-2.5">
          {headerLeading}
          <span className="font-semibold text-sm text-app-text tracking-tight">{t("library.title")}</span>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Search Box */}
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-app-text-dim" />
            <input 
              type="text" 
              placeholder={t("library.searchPlaceholder")} 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-app-input border border-app-border rounded-full pl-9 pr-4 py-1 text-xs text-app-text w-40 sm:w-64 focus:border-blue-500/50 outline-none transition-all placeholder:text-app-text-dim h-7"
            />
          </div>
          {headerTrailing}
        </div>
      </div>

      {/* Filter Tabs & Selection Actions Toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-app-divider bg-app-sidebar">
        {/* Left Side: Category Tabs & Inline Selection Action Bar */}
        <div className="flex items-center gap-3">
          {/* Pill Category Tabs */}
          <div className="flex items-center gap-1.5 bg-app-surface p-1 rounded-full border border-app-border">
            <button 
              onClick={() => setCategory("all")}
              className={`px-3.5 sm:px-4 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                category === "all" ? "bg-app-item-active text-app-text shadow-sm" : "text-app-text-muted hover:text-app-text"
              }`}
            >
              {t("library.all")}
            </button>
            <button 
              onClick={() => setCategory("images")}
              className={`px-3.5 sm:px-4 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                category === "images" ? "bg-app-item-active text-app-text shadow-sm" : "text-app-text-muted hover:text-app-text"
              }`}
            >
              {t("library.images")}
            </button>
            <button 
              onClick={() => setCategory("documents")}
              className={`px-3.5 sm:px-4 py-1.5 rounded-full text-xs font-medium transition-all cursor-pointer ${
                category === "documents" ? "bg-app-item-active text-app-text shadow-sm" : "text-app-text-muted hover:text-app-text"
              }`}
            >
              {t("library.documents")}
            </button>
          </div>

          {/* Inline Selection Action Bar */}
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 bg-app-card px-3 py-1 rounded-full border border-blue-500/30 animate-in fade-in slide-in-from-left-2 duration-150 shadow-sm text-app-text">
              <span className="text-xs font-semibold text-blue-500 pl-1 select-none">
                {t("library.selectedCount", { count: selectedIds.size.toString() })}
              </span>
              <div className="h-3.5 w-px bg-app-divider"></div>
              
              {/* Download Button */}
              <Tooltip content={t("library.download")} side="bottom">
                <button 
                  onClick={handleDownload}
                  disabled={isDownloading}
                  className="flex items-center gap-1.5 text-xs text-app-text-muted hover:text-app-text font-medium cursor-pointer transition-colors px-1 disabled:opacity-50"
                  aria-label={t("library.download")}
                >
                  <Download size={13} />
                  <span>{isDownloading ? t("download.preparing") : t("library.download")}</span>
                </button>
              </Tooltip>

              <div className="h-3.5 w-px bg-app-divider"></div>

              {/* Delete Button */}
              <Tooltip content={t("library.delete")} side="bottom">
                <button 
                  onClick={handleDelete}
                  disabled={isDeleting}
                  className="flex items-center gap-1.5 text-xs text-red-500 hover:text-red-600 font-medium cursor-pointer transition-colors px-1 disabled:opacity-50"
                  aria-label={t("library.delete")}
                >
                  <Trash2 size={13} />
                  <span>{isDeleting ? t("library.deleting") : t("library.delete")}</span>
                </button>
              </Tooltip>
            </div>
          )}
        </div>

        {/* Right Side: View Mode Toggle */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center bg-app-surface border border-app-border rounded-lg p-0.5">
            <Tooltip content={t("library.listView")} side="bottom">
              <button 
                onClick={() => setViewMode("list")}
                className={`p-1.5 rounded-md transition-colors cursor-pointer ${viewMode === "list" ? "bg-app-item-active text-app-text" : "text-app-text-muted hover:text-app-text"}`}
                aria-label={t("library.listView")}
              >
                <ListIcon size={14} />
              </button>
            </Tooltip>
            <Tooltip content={t("library.gridView")} side="bottom">
              <button 
                onClick={() => setViewMode("grid")}
                className={`p-1.5 rounded-md transition-colors cursor-pointer ${viewMode === "grid" ? "bg-app-item-active text-app-text" : "text-app-text-muted hover:text-app-text"}`}
                aria-label={t("library.gridView")}
              >
                <LayoutGrid size={14} />
              </button>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-scroll [scrollbar-gutter:stable] custom-scrollbar px-4 py-4 relative">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-64 text-app-text-dim space-y-2">
            <div className="w-6 h-6 border-2 border-app-border border-t-blue-500 rounded-full animate-spin"></div>
            <p className="text-xs text-app-text-dim">{t("settings.loadingStorage")}</p>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-app-text-dim space-y-3">
            <LayoutGrid size={40} className="opacity-25" />
            <p className="text-sm font-medium">{t("library.noItems")}</p>
            <p className="text-xs text-app-text-dim">{t("library.noItemsDesc")}</p>
          </div>
        ) : viewMode === "list" ? (
          <div className="w-full space-y-1">
            {/* Table Header */}
            <div className="flex items-center px-2 py-2 text-xs font-semibold text-app-text-dim border-b border-app-divider select-none">
              <div className="w-9 shrink-0 flex items-center">
                <input 
                  ref={headerCheckboxRef}
                  type="checkbox"
                  checked={isAllSelected}
                  onChange={toggleSelectAll}
                  className="rounded border-app-border-strong bg-transparent cursor-pointer accent-blue-500"
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
                className="flex-1 min-w-0 pr-4 pl-1 cursor-pointer hover:text-app-text transition-colors select-none truncate"
              >
                {t("library.colName")} {sort === "name" && (sortOrder === "desc" ? "↓" : "↑")}
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
                className="w-44 sm:w-48 md:w-56 shrink-0 text-left pr-4 cursor-pointer hover:text-app-text transition-colors select-none truncate"
              >
                {t("library.colConversation")} {sort === "chat" && (sortOrder === "desc" ? "↓" : "↑")}
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
                className="w-28 shrink-0 text-left cursor-pointer hover:text-app-text select-none"
              >
                {t("library.colModified")} {sort === "date" && (sortOrder === "desc" ? "↓" : "↑")}
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
                className="w-24 shrink-0 text-right pr-2 cursor-pointer hover:text-app-text select-none"
              >
                {t("library.colSize")} {sort === "size" && (sortOrder === "desc" ? "↓" : "↑")}
              </div>
            </div>

            {/* Table Rows */}
            {items.map(item => (
              <div 
                key={item.id} 
                className={`flex items-center px-2 py-2.5 hover:bg-app-item-hover rounded-xl cursor-pointer transition-colors group ${
                  selectedIds.has(item.id) ? "bg-app-item-active" : ""
                }`}
                onClick={() => toggleSelect(item.id)}
              >
                {/* Checkbox */}
                <div className="w-9 shrink-0 flex items-center" onClick={(e) => e.stopPropagation()}>
                  <input 
                    type="checkbox" 
                    checked={selectedIds.has(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    className="rounded border-app-border-strong bg-transparent cursor-pointer accent-blue-500"
                  />
                </div>

                {/* Name */}
                <div className="flex-1 min-w-0 pr-4 flex items-center gap-3">
                  {renderFileIcon(item.name)}
                  <span className="text-sm text-app-text truncate font-medium">
                    {item.name}
                  </span>
                </div>

                {/* Conversation */}
                <div className="w-44 sm:w-48 md:w-56 shrink-0 pr-4 text-xs truncate">
                  {item.chat_id && item.chat_title ? (
                    <Tooltip content={t("library.goToConversation", { title: item.chat_title })} side="top">
                      <span 
                        onClick={(e) => {
                          if (onItemChatSelect) onItemChatSelect();
                          if (onSelectChat && item.chat_id) {
                            e.stopPropagation();
                            onSelectChat(item.chat_id);
                          }
                        }}
                        className="text-app-text-muted hover:!text-blue-500 transition-colors inline-flex items-center gap-1.5 truncate max-w-full cursor-pointer"
                        aria-label={t("library.goToConversation", { title: item.chat_title })}
                      >
                        <MessageSquare size={13} className="shrink-0 opacity-70" />
                        <span className="truncate">{item.chat_title}</span>
                      </span>
                    </Tooltip>
                  ) : (
                    <span className="text-app-text-dim font-mono text-[11px]">-</span>
                  )}
                </div>

                {/* Modified */}
                <div className="w-28 shrink-0 text-xs text-app-text-dim font-mono">
                  {formatDate(item.modified)}
                </div>

                {/* Size */}
                <div className="w-24 shrink-0 text-xs text-app-text-dim text-right font-mono pr-2">
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
                className={`relative group cursor-pointer aspect-square rounded-2xl border bg-app-card overflow-hidden hover:border-app-border-strong transition-all flex flex-col justify-between p-3.5 ${
                  selectedIds.has(item.id) ? "border-blue-500 ring-1 ring-blue-500 bg-blue-500/5" : "border-app-border"
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
                    className="w-4 h-4 rounded border-app-border-strong bg-transparent cursor-pointer accent-blue-500"
                  />
                </div>

                {/* Center Icon Area */}
                <div className="flex-1 w-full flex items-center justify-center pt-2">
                  {renderGridFileIcon(item.name)}
                </div>

                {/* Bottom Info Bar */}
                <div className="w-full text-left pt-1">
                  <p className="text-xs font-medium text-app-text truncate">{item.name}</p>
                  <p className="text-[11px] text-app-text-dim mt-0.5 truncate font-mono">
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
