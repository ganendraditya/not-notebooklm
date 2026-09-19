import { useState, useEffect, useCallback, useRef } from "react";
import { Document, CitationGroundingHighlight, useDocumentStore } from "@/stores/documentStore";

export interface PaperDetailData {
  id: number;
  filename: string;
  created_at?: string;
  type: string;
  title: string;
  authors: string[];
  publication_date: string;
  year: string;
  journal: string;
  journal_metric: string;
  quality_tier?: number;
  citations: number;
  doi: string;
  url: string;
  pdf_url: string;
  abstract: string;
  abstract_type?: "official" | "ai_summary";
  is_oa?: boolean;
  access_status?: string;
  is_uploaded?: boolean;
  has_full_pdf?: boolean;
  is_abstract_only?: boolean;
  content: string;
}

interface UsePaperDetailsProps {
  activeChatId: string | null;
  backendUrl: string;
  externalViewingDoc?: Document | null;
  onViewingDocChange?: (doc: Document | null) => void;
  groundingHighlight?: CitationGroundingHighlight | null;
  documents?: Document[];
}

const MAX_PAPER_CACHE_ENTRIES = 50;
const globalPaperDetailsCache = new Map<string, PaperDetailData>();
const globalInFlightPaperRequests = new Map<string, Promise<PaperDetailData | null>>();

function getPaperCacheKey(chatId: string, docId: number): string {
  return `${chatId}:${docId}`;
}

export function getCachedPaperDetails(chatId: string, docId: number): PaperDetailData | undefined {
  return globalPaperDetailsCache.get(getPaperCacheKey(chatId, docId));
}

export function setCachedPaperDetails(chatId: string, docId: number, data: PaperDetailData): void {
  const key = getPaperCacheKey(chatId, docId);
  if (globalPaperDetailsCache.has(key)) {
    globalPaperDetailsCache.delete(key);
  } else if (globalPaperDetailsCache.size >= MAX_PAPER_CACHE_ENTRIES) {
    const oldestKey = globalPaperDetailsCache.keys().next().value;
    if (oldestKey !== undefined) {
      globalPaperDetailsCache.delete(oldestKey);
    }
  }
  globalPaperDetailsCache.set(key, data);
}

export async function prefetchDocumentContent(
  backendUrl: string,
  chatId: string,
  docId: number
): Promise<PaperDetailData | null> {
  if (!chatId || !docId || !backendUrl) return null;
  const key = getPaperCacheKey(chatId, docId);

  if (globalPaperDetailsCache.has(key)) {
    return globalPaperDetailsCache.get(key)!;
  }

  if (globalInFlightPaperRequests.has(key)) {
    return globalInFlightPaperRequests.get(key)!;
  }

  const promise = (async () => {
    try {
      const res = await fetch(`${backendUrl}/chats/${chatId}/documents/${docId}/content`);
      if (!res.ok) return null;
      const data = await res.json();
      if (data && !data.error) {
        setCachedPaperDetails(chatId, docId, data);
        return data;
      }
      return null;
    } catch {
      return null;
    } finally {
      globalInFlightPaperRequests.delete(key);
    }
  })();

  globalInFlightPaperRequests.set(key, promise);
  return promise;
}

export function usePaperDetails({
  activeChatId,
  backendUrl,
  externalViewingDoc,
  onViewingDocChange,
  groundingHighlight,
  documents,
}: UsePaperDetailsProps) {
  const [viewingDoc, setViewingDocState] = useState<Document | null>(externalViewingDoc || null);
  const [paperDetails, setPaperDetails] = useState<PaperDetailData | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"preview" | "pdf">("preview");

  const setViewingDoc = useCallback((doc: Document | null) => {
    setViewingDocState(doc);
    if (onViewingDocChange) {
      onViewingDocChange(doc);
    }
  }, [onViewingDocChange]);

  useEffect(() => {
    setViewingDocState(externalViewingDoc || null);
  }, [externalViewingDoc]);

  const updateDocumentsList = useDocumentStore((s) => s.updateDocumentsList);
  const prewarmedChatRef = useRef<string | null>(null);
  const prewarmedDocIds = useRef<Set<number>>(new Set());

  const syncUpgradedDocument = useCallback((targetDoc: Document, data: { filename?: string; has_full_pdf?: boolean; is_oa?: boolean }) => {
    const isUpgraded =
      (data.filename && data.filename !== targetDoc.filename) ||
      (data.has_full_pdf !== undefined && data.has_full_pdf !== targetDoc.has_full_pdf);

    if (isUpgraded) {
      const updatedFilename = data.filename || targetDoc.filename;
      const updatedHasPdf = data.has_full_pdf ?? targetDoc.has_full_pdf;
      const updatedIsOa = data.is_oa ?? targetDoc.is_oa;

      updateDocumentsList((prev) =>
        prev.map((d) => d.id === targetDoc.id ? { ...d, filename: updatedFilename, has_full_pdf: updatedHasPdf, is_oa: updatedIsOa } : d)
      );

      const updatedDoc: Document = {
        ...targetDoc,
        filename: updatedFilename,
        has_full_pdf: updatedHasPdf,
        is_oa: updatedIsOa,
      };

      setViewingDocState((prev) => (prev && prev.id === targetDoc.id ? updatedDoc : prev));
      if (onViewingDocChange) {
        onViewingDocChange(updatedDoc);
      }
    }
  }, [updateDocumentsList, onViewingDocChange]);

  // Proactive background pre-warming: pre-fetch full text content for workspace documents
  useEffect(() => {
    if (!activeChatId || !documents || documents.length === 0) return;
    let isCancelled = false;
    const currentChatId = activeChatId;

    if (prewarmedChatRef.current !== currentChatId) {
      prewarmedChatRef.current = currentChatId;
      prewarmedDocIds.current.clear();
    }

    documents.forEach(doc => {
      if (doc?.id && !prewarmedDocIds.current.has(doc.id)) {
        prewarmedDocIds.current.add(doc.id);
        prefetchDocumentContent(backendUrl, currentChatId, doc.id)
          .then(data => {
            if (isCancelled || prewarmedChatRef.current !== currentChatId) return;
            if (data && (
              (data.filename && data.filename !== doc.filename) ||
              (data.has_full_pdf !== undefined && data.has_full_pdf !== doc.has_full_pdf)
            )) {
              updateDocumentsList(prev =>
                prev.map(d => d.id === doc.id ? {
                  ...d,
                  filename: data.filename || d.filename,
                  has_full_pdf: data.has_full_pdf ?? d.has_full_pdf,
                  is_oa: data.is_oa ?? d.is_oa
                } : d)
              );
            }
          })
          .catch(() => {
            prewarmedDocIds.current.delete(doc.id);
          });
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [activeChatId, documents, backendUrl, updateDocumentsList]);

  // Whenever active chat changes, always reset viewingDoc and paperDetails to exit reader mode and show default sources list
  useEffect(() => {
    setViewingDocState(null);
    setPaperDetails(null);
    if (onViewingDocChange) {
      onViewingDocChange(null);
    }
  }, [activeChatId, onViewingDocChange]);

  useEffect(() => {
    if (!viewingDoc || !activeChatId) {
      setPaperDetails(null);
      setIsLoadingDetails(false);
      return;
    }

    // 1. Instant cache check (0ms) - eliminates skeleton flicker completely
    // Skip cache for .txt docs since backend may upgrade them to .pdf via on-demand OA fetch
    const isTxtDoc = viewingDoc.filename?.toLowerCase().endsWith('.txt');
    const cached = !isTxtDoc ? getCachedPaperDetails(activeChatId, viewingDoc.id) : null;
    if (cached && (cached.id === viewingDoc.id || cached.filename === viewingDoc.filename)) {
      setPaperDetails(cached);
      setIsLoadingDetails(false);
      syncUpgradedDocument(viewingDoc, cached);
      return;
    }

    // 2. Fetch if not yet in cache
    setIsLoadingDetails(true);
    let isMounted = true;

    prefetchDocumentContent(backendUrl, activeChatId, viewingDoc.id)
      .then(data => {
        if (!isMounted) return;
        if (data) {
          setPaperDetails(data);
          syncUpgradedDocument(viewingDoc, data);
        } else {
          setPaperDetails(null);
        }
      })
      .finally(() => {
        if (isMounted) setIsLoadingDetails(false);
      });

    return () => {
      isMounted = false;
    };
  }, [viewingDoc, activeChatId, backendUrl, syncUpgradedDocument]);

  useEffect(() => {
    if (groundingHighlight?.sentence || (groundingHighlight?.aiQuotes && groundingHighlight.aiQuotes.length > 0)) {
      setActiveTab("preview");
    }
  }, [groundingHighlight?.clickId, groundingHighlight?.sentence, groundingHighlight?.aiQuotes]);

  return {
    viewingDoc,
    setViewingDoc,
    paperDetails,
    isLoadingDetails,
    activeTab,
    setActiveTab
  };
}
