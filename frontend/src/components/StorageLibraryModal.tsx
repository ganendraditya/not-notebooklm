"use client";

import { useState, useEffect } from "react";
import { 
  X, Search, Trash2, ArrowLeft, Image as ImageIcon, 
  FileText, LayoutGrid, List as ListIcon, Download
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface LibraryItem {
  id: string;
  type: "file" | "image" | "chat";
  name: string;
  chat_id: string | null;
  size_bytes: number;
  modified: string;
  path: string;
}

interface StorageLibraryModalProps {
  isOpen: boolean;
  onClose: () => void;
  category: "all" | "files" | "images";
  backendUrl: string;
}

export default function StorageLibraryModal({
  isOpen,
  onClose,
  category: initialCategory,
  backendUrl
}: StorageLibraryModalProps) {
  const [category, setCategory] = useState(initialCategory);
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("date");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setCategory(initialCategory);
      fetchItems(initialCategory, search, sort);
    }
  }, [isOpen, initialCategory]);

  useEffect(() => {
    if (isOpen) {
      fetchItems(category, search, sort);
    }
  }, [category, search, sort, isOpen]);

  const fetchItems = async (cat: string, q: string, s: string) => {
    setIsLoading(true);
    try {
      const backendCat = cat === 'all' ? '' : cat;
      const res = await fetch(`${backendUrl}/storage/files?category=${backendCat}`);
      if (res.ok) {
        const data = await res.json();
        let filtered = data.filter((item: any) => item.filename.toLowerCase().includes(q.toLowerCase()));
        if (s === 'name') {
           filtered.sort((a: any, b: any) => a.filename.localeCompare(b.filename));
        } else if (s === 'size') {
           filtered.sort((a: any, b: any) => b.size - a.size);
        }
        
        const mappedItems = filtered.map((item: any) => ({
          id: item.id,
          type: item.category === 'images' ? 'image' : 'file',
          name: item.filename,
          chat_id: null,
          size_bytes: item.size,
          modified: item.uploaded_at,
          path: item.id
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
        fetchItems(category, search, sort);
      }
    } catch (e) {
      console.error("Failed to delete items:", e);
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isOpen) return null;

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const toggleSelect = (id: string) => {
    const newSel = new Set(selectedIds);
    if (newSel.has(id)) newSel.delete(id);
    else newSel.add(id);
    setSelectedIds(newSel);
  };

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-[#212124] animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#1b1c1e]">
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors">
            <ArrowLeft size={20} />
          </button>
          <h2 className="text-lg font-semibold text-white">Storage Library</h2>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors">
          <X size={20} />
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-white/5 bg-[#18181b]">
        <div className="flex items-center gap-2 bg-[#212124] p-1 rounded-lg border border-white/10">
          <button 
            onClick={() => setCategory("all")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${category === "all" ? "bg-white/10 text-white" : "text-gray-400 hover:text-gray-200"}`}
          >
            All
          </button>
          <button 
            onClick={() => setCategory("images")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${category === "images" ? "bg-white/10 text-white" : "text-gray-400 hover:text-gray-200"}`}
          >
            Images
          </button>
          <button 
            onClick={() => setCategory("files")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${category === "files" ? "bg-white/10 text-white" : "text-gray-400 hover:text-gray-200"}`}
          >
            Documents
          </button>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
            <input 
              type="text" 
              placeholder="Search..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-[#212124] border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-sm text-white w-48 focus:border-white/20 outline-none"
            />
          </div>
          <select 
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="bg-[#212124] border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-300 outline-none"
          >
            <option value="date">Date Modified</option>
            <option value="size">File Size</option>
            <option value="name">Name</option>
          </select>
          <div className="flex items-center bg-[#212124] border border-white/10 rounded-lg p-0.5">
            <button 
              onClick={() => setViewMode("list")}
              className={`p-1.5 rounded-md ${viewMode === "list" ? "bg-white/10 text-white" : "text-gray-400"}`}
            >
              <ListIcon size={16} />
            </button>
            <button 
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded-md ${viewMode === "grid" ? "bg-white/10 text-white" : "text-gray-400"}`}
            >
              <LayoutGrid size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6 relative">
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-gray-400">Loading library...</div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-2">
            <LayoutGrid size={48} className="opacity-20" />
            <p>No items found.</p>
          </div>
        ) : viewMode === "list" ? (
          <div className="space-y-1">
            <div className="flex items-center px-4 py-2 text-xs font-semibold text-gray-500 border-b border-white/5 uppercase tracking-wider">
              <div className="w-8"></div>
              <div className="flex-1">Name</div>
              <div className="w-32">Date</div>
              <div className="w-24 text-right">Size</div>
            </div>
            {items.map(item => (
              <label key={item.id} className="flex items-center px-4 py-3 hover:bg-white/5 rounded-xl cursor-pointer group">
                <div className="w-8">
                  <input 
                    type="checkbox" 
                    checked={selectedIds.has(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    className="rounded border-white/20 bg-black/20"
                  />
                </div>
                <div className="flex-1 flex items-center gap-3 min-w-0">
                  <div className="p-2 bg-white/5 rounded-lg text-gray-400">
                    {item.type === "image" ? <ImageIcon size={16} /> : <FileText size={16} />}
                  </div>
                  <span className="text-sm text-gray-200 truncate pr-4">{item.name}</span>
                </div>
                <div className="w-32 text-xs text-gray-500">{item.modified ? new Date(item.modified).toLocaleDateString() : '-'}</div>
                <div className="w-24 text-xs text-gray-500 text-right">{formatBytes(item.size_bytes)}</div>
              </label>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {items.map(item => (
              <label key={item.id} className="relative group cursor-pointer aspect-square rounded-xl border border-white/10 bg-[#18181b] overflow-hidden hover:border-white/30 transition-colors flex flex-col items-center justify-center">
                <div className="absolute top-2 left-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                  <input 
                    type="checkbox" 
                    checked={selectedIds.has(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    className="w-4 h-4 rounded"
                  />
                </div>
                {item.type === "image" ? (
                  <div className="absolute inset-0 bg-white/5 flex items-center justify-center text-gray-600">
                    <ImageIcon size={32} />
                  </div>
                ) : (
                  <FileText size={32} className="text-gray-600" />
                )}
                <div className="absolute inset-x-0 bottom-0 bg-black/60 backdrop-blur-sm p-2">
                  <p className="text-xs text-white truncate">{item.name}</p>
                  <p className="text-[10px] text-gray-400">{formatBytes(item.size_bytes)}</p>
                </div>
              </label>
            ))}
          </div>
        )}

        {/* Floating Selection Action Bar */}
        {selectedIds.size > 0 && (
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-blue-600 rounded-full px-4 py-2.5 shadow-2xl flex items-center gap-4 animate-in slide-in-from-bottom-10">
            <span className="text-sm text-white font-medium pl-2">
              {selectedIds.size} selected
            </span>
            <div className="h-4 w-px bg-white/20"></div>
            <button 
              onClick={handleDelete}
              disabled={isDeleting}
              className="flex items-center gap-2 text-sm text-white/90 hover:text-white px-2"
            >
              <Trash2 size={16} />
              {isDeleting ? "Deleting..." : "Delete"}
            </button>
            <button 
              onClick={() => setSelectedIds(new Set())}
              className="p-1 rounded-full hover:bg-white/10 text-white/70"
            >
              <X size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
