import { useState } from "react";
import { Document } from "@/stores/documentStore";

export function useDocumentMutation({
  activeChatId,
  backendUrl,
  documents,
  onDocumentUpdated,
  onDocumentDeleted,
  onBulkDocumentsDeleted,
  viewingDoc,
  setViewingDoc,
}: {
  activeChatId: string | null;
  backendUrl: string;
  documents: Document[];
  onDocumentUpdated?: (doc: Document) => void;
  onDocumentDeleted?: (id: number) => void;
  onBulkDocumentsDeleted?: (ids: number[]) => void;
  viewingDoc?: Document | null;
  setViewingDoc?: (doc: Document | null) => void;
  t?: (key: string) => string;
}) {
  // Rename State
  const [renamingDoc, setRenamingDoc] = useState<Document | null>(null);
  const [isSavingRename, setIsSavingRename] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);

  // Delete State
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  
  // Clean Duplicates State
  const [isCleaningDuplicates, setIsCleaningDuplicates] = useState(false);
  const [cleanFeedback, setCleanFeedback] = useState<string | null>(null);

  const handleSaveRename = async (cleanTitle: string) => {
    if (!activeChatId || !renamingDoc || isSavingRename) return;
    
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
        if (viewingDoc && viewingDoc.id === renamingDoc.id && setViewingDoc) {
          setViewingDoc({ ...viewingDoc, title: updatedDoc.title });
        }
        setRenamingDoc(null);
        return true; // success flag
      } else {
        const err = await res.json().catch(() => ({}));
        setRenameError(err.detail || "Failed to rename document.");
        return false;
      }
    } catch (err: any) {
      setRenameError(err?.message || "Network error while renaming document.");
      return false;
    } finally {
      setIsSavingRename(false);
    }
  };

  const handleConfirmBulkDelete = async (docIds: number[]) => {
    if (!activeChatId || isBulkDeleting || docIds.length === 0) return false;
    
    setIsBulkDeleting(true);
    try {
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
        if (viewingDoc && docIds.includes(viewingDoc.id) && setViewingDoc) {
          setViewingDoc(null);
        }
        return true;
      } else {
        console.error("Bulk delete failed:", res.status);
        return false;
      }
    } catch (err) {
      console.error("Bulk delete error:", err);
      return false;
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const handleCleanDuplicates = async () => {
    if (!activeChatId || isCleaningDuplicates || documents.length === 0) return;
    if (documents.length <= 1) {
      setCleanFeedback("No duplicates found");
      setTimeout(() => setCleanFeedback(null), 3000);
      return;
    }
    setIsCleaningDuplicates(true);
    setCleanFeedback(null);
    
    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/clean-duplicates`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        const deletedCount = data.deleted_count ?? data.cleaned_count ?? 0;
        const deletedIds = data.deleted_ids ?? data.cleaned_doc_ids ?? [];
        if (deletedCount > 0 && deletedIds.length > 0) {
          onBulkDocumentsDeleted?.(deletedIds);
          setCleanFeedback(`Removed ${deletedCount} duplicate file${deletedCount > 1 ? 's' : ''}`);
        } else {
          setCleanFeedback("No duplicates found");
        }
        setTimeout(() => setCleanFeedback(null), 4000);
      } else {
        const errData = await res.json().catch(() => null);
        setCleanFeedback(errData?.detail || "Failed to check duplicates");
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

  return {
    renamingDoc, setRenamingDoc,
    isSavingRename, setIsSavingRename,
    renameError, setRenameError,
    handleSaveRename,
    
    isBulkDeleting, setIsBulkDeleting,
    handleConfirmBulkDelete,
    
    isCleaningDuplicates, setIsCleaningDuplicates,
    cleanFeedback, setCleanFeedback,
    handleCleanDuplicates
  };
}