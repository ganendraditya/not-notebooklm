import { useCallback, useEffect, useRef, useState } from "react";
import type { Document } from "@/stores/documentStore";
import type { ChatDeleteProposal } from "@/lib/sourceActions";

interface PendingChatDelete extends ChatDeleteProposal {
  sourceNames: string[];
}

interface UseChatDeleteConfirmationOptions {
  activeChatId: string | null;
  activeChatIdRef: React.MutableRefObject<string | null>;
  backendUrl: string;
  documents: Document[];
  onDocumentsDeleted: (documentIds: number[]) => void;
}

export function useChatDeleteConfirmation({
  activeChatId,
  activeChatIdRef,
  backendUrl,
  documents,
  onDocumentsDeleted,
}: UseChatDeleteConfirmationOptions) {
  const [proposal, setProposal] = useState<PendingChatDelete | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [hasDeleteError, setHasDeleteError] = useState(false);
  const isDeletingRef = useRef(false);
  const proposalRef = useRef<PendingChatDelete | null>(null);
  const queuedProposalsRef = useRef<PendingChatDelete[]>([]);
  const documentsRef = useRef(documents);

  useEffect(() => {
    documentsRef.current = documents;
  }, [documents]);

  const setPendingProposal = useCallback((nextProposal: PendingChatDelete | null) => {
    proposalRef.current = nextProposal;
    setProposal(nextProposal);
  }, []);

  const resolveProposal = useCallback((nextProposal: ChatDeleteProposal): PendingChatDelete | null => {
    if (activeChatIdRef.current !== nextProposal.chatId) return null;

    const documentsById = new Map(documentsRef.current.map((doc) => [doc.id, doc]));
    const uniqueIds = [...new Set(nextProposal.documentIds)];
    const matchedDocuments = uniqueIds.map((id) => documentsById.get(id));
    if (uniqueIds.length === 0 || matchedDocuments.some((doc) => !doc)) return null;
    const resolvedDocuments = matchedDocuments.filter((doc): doc is Document => doc !== undefined);

    return {
      chatId: nextProposal.chatId,
      documentIds: uniqueIds,
      sourceNames: resolvedDocuments.map((doc) => doc.title?.trim() || doc.filename),
    };
  }, [activeChatIdRef]);

  const showNextQueuedProposal = useCallback(() => {
    if (isDeletingRef.current || proposalRef.current) return;

    while (queuedProposalsRef.current.length > 0) {
      const queuedProposal = queuedProposalsRef.current.shift();
      if (!queuedProposal) continue;

      const resolvedProposal = resolveProposal(queuedProposal);
      if (!resolvedProposal) continue;

      setPendingProposal(resolvedProposal);
      setHasDeleteError(false);
      return;
    }
  }, [resolveProposal, setPendingProposal]);

  useEffect(() => {
    setPendingProposal(null);
    setHasDeleteError(false);
    showNextQueuedProposal();
  }, [activeChatId, setPendingProposal, showNextQueuedProposal]);

  const requestConfirmation = useCallback((nextProposal: ChatDeleteProposal) => {
    const resolvedProposal = resolveProposal(nextProposal);
    if (!resolvedProposal) return;

    if (isDeletingRef.current || proposalRef.current) {
      queuedProposalsRef.current.push(resolvedProposal);
      return;
    }

    setPendingProposal(resolvedProposal);
    setHasDeleteError(false);
  }, [resolveProposal, setPendingProposal]);

  const cancel = useCallback(() => {
    if (isDeletingRef.current) return;
    setPendingProposal(null);
    setHasDeleteError(false);
    showNextQueuedProposal();
  }, [setPendingProposal, showNextQueuedProposal]);

  const confirm = useCallback(async () => {
    const proposalToDelete = proposalRef.current;
    if (!proposalToDelete || isDeletingRef.current) return;
    if (activeChatIdRef.current !== proposalToDelete.chatId) {
      setPendingProposal(null);
      showNextQueuedProposal();
      return;
    }

    isDeletingRef.current = true;
    setIsDeleting(true);
    setHasDeleteError(false);

    try {
      const response = await fetch(
        `${backendUrl}/chats/${encodeURIComponent(proposalToDelete.chatId)}/documents/bulk_delete`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ doc_ids: proposalToDelete.documentIds }),
        }
      );
      if (!response.ok) throw new Error(`Bulk delete request failed: ${response.status}`);

      if (activeChatIdRef.current === proposalToDelete.chatId) {
        const deletedIds = new Set(proposalToDelete.documentIds);
        documentsRef.current = documentsRef.current.filter((doc) => !deletedIds.has(doc.id));
        onDocumentsDeleted(proposalToDelete.documentIds);
      }
      if (proposalRef.current === proposalToDelete) {
        setPendingProposal(null);
      }
    } catch (error) {
      console.error("Failed to delete chat sources", error);
      if (
        activeChatIdRef.current === proposalToDelete.chatId &&
        proposalRef.current === proposalToDelete
      ) {
        setHasDeleteError(true);
      }
    } finally {
      isDeletingRef.current = false;
      setIsDeleting(false);
      showNextQueuedProposal();
    }
  }, [activeChatIdRef, backendUrl, onDocumentsDeleted, setPendingProposal, showNextQueuedProposal]);

  return {
    proposal,
    isDeleting,
    hasDeleteError,
    requestConfirmation,
    cancel,
    confirm,
  };
}
