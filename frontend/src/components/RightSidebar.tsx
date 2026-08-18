"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Plus, 
  Check, 
  Minus,
  Trash2, 
  Download,
  Sparkles, 
  Sidebar, 
  FileText, 
  Loader2, 
  ArrowRight, 
  BookOpen,
  Search,
  ExternalLink,
  ChevronRight,
  X
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Document } from "@/app/ChatClient";

interface PaperCandidate {
  title: string;
  year: string;
  doi: string;
  url: string;
  snippet: string;
}

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
  const [hoveredDocId, setHoveredDocId] = useState<number | null>(null);
  
  // Sorting state & dropdown
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [isSortMenuOpen, setIsSortMenuOpen] = useState(false);
  const sortMenuRef = useRef<HTMLDivElement>(null);

  // View mode: 'sources' (standard panel) or 'discovery' (expanded full view)
  const [viewMode, setViewMode] = useState<"sources" | "discovery">("sources");

  // Search query & Fast Research state
  const [searchQuery, setSearchQuery] = useState("");
  const [isResearching, setIsResearching] = useState(false);
  const [researchResults, setResearchResults] = useState<PaperCandidate[] | null>(null);
  const [requestedTarget, setRequestedTarget] = useState<number | null>(null);
  const [selectedCandidates, setSelectedCandidates] = useState<Record<number, boolean>>({});
  const [isImportingResults, setIsImportingResults] = useState(false);
  const [isImportedSuccess, setIsImportedSuccess] = useState(false);

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
        alert("Gagal menginisialisasi sesi chat.");
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
        alert(`Gagal upload: ${err.detail || "Terjadi kesalahan"}`);
      }
    } catch (err) {
      console.error("Upload failed", err);
      alert("Gagal menghubungi server untuk upload dokumen.");
    } finally {
      setIsUploading(false);
      if (e.target) e.target.value = '';
    }
  };

  const handleSearchSources = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = searchQuery.trim();
    if (!query || isResearching) return;

    setIsResearching(true);
    setResearchResults(null);
    setIsImportedSuccess(false);

    try {
      // Dynamically extract requested count (e.g. "cariin 50 paper" -> limit=50)
      const numMatch = query.match(/(\d+)\s*(?:paper|jurnal|artikel|sumber|sources|buah|biji)/i);
      const parsedNum = numMatch ? parseInt(numMatch[1], 10) : null;
      const targetLimit = parsedNum ? Math.min(Math.max(parsedNum, 1), 100) : 10;
      setRequestedTarget(parsedNum);

      const res = await fetch(`${backendUrl}/search_papers?query=${encodeURIComponent(query)}&limit=${targetLimit}`);
      if (res.ok) {
        const data: PaperCandidate[] = await res.json();
        setResearchResults(data);
        
        // Select all by default
        const initSelected: Record<number, boolean> = {};
        data.forEach((_, idx) => {
          initSelected[idx] = true;
        });
        setSelectedCandidates(initSelected);
      }
    } catch (err) {
      console.error("Failed to search papers:", err);
    } finally {
      setIsResearching(false);
    }
  };

  const toggleCandidateSelection = (index: number) => {
    setSelectedCandidates(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const handleToggleSelectAllCandidates = () => {
    if (!researchResults) return;
    const allSelected = researchResults.every((_, idx) => selectedCandidates[idx]);
    const nextState = !allSelected;
    const updated: Record<number, boolean> = {};
    researchResults.forEach((_, idx) => {
      updated[idx] = nextState;
    });
    setSelectedCandidates(updated);
  };

  const handleImportFastResearch = async () => {
    if (!researchResults || researchResults.length === 0) return;

    const toImport = researchResults.filter((_, idx) => selectedCandidates[idx]);
    if (toImport.length === 0) return;

    setIsImportingResults(true);
    try {
      let currentChatId = activeChatId;
      if (!currentChatId && onEnsureChatSession) {
        currentChatId = await onEnsureChatSession(searchQuery || toImport[0]?.title || "Riset Paper");
      }

      if (!currentChatId) {
        alert("Gagal menginisialisasi sesi chat.");
        return;
      }

      const res = await fetch(`${backendUrl}/chats/${currentChatId}/import_sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: toImport })
      });
      if (res.ok) {
        const createdDocs: Document[] = await res.json();
        createdDocs.forEach(doc => onDocumentAdded(doc));
        setIsImportedSuccess(true);
        setTimeout(() => {
          setResearchResults(null);
          setSearchQuery("");
          setIsImportedSuccess(false);
          setViewMode("sources");
        }, 800);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Gagal mengimpor paper: ${err.detail || "Terjadi kesalahan server"}`);
      }
    } catch (err) {
      console.error("Failed to import sources:", err);
      alert("Gagal menghubungi server untuk mengimpor paper.");
    } finally {
      setIsImportingResults(false);
    }
  };

  const handleDelete = async (docId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!activeChatId) return;
    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/${docId}`, {
        method: "DELETE"
      });
      if (res.ok && onDocumentDeleted) {
        onDocumentDeleted(docId);
      }
    } catch (err) {
      console.error("Failed to delete doc:", err);
    }
  };

  // Dynamically compute selection states
  const isAllSelected = documents.length > 0 && documents.every(d => selectedDocs[d.id] !== false);
  const isSomeSelected = documents.some(d => selectedDocs[d.id] !== false);
  const isPartiallySelected = isSomeSelected && !isAllSelected;

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
        // Single file: download original file directly
        const doc = selectedDocList[0];
        const link = document.createElement("a");
        link.href = `${backendUrl}/chats/${activeChatId}/documents/${doc.id}/download`;
        link.download = doc.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        // Multi-file (>= 2): bundle into a single clean ZIP archive
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

  const candidateSelectedCount = researchResults 
    ? researchResults.filter((_, idx) => selectedCandidates[idx]).length 
    : 0;

  // ==========================================
  // VIEW MODE 2: EXPANDED 'Sources > Source Discovery'
  // ==========================================
  if (viewMode === "discovery" && researchResults) {
    return (
      <aside className="w-80 sm:w-96 h-full bg-[#1e1f20] border-l border-white/10 flex flex-col shrink-0 select-none z-10 transition-all">
        {/* Header Breadcrumbs */}
        <div className="p-3.5 px-4 flex items-center justify-between border-b border-white/5">
          <div className="flex items-center gap-1.5 text-xs text-gray-400">
            <button 
              onClick={() => setViewMode("sources")}
              className="hover:text-white transition-colors cursor-pointer"
            >
              Sources
            </button>
            <ChevronRight size={13} className="text-gray-600" />
            <span className="text-white font-medium">Source Discovery</span>
          </div>

          <Button 
            variant="ghost" 
            size="icon" 
            className="h-7 w-7 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg cursor-pointer"
            onClick={() => setViewMode("sources")}
            title="Kembali ke Sources"
          >
            <X size={15} />
          </Button>
        </div>

        {/* Discovery Content */}
        <div className="p-4 space-y-3 flex-1 flex flex-col overflow-hidden">
          {/* Query Pill */}
          <div className="p-2.5 px-3 rounded-xl bg-white/5 border border-white/10 flex items-center gap-2 text-xs text-white">
            <Search size={13} className="text-gray-400 shrink-0" />
            <span className="truncate font-medium">{searchQuery || "Search query"}</span>
          </div>

          <p className="text-[11px] text-gray-400 leading-relaxed">
            {requestedTarget && researchResults.length < requestedTarget
              ? `Ditemukan ${researchResults.length} dari target ${requestedTarget} paper relevan (ketersediaan literatur spesifik pada repositori ilmiah terbatas).`
              : `Ditemukan ${researchResults.length} paper ilmiah yang relevan dengan kata kunci riset Anda.`}
          </p>

          {/* Select all row - aligned with p-2.5 item cards */}
          <div className="flex items-center justify-end text-xs text-gray-400 pt-1 px-2.5">
            <div 
              className="flex items-center gap-1.5 cursor-pointer hover:text-gray-200 transition-colors"
              onClick={handleToggleSelectAllCandidates}
            >
              <span className="text-[11px] font-medium">Select all</span>
              <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
                researchResults.every((_, idx) => selectedCandidates[idx]) ? "bg-blue-600 border-blue-600 text-white" : "border-gray-500 bg-transparent"
              }`}>
                {researchResults.every((_, idx) => selectedCandidates[idx]) && <Check size={10} strokeWidth={3} />}
              </div>
            </div>
          </div>

          {/* Scrollable Paper List */}
          <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar min-h-0">
            {researchResults.map((paper, idx) => {
              const isChecked = !!selectedCandidates[idx];

              return (
                <div
                  key={idx}
                  onClick={() => toggleCandidateSelection(idx)}
                  className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                    isChecked 
                      ? "bg-blue-950/30 border-blue-500/30 text-white" 
                      : "bg-[#28292c] border-white/5 text-gray-300 hover:border-white/20"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2.5">
                    <div className="flex items-start gap-2 min-w-0 flex-1">
                      <div className="w-5 h-5 rounded bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                        <BookOpen size={11} className="text-blue-400" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1">
                          <h5 className="text-xs font-semibold text-white truncate leading-snug">
                            {paper.title}
                          </h5>
                          {paper.url && (
                            <a 
                              href={paper.url} 
                              target="_blank" 
                              rel="noreferrer" 
                              onClick={(e) => e.stopPropagation()} 
                              className="text-blue-400 hover:text-blue-300 shrink-0"
                            >
                              <ExternalLink size={10} />
                            </a>
                          )}
                        </div>
                        {paper.snippet && (
                          <p className="text-[11px] text-gray-400 line-clamp-2 leading-relaxed mt-1">
                            {paper.snippet}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className={`w-3.5 h-3.5 rounded border mt-0.5 flex items-center justify-center shrink-0 transition-colors ${
                      isChecked ? "bg-blue-600 border-blue-600 text-white" : "border-gray-500 bg-transparent"
                    }`}>
                      {isChecked && <Check size={10} strokeWidth={3} />}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Sticky Bottom Actions Bar */}
          <div className="pt-3 border-t border-white/10 flex items-center justify-between">
            <span className="text-xs text-gray-400 font-medium">
              {candidateSelectedCount} sources selected
            </span>

            <Button
              size="sm"
              onClick={handleImportFastResearch}
              disabled={isImportingResults || candidateSelectedCount === 0 || isImportedSuccess}
              className="h-8 px-5 rounded-full bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow cursor-pointer disabled:opacity-50"
            >
              {isImportingResults ? (
                <>
                  <Loader2 size={12} className="animate-spin" />
                  <span>Importing...</span>
                </>
              ) : isImportedSuccess ? (
                <>
                  <Check size={12} />
                  <span>Imported!</span>
                </>
              ) : (
                <span>Import</span>
              )}
            </Button>
          </div>
        </div>
      </aside>
    );
  }

  // ==========================================
  // VIEW MODE 1: STANDARD SOURCES PANEL
  // ==========================================
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
          title="Tutup Sources"
        >
          <Sidebar size={16} className="rotate-180" />
        </Button>
      </div>

      {/* Hidden File Input for PDF Upload */}
      <input
        ref={fileInputRef}
        type="file"
        id="sources-file-upload"
        className="hidden"
        accept=".pdf"
        onChange={handleFileUpload}
        disabled={isUploading}
      />

      <div className="p-3.5 space-y-2.5 flex-1 flex flex-col overflow-y-auto custom-scrollbar min-h-0">
        {/* 2. Prominent '+ Add sources' Button (NotebookLM Style) */}
        <Button
          variant="outline"
          className="w-full h-11 rounded-full bg-[#262729] hover:bg-[#2e3033] border border-white/15 text-gray-100 hover:text-white font-medium text-sm flex items-center justify-center gap-2 cursor-pointer shadow-sm transition-colors"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
        >
          {isUploading ? (
            <>
              <Loader2 size={16} className="animate-spin text-blue-400" />
              <span>Mengunggah...</span>
            </>
          ) : (
            <>
              <Plus size={18} className="text-gray-300" />
              <span>Add sources</span>
            </>
          )}
        </Button>

        {/* 3. Compact Search Bar */}
        <form onSubmit={handleSearchSources} className="relative flex items-center">
          <input 
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search the web for new sources"
            disabled={isResearching}
            className="w-full h-10 pl-8 pr-8 rounded-xl bg-[#28292c] border border-white/10 text-xs text-white placeholder:text-gray-400 focus:outline-none focus:border-blue-500/60 transition-colors"
          />
          <Search size={13} className="absolute left-2.5 text-gray-400 pointer-events-none" />
          
          {isResearching ? (
            <Loader2 size={13} className="absolute right-2.5 animate-spin text-blue-400" />
          ) : searchQuery.trim() ? (
            <button
              type="submit"
              className="absolute right-1.5 p-1 rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors cursor-pointer"
              title="Cari Sources"
            >
              <ArrowRight size={11} />
            </button>
          ) : null}
        </form>

        {/* 4. While Searching: 'Researching...' Pulse Card */}
        {isResearching && (
          <div className="rounded-2xl bg-gradient-to-r from-blue-950/60 via-[#22242a] to-indigo-950/50 border border-blue-500/30 p-3.5 flex items-center gap-3 animate-pulse shadow-sm">
            <Sparkles size={16} className="text-blue-400 animate-spin" />
            <span className="text-xs font-medium text-blue-100">Researching...</span>
          </div>
        )}

        {/* 5. When Search Finished: 'Research completed!' Widget */}
        {researchResults && !isResearching && (
          <div className="rounded-2xl bg-[#28292c] border border-white/10 p-3.5 space-y-2.5 animate-in fade-in duration-200 shadow-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-white">
                <Sparkles size={14} className="text-blue-400" />
                <span>Research completed!</span>
              </div>
              <button 
                onClick={() => setViewMode("discovery")}
                className="text-[11px] text-blue-400 font-medium cursor-pointer hover:underline underline-offset-2"
              >
                View
              </button>
            </div>

            {researchResults.length === 0 ? (
              <p className="text-[11px] text-gray-400 py-2 text-center">
                Tidak ada paper ditemukan untuk kata kunci tersebut.
              </p>
            ) : (
              /* List of top 3 candidate items */
              <div className="space-y-2 pt-1">
                {researchResults.slice(0, 3).map((paper, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-left">
                    <div className="w-5 h-5 rounded bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                      <BookOpen size={11} className="text-blue-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h5 className="text-[11px] font-semibold text-gray-200 truncate leading-snug">
                        {paper.title}
                      </h5>
                      <p className="text-[10px] text-gray-400 line-clamp-1 leading-tight">
                        {paper.snippet || `Tahun ${paper.year}`}
                      </p>
                    </div>
                  </div>
                ))}

                {researchResults.length > 3 && (
                  <button
                    onClick={() => setViewMode("discovery")}
                    className="text-[11px] text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1 cursor-pointer pt-0.5"
                  >
                    <span>🔗 {researchResults.length - 3} more sources</span>
                  </button>
                )}
              </div>
            )}

            {/* Action Buttons: Delete & Import */}
            {researchResults.length > 0 && (
              <div className="flex items-center justify-end gap-2 pt-1 border-t border-white/5">
                <button
                  onClick={() => setResearchResults(null)}
                  className="text-xs text-gray-400 hover:text-white px-2 py-1 cursor-pointer"
                >
                  Delete
                </button>

                <Button
                  size="sm"
                  onClick={handleImportFastResearch}
                  disabled={isImportingResults || candidateSelectedCount === 0 || isImportedSuccess}
                  className="h-7 px-3.5 rounded-full bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1 shadow cursor-pointer disabled:opacity-50"
                >
                  {isImportingResults ? (
                    <>
                      <Loader2 size={12} className="animate-spin" />
                      <span>Importing...</span>
                    </>
                  ) : isImportedSuccess ? (
                    <>
                      <Check size={12} />
                      <span>Imported!</span>
                    </>
                  ) : (
                    <>
                      <Plus size={13} />
                      <span>Import</span>
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
        )}

        {/* 6. Controls Row: Sort (3 descending bars), Contextual Actions (Download & Delete), and Select All */}
        <div className="flex items-center justify-between pt-1 px-0 text-xs text-gray-400 relative">
          <div className="flex items-center gap-1">
            {/* Sort Button & Dropdown */}
            <div className="relative" ref={sortMenuRef}>
              <button 
                onClick={() => setIsSortMenuOpen(prev => !prev)}
                className="w-6 h-6 -ml-1 rounded text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-colors cursor-pointer flex items-center justify-center"
                title="Sort sources"
              >
                {/* 3 descending horizontal lines: top longest, 2nd medium, 3rd shortest */}
                <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" className="opacity-90">
                  <rect x="2" y="3" width="12" height="1.6" rx="0.8" />
                  <rect x="2" y="7.2" width="8" height="1.6" rx="0.8" />
                  <rect x="2" y="11.4" width="4.5" height="1.6" rx="0.8" />
                </svg>
              </button>

              {/* Sort Dropdown Menu (Title and Date added) */}
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
                title={selectedCount > 0 ? `Download ${selectedCount} file terpilih` : "Pilih referensi untuk men-download"}
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
                title={selectedCount > 0 ? `Hapus ${selectedCount} file terpilih` : "Pilih referensi untuk menghapus"}
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

        {/* 7. Saved Documents / Sources List (Compact height per item, flush left & right align) */}
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

              return (
                <div
                  key={doc.id}
                  onClick={() => toggleDocSelection(doc.id)}
                  className="flex items-center justify-between py-1.5 pl-0.5 pr-0.5 rounded-lg bg-transparent hover:bg-white/5 transition-colors cursor-pointer group"
                >
                  {/* Left: Compact Red PDF Badge + File Name */}
                  <div className="flex items-center gap-2 min-w-0 flex-1 mr-1.5">
                    <div className="w-5 h-5 rounded bg-red-950/70 border border-red-800/80 flex items-center justify-center shrink-0">
                      <span className="text-[7.5px] font-bold text-red-400 tracking-tighter uppercase font-mono">PDF</span>
                    </div>

                    <span className="text-[11.5px] text-gray-300 truncate group-hover:text-white font-normal" title={doc.filename}>
                      {doc.filename}
                    </span>
                  </div>

                  {/* Right: Checkbox (Always clean without hover delete icon) */}
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
              <h3 className="text-base font-semibold text-white">Hapus {selectedCount} sumber referensi?</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Dokumen yang dihapus tidak akan lagi digunakan oleh AI untuk menjawab pertanyaan dalam sesi chat ini.
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
                Batal
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
                    <span>Menghapus...</span>
                  </>
                ) : (
                  <span>Hapus ({selectedCount})</span>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
