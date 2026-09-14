import { useState, useRef, useEffect } from "react";
import { Document, PendingSourceItem } from "@/stores/documentStore";
import { peekBibliographyTitles } from "@/lib/sourceUtils";

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
    const baseId = sourceId.includes("_") ? sourceId.split("_")[0] : sourceId;
    cancelledIdsRef.current.add(baseId);
    cancelledIdsRef.current.add(sourceId);

    const controller = abortControllersRef.current.get(baseId) || abortControllersRef.current.get(sourceId);
    if (controller) {
      controller.abort();
      abortControllersRef.current.delete(baseId);
      abortControllersRef.current.delete(sourceId);
    }
    setInternalPendingSources(prev => prev.filter(p => !p.id.startsWith(baseId) && p.id !== sourceId));
  };

  const uploadFile = async (
    chatId: string, 
    file: File, 
    sourceId: string,
    associatedPendingIds: string[] = [sourceId]
  ) => {
    if (cancelledIdsRef.current.has(sourceId)) {
      setInternalPendingSources(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
      return;
    }

    const controller = new AbortController();
    abortControllersRef.current.set(sourceId, controller);

    const formData = new FormData();
    formData.append("file", file);
    
    setInternalPendingSources(prev => prev.map(p => 
      associatedPendingIds.includes(p.id) ? { ...p, status: "uploading" } : p
    ));
    
    try {
      const res = await fetch(`${backendUrl}/chats/${chatId}/upload`, {
        method: "POST",
        body: formData,
        signal: controller.signal
      });
      
      if (res.ok) {
        const result = await res.json();
        if (Array.isArray(result)) {
          result.forEach((doc: Document) => {
            onDocumentAdded?.(doc, chatId);
          });
        } else {
          onDocumentAdded?.(result, chatId);
        }
        setInternalPendingSources(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
      } else {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Upload failed");
      }
    } catch (error: any) {
      if (error.name === "AbortError" || cancelledIdsRef.current.has(sourceId)) {
        setInternalPendingSources(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
        return;
      }
      setInternalPendingSources(prev => prev.map(p => 
        associatedPendingIds.includes(p.id) ? { ...p, status: "error", error: error.message || "Upload failed" } : p
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

    // Disassemble multi-entry bibliography files (BibTeX, RIS) into individual pending cards
    const batchTasks: { file: File; baseId: string; pendingIds: string[] }[] = [];
    const allPending: PendingSourceItem[] = [];

    for (const file of files) {
      const baseId = Math.random().toString(36).substring(7);
      const peekedTitles = await peekBibliographyTitles(file);

      if (peekedTitles.length > 0) {
        const pendingIds: string[] = [];
        peekedTitles.forEach((title, idx) => {
          const subId = `${baseId}_${idx}`;
          pendingIds.push(subId);
          allPending.push({
            id: subId,
            filename: title,
            type: "file",
            status: "uploading"
          });
        });
        batchTasks.push({ file, baseId, pendingIds });
      } else {
        allPending.push({
          id: baseId,
          filename: file.name,
          type: "file",
          status: "uploading"
        });
        batchTasks.push({ file, baseId, pendingIds: [baseId] });
      }
    }

    setInternalPendingSources(prev => [...prev, ...allPending]);

    for (const task of batchTasks) {
      if (cancelledIdsRef.current.has(task.baseId)) {
        continue;
      }
      await uploadFile(targetChatId, task.file, task.baseId, task.pendingIds);
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