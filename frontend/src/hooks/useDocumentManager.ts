import { useState, useMemo } from "react";
import { Document, PendingSourceItem } from "@/stores/documentStore";
import { consumeSSEStream } from "@/lib/sse";
import { DownloadTask, DownloadManager } from "@/components/DownloadManager";

export function useDocumentManager({
  documents,
  externalPendingSources = [],
  activeChatId,
  backendUrl,
  onDocumentAdded,
  onDocumentUpdated,
  onDocumentDeleted,
  onBulkDocumentsDeleted,
  onEnsureChatSession,
  viewingDoc,
  setViewingDoc,
  t
}: {
  documents: Document[];
  externalPendingSources?: PendingSourceItem[];
  activeChatId: string | null;
  backendUrl: string;
  onDocumentAdded?: (doc: Document, targetChatId?: string) => void;
  onDocumentUpdated?: (doc: Document) => void;
  onDocumentDeleted?: (id: number) => void;
  onBulkDocumentsDeleted?: (ids: number[]) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  viewingDoc?: any;
  setViewingDoc?: any;
  t: any;
}) {
  const [selectedDocs, setSelectedDocs] = useState<Record<number, boolean>>({});
  
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [isSortMenuOpen, setIsSortMenuOpen] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState<number | null>(null);

  const [isCleaningDuplicates, setIsCleaningDuplicates] = useState(false);
  const [cleanFeedback, setCleanFeedback] = useState<string | null>(null);
  
  const [isAddSourcesModalOpen, setIsAddSourcesModalOpen] = useState(false);
  const [doiInput, setDoiInput] = useState("");
  const [internalPendingSources, setInternalPendingSources] = useState<PendingSourceItem[]>([]);
  const pendingSources = useMemo(() => {
    return [...internalPendingSources, ...externalPendingSources];
  }, [internalPendingSources, externalPendingSources]);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [renamingDoc, setRenamingDoc] = useState<Document | null>(null);
  const [renameTitleInput, setRenameTitleInput] = useState("");
  const [isSavingRename, setIsSavingRename] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);

  const [docToDelete, setDocToDelete] = useState<number | null>(null);
  const [showBulkDeleteConfirm, setShowBulkDeleteConfirm] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [isBulkDownloading, setIsBulkDownloading] = useState(false);
  const [downloadTask, setDownloadTask] = useState<DownloadTask | null>(null);

  const selectedDocList = useMemo(() => documents.filter(doc => selectedDocs[doc.id]), [documents, selectedDocs]);
  const selectedCount = selectedDocList.length;
  
  const isAllSelected = documents.length > 0 && selectedCount === documents.length;
  const isPartiallySelected = selectedCount > 0 && selectedCount < documents.length;

  const sortedDocuments = useMemo(() => {
    const docs = [...documents];
    docs.sort((a, b) => {
      let cmp = 0;
      if (sortBy === "title") {
        const titleA = (a.title || a.filename).toLowerCase();
        const titleB = (b.title || b.filename).toLowerCase();
        cmp = titleA.localeCompare(titleB);
      } else {
        const dateA = new Date(a.created_at || "").getTime();
        const dateB = new Date(b.created_at || "").getTime();
        cmp = dateA - dateB;
      }
      return sortDirection === "asc" ? cmp : -cmp;
    });
    return docs;
  }, [documents, sortBy, sortDirection]);

  const toggleDocSelection = (docId: number) => {
    setSelectedDocs(prev => {
      const current = prev[docId] !== undefined ? prev[docId] : true;
      return {
        ...prev,
        [docId]: !current
      };
    });
  };

  const handleToggleSelectAll = () => {
    if (documents.length === 0) return;
    if (isAllSelected) {
      setSelectedDocs({});
    } else {
      const newSelection: Record<number, boolean> = {};
      documents.forEach(doc => { newSelection[doc.id] = true; });
      setSelectedDocs(newSelection);
    }
  };

  const getFileBadgeInfo = (filename: string) => {
    if (filename.startsWith("10.") || filename.startsWith("DOI:") || filename.includes("doi.org")) {
      return { label: "DOI", bg: "bg-blue-600/15 border-blue-500/40 text-blue-500" };
    }
    const ext = filename.split(".").pop()?.toLowerCase() || "doc";
    if (ext === "pdf") {
      return { label: "PDF", bg: "bg-red-600/15 border-red-500/40 text-red-500" };
    } else if (ext === "docx" || ext === "doc") {
      return { label: "DOC", bg: "bg-blue-600/15 border-blue-500/40 text-blue-500" };
    } else if (ext === "bib" || ext === "bibtex") {
      return { label: "BIB", bg: "bg-amber-600/15 border-amber-500/40 text-amber-500" };
    } else if (ext === "ris") {
      return { label: "RIS", bg: "bg-orange-600/15 border-orange-500/40 text-orange-500" };
    } else if (ext === "md") {
      return { label: "MD", bg: "bg-purple-600/15 border-purple-500/40 text-purple-500" };
    } else {
      return { label: "TXT", bg: "bg-app-item-hover border-app-border text-app-text-muted" };
    }
  };

  const handleOpenRename = () => {
    if (selectedCount !== 1) return;
    const targetDoc = selectedDocList[0];
    setRenamingDoc(targetDoc);
    setRenameTitleInput(targetDoc.title || targetDoc.filename.replace(/\.[^/.]+$/, "").replace(/_/g, " "));
    setRenameError(null);
    setIsRenameModalOpen(true);
  };

  const handleSaveRename = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!activeChatId || !renamingDoc || isSavingRename) return;
    const cleanTitle = renameTitleInput.trim();
    if (!cleanTitle) {
      setRenameError("Document title cannot be empty.");
      return;
    }
    setIsSavingRename(true);
    setRenameError(null);
    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/${renamingDoc.id}/rename`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: cleanTitle })
      });
      if (res.ok) {
        const updatedDoc = await res.json();
        onDocumentUpdated?.(updatedDoc);
        if (viewingDoc && ((viewingDoc as any)?.id || "undefined") === renamingDoc.id && setViewingDoc) {
          setViewingDoc((prev: any) => prev ? { ...prev, title: updatedDoc.title } : null);
        }
        setIsRenameModalOpen(false);
        setRenamingDoc(null);
      } else {
        const err = await res.json().catch(() => ({}));
        setRenameError(err.detail || "Failed to rename document.");
      }
    } catch (err: any) {
      setRenameError(err?.message || "Network error while renaming document.");
    } finally {
      setIsSavingRename(false);
    }
  };

  const handleCleanDuplicates = async () => {
    if (!activeChatId || isCleaningDuplicates || documents.length === 0) return;
    setIsCleaningDuplicates(true);
    setCleanFeedback(null);
    
    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/clean-duplicates`, { method: "POST" });
      if (res.ok) {
        const { deleted_count, deleted_ids } = await res.json();
        if (deleted_count > 0 && deleted_ids && deleted_ids.length > 0) {
          onBulkDocumentsDeleted?.(deleted_ids);
          setCleanFeedback(`Removed ${deleted_count} duplicate file${deleted_count > 1 ? 's' : ''}`);
        } else {
          setCleanFeedback("No duplicates found");
        }
        setTimeout(() => setCleanFeedback(null), 4000);
      } else {
        setCleanFeedback("Failed to check duplicates");
        setTimeout(() => setCleanFeedback(null), 3000);
      }
    } catch (err) {
      console.error("Clean duplicates error:", err);
      setCleanFeedback("Network error");
      setTimeout(() => setCleanFeedback(null), 3000);
    } finally {
      setIsCleaningDuplicates(false);
    }
  };

  const downloadFileText = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleBulkDownload = async () => {
    if (!activeChatId || selectedCount === 0 || isBulkDownloading) return;
    setIsBulkDownloading(true);
    const docIds = selectedDocList.map(d => d.id);

    if (docIds.length === 1) {
      try {
        const doc = selectedDocList[0];
        const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/${doc.id}/download`);
        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          setDownloadTask({
            status: "error",
            total: 1,
            current: 0,
            percent: 0,
            currentFile: doc.filename,
            errorMsg: errJson.detail || "Naskah lengkap PDF tidak tersedia untuk diunduh."
          });
          return;
        }
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = doc.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        console.error("Single download error:", err);
      } finally {
        setIsBulkDownloading(false);
      }
      return;
    }

    setDownloadTask({
      status: "preparing",
      total: docIds.length,
      current: 0,
      percent: 0,
      currentFile: "Menyiapkan kompresi..."
    });

    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/bulk-download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: docIds })
      });

      if (!res.ok) {
        throw new Error("Failed to start zip stream");
      }

      await consumeSSEStream(res, (event) => {
        const data = JSON.parse(event.data);
        if (event.event === "progress") {
          setDownloadTask(prev => ({
            ...prev!,
            status: "zipping",
            current: data.current,
            total: data.total,
            percent: Math.round((data.current / data.total) * 100),
            currentFile: data.filename || "Memproses file...",
            downloadedCount: data.downloaded_count,
            skippedCount: data.skipped_count,
            totalSizeMb: data.total_size_mb
          }));
        } else if (event.event === "complete") {
          const zipUrl = `${backendUrl}${data.download_url}`;
          setDownloadTask({
            status: "complete",
            total: data.total,
            current: data.total,
            percent: 100,
            currentFile: data.filename || "Download.zip",
            downloadedCount: data.downloaded_count,
            skippedCount: data.skipped_count,
            totalSizeMb: data.total_size_mb
          });
          
          const link = document.createElement("a");
          link.href = zipUrl;
          link.setAttribute("download", "");
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } else if (event.event === "error") {
          setDownloadTask({
            status: "error",
            total: docIds.length,
            current: 0,
            percent: 0,
            currentFile: "",
            errorMsg: data.detail || "Gagal mengompres dokumen."
          });
        }
      });
    } catch (err: any) {
      console.error("Bulk download SSE error:", err);
      setDownloadTask({
        status: "error",
        total: docIds.length,
        current: 0,
        percent: 0,
        currentFile: "",
        errorMsg: err.message || "Koneksi terputus saat mengunduh."
      });
    } finally {
      setIsBulkDownloading(false);
    }
  };

  const handleConfirmBulkDelete = async () => {
    if (!activeChatId || isBulkDeleting) return;
    setIsBulkDeleting(true);
    try {
      const docIds = docToDelete !== null ? [docToDelete] : selectedDocList.map(d => d.id);
      
      if (docIds.length === 0) {
        setIsBulkDeleting(false);
        return;
      }
      
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
        setDocToDelete(null); // Reset after success
        if (viewingDoc && docIds.includes(((viewingDoc as any)?.id || "undefined"))) {
          setViewingDoc(null);
        }
      } else {
        alert(t("right.deleteError") || "Error deleting documents");
      }
    } catch (err) {
      console.error("Bulk delete error:", err);
      alert(t("right.deleteError") || "Error deleting documents");
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const uploadFile = async (chatId: string, file: File, sourceId: string) => {
    const formData = new FormData();
    formData.append("file", file);
    
    setInternalPendingSources(prev => prev.map(p => 
      p.id === sourceId ? { ...p, status: "uploading" } : p
    ));
    
    try {
      const res = await fetch(`${backendUrl}/chats/${chatId}/upload`, {
        method: "POST",
        body: formData,
      });
      
      if (res.ok && onDocumentAdded) {
        const newDoc = await res.json();
        onDocumentAdded(newDoc, chatId);
        setInternalPendingSources(prev => prev.filter(p => p.id !== sourceId));
      } else {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Upload failed");
      }
    } catch (error: any) {
      setInternalPendingSources(prev => prev.map(p => 
        p.id === sourceId ? { ...p, status: "error", error: error.message || "Upload failed" } : p
      ));
    }
  };

  const importDoi = async (chatId: string, doi: string, sourceId: string) => {
    setInternalPendingSources(prev => prev.map(p => 
      p.id === sourceId ? { ...p, status: "uploading" } : p
    ));
    
    try {
      const res = await fetch(`${backendUrl}/chats/${chatId}/documents/import-doi`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doi })
      });
      
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to process DOI.");
      }

      await consumeSSEStream(res, (event) => {
        if (event.event === "complete") {
          const doc = JSON.parse(event.data);
          onDocumentAdded?.(doc, chatId);
          setInternalPendingSources(prev => prev.filter(p => p.id !== sourceId));
        } else if (event.event === "error") {
          throw new Error(event.data);
        }
      });
    } catch (error: any) {
      setInternalPendingSources(prev => prev.map(p => 
        p.id === sourceId ? { ...p, status: "error", error: error.message || "Import failed" } : p
      ));
    }
  };

  const handleUploadBatch = async (files: File[]) => {
    let targetChatId = activeChatId;
    if (!targetChatId && onEnsureChatSession) {
      targetChatId = await onEnsureChatSession(t("ui.defaultChatTitle") || "New Project");
    }
    if (!targetChatId) return;

    setIsAddSourcesModalOpen(false);

    const newPending: PendingSourceItem[] = files.map(file => ({
      id: Math.random().toString(36).substring(7),
      filename: file.name,
      type: "file",
      status: "uploading"
    }));

    setInternalPendingSources(prev => [...prev, ...newPending]);

    for (let i = 0; i < files.length; i++) {
      await uploadFile(targetChatId, files[i], newPending[i].id);
    }
  };

  const handleImportDoi = async (e?: React.FormEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!doiInput.trim()) return;

    let targetChatId = activeChatId;
    if (!targetChatId && onEnsureChatSession) {
      targetChatId = await onEnsureChatSession(t("ui.defaultChatTitle") || "New Project");
    }
    if (!targetChatId) return;

    const doi = doiInput.trim();
    setDoiInput("");
    setIsAddSourcesModalOpen(false);

    const sourceId = Math.random().toString(36).substring(7);
    const newPending: PendingSourceItem = {
      id: sourceId,
      filename: doi,
      type: "doi",
      doi: doi,
      status: "uploading"
    };

    setInternalPendingSources(prev => [...prev, newPending]);
    await importDoi(targetChatId, doi, sourceId);
  };

  return {
    selectedDocs, setSelectedDocs,
    sortBy, setSortBy,
    sortDirection, setSortDirection,
    isSortMenuOpen, setIsSortMenuOpen,
    activeMenuId, setActiveMenuId,
    isCleaningDuplicates, setIsCleaningDuplicates,
    cleanFeedback, setCleanFeedback,
    isAddSourcesModalOpen, setIsAddSourcesModalOpen,
    doiInput, setDoiInput,
    internalPendingSources, setInternalPendingSources,
    pendingSources,
    isDraggingOver, setIsDraggingOver,
    isRenameModalOpen, setIsRenameModalOpen,
    renamingDoc, setRenamingDoc,
    renameTitleInput, setRenameTitleInput,
    isSavingRename, setIsSavingRename,
    renameError, setRenameError,
    docToDelete, setDocToDelete,
    showBulkDeleteConfirm, setShowBulkDeleteConfirm,
    isBulkDeleting, setIsBulkDeleting,
    isBulkDownloading, setIsBulkDownloading,
    downloadTask, setDownloadTask,
    selectedDocList, selectedCount,
    isAllSelected, isPartiallySelected,
    sortedDocuments,
    toggleDocSelection, handleToggleSelectAll,
    getFileBadgeInfo, handleOpenRename, handleSaveRename,
    handleCleanDuplicates, handleBulkDownload, handleConfirmBulkDelete,
    handleUploadBatch, handleImportDoi, downloadFileText
  };
}
