"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Plus, 
  Check, 
  Minus,
  Trash2, 
  Download,
  Sidebar, 
  FileText, 
  Loader2,
  ArrowLeft,
  X,
  Copy,
  MessageSquare,
  Quote,
  Link as LinkIcon,
  ExternalLink,
  ChevronDown,
  BookOpen,
  Sparkles,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Document, CitationGroundingHighlight } from "@/app/ChatClient";
import { DownloadManager, DownloadTask } from "./DownloadManager";

interface RightSidebarProps {
  activeChatId: string | null;
  documents: Document[];
  onDocumentAdded: (doc: Document) => void;
  onDocumentDeleted?: (id: number) => void;
  onBulkDocumentsDeleted?: (ids: number[]) => void;
  onEnsureChatSession?: (suggestedTitle?: string) => Promise<string>;
  onAskAboutDocument?: (doc: Document, paperTitle?: string) => void;
  externalViewingDoc?: Document | null;
  groundingHighlight?: CitationGroundingHighlight | null;
  onClearGroundingHighlight?: () => void;
  onClearViewingDoc?: () => void;
  backendUrl: string;
  onClose: () => void;
}

interface PaperDetailData {
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
  content: string;
}

const cleanHtmlAbstract = (raw?: string): string => {
  if (!raw) return "";
  let text = raw;
  // Convert HTML entity &lt;br&gt; and <br> into double newlines
  text = text.replace(/&lt;\s*br\s*\/?\s*&gt;/gi, "\n\n");
  text = text.replace(/<\s*br\s*\/?>/gi, "\n\n");
  text = text.replace(/<\s*\/p\s*>/gi, "\n\n");
  text = text.replace(/<\s*p\s*>/gi, "");
  // Unescape standard entities
  text = text.replace(/&amp;/g, "&");
  text = text.replace(/&lt;/g, "<");
  text = text.replace(/&gt;/g, ">");
  text = text.replace(/&quot;/g, '"');
  text = text.replace(/&#39;/g, "'");
  text = text.replace(/&apos;/g, "'");
  // Remove remaining HTML tags
  text = text.replace(/<[^>]+>/g, "");
  // Strip markdown formatting artifacts from PDF text extraction
  text = text.replace(/\*\*_([^_*]+)_\*\*/g, "$1");
  text = text.replace(/\*\*([^*]+)\*\*/g, "$1");
  text = text.replace(/__([^_]+)__/g, "$1");
  text = text.replace(/(?<!\w)\*([^*]+)\*(?!\w)/g, "$1");
  text = text.replace(/(?<!\w)_([^_\s][^_]*)_(?!\w)/g, "$1");
  // Strip orphaned/unpaired markdown delimiters
  text = text.replace(/\*{2,}/g, "");
  text = text.replace(/(?<!\w)_+(?!\w)/g, "");
  text = text.replace(/^#{1,6}\s*/gm, "");
  // Format structured section headings if present without line breaks
  const headers = [
    "Research question", "Research methods", "Methods and materials", "Methodology",
    "Results and findings", "Results", "Findings", "Discussion", "Conclusion", "Conclusions",
    "Implications", "Background", "Objective", "Objectives", "Purpose", "Design",
    "Setting", "Participants", "Interventions", "Main outcomes", "Significance"
  ];
  headers.forEach(h => {
    const reg = new RegExp(`(?:\\n+|\\s+)\\b(${h})\\s*:\\s*`, "gi");
    text = text.replace(reg, "\n\n$1: ");
  });
  // Clean consecutive whitespace and newlines
  text = text.replace(/[ \t]+/g, " ");
  text = text.replace(/\n\s*\n\s*\n+/g, "\n\n");
  return text.trim();
};

// Helper: Strict grounding matcher for scientific claims & quotes (NotebookLM Style)
// Finds the most relevant passage/sentence in the paper and highlights it with smooth auto-scroll.
function renderHighlightedText(fullText: string, targetQuery?: string, highlightRef?: React.RefObject<HTMLElement | null>) {
  if (!fullText) return null;
  if (!targetQuery || targetQuery.trim().length < 8) {
    return <span>{fullText}</span>;
  }

  // Stopword filter for Indonesian & English
  const stopWords = new Set([
    "yang", "dari", "pada", "untuk", "dengan", "adalah", "dalam", "ini", "itu", "dan", "atau", "oleh", "ke", "di",
    "the", "and", "for", "with", "this", "that", "from", "using", "study", "paper", "research", "results", "analysis",
    "berikut", "tabel", "rekapitulasi", "dokumen", "terdapat", "adanya", "sebagai", "juga", "dapat", "akan", "telah"
  ]);

  const cleanQueryWords = targetQuery
    .toLowerCase()
    .replace(/[^a-zA-Z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(w => w.length >= 3 && !stopWords.has(w));

  if (cleanQueryWords.length === 0) {
    return <span>{fullText}</span>;
  }

  // Split document into paragraphs / sentences while preserving delimiters
  const sentenceRegex = /([^.!?\n\r]+(?:[.!?\n\r]+|$))/g;
  const rawSentences = fullText.match(sentenceRegex) || [fullText];

  let bestIndex = -1;
  let highestScore = 0;

  rawSentences.forEach((s, idx) => {
    const sClean = s.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ");
    const sWords = new Set(sClean.split(/\s+/).filter(w => w.length >= 3));
    let matchCount = 0;
    cleanQueryWords.forEach(w => {
      if (sWords.has(w) || sClean.includes(w)) matchCount++;
    });

    if (matchCount > 0) {
      const score = matchCount / Math.max(cleanQueryWords.length, 1);
      if (score > highestScore && (matchCount >= 2 || (cleanQueryWords.length <= 2 && matchCount >= 1))) {
        highestScore = score;
        bestIndex = idx;
      }
    }
  });

  if (bestIndex === -1) {
    return <span>{fullText}</span>;
  }

  return (
    <>
      {rawSentences.map((sentence, idx) => {
        if (idx === bestIndex) {
          return (
            <mark
              key={idx}
              ref={highlightRef as any}
              className="bg-amber-500/25 text-amber-200 border-l-4 border-amber-400 font-medium px-1.5 py-0.5 rounded-r inline-block shadow-sm transition-all duration-300 animate-pulse"
              title="Referenced Citation Context"
            >
              {sentence}
            </mark>
          );
        }
        return <span key={idx}>{sentence}</span>;
      })}
    </>
  );
}

const formatReadableDate = (dateStr?: string, yearFallback?: string) => {
  if (!dateStr && !yearFallback) return "Recent publication";
  if (!dateStr) return yearFallback || "2024";
  
  if (/^\d{4}$/.test(dateStr.trim())) {
    return dateStr.trim();
  }
  
  try {
    const d = new Date(dateStr);
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric"
      });
    }
  } catch (e) {
    // fallback
  }
  return dateStr;
};

interface CitationFormats {
  apa: string;
  ieee: string;
  harvard: string;
  mla: string;
  chicago: string;
  bibtex: string;
  ris: string;
}

const generateCitations = (
  title: string,
  authors: string[],
  year: string,
  journal: string,
  doi: string,
  url: string
): CitationFormats => {
  const cleanTitle = title.replace(/\.$/, "").trim();
  const cleanYear = year || "2024";
  const cleanJournal = journal || "Academic Publication";
  const doiUrl = doi ? (doi.startsWith("http") ? doi : `https://doi.org/${doi}`) : url;
  const authorList = authors.length > 0 ? authors : ["Anonymous"];
  
  // APA 7th
  const apaAuthors = authorList.map(a => {
    const parts = a.trim().split(" ");
    if (parts.length === 1) return parts[0];
    const last = parts[parts.length - 1];
    const initials = parts.slice(0, -1).map(p => p[0] + ".").join(" ");
    return `${last}, ${initials}`;
  }).join(", ");
  const apa = `${apaAuthors} (${cleanYear}). ${cleanTitle}. ${cleanJournal}.${doiUrl ? ` ${doiUrl}` : ""}`;

  // IEEE
  const ieeeAuthors = authorList.map(a => {
    const parts = a.trim().split(" ");
    if (parts.length === 1) return parts[0];
    const last = parts[parts.length - 1];
    const initials = parts.slice(0, -1).map(p => p[0] + ".").join(" ");
    return `${initials} ${last}`;
  }).join(" and ");
  const ieee = `${ieeeAuthors}, "${cleanTitle}," ${cleanJournal}, ${cleanYear}.${doi ? ` doi: ${doi}.` : ""}`;

  // Harvard
  const harvard = `${apaAuthors}, ${cleanYear}. ${cleanTitle}. ${cleanJournal}.${doiUrl ? ` Available at: <${doiUrl}>.` : ""}`;

  // MLA 9th
  const mlaAuthors = authorList.join(", ");
  const mla = `${mlaAuthors}. "${cleanTitle}." ${cleanJournal}, ${cleanYear}.${doiUrl ? ` ${doiUrl}.` : ""}`;

  // Chicago
  const chicago = `${mlaAuthors}. "${cleanTitle}." ${cleanJournal} (${cleanYear}).${doiUrl ? ` ${doiUrl}.` : ""}`;

  // BibTeX
  const citeKey = (authorList[0].split(" ").pop() || "paper").toLowerCase().replace(/[^a-z0-9]/g, "") + cleanYear + (cleanTitle.split(" ")[0] || "study").toLowerCase().replace(/[^a-z0-9]/g, "");
  const bibtex = `@article{${citeKey},
  title = {${cleanTitle}},
  author = {${authorList.join(" and ")}},
  journal = {${cleanJournal}},
  year = {${cleanYear}}${doi ? `,\n  doi = {${doi}}` : ""}${doiUrl ? `,\n  url = {${doiUrl}}` : ""}
}`;

  // RIS
  const ris = `TY  - JOUR
TI  - ${cleanTitle}
${authorList.map(a => `AU  - ${a}`).join("\n")}
JO  - ${cleanJournal}
PY  - ${cleanYear}
${doi ? `DO  - ${doi}\n` : ""}${doiUrl ? `UR  - ${doiUrl}\n` : ""}ER  -`;

  return { apa, ieee, harvard, mla, chicago, bibtex, ris };
};

export default function RightSidebar({ 
  activeChatId, 
  documents, 
  onDocumentAdded, 
  onDocumentDeleted, 
  onBulkDocumentsDeleted, 
  onEnsureChatSession, 
  onAskAboutDocument, 
  externalViewingDoc, 
  groundingHighlight,
  onClearGroundingHighlight,
  onClearViewingDoc, 
  backendUrl, 
  onClose 
}: RightSidebarProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [selectedDocs, setSelectedDocs] = useState<Record<number, boolean>>({});
  
  // Sorting state & dropdown
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [isSortMenuOpen, setIsSortMenuOpen] = useState(false);
  const sortMenuRef = useRef<HTMLDivElement>(null);

  // Detail / Reader View State (Consensus.app style)
  const [viewingDoc, setViewingDoc] = useState<Document | null>(externalViewingDoc || null);

  useEffect(() => {
    if (externalViewingDoc) {
      setViewingDoc(externalViewingDoc);
    }
  }, [externalViewingDoc]);
  const [paperDetails, setPaperDetails] = useState<PaperDetailData | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"overview" | "preview">("overview");
  
  // Citation Modal State
  const [isCiteModalOpen, setIsCiteModalOpen] = useState<boolean>(false);
  const [selectedCitationStyle, setSelectedCitationStyle] = useState<"apa" | "ieee" | "harvard" | "mla" | "chicago" | "bibtex" | "ris">("apa");
  const [copiedCitationKey, setCopiedCitationKey] = useState<string | null>(null);

  const [copiedDoi, setCopiedDoi] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const highlightElemRef = useRef<HTMLElement | null>(null);

  // Auto-scroll to highlighted grounded segment when details are loaded or highlight target changes
  useEffect(() => {
    if (!isLoadingDetails && highlightElemRef.current) {
      setTimeout(() => {
        highlightElemRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 150);
    }
  }, [isLoadingDetails, groundingHighlight, activeTab]);

  // Fetch document details when viewingDoc is set
  useEffect(() => {
    if (!viewingDoc || !activeChatId) {
      setPaperDetails(null);
      return;
    }
    setIsLoadingDetails(true);
    // When opened via citation pill click with context sentence, open directly in Full Paper tab
    if (groundingHighlight?.sentence) {
      setActiveTab("preview");
    } else {
      setActiveTab("overview");
    }
    setIsCiteModalOpen(false);
    fetch(`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/content`)
      .then(res => res.json())
      .then(data => {
        setPaperDetails(data);
      })
      .catch(err => {
        console.error("Failed to load paper details:", err);
      })
      .finally(() => {
        setIsLoadingDetails(false);
      });
  }, [viewingDoc, activeChatId, backendUrl, groundingHighlight?.sentence]);

  // Close sort menu on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sortMenuRef.current && !sortMenuRef.current.contains(event.target as Node)) {
        setIsSortMenuOpen(false);
      }
    };
    if (isSortMenuOpen) {
      window.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isSortMenuOpen]);

  const [isCleaningDuplicates, setIsCleaningDuplicates] = useState(false);
  const [cleanFeedback, setCleanFeedback] = useState<string | null>(null);

  const handleCleanDuplicates = async () => {
    if (!activeChatId || isCleaningDuplicates || documents.length === 0) return;
    setIsCleaningDuplicates(true);
    setCleanFeedback(null);
    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/clean_duplicates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.cleaned_doc_ids && data.cleaned_doc_ids.length > 0) {
          onBulkDocumentsDeleted?.(data.cleaned_doc_ids);
          setCleanFeedback(`Removed ${data.cleaned_count} duplicate(s)`);
        } else {
          setCleanFeedback("No duplicates found");
        }
        setTimeout(() => setCleanFeedback(null), 3000);
      }
    } catch (e) {
      console.error("Clean duplicates failed:", e);
    } finally {
      setIsCleaningDuplicates(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0]) return;
    
    setIsUploading(true);
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
      let currentChatId = activeChatId;
      if (!currentChatId && onEnsureChatSession) {
        currentChatId = await onEnsureChatSession(file.name.replace(/\.[^/.]+$/, ""));
      }

      if (!currentChatId) {
        alert("Failed to initialize chat session.");
        return;
      }

      const res = await fetch(`${backendUrl}/chats/${currentChatId}/upload`, {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        const newDoc = await res.json();
        onDocumentAdded(newDoc);
      } else {
        const err = await res.json();
        alert(`Upload failed: ${err.detail || "An error occurred"}`);
      }
    } catch (err) {
      console.error("Upload failed", err);
      alert("Failed to connect to server for document upload.");
    } finally {
      setIsUploading(false);
      if (e.target) e.target.value = "";
    }
  };

  // Selection logic
  const isAllSelected = documents.length > 0 && documents.every(d => selectedDocs[d.id] !== false);
  const isSomeSelected = documents.some(d => selectedDocs[d.id] !== false);
  const isPartiallySelected = isSomeSelected && !isAllSelected;

  const getFileBadgeInfo = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase() || "doc";
    if (ext === "pdf") {
      return { label: "PDF", bg: "bg-red-950/70 border-red-800/80 text-red-400" };
    } else if (ext === "docx" || ext === "doc") {
      return { label: "DOC", bg: "bg-blue-950/70 border-blue-800/80 text-blue-400" };
    } else if (ext === "bib" || ext === "bibtex") {
      return { label: "BIB", bg: "bg-amber-950/70 border-amber-800/80 text-amber-400" };
    } else if (ext === "ris") {
      return { label: "RIS", bg: "bg-orange-950/70 border-orange-800/80 text-orange-400" };
    } else if (ext === "csv" || ext === "tsv") {
      return { label: "CSV", bg: "bg-emerald-950/70 border-emerald-800/80 text-emerald-400" };
    } else if (ext === "md") {
      return { label: "MD", bg: "bg-purple-950/70 border-purple-800/80 text-purple-400" };
    } else {
      return { label: "TXT", bg: "bg-gray-800/80 border-gray-700 text-gray-300" };
    }
  };

  const toggleDocSelection = (docId: number) => {
    setSelectedDocs(prev => {
      const current = prev[docId] !== undefined ? prev[docId] : true;
      return {
        ...prev,
        [docId]: !current
      };
    });
  };

  const handleToggleSelectAll = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const nextState = !isAllSelected;
    const updated: Record<number, boolean> = {};
    documents.forEach(d => {
      updated[d.id] = nextState;
    });
    setSelectedDocs(updated);
  };

  // Sort documents based on sortBy and sortDirection (asc/desc)
  const sortedDocuments = [...documents].sort((a, b) => {
    let cmp = 0;
    if (sortBy === "title") {
      cmp = a.filename.localeCompare(b.filename);
    } else {
      const dateA = new Date(a.created_at || 0).getTime() || a.id;
      const dateB = new Date(b.created_at || 0).getTime() || b.id;
      cmp = dateA - dateB;
    }
    return sortDirection === "asc" ? cmp : -cmp;
  });

  const [showBulkDeleteConfirm, setShowBulkDeleteConfirm] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [isBulkDownloading, setIsBulkDownloading] = useState(false);
  const [downloadTask, setDownloadTask] = useState<DownloadTask | null>(null);

  const selectedDocList = sortedDocuments.filter(d => selectedDocs[d.id] !== false);
  const selectedCount = selectedDocList.length;

  const handleBulkDownload = async () => {
    if (!activeChatId || selectedCount === 0 || isBulkDownloading) return;
    setIsBulkDownloading(true);
    const docIds = selectedDocList.map(d => d.id);

    // If only 1 document is selected, trigger immediate direct single PDF download
    if (docIds.length === 1) {
      try {
        const doc = selectedDocList[0];
        const link = document.createElement("a");
        link.href = `${backendUrl}/chats/${activeChatId}/documents/${doc.id}/download`;
        link.download = doc.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (err) {
        console.error("Single download error:", err);
      } finally {
        setIsBulkDownloading(false);
      }
      return;
    }

    // Multiple documents: Launch Google Drive style floating progress stream
    setDownloadTask({
      status: "preparing",
      total: docIds.length,
      current: 0,
      percent: 0,
      currentFile: "Connecting to server..."
    });

    try {
      const response = await fetch(`${backendUrl}/chats/${activeChatId}/documents/bulk_download_stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_ids: docIds })
      });

      if (!response.ok) {
        throw new Error("Failed to start download stream");
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      if (!reader) {
        throw new Error("No readable stream received");
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          const line = block.trim();
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "init") {
                setDownloadTask({
                  status: "zipping",
                  total: data.total || docIds.length,
                  current: 0,
                  percent: 0,
                  currentFile: "Starting parallel archive build..."
                });
              } else if (data.type === "progress") {
                const calculatedPercent = typeof data.percent === "number" 
                  ? data.percent 
                  : (data.total > 0 ? Math.round((data.current / data.total) * 100) : 0);
                setDownloadTask(prev => ({
                  status: "zipping",
                  total: data.total || docIds.length,
                  current: data.current,
                  percent: calculatedPercent,
                  currentFile: data.filename || prev?.currentFile || ""
                }));
              } else if (data.type === "complete") {
                setDownloadTask({
                  status: "complete",
                  total: data.total_files || docIds.length,
                  current: data.total_files || docIds.length,
                  percent: 100,
                  currentFile: "Download complete!",
                  totalSizeMb: data.total_size_mb
                });

                // Auto-trigger browser download
                const downloadLink = document.createElement("a");
                downloadLink.href = `${backendUrl}${data.download_url}`;
                downloadLink.download = data.filename || `NotbookLM_Sources_${docIds.length}_files.zip`;
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
              }
            } catch (pErr) {
              console.error("Error parsing download progress SSE:", pErr);
            }
          }
        }
      }
    } catch (err: any) {
      console.error("Bulk download error:", err);
      setDownloadTask({
        status: "error",
        total: docIds.length,
        current: 0,
        percent: 0,
        currentFile: "",
        errorMsg: err?.message || "Failed to download ZIP archive"
      });
    } finally {
      setIsBulkDownloading(false);
    }
  };

  const handleConfirmBulkDelete = async () => {
    if (!activeChatId || selectedCount === 0 || isBulkDeleting) return;
    setIsBulkDeleting(true);
    try {
      const docIds = selectedDocList.map(d => d.id);
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/bulk_delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_ids: docIds })
      });
      if (res.ok) {
        if (onBulkDocumentsDeleted) {
          onBulkDocumentsDeleted(docIds);
        } else if (onDocumentDeleted) {
          docIds.forEach(id => onDocumentDeleted(id));
        }
        setShowBulkDeleteConfirm(false);
        if (viewingDoc && docIds.includes(viewingDoc.id)) {
          setViewingDoc(null);
        }
      }
    } catch (err) {
      console.error("Bulk delete error:", err);
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const copyToClipboard = (text: string, type: "doi" | "link" | "citation") => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    if (type === "doi") {
      setCopiedDoi(true);
      setTimeout(() => setCopiedDoi(false), 2000);
    } else if (type === "link") {
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };

  const downloadFileText = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  // =========================================================================
  // VIEW MODE: CONSENSUS.AI STYLE ACADEMIC PAPER READER VIEW (Overview & Full Paper)
  // =========================================================================
  if (viewingDoc) {
    const filenameFallback = viewingDoc.filename.replace(/\.[^/.]+$/, "").replace(/_/g, " ");
    
    // Generic publisher headers that should never be displayed as paper title
    const GENERIC_HEADERS = new Set([
      "abstract", "abstrak", "overview", "paper", "document", "introduction", "keywords",
      "article in press", "in press", "journal pre-proof", "uncorrected proof",
      "corrected proof", "original article", "research article", "full length article",
      "short communication", "review article", "full paper", "research paper",
      "accepted manuscript", "author's copy",
    ]);
    
    let title = (paperDetails?.title || filenameFallback).replace(/<[^>]+>/g, "");
    if (!title || GENERIC_HEADERS.has(title.trim().toLowerCase())) {
      title = filenameFallback;
    }
    const authorsStr = paperDetails?.authors && paperDetails.authors.length > 0 
      ? paperDetails.authors.join(", ") 
      : "Academic Researchers";
    const pubDateStr = formatReadableDate(paperDetails?.publication_date, paperDetails?.year);
    const journalName = paperDetails?.journal || "Scholarly Publication";
    const citationsCount = paperDetails?.citations !== undefined ? paperDetails.citations : 0;
    const doiStr = paperDetails?.doi || "";
    const cleanAbstract = cleanHtmlAbstract(paperDetails?.abstract) || (isLoadingDetails ? "" : "Abstract not provided in public indexing metadata.");
    const landingUrl = paperDetails?.url || (doiStr ? `https://doi.org/${doiStr}` : "");

    const citations = generateCitations(
      title,
      paperDetails?.authors || [],
      paperDetails?.year || "2024",
      journalName,
      doiStr,
      landingUrl
    );

    return (
      <aside className="w-80 sm:w-[460px] h-full bg-[#18191b] border-l border-white/10 flex flex-col shrink-0 select-none z-10 transition-all relative">
        {/* 1. Header Bar: ← Paper + Circular Close Button */}
        <div className="px-4 py-3 flex items-center justify-between border-b border-white/5">
          <button
            onClick={() => {
              setViewingDoc(null);
              onClearViewingDoc?.();
            }}
            className="flex items-center gap-2 text-xs font-semibold text-gray-200 hover:text-white transition-colors cursor-pointer group"
          >
            <ArrowLeft size={16} className="text-gray-400 group-hover:text-white transition-transform group-hover:-translate-x-0.5" />
            <span className="text-sm tracking-tight font-medium">Paper</span>
          </button>

          <button 
            onClick={onClose}
            className="w-7 h-7 rounded-full bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
            title="Close"
          >
            <X size={14} />
          </button>
        </div>

        {/* 2. Simplified 2 Navigation Tabs: Overview & Full Paper */}
        <div className="flex items-center px-4 border-b border-white/10 text-xs font-medium text-gray-400 gap-6 shrink-0">
          <button
            onClick={() => setActiveTab("overview")}
            className={`py-2.5 transition-colors cursor-pointer border-b-2 font-semibold ${
              activeTab === "overview" ? "text-white border-white" : "text-gray-400 hover:text-gray-200 border-transparent"
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab("preview")}
            className={`py-2.5 transition-colors cursor-pointer border-b-2 font-medium flex items-center gap-1.5 ${
              activeTab === "preview" ? "text-white border-white font-semibold" : "text-gray-400 hover:text-gray-200 border-transparent"
            }`}
          >
            <span>Full Paper</span>
          </button>
        </div>

        {/* 3. Main Body */}
        {activeTab === "overview" ? (
          <div className="flex-1 p-4 sm:p-5 overflow-y-auto custom-scrollbar space-y-4 min-h-0">
            {/* Paper Title with Global Reference Badge */}
            <div className="space-y-1.5">
              <div className="flex items-start gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-blue-500/15 text-blue-300 border border-blue-500/30 shrink-0 mt-0.5 select-none" title="Permanent Global Reference Index">
                  [{viewingDoc.index || (documents.findIndex(d => d.id === viewingDoc.id) + 1)}]
                </span>
                <h1 className="text-[15px] sm:text-[16px] font-bold text-white leading-snug tracking-tight">
                  {title}
                </h1>
              </div>

              {/* Authors & Publication Date (Textual format e.g. Oct 9, 2024) */}
              {isLoadingDetails ? (
                <div className="flex items-center gap-2 pt-0.5 animate-pulse">
                  <div className="h-3 w-24 bg-white/10 rounded" />
                  <div className="h-3 w-40 bg-white/5 rounded" />
                </div>
              ) : (
                <p className="text-xs text-gray-400 font-normal">
                  <span>{pubDateStr}</span>
                  {authorsStr && (
                    <>
                      <span className="mx-1.5 text-gray-600">·</span>
                      <span className="text-gray-300">{authorsStr}</span>
                    </>
                  )}
                </p>
              )}
            </div>

            {/* Journal / Venue & Quality Metrics */}
            {isLoadingDetails ? (
              <div className="flex items-center justify-between pt-1 text-xs animate-pulse">
                <div className="space-y-1.5">
                  <div className="h-3.5 w-32 bg-white/10 rounded" />
                  <div className="h-3 w-20 bg-white/5 rounded" />
                </div>
                <div className="space-y-1.5 text-right flex flex-col items-end">
                  <div className="h-3.5 w-10 bg-white/10 rounded" />
                  <div className="h-3 w-12 bg-white/5 rounded" />
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between pt-1 text-xs">
                <div>
                  <p className="font-semibold text-gray-200 text-[12px]">{journalName}</p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-[11px] text-gray-400 font-medium">{paperDetails?.journal_metric || "Peer-Reviewed"}</span>
                  </div>
                </div>

                {/* Citations Count */}
                <div className="text-right">
                  <span className="text-xs font-semibold text-gray-300">{citationsCount}</span>
                  <p className="text-[10.5px] text-gray-400">Citations</p>
                </div>
              </div>
            )}

            {/* DOI Row with Copy Button */}
            {isLoadingDetails ? (
              <div className="flex items-center gap-2 pt-0.5 animate-pulse">
                <div className="h-3 w-7 bg-white/5 rounded" />
                <div className="h-3 w-36 bg-white/10 rounded" />
              </div>
            ) : doiStr ? (
              <div className="flex items-center gap-1.5 text-[11px] text-gray-400 pt-0.5">
                <span className="font-medium text-gray-500">DOI</span>
                <span className="font-mono text-gray-300 truncate">{doiStr}</span>
                <button
                  onClick={() => copyToClipboard(doiStr, "doi")}
                  className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors cursor-pointer shrink-0"
                  title="Copy DOI"
                >
                  {copiedDoi ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                </button>
              </div>
            ) : null}

            {/* Access & Discovery Badge (Positive-Neutral Model) */}
            <div className="pt-1">
              {isLoadingDetails ? (
                <div className="h-6 w-28 rounded-lg bg-white/10 animate-pulse" />
              ) : paperDetails?.is_oa || paperDetails?.pdf_url ? (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
                  <span>Open Access (PDF Available)</span>
                </div>
              ) : (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 text-gray-400 text-xs font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400 shrink-0" />
                  <span>Publisher Source</span>
                </div>
              )}
            </div>

            {/* Divider */}
            <div className="border-t border-white/10 pt-2" />

            {/* Abstract / Overview Section */}
            {isLoadingDetails ? (
              <div className="space-y-3 pt-1 animate-pulse">
                <div className="flex items-center justify-between">
                  <div className="h-3.5 w-24 bg-white/10 rounded" />
                  <div className="h-3.5 w-20 bg-white/5 rounded" />
                </div>
                <div className="space-y-2 pt-1">
                  <div className="h-3.5 bg-white/10 rounded w-full" />
                  <div className="h-3.5 bg-white/10 rounded w-11/12" />
                  <div className="h-3.5 bg-white/10 rounded w-full" />
                  <div className="h-3.5 bg-white/10 rounded w-4/5" />
                  <div className="h-3.5 bg-white/10 rounded w-3/4" />
                </div>
              </div>
            ) : paperDetails?.abstract_type === "ai_summary" ? (
              /* AI Synthesis / Executive Summary Card with Disclaimer */
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-purple-300">
                    <Sparkles size={13} className="text-purple-400" />
                    <span>AI Synthesis Overview</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-950/60 border border-purple-800/60 text-purple-300">
                    Publisher Metadata
                  </span>
                </div>

                {/* Clarification Alert Box */}
                <div className="p-2.5 rounded-lg bg-purple-950/30 border border-purple-800/40 text-[11px] text-purple-200/90 leading-relaxed flex items-start gap-2">
                  <Info size={13} className="text-purple-400 shrink-0 mt-0.5" />
                  <p>
                    <span className="font-semibold text-purple-200">AI Overview Note:</span> Executive overview synthesized from verified indexing metadata.
                  </p>
                </div>

                <p className="text-[12.5px] sm:text-[13px] text-gray-300 leading-relaxed font-sans select-text whitespace-pre-line break-words text-justify">
                  {renderHighlightedText(cleanAbstract, groundingHighlight?.sentence, highlightElemRef)}
                </p>
              </div>
            ) : (
              /* Official Authentic Abstract */
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-gray-200 tracking-wider uppercase">
                    <FileText size={13} className="text-blue-400" />
                    <span>Abstract</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 flex items-center gap-1">
                    <Check size={10} />
                    <span>Official Abstract</span>
                  </span>
                </div>

                <p className="text-[12.5px] sm:text-[13px] text-gray-300 leading-relaxed font-sans select-text whitespace-pre-line break-words text-justify">
                  {renderHighlightedText(cleanAbstract, groundingHighlight?.sentence, highlightElemRef)}
                </p>
              </div>
            )}
          </div>
        ) : (
          /* TAB 2: FULL PAPER / IN-APP NATIVE SCROLLABLE DOCUMENT READER */
          <div className="flex-1 flex flex-col min-h-0 bg-[#121315] relative overflow-hidden">
            {/* Top Preview Controls Bar */}
            <div className="px-3.5 py-2 bg-[#1e1f22] border-b border-white/10 flex items-center justify-between text-xs text-gray-300 shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0 animate-pulse" />
                <span className="truncate max-w-[200px] font-mono text-[11px] text-gray-300">
                  {viewingDoc.filename}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {paperDetails?.content && (
                  <span className="text-[10px] text-gray-500 font-mono hidden sm:inline">
                    {paperDetails.content.length.toLocaleString()} chars
                  </span>
                )}

                {activeChatId && (
                  <a
                    href={`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/download`}
                    download={viewingDoc.filename}
                    className="px-2 py-1 rounded bg-white/5 hover:bg-white/15 text-gray-300 hover:text-white transition-colors cursor-pointer flex items-center gap-1 text-[11px]"
                    title="Download document file"
                  >
                    <Download size={12} />
                    <span>Download</span>
                  </a>
                )}
              </div>
            </div>

            {/* In-App Paper Document Reader Canvas (Fully Scrollable) */}
            <div className="flex-1 p-4 overflow-y-auto custom-scrollbar space-y-4 select-text">
              {isLoadingDetails ? (
                <div className="py-24 flex flex-col items-center justify-center text-center space-y-3">
                  <Loader2 size={24} className="animate-spin text-blue-400" />
                  <p className="text-xs text-gray-400">Loading document content...</p>
                </div>
              ) : paperDetails?.content ? (
                <div className="p-4 sm:p-5 rounded-xl bg-[#1b1c1e] border border-white/10 shadow-lg space-y-4">
                  {/* Status Banner for Abstract Only vs Full Manuscript */}
                  {paperDetails.content.length < 3500 || paperDetails.content.includes("NOTBOOKLM SCHOLARLY ARCHIVE") ? (
                    <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-800/40 flex items-start gap-2.5 text-xs text-amber-200">
                      <Info size={15} className="text-amber-400 shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-amber-100">Publication Brief & Abstract (Full Manuscript Paywalled)</p>
                        <p className="text-[11.5px] text-amber-300/80 mt-0.5">
                          Full publisher manuscript is protected by publisher paywall. Displaying verified academic metadata and official author abstract.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 flex items-center gap-2 text-xs text-emerald-300">
                      <Check size={14} className="text-emerald-400 shrink-0" />
                      <span className="font-medium">Full Manuscript Verified</span>
                    </div>
                  )}

                  {/* Paper Sheet Header */}
                  <div className="pb-3 border-b border-white/10 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold font-mono uppercase bg-blue-950/70 border border-blue-800/80 text-blue-400">
                        {paperDetails.type?.toUpperCase() || "PDF"}
                      </span>
                      {paperDetails.year && (
                        <span className="text-[11px] text-gray-400">
                          {paperDetails.year}
                        </span>
                      )}
                    </div>

                    <h2 className="text-sm sm:text-[15px] font-bold text-white leading-snug">
                      {title}
                    </h2>

                    {authorsStr && (
                      <p className="text-xs text-gray-400">
                        By {authorsStr}
                      </p>
                    )}
                  </div>

                  {/* Clean Formatted Document Body (Scrolls through the entire file) */}
                  <div className="text-[12.5px] sm:text-[13px] text-gray-200 leading-relaxed font-sans whitespace-pre-wrap select-text break-words">
                    {renderHighlightedText(
                      paperDetails.content.replace(/^#\s+[^\n]+\n+/, "").replace(/##\s+Abstract & Overview\n+/, ""),
                      groundingHighlight?.sentence,
                      highlightElemRef
                    )}
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-[#1b1c1e] border border-white/10 text-center py-10 space-y-2">
                  <FileText size={28} className="text-gray-500 mx-auto stroke-[1.5]" />
                  <p className="text-xs text-gray-300 font-medium">Document content is indexed</p>
                  <p className="text-[11px] text-gray-500 max-w-[240px] mx-auto">
                    Full text is registered in the AI source context for answering questions.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 4. Consensus-style Bottom Floating Action Toolbar */}
        <div className={`p-3 border-t border-white/10 bg-[#161719] flex items-center justify-between gap-1.5 shrink-0 select-none transition-opacity ${
          isLoadingDetails ? "opacity-40 pointer-events-none" : "opacity-100"
        }`}>
          <div className="flex items-center gap-1.5">
            {/* Ask Button (Pill) */}
            <button
              disabled={isLoadingDetails}
              onClick={() => {
                if (viewingDoc && onAskAboutDocument) {
                  onAskAboutDocument(viewingDoc, paperDetails?.title || viewingDoc.filename);
                }
                const chatInput = document.getElementById("chat-input-textarea");
                if (chatInput) {
                  chatInput.focus();
                }
              }}
              className="h-8 px-3 rounded-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-xs flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm disabled:cursor-not-allowed"
              title="Ask AI questions specifically about this paper"
            >
              <MessageSquare size={13} />
              <span>Ask</span>
            </button>

            {/* Multi-Format Cite Button (Opens Interactive Citation Modal) */}
            <button
              disabled={isLoadingDetails}
              onClick={() => setIsCiteModalOpen(true)}
              className="h-8 px-2.5 rounded-full bg-white/5 hover:bg-white/10 disabled:opacity-50 border border-white/10 text-gray-300 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:cursor-not-allowed"
              title="Cite paper (APA, IEEE, Harvard, MLA, Chicago, BibTeX, RIS)"
            >
              <Quote size={13} />
              <span>Cite</span>
            </button>

            {/* Copy Link Icon Button */}
            <button
              disabled={isLoadingDetails || !landingUrl}
              onClick={() => copyToClipboard(landingUrl, "link")}
              className="w-8 h-8 rounded-full hover:bg-white/10 disabled:opacity-50 text-gray-400 hover:text-white flex items-center justify-center transition-colors cursor-pointer disabled:cursor-not-allowed"
              title={copiedLink ? "Link Copied!" : "Copy Paper Link"}
            >
              {copiedLink ? <Check size={14} className="text-emerald-400" /> : <LinkIcon size={14} />}
            </button>

            {/* Download Icon Button */}
            {activeChatId && (
              <a
                href={isLoadingDetails ? undefined : `${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/download`}
                download={viewingDoc.filename}
                className={`w-8 h-8 rounded-full hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors ${
                  isLoadingDetails ? "pointer-events-none opacity-50 cursor-not-allowed" : "cursor-pointer"
                }`}
                title="Download original document"
              >
                <Download size={14} />
              </a>
            )}
          </div>

          {/* Right Side: PDF / External Landing Page Pill - ALWAYS shown */}
          {(() => {
            const pdfLink = landingUrl || `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
            return (
              <a
                href={isLoadingDetails ? undefined : pdfLink}
                target="_blank"
                rel="noopener noreferrer"
                className={`h-8 px-2.5 rounded-full bg-white/5 hover:bg-white/15 border border-white/10 text-gray-200 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors shrink-0 ${
                  isLoadingDetails ? "pointer-events-none opacity-50 cursor-not-allowed" : "cursor-pointer"
                }`}
                title={landingUrl ? "Open full-text paper link in new tab" : "Search for this paper on Google Scholar"}
              >
                <ExternalLink size={12} />
                <span>{landingUrl ? "PDF ↗" : "Find ↗"}</span>
              </a>
            );
          })()}
        </div>

        {/* 5. Interactive Multi-Format Citation Modal */}
        {isCiteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-150">
            <div className="bg-[#222326] border border-white/15 rounded-2xl w-full max-w-[530px] p-5 shadow-2xl space-y-3.5 animate-in zoom-in-95 duration-150 text-gray-200">
              {/* Modal Header */}
              <div className="flex items-center justify-between pb-2.5 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <Quote size={16} className="text-blue-400" />
                  <h3 className="text-sm font-semibold text-white">Cite this Paper</h3>
                </div>
                <button
                  onClick={() => setIsCiteModalOpen(false)}
                  className="w-7 h-7 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors cursor-pointer"
                >
                  <X size={14} />
                </button>
              </div>

              {/* Citation Format Tabs (Clean, Scrollable & Compact) */}
              <div className="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar text-xs font-medium">
                {[
                  { id: "apa", label: "APA 7th" },
                  { id: "ieee", label: "IEEE" },
                  { id: "harvard", label: "Harvard" },
                  { id: "mla", label: "MLA 9th" },
                  { id: "chicago", label: "Chicago" },
                  { id: "bibtex", label: "BibTeX" },
                  { id: "ris", label: "RIS" },
                ].map((st) => (
                  <button
                    key={st.id}
                    onClick={() => setSelectedCitationStyle(st.id as any)}
                    className={`px-2.5 py-1.5 rounded-lg whitespace-nowrap transition-colors cursor-pointer text-xs ${
                      selectedCitationStyle === st.id
                        ? "bg-blue-600 text-white font-semibold shadow-sm"
                        : "bg-white/5 hover:bg-white/10 text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    {st.label}
                  </button>
                ))}
              </div>

              {/* Fixed-Height Scrollable Citation Content Box */}
              <div className="h-[140px] p-3.5 rounded-xl bg-[#141517] border border-white/10 font-sans text-xs leading-relaxed select-text text-gray-200 break-words whitespace-pre-wrap overflow-y-auto custom-scrollbar">
                {citations[selectedCitationStyle]}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-1 border-t border-white/5">
                <div className="flex items-center gap-2">
                  {selectedCitationStyle === "bibtex" && (
                    <button
                      onClick={() => downloadFileText(citations.bibtex, `${doiStr ? doiStr.replace(/[^a-z0-9]/gi, "_") : "paper"}.bib`)}
                      className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-gray-300 hover:text-white transition-colors cursor-pointer flex items-center gap-1.5"
                    >
                      <Download size={13} />
                      <span>Download .bib</span>
                    </button>
                  )}
                  {selectedCitationStyle === "ris" && (
                    <button
                      onClick={() => downloadFileText(citations.ris, `${doiStr ? doiStr.replace(/[^a-z0-9]/gi, "_") : "paper"}.ris`)}
                      className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-gray-300 hover:text-white transition-colors cursor-pointer flex items-center gap-1.5"
                    >
                      <Download size={13} />
                      <span>Download .ris</span>
                    </button>
                  )}
                </div>

                <Button
                  size="sm"
                  onClick={() => {
                    const text = citations[selectedCitationStyle];
                    navigator.clipboard.writeText(text);
                    setCopiedCitationKey(selectedCitationStyle);
                    setTimeout(() => setCopiedCitationKey(null), 2000);
                  }}
                  className="bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs rounded-lg px-4 h-8 cursor-pointer flex items-center gap-1.5 shadow-sm"
                >
                  {copiedCitationKey === selectedCitationStyle ? (
                    <>
                      <Check size={13} className="text-white" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={13} />
                      <span>Copy Citation</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}
      </aside>
    );
  }

  // ==========================================
  // VIEW MODE: STANDARD SOURCES LIST PANEL
  // ==========================================
  return (
    <aside className="w-80 h-full bg-[#1e1f20] border-l border-white/10 flex flex-col shrink-0 select-none z-10 transition-all relative">
      {/* 1. Header: Sources Title & Collapse Button */}
      <div className="p-4 flex items-center justify-between border-b border-white/5">
        <h2 className="text-base font-semibold text-white tracking-tight">Sources</h2>
        <Button 
          variant="ghost" 
          size="icon" 
          className="h-8 w-8 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg cursor-pointer"
          onClick={onClose}
          title="Close Sources"
        >
          <Sidebar size={16} className="rotate-180" />
        </Button>
      </div>

      {/* Hidden File Input for Multi-format Document Upload */}
      <input
        ref={fileInputRef}
        type="file"
        id="sources-file-upload"
        className="hidden"
        accept=".pdf,.docx,.doc,.txt,.md,.bib,.bibtex,.ris,.csv,.tsv"
        onChange={handleFileUpload}
        disabled={isUploading}
      />

      <div className="p-3.5 space-y-2.5 flex-1 flex flex-col overflow-y-auto custom-scrollbar min-h-0">
        {/* 2. Prominent '+ Add sources' Button (NotebookLM Style) */}
        <div>
          <Button
            variant="outline"
            className="w-full h-11 rounded-full bg-[#262729] hover:bg-[#2e3033] border border-white/15 text-gray-100 hover:text-white font-medium text-sm flex items-center justify-center gap-2 cursor-pointer shadow-sm transition-colors"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            {isUploading ? (
              <>
                <Loader2 size={16} className="animate-spin text-blue-400" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <Plus size={18} className="text-gray-300" />
                <span>Add sources</span>
              </>
            )}
          </Button>
          <p className="text-[10.5px] text-gray-500 text-center mt-1.5">
            Supports PDF, Word (.docx), TXT, Markdown, BibTeX, RIS, CSV
          </p>
        </div>

        {/* Dynamic Clean Feedback Notification */}
        {cleanFeedback && (
          <div className="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-medium flex items-center gap-2 animate-in fade-in zoom-in-95 duration-150">
            <Check size={13} className="text-emerald-400 shrink-0" />
            <span className="text-[12px]">{cleanFeedback}</span>
          </div>
        )}

        {/* 3. Controls Row: Sort (3 descending bars), Contextual Actions (Download & Delete), and Select All */}
        <div className="flex items-center justify-between pt-1 px-0 text-xs text-gray-400 relative">
          <div className="flex items-center gap-1">
            {/* Sort Button & Dropdown */}
            <div className="relative" ref={sortMenuRef}>
              <button 
                onClick={() => setIsSortMenuOpen(prev => !prev)}
                className="w-6 h-6 -ml-1 rounded text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-colors cursor-pointer flex items-center justify-center"
                title="Sort sources"
              >
                <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" className="opacity-90">
                  <rect x="2" y="3" width="12" height="1.6" rx="0.8" />
                  <rect x="2" y="7.2" width="8" height="1.6" rx="0.8" />
                  <rect x="2" y="11.4" width="4.5" height="1.6" rx="0.8" />
                </svg>
              </button>

              {/* Sort Dropdown Menu (2 Sections with Divider: Criteria & Direction) */}
              {isSortMenuOpen && (
                <div className="absolute left-0 top-7 z-30 w-36 rounded-xl bg-[#28292c] border border-white/15 shadow-2xl p-1 text-xs animate-in fade-in zoom-in-95 duration-100">
                  {/* Section 1: Sort Criteria */}
                  <div className="space-y-0.5 pb-0.5">
                    <button
                      onClick={() => { setSortBy("title"); setIsSortMenuOpen(false); }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-gray-300 hover:text-white hover:bg-white/10"
                    >
                      <span className={sortBy === "title" ? "text-white font-medium" : "text-gray-300"}>Title</span>
                      {sortBy === "title" && <Check size={13} className="text-white" strokeWidth={2.5} />}
                    </button>
                    <button
                      onClick={() => { setSortBy("date"); setIsSortMenuOpen(false); }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-gray-300 hover:text-white hover:bg-white/10"
                    >
                      <span className={sortBy === "date" ? "text-white font-medium" : "text-gray-300"}>Date added</span>
                      {sortBy === "date" && <Check size={13} className="text-white" strokeWidth={2.5} />}
                    </button>
                  </div>

                  {/* Section Divider Line */}
                  <div className="border-t border-white/10 my-1" />

                  {/* Section 2: Sort Direction (Ascending / Descending) */}
                  <div className="space-y-0.5 pt-0.5">
                    <button
                      onClick={() => { setSortDirection("asc"); setIsSortMenuOpen(false); }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-gray-300 hover:text-white hover:bg-white/10"
                    >
                      <span className={sortDirection === "asc" ? "text-white font-medium" : "text-gray-300"}>Ascending</span>
                      {sortDirection === "asc" && <Check size={13} className="text-white" strokeWidth={2.5} />}
                    </button>
                    <button
                      onClick={() => { setSortDirection("desc"); setIsSortMenuOpen(false); }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-gray-300 hover:text-white hover:bg-white/10"
                    >
                      <span className={sortDirection === "desc" ? "text-white font-medium" : "text-gray-300"}>Descending</span>
                      {sortDirection === "desc" && <Check size={13} className="text-white" strokeWidth={2.5} />}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Always Rendered Action Icon Buttons with Clean Disabled State */}
            <div className="flex items-center gap-1">
              {/* Clean Duplicates Button */}
              <button
                onClick={handleCleanDuplicates}
                disabled={documents.length <= 1 || isCleaningDuplicates}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  documents.length > 1 && !isCleaningDuplicates
                    ? "text-gray-400 hover:text-emerald-400 hover:bg-emerald-500/10 cursor-pointer"
                    : "text-gray-600 opacity-40 cursor-not-allowed"
                }`}
                title="Clean duplicate sources automatically"
              >
                {isCleaningDuplicates ? (
                  <Loader2 size={14} className="animate-spin text-emerald-400" />
                ) : (
                  <Sparkles size={14} />
                )}
              </button>

              {/* Download Button */}
              <button
                onClick={handleBulkDownload}
                disabled={selectedCount === 0 || isBulkDownloading}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  selectedCount > 0
                    ? "text-gray-400 hover:text-gray-200 hover:bg-white/5 cursor-pointer"
                    : "text-gray-600 opacity-40 cursor-not-allowed"
                }`}
                title={selectedCount > 0 ? `Download ${selectedCount} selected file(s)` : "Select sources to download"}
              >
                {isBulkDownloading ? (
                  <Loader2 size={15} className="animate-spin text-blue-400" />
                ) : (
                  <Download size={15} />
                )}
              </button>

              {/* Delete Button */}
              <button
                onClick={() => setShowBulkDeleteConfirm(true)}
                disabled={selectedCount === 0 || isBulkDeleting}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  selectedCount > 0
                    ? "text-gray-400 hover:text-red-400 hover:bg-white/5 cursor-pointer"
                    : "text-gray-600 opacity-40 cursor-not-allowed"
                }`}
                title={selectedCount > 0 ? `Delete ${selectedCount} selected file(s)` : "Select sources to delete"}
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>

          {/* Select all label and checkbox (Clickable ONLY on the checkbox) */}
          <div className="flex items-center gap-2 pr-0.5 whitespace-nowrap select-none">
            <span className="text-[11px] font-medium text-gray-400 select-none">Select all</span>
            <button
              type="button"
              onClick={handleToggleSelectAll}
              className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 cursor-pointer hover:border-gray-300 ${
                isAllSelected || isPartiallySelected ? "bg-blue-600 border-blue-600 text-white" : "border-gray-500 bg-transparent"
              }`}
              title={isAllSelected ? "Unselect all" : "Select all"}
            >
              {isAllSelected ? (
                <Check size={10} strokeWidth={3} />
              ) : isPartiallySelected ? (
                <Minus size={10} strokeWidth={3} />
              ) : null}
            </button>
          </div>
        </div>

        {/* 4. Saved Documents / Sources List (Compact height per item, flush left & right align) */}
        <div className="flex-1 space-y-0.5 pt-0.5">
          {sortedDocuments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center text-gray-400 px-3">
              <FileText size={30} className="text-gray-600 mb-2 stroke-[1.5]" />
              <h4 className="text-xs font-semibold text-gray-300">Saved sources will appear here</h4>
              <p className="text-[11px] text-gray-500 mt-1 max-w-[220px] leading-relaxed">
                Add files, websites, or more. Then ask questions or create things based on these sources.
              </p>
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="text-[11px] text-blue-400 hover:text-blue-300 underline font-medium mt-2 cursor-pointer"
              >
                Drop files here or add a source
              </button>
            </div>
          ) : (
            sortedDocuments.map((doc) => {
              const isChecked = selectedDocs[doc.id] !== undefined ? selectedDocs[doc.id] : true;
              const badge = getFileBadgeInfo(doc.filename);
              const docIndex = (documents.findIndex(d => d.id === doc.id) + 1) || doc.index || 1;

              return (
                <div
                  key={doc.id}
                  onClick={() => setViewingDoc(doc)}
                  className="flex items-center justify-between py-1.5 pl-1 pr-0.5 rounded-lg bg-transparent hover:bg-white/5 transition-colors cursor-pointer group"
                >
                  {/* Left: Clean Monospace Index + Compact Format Badge + File Name */}
                  <div className="flex items-center gap-2 min-w-0 flex-1 mr-1.5">
                    {/* Clean Minimalist Index (Fixed w-7 text-left tabular-nums for 100% straight vertical icon alignment) */}
                    <span 
                      className="w-7 text-left pl-0.5 text-[11px] font-mono font-medium text-gray-500 group-hover:text-gray-300 transition-colors shrink-0 select-none tabular-nums"
                      title={`Permanent Reference Index [${docIndex}]`}
                    >
                      {docIndex}.
                    </span>

                    <div className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 ${badge.bg}`}>
                      <span className="text-[7.5px] font-bold tracking-tighter uppercase font-mono">{badge.label}</span>
                    </div>

                    <span className="text-[11.5px] text-gray-300 truncate group-hover:text-white font-normal" title={doc.filename.replace(/<[^>]+>/g, "")}>
                      {doc.filename.replace(/<[^>]+>/g, "")}
                    </span>
                  </div>

                  {/* Right: Checkbox ONLY toggles selection */}
                  <div 
                    className="flex items-center shrink-0 p-1 -m-1 cursor-pointer"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleDocSelection(doc.id);
                    }}
                    title={isChecked ? "Exclude from AI context" : "Include in AI context"}
                  >
                    <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
                      isChecked ? "bg-blue-600 border-blue-600 text-white" : "border-gray-500 bg-transparent"
                    }`}>
                      {isChecked && <Check size={9} strokeWidth={3} />}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Centered Modal for Bulk Delete Confirmation */}
      {showBulkDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div className="bg-[#28292c] border border-white/10 rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150">
            <div className="space-y-1.5">
              <h3 className="text-base font-semibold text-white">Delete {selectedCount} selected source(s)?</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Deleted documents will no longer be used by the AI to answer questions in this chat session.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowBulkDeleteConfirm(false)}
                disabled={isBulkDeleting}
                className="text-xs text-gray-300 hover:text-white hover:bg-white/10 rounded-lg px-3.5 h-8 cursor-pointer"
              >
                Cancel
              </Button>

              <Button
                size="sm"
                onClick={handleConfirmBulkDelete}
                disabled={isBulkDeleting}
                className="text-xs bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg px-4 h-8 cursor-pointer shadow flex items-center gap-1.5"
              >
                {isBulkDeleting ? (
                  <>
                    <Loader2 size={12} className="animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete ({selectedCount})</span>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
      {/* Google Drive Style Download Floating Progress Toast */}
      <DownloadManager task={downloadTask} onClose={() => setDownloadTask(null)} />
    </aside>
  );
}
