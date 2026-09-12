import { useState, useRef, useEffect } from "react";
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
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const cancelledIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const controllers = abortControllersRef.current;
    const cancelled = cancelledIdsRef.current;
    return () => {
      controllers.forEach(controller => controller.abort());
      controllers.clear();
      cancelled.clear();
    };
  }, []);

  const cancelUpload = (sourceId: string) => {
    cancelledIdsRef.current.add(sourceId);
    const controller = abortControllersRef.current.get(sourceId);
    if (controller) {
      controller.abort();
      abortControllersRef.current.delete(sourceId);
    }
    setInternalPendingSources(prev => prev.filter(p => p.id !== sourceId));
  };

  const uploadFile = async (chatId: string, file: File, sourceId: string) => {
    if (cancelledIdsRef.current.has(sourceId)) {
      setInternalPendingSources(prev => prev.filter(p => p.id !== sourceId));
      return;
    }

    const controller = new AbortController();
    abortControllersRef.current.set(sourceId, controller);

    const formData = new FormData();
    formData.append("file", file);
    
    setInternalPendingSources(prev => prev.map(p => 
      p.id === sourceId ? { ...p, status: "uploading" } : p
    ));
    
    try {
      const res = await fetch(`${backendUrl}/chats/${chatId}/upload`, {
        method: "POST",
        body: formData,
        signal: controller.signal
      });
      
      if (res.ok) {
        const newDoc = await res.json();
        onDocumentAdded?.(newDoc, chatId);
        setInternalPendingSources(prev => prev.filter(p => p.id !== sourceId));
      } else {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Upload failed");
      }
    } catch (error: any) {
      if (error.name === "AbortError" || cancelledIdsRef.current.has(sourceId)) {
        setInternalPendingSources(prev => prev.filter(p => p.id !== sourceId));
        return;
      }
      setInternalPendingSources(prev => prev.map(p => 
        p.id === sourceId ? { ...p, status: "error", error: error.message || "Upload failed" } : p
      ));
    } finally {
      abortControllersRef.current.delete(sourceId);
      cancelledIdsRef.current.delete(sourceId);
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
      const sourceId = newPending[i].id;
      if (cancelledIdsRef.current.has(sourceId)) {
        continue;
      }
      await uploadFile(targetChatId, files[i], sourceId);
    }
  };

  return {
    internalPendingSources,
    setInternalPendingSources,
    handleUploadBatch,
    uploadFile,
    cancelUpload
  };
}