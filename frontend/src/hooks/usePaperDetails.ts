import { useState, useEffect, useCallback } from "react";
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

  // Proactive background pre-warming: pre-fetch full text content for workspace documents
  useEffect(() => {
    if (!activeChatId || !documents || documents.length === 0) return;
    documents.forEach(doc => {
      if (doc?.id) {
        prefetchDocumentContent(backendUrl, activeChatId, doc.id);
      }
    });
  }, [activeChatId, documents, backendUrl]);

  // Whenever active chat changes, always reset viewingDoc and paperDetails to exit reader mode and show default sources list
  useEffect(() => {
    setViewingDocState(null);
    setPaperDetails(null);
    if (onViewingDocChange) {
      onViewingDocChange(null);
    }
  }, [activeChatId, onViewingDocChange]);

  const updateDocumentsList = useDocumentStore((s) => s.updateDocumentsList);

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
      // Sync store if backend upgraded filename (e.g. .txt -> .pdf via on-demand OA fetch)
      if (cached.filename && cached.filename !== viewingDoc.filename) {
        updateDocumentsList((prev) =>
          prev.map((d) => d.id === viewingDoc.id ? { ...d, filename: cached.filename, has_full_pdf: cached.has_full_pdf, is_oa: cached.is_oa } : d)
        );
      }
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
          // Sync store if backend upgraded filename (e.g. .txt -> .pdf via on-demand OA fetch)
          if (data.filename && data.filename !== viewingDoc.filename) {
            updateDocumentsList((prev) =>
              prev.map((d) => d.id === viewingDoc.id ? { ...d, filename: data.filename, has_full_pdf: data.has_full_pdf, is_oa: data.is_oa } : d)
            );
          }
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
  }, [viewingDoc, activeChatId, backendUrl, updateDocumentsList]);

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
