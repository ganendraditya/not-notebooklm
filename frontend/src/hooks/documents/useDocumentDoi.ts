import { useState, useRef, useEffect } from "react";
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
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const cancelledIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const controllers = abortControllersRef.current;
    const cancelled = cancelledIdsRef.current;
    return () => {
      controllers.forEach(c => c.abort());
      controllers.clear();
      cancelled.clear();
    };
  }, []);

  const cancelDoi = (sourceId: string) => {
    cancelledIdsRef.current.add(sourceId);
    const controller = abortControllersRef.current.get(sourceId);
    if (controller) {
      controller.abort();
      abortControllersRef.current.delete(sourceId);
    }
    setDoiPendingSources(prev => prev.filter(p => p.id !== sourceId));
  };

  const importDoi = async (chatId: string, doi: string, sourceId: string) => {
    if (cancelledIdsRef.current.has(sourceId)) {
      setDoiPendingSources(prev => prev.filter(p => p.id !== sourceId));
      return;
    }

    const controller = new AbortController();
    abortControllersRef.current.set(sourceId, controller);

    setDoiPendingSources(prev => prev.map(p => 
      p.id === sourceId ? { ...p, status: "uploading" } : p
    ));
    
    try {
      const res = await fetch(`${backendUrl}/chats/${chatId}/documents/import-doi`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doi }),
        signal: controller.signal
      });
      
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to process DOI.");
      }

      if (controller.signal.aborted || cancelledIdsRef.current.has(sourceId)) {
        setDoiPendingSources(prev => prev.filter(p => p.id !== sourceId));
        return;
      }

      const doc = await res.json();
      if (controller.signal.aborted || cancelledIdsRef.current.has(sourceId)) {
        setDoiPendingSources(prev => prev.filter(p => p.id !== sourceId));
        return;
      }

      onDocumentAdded?.(doc, chatId);
      setDoiPendingSources(prev => prev.filter(p => p.id !== sourceId));
    } catch (error: any) {
      if (error.name === "AbortError" || controller.signal.aborted || cancelledIdsRef.current.has(sourceId)) {
        setDoiPendingSources(prev => prev.filter(p => p.id !== sourceId));
        return;
      }
      setDoiPendingSources(prev => prev.map(p => 
        p.id === sourceId ? { ...p, status: "error", error: error.message || "Import failed" } : p
      ));
    } finally {
      abortControllersRef.current.delete(sourceId);
      cancelledIdsRef.current.delete(sourceId);
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
    handleImportDoi,
    cancelDoi
  };
}