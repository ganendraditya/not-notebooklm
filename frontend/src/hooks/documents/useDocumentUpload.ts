import { useState, useRef, useEffect } from "react";
import { Document, PendingSourceItem, useDocumentStore } from "@/stores/documentStore";
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
  const [uploadFeedback, setUploadFeedback] = useState<string | null>(null);
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const cancelledIdsRef = useRef<Set<string>>(new Set());
  const feedbackTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const controllers = abortControllersRef.current;
    const cancelled = cancelledIdsRef.current;
    return () => {
      controllers.forEach(controller => controller.abort());
      controllers.clear();
      cancelled.clear();
      if (feedbackTimeoutRef.current) clearTimeout(feedbackTimeoutRef.current);
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
    useDocumentStore.getState().updatePendingSourcesList(prev => prev.filter(p => !p.id.startsWith(baseId) && p.id !== sourceId));
  };

  const uploadFile = async (
    chatId: string, 
    file: File, 
    sourceId: string,
    associatedPendingIds: string[] = [sourceId],
    progressTracker?: { current: number; total: number }
  ) => {
    if (cancelledIdsRef.current.has(sourceId)) {
      setInternalPendingSources(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
      useDocumentStore.getState().updatePendingSourcesList(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
      return;
    }

    const controller = new AbortController();
    abortControllersRef.current.set(sourceId, controller);

    const formData = new FormData();
    formData.append("file", file);
    
    setInternalPendingSources(prev => prev.map(p => 
      associatedPendingIds.includes(p.id) ? { ...p, status: "uploading" } : p
    ));
    useDocumentStore.getState().updatePendingSourcesList(prev => prev.map(p => 
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
        const docs: Document[] = Array.isArray(result) ? result : [result];

        // Progressive resolution: resolve each document with smooth visual pacing so loading animation is visible
        for (let i = 0; i < docs.length; i++) {
          const doc = docs[i];
          const matchingPendingId = associatedPendingIds[i] || associatedPendingIds[0];

          if (!cancelledIdsRef.current.has(matchingPendingId) && !cancelledIdsRef.current.has(sourceId)) {
            // Paced transition (220ms) so each item smoothly transitions from pending spinner to finalized document card
            if (docs.length > 1 || (progressTracker && progressTracker.total > 1)) {
              await new Promise(resolve => setTimeout(resolve, 220));
            }

            onDocumentAdded?.(doc, chatId);
            setInternalPendingSources(prev => prev.filter(p => p.id !== matchingPendingId));
            useDocumentStore.getState().updatePendingSourcesList(prev => prev.filter(p => p.id !== matchingPendingId));

            if (progressTracker) {
              progressTracker.current++;
              setUploadFeedback(`Importing sources (${progressTracker.current}/${progressTracker.total})...`);
            }
          }
        }
        // Ensure any remaining pending ids for this batch task are cleaned up
        setInternalPendingSources(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
        useDocumentStore.getState().updatePendingSourcesList(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
      } else {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Upload failed");
      }
    } catch (error: any) {
      if (error.name === "AbortError" || cancelledIdsRef.current.has(sourceId)) {
        setInternalPendingSources(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
        useDocumentStore.getState().updatePendingSourcesList(prev => prev.filter(p => !associatedPendingIds.includes(p.id)));
        return;
      }
      setInternalPendingSources(prev => prev.map(p => 
        associatedPendingIds.includes(p.id) ? { ...p, status: "error", error: error.message || "Upload failed" } : p
      ));
      useDocumentStore.getState().updatePendingSourcesList(prev => prev.map(p => 
        associatedPendingIds.includes(p.id) ? { ...p, status: "error", error: error.message || "Upload failed" } : p
      ));
      setUploadFeedback(`Upload failed: ${error.message || "Could not process file"}`);
      if (feedbackTimeoutRef.current) clearTimeout(feedbackTimeoutRef.current);
      feedbackTimeoutRef.current = setTimeout(() => setUploadFeedback(null), 4000);
    } finally {
      abortControllersRef.current.delete(sourceId);
      cancelledIdsRef.current.delete(sourceId);
    }
  };

  const handleUploadBatch = async (files: File[]) => {
    if (!files || files.length === 0) return;

    if (feedbackTimeoutRef.current) clearTimeout(feedbackTimeoutRef.current);

    // 1. Disassemble multi-entry bibliography files (BibTeX, RIS) into individual pending cards IMMEDIATELY
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

    const totalSources = allPending.length;
    if (totalSources > 1) {
      setUploadFeedback(`Detected ${totalSources} sources in upload queue. Loading...`);
    }

    // 2. Dispatch pending items to store IMMEDIATELY (0ms) so spinners appear right away
    setInternalPendingSources(prev => [...prev, ...allPending]);
    useDocumentStore.getState().updatePendingSourcesList(prev => [...prev, ...allPending]);

    // 3. Ensure chat session exists
    let targetChatId = activeChatId;
    if (!targetChatId && onEnsureChatSession) {
      try {
        targetChatId = await onEnsureChatSession(t("ui.newChat") || "New chat");
      } catch (err) {
        console.error("Failed to ensure chat session:", err);
      }
    }
    if (!targetChatId) {
      const pendingIdSet = new Set(allPending.map(p => p.id));
      setInternalPendingSources(prev => prev.filter(p => !pendingIdSet.has(p.id)));
      useDocumentStore.getState().updatePendingSourcesList(prev => prev.filter(p => !pendingIdSet.has(p.id)));
      setUploadFeedback("Failed to create chat session for upload.");
      return;
    }

    // 4. Sequentially process upload tasks
    const progressTracker = totalSources > 1 ? { current: 0, total: totalSources } : undefined;

    for (const task of batchTasks) {
      if (cancelledIdsRef.current.has(task.baseId)) {
        continue;
      }
      await uploadFile(targetChatId, task.file, task.baseId, task.pendingIds, progressTracker);
    }

    if (totalSources > 1) {
      setUploadFeedback(`Successfully imported ${totalSources} sources.`);
      if (feedbackTimeoutRef.current) clearTimeout(feedbackTimeoutRef.current);
      feedbackTimeoutRef.current = setTimeout(() => setUploadFeedback(null), 3500);
    }
  };

  return {
    internalPendingSources,
    setInternalPendingSources,
    uploadFeedback,
    setUploadFeedback,
    handleUploadBatch,
    uploadFile,
    cancelUpload
  };
}