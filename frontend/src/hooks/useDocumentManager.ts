import { useState, useMemo } from "react";
import { Document, PendingSourceItem } from "@/stores/documentStore";

import { useDocumentUpload } from "./documents/useDocumentUpload";
import { useDocumentDoi } from "./documents/useDocumentDoi";
import { useDocumentMutation } from "./documents/useDocumentMutation";
import { useDocumentDownload } from "./documents/useDocumentDownload";
import { useDocumentSelection } from "./documents/useDocumentSelection";

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
  onCancelPendingSource,
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
  viewingDoc?: Document | null;
  setViewingDoc?: (doc: Document | null) => void;
  onCancelPendingSource?: (id: string) => void;
  t: (key: string) => string;
}) {
  // Modal states that bridge multiple logics
  const [isAddSourcesModalOpen, setIsAddSourcesModalOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [renameTitleInput, setRenameTitleInput] = useState("");
  const [docToDelete, setDocToDelete] = useState<number | null>(null);
  const [showBulkDeleteConfirm, setShowBulkDeleteConfirm] = useState(false);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [doiInput, setDoiInput] = useState("");

  // 1. Selection & Sorting
  const selection = useDocumentSelection(documents);

  // 2. Upload Files
  const upload = useDocumentUpload({
    activeChatId, backendUrl, onDocumentAdded, onEnsureChatSession, t
  });

  // 3. DOI Import
  const doi = useDocumentDoi({
    activeChatId, backendUrl, onDocumentAdded, onEnsureChatSession, t
  });

  // 4. Mutation (Rename, Delete, Clean)
  const mutation = useDocumentMutation({
    activeChatId, backendUrl, documents, onDocumentUpdated, onDocumentDeleted, 
    onBulkDocumentsDeleted, viewingDoc, setViewingDoc, t
  });

  // 5. Downloads
  const download = useDocumentDownload({ activeChatId, backendUrl, t });

  // Merge Pending Sources
  const pendingSources = useMemo(() => {
    return [...upload.internalPendingSources, ...doi.doiPendingSources, ...externalPendingSources];
  }, [upload.internalPendingSources, doi.doiPendingSources, externalPendingSources]);

  // Facade wrappers for UI bindings
  const handleOpenRename = () => {
    if (selection.selectedCount !== 1) return;
    const targetDoc = selection.selectedDocList[0];
    mutation.setRenamingDoc(targetDoc);
    setRenameTitleInput(targetDoc.title || targetDoc.filename.replace(/\.[^/.]+$/, "").replace(/_/g, " "));
    mutation.setRenameError(null);
    setIsRenameModalOpen(true);
  };

  const handleSaveRename = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const success = await mutation.handleSaveRename(renameTitleInput.trim());
    if (success) {
      setIsRenameModalOpen(false);
    }
  };

  const handleConfirmBulkDeleteWrap = async () => {
    const docIds = docToDelete !== null ? [docToDelete] : selection.selectedDocList.map(d => d.id);
    const success = await mutation.handleConfirmBulkDelete(docIds);
    if (success) {
      setShowBulkDeleteConfirm(false);
      setDocToDelete(null);
    }
  };

  const handleImportDoiWrap = async (e?: React.FormEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!doiInput.trim()) return;
    const val = doiInput.trim();
    setDoiInput("");
    setIsAddSourcesModalOpen(false);
    await doi.handleImportDoi(val);
  };

  const handleUploadBatchWrap = async (files: File[]) => {
    setIsAddSourcesModalOpen(false);
    await upload.handleUploadBatch(files);
  };

  const handleBulkDownloadWrap = async () => {
    await download.handleBulkDownload(selection.selectedDocList);
  };

  const cancelPendingSource = (pendingId: string) => {
    if (upload.internalPendingSources.some(p => p.id === pendingId)) {
      upload.cancelUpload(pendingId);
    } else if (doi.doiPendingSources.some(p => p.id === pendingId)) {
      doi.cancelDoi(pendingId);
    } else {
      onCancelPendingSource?.(pendingId);
    }
  };

  return {
    // Expose all Selection state
    ...selection,
    
    // Expose Mutation state
    ...mutation,
    handleOpenRename,
    handleSaveRename,
    handleConfirmBulkDelete: handleConfirmBulkDeleteWrap,
    
    // Expose Download state
    ...download,
    setIsBulkDownloading: download.setIsBulkDownloading,
    handleBulkDownload: handleBulkDownloadWrap,
    
    // Expose Upload & DOI
    pendingSources,
    internalPendingSources: upload.internalPendingSources,
    setInternalPendingSources: upload.setInternalPendingSources,
    handleUploadBatch: handleUploadBatchWrap,
    handleImportDoi: handleImportDoiWrap,
    cancelPendingSource,
    
    // Expose Modals & Inputs
    isAddSourcesModalOpen, setIsAddSourcesModalOpen,
    isRenameModalOpen, setIsRenameModalOpen,
    renameTitleInput, setRenameTitleInput,
    docToDelete, setDocToDelete,
    showBulkDeleteConfirm, setShowBulkDeleteConfirm,
    isDraggingOver, setIsDraggingOver,
    doiInput, setDoiInput
  };
}