import { useState } from "react";
import { Document, PendingSourceItem } from "@/stores/documentStore";

export function useDocumentUpload({
  activeChatId,
  backendUrl,
  onDocumentAdded,
  onEnsureChatSession,
  t
}: {
  activeChatId: string | null;
  backendUrl: string;
  onDocumentAdded?: (doc: Document, targetChatId?: string) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  t: any;
}) {
  const [internalPendingSources, setInternalPendingSources] = useState<PendingSourceItem[]>([]);

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

  const handleUploadBatch = async (files: File[]) => {
    let targetChatId = activeChatId;
    if (!targetChatId && onEnsureChatSession) {
      targetChatId = await onEnsureChatSession(t("ui.defaultChatTitle") || "New Project");
    }
    if (!targetChatId) return;

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

  return {
    internalPendingSources,
    setInternalPendingSources,
    handleUploadBatch,
    uploadFile
  };
}