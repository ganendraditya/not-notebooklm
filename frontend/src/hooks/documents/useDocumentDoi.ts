import { useState } from "react";
import { Document, PendingSourceItem } from "@/stores/documentStore";

export function useDocumentDoi({
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
  const [doiPendingSources, setDoiPendingSources] = useState<PendingSourceItem[]>([]);

  const importDoi = async (chatId: string, doi: string, sourceId: string) => {
    setDoiPendingSources(prev => prev.map(p => 
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

      const doc = await res.json();
      onDocumentAdded?.(doc, chatId);
      setDoiPendingSources(prev => prev.filter(p => p.id !== sourceId));
    } catch (error: any) {
      setDoiPendingSources(prev => prev.map(p => 
        p.id === sourceId ? { ...p, status: "error", error: error.message || "Import failed" } : p
      ));
    }
  };

  const handleImportDoi = async (doi: string) => {
    if (!doi.trim()) return;

    let targetChatId = activeChatId;
    if (!targetChatId && onEnsureChatSession) {
      targetChatId = await onEnsureChatSession(t("ui.defaultChatTitle") || "New Project");
    }
    if (!targetChatId) return;

    const sourceId = Math.random().toString(36).substring(7);
    const newPending: PendingSourceItem = {
      id: sourceId,
      filename: doi,
      type: "doi",
      doi: doi,
      status: "uploading"
    };

    setDoiPendingSources(prev => [...prev, newPending]);
    await importDoi(targetChatId, doi, sourceId);
  };

  return {
    doiPendingSources,
    handleImportDoi
  };
}