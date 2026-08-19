"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Plus, 
  Check, 
  Minus,
  Trash2, 
  Download,
  Sidebar, 
  FileText, 
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Document } from "@/app/ChatClient";

interface RightSidebarProps {
  activeChatId: string | null;
  documents: Document[];
  onDocumentAdded: (doc: Document) => void;
  onDocumentDeleted?: (id: number) => void;
  onBulkDocumentsDeleted?: (ids: number[]) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  backendUrl: string;
  onClose: () => void;
}

export default function RightSidebar({ 
  activeChatId, 
  documents, 
  onDocumentAdded,
  onDocumentDeleted,
  onBulkDocumentsDeleted,
  onEnsureChatSession,
  backendUrl,
  onClose
}: RightSidebarProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [selectedDocs, setSelectedDocs] = useState<Record<number, boolean>>({});
  
  // Sorting state & dropdown
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [isSortMenuOpen, setIsSortMenuOpen] = useState(false);
  const sortMenuRef = useRef<HTMLDivElement>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Close sort menu on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sortMenuRef.current && !sortMenuRef.current.contains(event.target as Node)) {
        setIsSortMenuOpen(false);
      }
    };
    if (isSortMenuOpen) {
      window.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isSortMenuOpen]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0]) return;
    
    setIsUploading(true);
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
      let currentChatId = activeChatId;
      if (!currentChatId && onEnsureChatSession) {
        currentChatId = await onEnsureChatSession(file.name.replace(/\.[^/.]+$/, ""));
      }

      if (!currentChatId) {
        alert("Failed to initialize chat session.");
        return;
      }

      const res = await fetch(`${backendUrl}/chats/${currentChatId}/upload`, {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        const newDoc = await res.json();
        onDocumentAdded(newDoc);
      } else {
        const err = await res.json();
        alert(`Upload failed: ${err.detail || "An error occurred"}`);
      }
    } catch (err) {
      console.error("Upload failed", err);
      alert("Failed to connect to server for document upload.");
    } finally {
      setIsUploading(false);
      if (e.target) e.target.value = "";
    }
  };

  // Selection logic
  const isAllSelected = documents.length > 0 && documents.every(d => selectedDocs[d.id] !== false);
  const isSomeSelected = documents.some(d => selectedDocs[d.id] !== false);
  const isPartiallySelected = isSomeSelected && !isAllSelected;

  const getFileBadgeInfo = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase() || "doc";
    if (ext === "pdf") {
      return { label: "PDF", bg: "bg-red-950/70 border-red-800/80 text-red-400" };
    } else if (ext === "docx" || ext === "doc") {
      return { label: "DOC", bg: "bg-blue-950/70 border-blue-800/80 text-blue-400" };
    } else if (ext === "bib" || ext === "bibtex") {
      return { label: "BIB", bg: "bg-amber-950/70 border-amber-800/80 text-amber-400" };
    } else if (ext === "ris") {
      return { label: "RIS", bg: "bg-orange-950/70 border-orange-800/80 text-orange-400" };
    } else if (ext === "csv" || ext === "tsv") {
      return { label: "CSV", bg: "bg-emerald-950/70 border-emerald-800/80 text-emerald-400" };
    } else if (ext === "md") {
      return { label: "MD", bg: "bg-purple-950/70 border-purple-800/80 text-purple-400" };
    } else {
      return { label: "TXT", bg: "bg-gray-800/80 border-gray-700 text-gray-300" };
    }
  };

  const toggleDocSelection = (docId: number) => {
    setSelectedDocs(prev => {
      const current = prev[docId] !== undefined ? prev[docId] : true;
      return {
        ...prev,
        [docId]: !current
      };
    });
  };

  const handleToggleSelectAll = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const nextState = !isAllSelected;
    const updated: Record<number, boolean> = {};
    documents.forEach(d => {
      updated[d.id] = nextState;
    });
    setSelectedDocs(updated);
  };

  // Sort documents based on sortBy
  const sortedDocuments = [...documents].sort((a, b) => {
    if (sortBy === "title") {
      return a.filename.localeCompare(b.filename);
    } else {
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
    }
  });

  const [showBulkDeleteConfirm, setShowBulkDeleteConfirm] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [isBulkDownloading, setIsBulkDownloading] = useState(false);

  const selectedDocList = sortedDocuments.filter(d => selectedDocs[d.id] !== false);
  const selectedCount = selectedDocList.length;

  const handleBulkDownload = async () => {
    if (!activeChatId || selectedCount === 0 || isBulkDownloading) return;
    setIsBulkDownloading(true);
    try {
      const docIds = selectedDocList.map(d => d.id);
      
      if (docIds.length === 1) {
        const doc = selectedDocList[0];
        const link = document.createElement("a");
        link.href = `${backendUrl}/chats/${activeChatId}/documents/${doc.id}/download`;
        link.download = doc.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/bulk_download`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ doc_ids: docIds })
        });
        
        if (!res.ok) throw new Error("Failed to download ZIP archive");
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `NotbookLM_Sources_${docIds.length}_files.zip`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error("Bulk download error:", err);
    } finally {
      setIsBulkDownloading(false);
    }
  };

  const handleConfirmBulkDelete = async () => {
    if (!activeChatId || selectedCount === 0 || isBulkDeleting) return;
    setIsBulkDeleting(true);
    try {
      const docIds = selectedDocList.map(d => d.id);
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/bulk_delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_ids: docIds })
      });
      if (res.ok) {
        if (onBulkDocumentsDeleted) {
          onBulkDocumentsDeleted(docIds);
        } else if (onDocumentDeleted) {
          docIds.forEach(id => onDocumentDeleted(id));
        }
        setShowBulkDeleteConfirm(false);
      }
    } catch (err) {
      console.error("Bulk delete error:", err);
    } finally {
      setIsBulkDeleting(false);
    }
  };

  return (
    <aside className="w-80 h-full bg-[#1e1f20] border-l border-white/10 flex flex-col shrink-0 select-none z-10 transition-all">
      {/* 1. Header: Sources Title & Collapse Button */}
      <div className="p-4 flex items-center justify-between border-b border-white/5">
        <h2 className="text-base font-semibold text-white tracking-tight">Sources</h2>
        <Button 
          variant="ghost" 
          size="icon" 
          className="h-8 w-8 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg cursor-pointer"
          onClick={onClose}
          title="Close Sources"
        >
          <Sidebar size={16} className="rotate-180" />
        </Button>
      </div>

      {/* Hidden File Input for Multi-format Document Upload */}
      <input
        ref={fileInputRef}
        type="file"
        id="sources-file-upload"
        className="hidden"
        accept=".pdf,.docx,.doc,.txt,.md,.bib,.bibtex,.ris,.csv,.tsv"
        onChange={handleFileUpload}
        disabled={isUploading}
      />

      <div className="p-3.5 space-y-2.5 flex-1 flex flex-col overflow-y-auto custom-scrollbar min-h-0">
        {/* 2. Prominent '+ Add sources' Button (NotebookLM Style) */}
        <div>
          <Button
            variant="outline"
            className="w-full h-11 rounded-full bg-[#262729] hover:bg-[#2e3033] border border-white/15 text-gray-100 hover:text-white font-medium text-sm flex items-center justify-center gap-2 cursor-pointer shadow-sm transition-colors"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            {isUploading ? (
              <>
                <Loader2 size={16} className="animate-spin text-blue-400" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <Plus size={18} className="text-gray-300" />
                <span>Add sources</span>
              </>
            )}
          </Button>
          <p className="text-[10.5px] text-gray-500 text-center mt-1.5">
            Supports PDF, Word (.docx), TXT, Markdown, BibTeX, RIS, CSV
          </p>
        </div>

        {/* 3. Controls Row: Sort (3 descending bars), Contextual Actions (Download & Delete), and Select All */}
        <div className="flex items-center justify-between pt-1 px-0 text-xs text-gray-400 relative">
          <div className="flex items-center gap-1">
            {/* Sort Button & Dropdown */}
            <div className="relative" ref={sortMenuRef}>
              <button 
                onClick={() => setIsSortMenuOpen(prev => !prev)}
                className="w-6 h-6 -ml-1 rounded text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-colors cursor-pointer flex items-center justify-center"
                title="Sort sources"
              >
                <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" className="opacity-90">
                  <rect x="2" y="3" width="12" height="1.6" rx="0.8" />
                  <rect x="2" y="7.2" width="8" height="1.6" rx="0.8" />
                  <rect x="2" y="11.4" width="4.5" height="1.6" rx="0.8" />
                </svg>
              </button>

              {/* Sort Dropdown Menu */}
              {isSortMenuOpen && (
                <div className="absolute left-0 top-7 z-30 w-32 rounded-xl bg-[#28292c] border border-white/15 shadow-2xl p-1 text-xs animate-in fade-in zoom-in-95 duration-100">
                  <button
                    onClick={() => { setSortBy("title"); setIsSortMenuOpen(false); }}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer ${
                      sortBy === "title" ? "bg-blue-600 text-white font-medium" : "text-gray-300 hover:bg-white/5"
                    }`}
                  >
                    <span>Title</span>
                    {sortBy === "title" && <Check size={11} />}
                  </button>
                  <button
                    onClick={() => { setSortBy("date"); setIsSortMenuOpen(false); }}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer ${
                      sortBy === "date" ? "bg-blue-600 text-white font-medium" : "text-gray-300 hover:bg-white/5"
                    }`}
                  >
                    <span>Date added</span>
                    {sortBy === "date" && <Check size={11} />}
                  </button>
                </div>
              )}
            </div>

            {/* Always Rendered Action Icon Buttons with Clean Disabled State */}
            <div className="flex items-center gap-1">
              {/* Download Button */}
              <button
                onClick={handleBulkDownload}
                disabled={selectedCount === 0 || isBulkDownloading}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  selectedCount > 0
                    ? "text-gray-400 hover:text-gray-200 hover:bg-white/5 cursor-pointer"
                    : "text-gray-600 opacity-40 cursor-not-allowed"
                }`}
                title={selectedCount > 0 ? `Download ${selectedCount} selected file(s)` : "Select sources to download"}
              >
                {isBulkDownloading ? (
                  <Loader2 size={15} className="animate-spin text-blue-400" />
                ) : (
                  <Download size={15} />
                )}
              </button>

              {/* Delete Button */}
              <button
                onClick={() => setShowBulkDeleteConfirm(true)}
                disabled={selectedCount === 0 || isBulkDeleting}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  selectedCount > 0
                    ? "text-gray-400 hover:text-red-400 hover:bg-white/5 cursor-pointer"
                    : "text-gray-600 opacity-40 cursor-not-allowed"
                }`}
                title={selectedCount > 0 ? `Delete ${selectedCount} selected file(s)` : "Select sources to delete"}
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>

          {/* Select all label and checkbox (Clickable ONLY on the checkbox) */}
          <div className="flex items-center gap-2 pr-0.5 whitespace-nowrap select-none">
            <span className="text-[11px] font-medium text-gray-400 select-none">Select all</span>
            <button
              type="button"
              onClick={handleToggleSelectAll}
              className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 cursor-pointer hover:border-gray-300 ${
                isAllSelected || isPartiallySelected ? "bg-blue-600 border-blue-600 text-white" : "border-gray-500 bg-transparent"
              }`}
              title={isAllSelected ? "Unselect all" : "Select all"}
            >
              {isAllSelected ? (
                <Check size={10} strokeWidth={3} />
              ) : isPartiallySelected ? (
                <Minus size={10} strokeWidth={3} />
              ) : null}
            </button>
          </div>
        </div>

        {/* 4. Saved Documents / Sources List (Compact height per item, flush left & right align) */}
        <div className="flex-1 space-y-0.5 pt-0.5">
          {sortedDocuments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center text-gray-400 px-3">
              <FileText size={30} className="text-gray-600 mb-2 stroke-[1.5]" />
              <h4 className="text-xs font-semibold text-gray-300">Saved sources will appear here</h4>
              <p className="text-[11px] text-gray-500 mt-1 max-w-[220px] leading-relaxed">
                Add files, websites, or more. Then ask questions or create things based on these sources.
              </p>
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="text-[11px] text-blue-400 hover:text-blue-300 underline font-medium mt-2 cursor-pointer"
              >
                Drop files here or add a source
              </button>
            </div>
          ) : (
            sortedDocuments.map((doc) => {
              const isChecked = selectedDocs[doc.id] !== undefined ? selectedDocs[doc.id] : true;
              const badge = getFileBadgeInfo(doc.filename);

              return (
                <div
                  key={doc.id}
                  onClick={() => toggleDocSelection(doc.id)}
                  className="flex items-center justify-between py-1.5 pl-0.5 pr-0.5 rounded-lg bg-transparent hover:bg-white/5 transition-colors cursor-pointer group"
                >
                  {/* Left: Compact Format Badge + File Name */}
                  <div className="flex items-center gap-2 min-w-0 flex-1 mr-1.5">
                    <div className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 ${badge.bg}`}>
                      <span className="text-[7.5px] font-bold tracking-tighter uppercase font-mono">{badge.label}</span>
                    </div>

                    <span className="text-[11.5px] text-gray-300 truncate group-hover:text-white font-normal" title={doc.filename}>
                      {doc.filename}
                    </span>
                  </div>

                  {/* Right: Checkbox */}
                  <div className="flex items-center shrink-0">
                    <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
                      isChecked ? "bg-blue-600 border-blue-600 text-white" : "border-gray-500 bg-transparent"
                    }`}>
                      {isChecked && <Check size={9} strokeWidth={3} />}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Centered Modal for Bulk Delete Confirmation */}
      {showBulkDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div className="bg-[#28292c] border border-white/10 rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150">
            <div className="space-y-1.5">
              <h3 className="text-base font-semibold text-white">Delete {selectedCount} selected source(s)?</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Deleted documents will no longer be used by the AI to answer questions in this chat session.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowBulkDeleteConfirm(false)}
                disabled={isBulkDeleting}
                className="text-xs text-gray-300 hover:text-white hover:bg-white/10 rounded-lg px-3.5 h-8 cursor-pointer"
              >
                Cancel
              </Button>

              <Button
                size="sm"
                onClick={handleConfirmBulkDelete}
                disabled={isBulkDeleting}
                className="text-xs bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow flex items-center gap-1.5"
              >
                {isBulkDeleting ? (
                  <>
                    <Loader2 size={12} className="animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete ({selectedCount})</span>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
