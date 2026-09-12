import { useState, useRef, useEffect, useCallback } from "react";
import { Document, CitationGroundingHighlight } from "@/stores/documentStore";

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
}

const MAX_CACHE_ENTRIES = 30;

function getFromLruCache<K, V>(cache: Map<K, V>, key: K): V | undefined {
  if (!cache.has(key)) return undefined;
  const val = cache.get(key)!;
  cache.delete(key);
  cache.set(key, val);
  return val;
}

function setInLruCache<K, V>(cache: Map<K, V>, key: K, value: V, maxSize: number = MAX_CACHE_ENTRIES) {
  if (cache.has(key)) {
    cache.delete(key);
  } else if (cache.size >= maxSize) {
    const oldestKey = cache.keys().next().value;
    if (oldestKey !== undefined) {
      cache.delete(oldestKey);
    }
  }
  cache.set(key, value);
}

export function usePaperDetails({
  activeChatId,
  backendUrl,
  externalViewingDoc,
  onViewingDocChange,
  groundingHighlight,
}: UsePaperDetailsProps) {
  const [viewingDoc, setViewingDocState] = useState<Document | null>(externalViewingDoc || null);
  const [paperDetails, setPaperDetails] = useState<PaperDetailData | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"preview" | "pdf">("preview");

  const paperDetailsCacheRef = useRef<Map<number, PaperDetailData>>(new Map());

  const setViewingDoc = useCallback((doc: Document | null) => {
    setViewingDocState(doc);
    if (onViewingDocChange) {
      onViewingDocChange(doc);
    }
  }, [onViewingDocChange]);

  useEffect(() => {
    setViewingDocState(externalViewingDoc || null);
  }, [externalViewingDoc]);

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
      return;
    }

    const cached = getFromLruCache(paperDetailsCacheRef.current, viewingDoc.id);
    if (cached && (cached.id === viewingDoc.id || cached.filename === viewingDoc.filename)) {
      setPaperDetails(cached);
      setIsLoadingDetails(false);
      return;
    }

    setPaperDetails(null);
    setIsLoadingDetails(true);
    
    let isMounted = true;

    fetch(`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/content`)
      .then(res => res.json())
      .then(data => {
        if (!isMounted) return;
        if (data && !data.error) {
          setInLruCache(paperDetailsCacheRef.current, viewingDoc.id, data);
          setPaperDetails(data);
        } else {
          setPaperDetails(null);
        }
      })
      .catch(err => {
        if (!isMounted) return;
        console.error("Failed to load paper details:", err);
        setPaperDetails(null);
      })
      .finally(() => {
        if (isMounted) setIsLoadingDetails(false);
      });
      
    return () => {
      isMounted = false;
    };
  }, [viewingDoc, activeChatId, backendUrl]);

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
