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

  useEffect(() => {
    setProposal(null);
    setHasDeleteError(false);
  }, [activeChatId]);

  const requestConfirmation = useCallback((nextProposal: ChatDeleteProposal) => {
    if (activeChatIdRef.current !== nextProposal.chatId) return;

    const documentsById = new Map(documents.map((doc) => [doc.id, doc]));
    const uniqueIds = [...new Set(nextProposal.documentIds)];
    const matchedDocuments = uniqueIds.map((id) => documentsById.get(id));
    if (uniqueIds.length === 0 || matchedDocuments.some((doc) => !doc)) return;
    const resolvedDocuments = matchedDocuments.filter((doc): doc is Document => doc !== undefined);

    setProposal({
      chatId: nextProposal.chatId,
      documentIds: uniqueIds,
      sourceNames: resolvedDocuments.map((doc) => doc.title?.trim() || doc.filename),
    });
    setHasDeleteError(false);
  }, [activeChatIdRef, documents]);

  const cancel = useCallback(() => {
    if (isDeletingRef.current) return;
    setProposal(null);
    setHasDeleteError(false);
  }, []);

  const confirm = useCallback(async () => {
    if (!proposal || isDeletingRef.current) return;
    if (activeChatIdRef.current !== proposal.chatId) {
      setProposal((current) => current === proposal ? null : current);
      return;
    }

    isDeletingRef.current = true;
    setIsDeleting(true);
    setHasDeleteError(false);

    try {
      const response = await fetch(
        `${backendUrl}/chats/${encodeURIComponent(proposal.chatId)}/documents/bulk_delete`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ doc_ids: proposal.documentIds }),
        }
      );
      if (!response.ok) throw new Error(`Bulk delete request failed: ${response.status}`);

      if (activeChatIdRef.current === proposal.chatId) {
        onDocumentsDeleted(proposal.documentIds);
      }
      setProposal((current) => current === proposal ? null : current);
    } catch (error) {
      console.error("Failed to delete chat sources", error);
      if (activeChatIdRef.current === proposal.chatId) {
        setHasDeleteError(true);
      }
    } finally {
      isDeletingRef.current = false;
      setIsDeleting(false);
    }
  }, [activeChatIdRef, backendUrl, onDocumentsDeleted, proposal]);

  return {
    proposal,
    isDeleting,
    hasDeleteError,
    requestConfirmation,
    cancel,
    confirm,
  };
}
