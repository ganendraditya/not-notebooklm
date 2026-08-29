"use client";

import { useState, useRef, useEffect, useMemo } from "react";
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
  ChevronUp,
  BookOpen,
  Sparkles,
  Info,
  Search,
  UploadCloud,
  AlertCircle,
  Pencil,
  MoreHorizontal
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Document, CitationGroundingHighlight, PendingSourceItem } from "@/stores/documentStore";
import { useTranslation } from "@/lib/i18n";
import { consumeSSEStream } from "@/lib/sse";
import { DownloadManager, DownloadTask } from "./DownloadManager";
import { BulkDeleteModal, RenameModal } from "./sidebar/SidebarModals";

interface RightSidebarProps {
  activeChatId: string | null;
  documents: Document[];
  pendingSources?: PendingSourceItem[];
  onDocumentAdded: (doc: Document, targetChatId?: string) => void;
  onDocumentUpdated?: (doc: Document) => void;
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

// export interface PendingSourceItem {
//   id: string;
//   filename: string;
//   type: "file" | "doi";
//   doi?: string;
//   status: "uploading" | "error";
//   error?: string;
// }

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
  has_full_pdf?: boolean;
  is_abstract_only?: boolean;
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
  // Unescape standard and hex HTML entities (e.g. &#x0D;, &#13;, &#10;)
  text = text.replace(/&#x0*d;/gi, "\n");
  text = text.replace(/&#x0*a;/gi, "\n");
  text = text.replace(/&#13;/g, "\n");
  text = text.replace(/&#10;/g, "\n");
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

interface HighlightMatchResult {
  nodes: React.ReactNode;
  matchCount: number;
}

// Helper: Dynamic semantic grounding matcher for scientific claims & quotes (NotebookLM Style)
// Primary path: AI-decided verbatim quotes from CITATION_MAP. Fallback: Contextual semantic matcher.
function getHighlightedContent(
  fullText: string, 
  targetQuery?: string, 
  highlightRefsMap?: React.MutableRefObject<Map<number, HTMLElement>>,
  activeMatchIndex: number = 0,
  aiQuotes?: string[]
): HighlightMatchResult {
  if (!fullText) return { nodes: null, matchCount: 0 };

  // Tokenize document text into atomic chunks (sentences / table cells / headings)
  // Preserve decimal numbers (92.23%) by not splitting on period between digits
  const rawSentences: string[] = [];
  // Split on sentence-ending punctuation (.!?) only when NOT between digits and followed by whitespace/EOL
  const sentenceSplitRegex = /(?<!\d)(?<!\d\s)[.!?]+(?=\s|$)|[\n\r]+/g;
  let lastSplitEnd = 0;
  let splitMatch;
  while ((splitMatch = sentenceSplitRegex.exec(fullText)) !== null) {
    const chunk = fullText.substring(lastSplitEnd, splitMatch.index + splitMatch[0].length);
    if (chunk.trim().length > 0) {
      rawSentences.push(chunk);
    }
    lastSplitEnd = splitMatch.index + splitMatch[0].length;
  }
  if (lastSplitEnd < fullText.length) {
    const tail = fullText.substring(lastSplitEnd);
    if (tail.trim().length > 0) {
      rawSentences.push(tail);
    }
  }
  if (rawSentences.length === 0) return { nodes: <span>{fullText}</span>, matchCount: 0 };

  // 1. PRIMARY AI-DRIVEN GROUNDING PATH:
  // If Gemini 3.7 Flash High provided exact verbatim quote(s), match against them directly!
  if (aiQuotes && aiQuotes.length > 0) {
    const aiHighlightedIndices = new Set<number>();
    const aiClusters: number[][] = [];

    // If multiple quotes exist for this document, prioritize quotes matching the clicked cell context (targetQuery)
    let selectedQuotes = aiQuotes;
    if (aiQuotes.length > 1 && targetQuery && targetQuery.trim().length > 3) {
      const cleanTarget = targetQuery.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim();
      const targetTokens = new Set(cleanTarget.split(/\s+/).filter(w => w.length >= 3));

      // Score each quote against the clicked targetQuery
      const scoredQuotes = aiQuotes.map(q => {
        const qClean = q.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ");
        let hits = 0;
        targetTokens.forEach(t => {
          if (qClean.includes(t)) hits++;
        });
        return { quote: q, score: hits };
      });

      const maxScore = Math.max(...scoredQuotes.map(sq => sq.score));
      // If one quote is clearly more relevant to the clicked cell, use only the relevant quote(s)
      if (maxScore > 0) {
        selectedQuotes = scoredQuotes.filter(sq => sq.score >= maxScore * 0.7).map(sq => sq.quote);
      }
    }

    selectedQuotes.forEach(quote => {
      if (!quote || quote.trim().length < 5) return;
      const cleanQuote = quote.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim().replace(/\s+/g, " ");
      const quoteWords = cleanQuote.split(/\s+/).filter(w => w.length >= 2);
      if (quoteWords.length === 0) return;

      // Extract numeric tokens from the quote (e.g. "92", "23", "0", "718") for metric-aware matching
      const quoteNumbers = cleanQuote.match(/\b\d+\b/g) || [];

      // Check for exact substring match (bidirectional)
      let foundExact = false;
      rawSentences.forEach((s, idx) => {
        // Skip title heading in matches
        if (idx === 0 && /^#\s+/i.test(s.trim())) return;
        const sClean = s.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim().replace(/\s+/g, " ");
        if (sClean.length >= 15 && (sClean.includes(cleanQuote) || cleanQuote.includes(sClean))) {
          aiHighlightedIndices.add(idx);
          foundExact = true;
        }
      });

      if (!foundExact) {
        // High-precision keyword overlap with numeric bonus
        let bestSentenceIdx = -1;
        let highestScore = 0;

        rawSentences.forEach((s, idx) => {
          // Never highlight Document Title (idx 0) on quote matching
          if (idx === 0 && /^#\s+/i.test(s.trim())) return;
          const sClean = s.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim().replace(/\s+/g, " ");
          // Skip very short fragments and metadata lines
          if (sClean.length < 15) return;
          if (/https?\s|doi\s|issn|available online|halaman/.test(sClean)) return;

          let wordOverlap = 0;
          quoteWords.forEach(qw => {
            if (sClean.includes(qw)) wordOverlap++;
          });
          const wordRatio = wordOverlap / quoteWords.length;

          // Count how many numeric tokens from the quote appear in this sentence
          let numericHits = 0;
          if (quoteNumbers.length > 0) {
            const sNumbers = sClean.match(/\b\d+\b/g) || [];
            const sNumSet = new Set(sNumbers);
            quoteNumbers.forEach(n => { if (sNumSet.has(n)) numericHits++; });
          }
          // ponytail: numeric bonus — upgrade path: use decimal-aware matching (e.g. "92.23" as single token)
          const numericBonus = quoteNumbers.length > 0 ? (numericHits / quoteNumbers.length) * 0.25 : 0;
          const combinedScore = wordRatio + numericBonus;

          // Require at least 25% word overlap for quote matching to avoid title/abstract drift
          if (wordRatio >= 0.25 && combinedScore > highestScore) {
            highestScore = combinedScore;
            bestSentenceIdx = idx;
          }
        });

        if (bestSentenceIdx !== -1) {
          aiHighlightedIndices.add(bestSentenceIdx);
        }
      }
    });

    if (aiHighlightedIndices.size > 0) {
      const sortedIndices = Array.from(aiHighlightedIndices).sort((a, b) => a - b);
      let currentCluster: number[] = [];
      sortedIndices.forEach(idx => {
        if (currentCluster.length === 0) {
          currentCluster.push(idx);
        } else {
          const last = currentCluster[currentCluster.length - 1];
          if (idx === last + 1) {
            currentCluster.push(idx);
          } else {
            aiClusters.push([...currentCluster]);
            currentCluster = [idx];
          }
        }
      });
      if (currentCluster.length > 0) {
        aiClusters.push(currentCluster);
      }

      const indexToClusterMap = new Map<number, number>();
      aiClusters.forEach((clust, cIdx) => {
        clust.forEach(idx => {
          indexToClusterMap.set(idx, cIdx);
        });
      });

      const nodes = (
        <>
          {rawSentences.map((sentence, idx) => {
            const isHighlighted = aiHighlightedIndices.has(idx);
            if (isHighlighted) {
              const clusterIdx = indexToClusterMap.get(idx) ?? 0;
              const isClusterAnchor = aiClusters[clusterIdx]?.[0] === idx;
              const isActiveCluster = clusterIdx === activeMatchIndex;

              return (
                <mark
                  key={idx}
                  ref={(el) => {
                    if (el && isClusterAnchor && highlightRefsMap) {
                      highlightRefsMap.current.set(clusterIdx, el);
                    }
                  }}
                  className={`font-medium px-1 py-0.5 rounded inline leading-relaxed transition-all box-decoration-clone ${
                    isActiveCluster
                      ? "bg-amber-300 dark:bg-amber-500/40 text-amber-950 dark:text-amber-100 ring-2 ring-amber-500 shadow-sm"
                      : "bg-amber-200/80 dark:bg-amber-500/25 text-amber-950 dark:text-amber-100 border-b-2 border-amber-500/50"
                  }`}
                  title={`AI Grounded Evidence ${clusterIdx + 1} of ${aiClusters.length}`}
                >
                  {sentence}
                </mark>
              );
            }
            return <span key={idx}>{sentence}</span>;
          })}
        </>
      );

      return {
        nodes,
        matchCount: aiClusters.length
      };
    }
  }

  // Identify where the bibliography / reference list starts in the document to avoid grounding on references
  let refSectionIndex = -1;
  const refHeaderRegex = /^\s*(?:#+\s*)?(?:daftar\s+pustaka|references|bibliography|daftar\s+referensi|referensi)\b/i;
  for (let i = 0; i < rawSentences.length; i++) {
    if (refHeaderRegex.test(rawSentences[i].trim())) {
      refSectionIndex = i;
      break;
    }
  }

  // Common stopwords in Indonesian and English
  const stopWords = new Set([
    "yang", "dari", "pada", "untuk", "dengan", "adalah", "dalam", "ini", "itu", "dan", "atau", "oleh", "ke", "di",
    "the", "and", "for", "with", "this", "that", "from", "using", "paper", "berikut", "tabel", "rekapitulasi",
    "dokumen", "terdapat", "adanya", "sebagai", "juga", "dapat", "akan", "telah", "namun", "serta", "karena",
    "bisa", "lebih", "secara", "seperti", "yaitu", "yakni", "merupakan", "berdasarkan", "parameter", "metode",
    "hasil", "nilai", "sebesar", "ketika", "menggunakan"
  ]);

  // Normalize query & strip LaTeX delimiters ($C=10$, \gamma=1 -> c=10, gamma=1)
  const normQuery = (targetQuery || "")
    .toLowerCase()
    .replace(/\$([^$]+)\$/g, "$1")
    .replace(/\\(?:gamma|alpha|beta|sigma|lambda|theta)\b/gi, (m) => m.substring(1));
  
  // Extract explicit numerical metrics with decimals or %: e.g. "69,15%", "84.37%", "0.87"
  const rawMetricMatches = (normQuery.match(/\b\d+[,.]\d+%?\b|\b\d+%\b/g) || []);
  const metricsSet = new Set(
    rawMetricMatches.map(m => m.toLowerCase().replace(/,/g, ".").replace(/%/g, ""))
  );

  // Extract parameter bindings: e.g. "c=10", "gamma=1", "k=5", "fold=10"
  const paramBindings = (normQuery.match(/\b[a-z_]+\s*=\s*\d+(?:[,.]\d+)?\b/g) || []).map(p => p.replace(/\s+/g, ""));

  // Extract model/algorithm/parameter specific terms: e.g. "svm", "rbf", "gamma", "tfidf", "kernel", "logistic", "naive"
  const cleanTokens = normQuery
    .replace(/[^a-zA-Z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(w => w.length >= 2 && !stopWords.has(w) && !/^\d+$/.test(w));

  // Extract keyphrases (2-word & 3-word n-grams)
  const queryPhrases: string[] = [];
  for (let i = 0; i < cleanTokens.length - 1; i++) {
    queryPhrases.push(`${cleanTokens[i]} ${cleanTokens[i + 1]}`);
    if (i < cleanTokens.length - 2) {
      queryPhrases.push(`${cleanTokens[i]} ${cleanTokens[i + 1]} ${cleanTokens[i + 2]}`);
    }
  }

  // Calculate scores for each sentence with semantic entity weighting
  let maxSingleScore = 0;
  const sentenceScores = rawSentences.map((s, idx) => {
    if (refSectionIndex !== -1 && idx >= refSectionIndex) {
      return 0;
    }

    const sLower = s.toLowerCase();
    
    // Ignore bibliography, page numbers, journal header lines, URL lines, and short metadata fragments
    if (/https?:\/\/|doi\.org|\bvol(?:ume)?\s*\d+|\bp-issn\b|\be-issn\b|\bissn\b|\bhalaman\b|\bavailable online\b|\.ac\.id|\.org\/index/i.test(sLower)) {
      return 0;
    }
    // Skip top title, metadata lines, and heading 1 from matching if searching within body
    if (idx === 0 && /^#\s+/i.test(s.trim())) {
      return 0;
    }

    const sNormalizedNumbers = sLower
      .replace(/(\d+)\s*[,.]\s*(\d+)/g, "$1.$2")
      .replace(/(\d+)\s+%/g, "$1%");
    const sClean = sNormalizedNumbers.replace(/[^a-zA-Z0-9\s]/g, " ");
    const sWords = new Set(sClean.split(/\s+/).filter(w => w.length >= 2));

    let score = 0;

    // 1. Parameter bindings match (e.g. "c=10", "gamma=1" matching "c = 10", "c=10", "gamma = 1") (Weight: 35 points)
    paramBindings.forEach(pb => {
      const parts = pb.split("=");
      if (parts.length === 2) {
        const paramName = parts[0];
        const paramVal = parts[1];
        const paramRegex = new RegExp(`\\b${paramName}\\s*=\\s*${paramVal}\\b`, "i");
        if (paramRegex.test(sLower) || (sWords.has(paramName) && sNormalizedNumbers.includes(paramVal))) {
          score += 35;
        }
      }
    });

    // 1. Exact Decimal/Percentage/Value Metric match
    // Matches "0,87", "0.87", "87%", "87", "0,88", "0.88"
    metricsSet.forEach(m => {
      const mComma = m.replace(/\./g, ",");
      const isDecimalMatch = sNormalizedNumbers.includes(m) || sLower.includes(mComma);
      if (isDecimalMatch) {
        score += 35;
      } else if (m.startsWith("0.")) {
        // Convert decimal to percentage or integer representation: e.g. 0.87 -> 87% / 87
        const pctInt = `${Math.round(parseFloat(m) * 100)}`;
        if (sNormalizedNumbers.includes(`${pctInt}%`) || sClean.includes(pctInt)) {
          score += 35;
        }
      } else if (/^\d+$/.test(m) && parseInt(m, 10) > 10) {
        // Integer percentage representation: e.g. 87 -> 0.87 or 87%
        const decVal = (parseInt(m, 10) / 100).toFixed(2);
        if (sNormalizedNumbers.includes(decVal) || sLower.includes(decVal.replace(/\./g, ","))) {
          score += 35;
        }
      }
    });

    // 2. Specific keyphrase n-grams (e.g. "akurasi tertinggi", "model terbaik", "kata positif", "sentimen netral")
    queryPhrases.forEach(ph => {
      if (sClean.includes(ph)) {
        score += 16;
      }
    });

    // 3. Domain Entity / Model / Sentiment keywords (Weight: 5 points)
    // Matches "bahagia", "rajin", "senang", "capek", "muak", "bosen", "netral", "akurasi"
    cleanTokens.forEach(w => {
      if (sWords.has(w) || sClean.includes(w)) {
        score += 5;
      }
    });

    if (score > maxSingleScore) {
      maxSingleScore = score;
    }

    return score;
  });

  // Dynamic Multi-Highlight Selection & Clustering:
  const highlightedIndices = new Set<number>();
  const clusters: number[][] = [];

  if (maxSingleScore > 0) {
    // Selectivity threshold: Keep top evidence passages matching query claims
    const threshold = Math.max(10, maxSingleScore * 0.40);
    
    // Pick candidate sentences meeting threshold
    const candidateIndices: number[] = [];
    sentenceScores.forEach((sc, idx) => {
      if (sc >= threshold) {
        candidateIndices.push(idx);
      }
    });

    // Add candidates to highlighted set
    candidateIndices.forEach(idx => highlightedIndices.add(idx));

    // Connect adjacent 1-to-2 sentence gaps in the same paragraph if context flows cohesively
    for (let i = 0; i < candidateIndices.length - 1; i++) {
      const curr = candidateIndices[i];
      const next = candidateIndices[i + 1];
      const gap = next - curr;
      if (gap >= 2 && gap <= 3) {
        for (let g = curr + 1; g < next; g++) {
          highlightedIndices.add(g);
        }
      }
    }
  }

  // Fallback: If no match above threshold, highlight best matching sentence ONLY if it scored >= 15 (strict significance)
  if (highlightedIndices.size === 0) {
    let fallbackIdx = -1;
    let bestScore = 14; // Must have substantial overlap (at least 3 keywords or keyphrase/metric) to qualify
    sentenceScores.forEach((sc, idx) => {
      if (sc > bestScore) {
        bestScore = sc;
        fallbackIdx = idx;
      }
    });
    if (fallbackIdx >= 0) {
      highlightedIndices.add(fallbackIdx);
    }
  }

  // If still nothing matched, return unhighlighted text (no random highlight)
  if (highlightedIndices.size === 0) {
    return {
      nodes: <span>{fullText}</span>,
      matchCount: 0
    };
  }

  // Group highlighted contiguous indices into distinct clusters/passages
  const sortedIndices = Array.from(highlightedIndices).sort((a, b) => a - b);
  let currentCluster: number[] = [];
  sortedIndices.forEach(idx => {
    if (currentCluster.length === 0) {
      currentCluster.push(idx);
    } else {
      const last = currentCluster[currentCluster.length - 1];
      if (idx === last + 1) {
        currentCluster.push(idx);
      } else {
        clusters.push([...currentCluster]);
        currentCluster = [idx];
      }
    }
  });
  if (currentCluster.length > 0) {
    clusters.push(currentCluster);
  }

  // Map each highlighted sentence index to its cluster index
  const indexToClusterMap = new Map<number, number>();
  clusters.forEach((clust, cIdx) => {
    clust.forEach(idx => {
      indexToClusterMap.set(idx, cIdx);
    });
  });

  const nodes = (
    <>
      {rawSentences.map((sentence, idx) => {
        const isHighlighted = highlightedIndices.has(idx);
        if (isHighlighted) {
          const clusterIdx = indexToClusterMap.get(idx) ?? 0;
          const isClusterAnchor = clusters[clusterIdx]?.[0] === idx;
          const isActiveCluster = clusterIdx === activeMatchIndex;

          return (
            <mark
              key={idx}
              ref={(el) => {
                if (el && isClusterAnchor && highlightRefsMap) {
                  highlightRefsMap.current.set(clusterIdx, el);
                }
              }}
              className={`font-medium px-1 py-0.5 rounded inline leading-relaxed transition-all box-decoration-clone ${
                isActiveCluster
                  ? "bg-amber-300 dark:bg-amber-500/40 text-amber-950 dark:text-amber-100 ring-2 ring-amber-500 shadow-sm"
                  : "bg-amber-200/80 dark:bg-amber-500/25 text-amber-950 dark:text-amber-100 border-b-2 border-amber-500/50"
              }`}
              title={`Evidence Match ${clusterIdx + 1} of ${clusters.length}`}
            >
              {sentence}
            </mark>
          );
        }
        return <span key={idx}>{sentence}</span>;
      })}
    </>
  );

  return {
    nodes,
    matchCount: clusters.length
  };
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
  pendingSources: externalPendingSources = [],
  onDocumentAdded, 
  onDocumentUpdated,
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
  const { t } = useTranslation();
  const [isUploading, setIsUploading] = useState(false);
  const [selectedDocs, setSelectedDocs] = useState<Record<number, boolean>>({});
  
  // Sorting state & dropdown
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [isSortMenuOpen, setIsSortMenuOpen] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState<number | null>(null);
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
  const [activeTab, setActiveTab] = useState<"preview" | "pdf">("preview");
  
  // Citation Modal State
  const [isCiteModalOpen, setIsCiteModalOpen] = useState<boolean>(false);
  const [selectedCitationStyle, setSelectedCitationStyle] = useState<"apa" | "ieee" | "harvard" | "mla" | "chicago" | "bibtex" | "ris">("apa");
  const [copiedCitationKey, setCopiedCitationKey] = useState<string | null>(null);

  const [copiedDoi, setCopiedDoi] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeMatchIndex, setActiveMatchIndex] = useState<number>(0);
  const [totalMatches, setTotalMatches] = useState<number>(0);
  const highlightRefsMap = useRef<Map<number, HTMLElement>>(new Map());

  // Reset active highlight match index when highlighted target changes (or same citation re-clicked)
  useEffect(() => {
    setActiveMatchIndex(0);
    highlightRefsMap.current.clear();
  }, [groundingHighlight?.clickId, groundingHighlight?.sentence, viewingDoc?.id]);

  // Auto-scroll to current active highlighted cluster
  useEffect(() => {
    if (!isLoadingDetails) {
      const timer = setTimeout(() => {
        const targetEl = highlightRefsMap.current.get(activeMatchIndex);
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [isLoadingDetails, activeMatchIndex, groundingHighlight, activeTab, paperDetails?.content]);

  // Local memory cache for instant viewer loading without repeated network/parsing overhead
  const paperDetailsCacheRef = useRef<Map<number, PaperDetailData>>(new Map());

  // Fetch document details when viewingDoc is set
  useEffect(() => {
    if (!viewingDoc || !activeChatId) {
      setPaperDetails(null);
      return;
    }

    // Check client-side memory cache for zero-latency instant rendering
    if (paperDetailsCacheRef.current.has(viewingDoc.id)) {
      setPaperDetails(paperDetailsCacheRef.current.get(viewingDoc.id)!);
      setIsLoadingDetails(false);
      setIsCiteModalOpen(false);
      return;
    }

    setIsLoadingDetails(true);
    setIsCiteModalOpen(false);
    fetch(`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/content`)
      .then(res => res.json())
      .then(data => {
        if (data && !data.error) {
          paperDetailsCacheRef.current.set(viewingDoc.id, data);
        }
        setPaperDetails(data);
      })
      .catch(err => {
        console.error("Failed to load paper details:", err);
      })
      .finally(() => {
        setIsLoadingDetails(false);
      });
  }, [viewingDoc, activeChatId, backendUrl]);

  // Switch to preview tab when citation grounding highlight is active
  useEffect(() => {
    if (groundingHighlight?.sentence) {
      setActiveTab("preview");
    }
  }, [groundingHighlight?.clickId, groundingHighlight?.sentence]);

  // Close sort menu on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // Logic for main sort menu
      if (isSortMenuOpen && sortMenuRef.current && !sortMenuRef.current.contains(event.target as Node)) {
        setIsSortMenuOpen(false);
      }
      
      // Logic for 3 dots menu
      // Check if click is outside of any document action menu (which we assume has a specific data attribute to avoid conflicts)
      const target = event.target as HTMLElement;
      if (activeMenuId !== null && !target.closest('.document-action-menu-container')) {
        setActiveMenuId(null);
      }
    };
    
    if (isSortMenuOpen || activeMenuId !== null) {
      window.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isSortMenuOpen, activeMenuId]);

  const [isCleaningDuplicates, setIsCleaningDuplicates] = useState(false);
  const [cleanFeedback, setCleanFeedback] = useState<string | null>(null);
  const [isAddSourcesModalOpen, setIsAddSourcesModalOpen] = useState(false);
  const [doiInput, setDoiInput] = useState("");
  const [internalPendingSources, setInternalPendingSources] = useState<PendingSourceItem[]>([]);
  const pendingSources = useMemo(() => {
    return [...internalPendingSources, ...externalPendingSources];
  }, [internalPendingSources, externalPendingSources]);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  // Rename source state
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [renamingDoc, setRenamingDoc] = useState<Document | null>(null);
  const [renameTitleInput, setRenameTitleInput] = useState("");
  const [isSavingRename, setIsSavingRename] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);

  const handleOpenRename = () => {
    if (selectedCount !== 1) return;
    const targetDoc = selectedDocList[0];
    setRenamingDoc(targetDoc);
    setRenameTitleInput(targetDoc.title || targetDoc.filename.replace(/\.[^/.]+$/, "").replace(/_/g, " "));
    setRenameError(null);
    setIsRenameModalOpen(true);
  };

  const handleSaveRename = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!activeChatId || !renamingDoc || isSavingRename) return;
    const cleanTitle = renameTitleInput.trim();
    if (!cleanTitle) {
      setRenameError("Document title cannot be empty.");
      return;
    }
    setIsSavingRename(true);
    setRenameError(null);
    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/${renamingDoc.id}/rename`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: cleanTitle })
      });
      if (res.ok) {
        const updatedDoc = await res.json();
        onDocumentUpdated?.(updatedDoc);
        if (viewingDoc && viewingDoc.id === renamingDoc.id) {
          setViewingDoc(prev => prev ? { ...prev, title: updatedDoc.title } : null);
          setPaperDetails(prev => prev ? { ...prev, title: updatedDoc.title } : null);
        }
        setIsRenameModalOpen(false);
        setRenamingDoc(null);
      } else {
        const err = await res.json().catch(() => ({}));
        setRenameError(err.detail || "Failed to rename document.");
      }
    } catch (err: any) {
      setRenameError(err?.message || "Network error while renaming document.");
    } finally {
      setIsSavingRename(false);
    }
  };

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
      } else {
        const err = await res.json().catch(() => ({}));
        setCleanFeedback(err.detail || "Failed to clean duplicates");
      }
      setTimeout(() => setCleanFeedback(null), 3500);
    } catch (e: any) {
      console.error("Clean duplicates failed:", e);
      setCleanFeedback("Network error connecting to server");
      setTimeout(() => setCleanFeedback(null), 3500);
    } finally {
      setIsCleaningDuplicates(false);
    }
  };

  const SUPPORTED_EXTENSIONS = new Set([
    ".pdf", ".docx", ".doc", ".txt", ".md", ".bib", ".bibtex", ".ris"
  ]);

  const handleUploadBatch = async (files: File[]) => {
    if (!files || files.length === 0) return;

    // Filter out unsupported files (e.g. .exe, .zip, etc.)
    const validFiles = files.filter(f => {
      const ext = f.name.toLowerCase().slice(f.name.lastIndexOf("."));
      return SUPPORTED_EXTENSIONS.has(ext);
    });

    if (validFiles.length === 0) {
      alert(t('alert.unsupportedFormat') || "Unsupported file format. Supported formats: .pdf, .docx, .doc, .txt, .md, .bib, .ris");
      return;
    }

    if (validFiles.length < files.length) {
      const skippedCount = files.length - validFiles.length;
      console.warn(`[Upload] Skipped ${skippedCount} unsupported file(s).`);
    }

    // Check capacity limit of 300
    const availableSlots = Math.max(0, 300 - (documents.length + pendingSources.length));
    if (availableSlots <= 0) {
      alert(t('alert.limitReached') || "Source limit reached! Maximum capacity is 300 sources per notebook.");
      return;
    }

    const filesToUpload = validFiles.slice(0, availableSlots);
    if (validFiles.length > availableSlots) {
      alert((t('alert.capacityWarning') || `Capacity limit warning: Only uploading {n} out of {m} valid files to respect the 300 source cap.`)
        .replace('{n}', availableSlots.toString())
        .replace('{m}', validFiles.length.toString()));
    }

    const newPendingItems: { item: PendingSourceItem; file: File }[] = filesToUpload.map((f) => ({
      item: {
        id: `pending-file-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        filename: f.name,
        type: "file",
        status: "uploading",
      },
      file: f,
    }));

    // Instantly append pending items to sidebar & close modal dialog immediately (NotebookLM UX)
    setInternalPendingSources(prev => [...prev, ...newPendingItems.map(n => n.item)]);
    setIsAddSourcesModalOpen(false);

    try {
      let currentChatId = activeChatId;
      if (!currentChatId && onEnsureChatSession) {
        const firstTitle = filesToUpload[0].name.replace(/\.[^/.]+$/, "");
        currentChatId = await onEnsureChatSession(firstTitle);
      }

      if (!currentChatId) {
        const targetIds = new Set(newPendingItems.map(n => n.item.id));
        setInternalPendingSources(prev => prev.map(p => targetIds.has(p.id) ? {
          ...p,
          status: "error",
          error: "Failed to initialize notebook chat session."
        } : p));
        return;
      }

      // Concurrency Pool Worker: upload up to 3 files simultaneously
      const queue = [...newPendingItems];
      const CONCURRENCY_LIMIT = 3;

      const worker = async () => {
        while (queue.length > 0) {
          const task = queue.shift();
          if (!task) break;
          const { item, file } = task;
          const formData = new FormData();
          formData.append("file", file);

          try {
            const res = await fetch(`${backendUrl}/chats/${currentChatId}/upload`, {
              method: "POST",
              body: formData,
            });
            if (res.ok) {
              const newDoc = await res.json();
              onDocumentAdded(newDoc, currentChatId);
              // Successfully indexed, remove from pending list
              setInternalPendingSources(prev => prev.filter(p => p.id !== item.id));
            } else {
              const err = await res.json().catch(() => ({}));
              setInternalPendingSources(prev => prev.map(p => p.id === item.id ? {
                ...p,
                status: "error",
                error: err.detail || "Failed to upload and parse document."
              } : p));
            }
          } catch (err: any) {
            setInternalPendingSources(prev => prev.map(p => p.id === item.id ? {
              ...p,
              status: "error",
              error: err?.message || "Failed to connect to server."
            } : p));
          }
        }
      };

      const pool = Array.from({ length: Math.min(CONCURRENCY_LIMIT, newPendingItems.length) }, () => worker());
      await Promise.all(pool);
    } catch (e) {
      console.error("Batch upload failed:", e);
    }
  };

  const handleImportDoi = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanDoi = doiInput.trim();
    if (!cleanDoi) return;

    // Check capacity
    if (documents.length + pendingSources.length >= 300) {
      alert(t('alert.limitReached') || "Source limit reached! Maximum capacity is 300 sources per notebook.");
      return;
    }

    const tempId = `pending-doi-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const pendingItem: PendingSourceItem = {
      id: tempId,
      filename: cleanDoi.startsWith("10.") || cleanDoi.includes("doi.org") ? `DOI: ${cleanDoi}` : cleanDoi,
      type: "doi",
      doi: cleanDoi,
      status: "uploading",
    };

    // Instantly append to sources list and close modal dialog immediately
    setInternalPendingSources(prev => [...prev, pendingItem]);
    setDoiInput("");
    setIsAddSourcesModalOpen(false);

    try {
      let currentChatId = activeChatId;
      if (!currentChatId && onEnsureChatSession) {
        currentChatId = await onEnsureChatSession("Research Paper");
      }
      if (!currentChatId) {
        setInternalPendingSources(prev => prev.map(p => p.id === tempId ? {
          ...p,
          status: "error",
          error: "Failed to initialize notebook chat session."
        } : p));
        return;
      }

      const res = await fetch(`${backendUrl}/chats/${currentChatId}/import_doi`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doi: cleanDoi })
      });

      if (res.ok) {
        const newDoc = await res.json();
        onDocumentAdded(newDoc, currentChatId);
        setInternalPendingSources(prev => prev.filter(p => p.id !== tempId));
      } else {
        const err = await res.json().catch(() => ({}));
        setInternalPendingSources(prev => prev.map(p => p.id === tempId ? {
          ...p,
          status: "error",
          error: err.detail || "Publication not found for the provided DOI."
        } : p));
      }
    } catch (err: any) {
      setInternalPendingSources(prev => prev.map(p => p.id === tempId ? {
        ...p,
        status: "error",
        error: err?.message || "Failed to resolve DOI from academic registries."
      } : p));
    }
  };

  // Selection logic
  const isAllSelected = documents.length > 0 && documents.every(d => selectedDocs[d.id] !== false);
  const isSomeSelected = documents.some(d => selectedDocs[d.id] !== false);
  const isPartiallySelected = isSomeSelected && !isAllSelected;

  const getFileBadgeInfo = (filename: string) => {
    if (filename.startsWith("10.") || filename.startsWith("DOI:") || filename.includes("doi.org")) {
      return { label: "DOI", bg: "bg-blue-600/15 border-blue-500/40 text-blue-500" };
    }
    const ext = filename.split(".").pop()?.toLowerCase() || "doc";
    if (ext === "pdf") {
      return { label: "PDF", bg: "bg-red-600/15 border-red-500/40 text-red-500" };
    } else if (ext === "docx" || ext === "doc") {
      return { label: "DOC", bg: "bg-blue-600/15 border-blue-500/40 text-blue-500" };
    } else if (ext === "bib" || ext === "bibtex") {
      return { label: "BIB", bg: "bg-amber-600/15 border-amber-500/40 text-amber-500" };
    } else if (ext === "ris") {
      return { label: "RIS", bg: "bg-orange-600/15 border-orange-500/40 text-orange-500" };
    } else if (ext === "md") {
      return { label: "MD", bg: "bg-purple-600/15 border-purple-500/40 text-purple-500" };
    } else {
      return { label: "TXT", bg: "bg-app-item-hover border-app-border text-app-text-muted" };
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

    // If only 1 document is selected, trigger single PDF download with proper error handling
    if (docIds.length === 1) {
      try {
        const doc = selectedDocList[0];
        const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/${doc.id}/download`);
        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          setDownloadTask({
            status: "error",
            total: 1,
            current: 0,
            percent: 0,
            currentFile: doc.filename,
            errorMsg: errJson.detail || "Naskah lengkap PDF tidak tersedia untuk diunduh (hanya abstrak/paywalled)."
          });
          return;
        }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = doc.filename.endsWith(".pdf") ? doc.filename : `${doc.filename}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (err: any) {
        console.error("Single download error:", err);
        setDownloadTask({
          status: "error",
          total: 1,
          current: 0,
          percent: 0,
          currentFile: "",
          errorMsg: err?.message || "Gagal mengunduh dokumen."
        });
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
      currentFile: t('download.connecting')
    });

    try {
      const response = await fetch(`${backendUrl}/chats/${activeChatId}/documents/bulk_download_stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_ids: docIds })
      });

      await consumeSSEStream(response, (data: any) => {
        if (data.type === "init") {
          setDownloadTask({
            status: "zipping",
            total: data.total || docIds.length,
            current: 0,
            percent: 0,
            currentFile: t('download.startingParallel')
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
            currentFile: data.filename || prev?.currentFile || "",
            downloadedCount: data.downloaded_count,
            skippedCount: data.skipped_count
          }));
        } else if (data.type === "error") {
          setDownloadTask({
            status: "error",
            total: docIds.length,
            current: 0,
            percent: 0,
            currentFile: "",
            errorMsg: data.message || t('download.failedZip')
          });
        } else if (data.type === "complete") {
          setDownloadTask({
            status: "complete",
            total: data.total || data.total_files || docIds.length,
            current: data.total || data.total_files || docIds.length,
            percent: 100,
            downloadedCount: data.downloaded_count,
            skippedCount: data.skipped_count,
            currentFile: t('download.downloadComplete'),
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
      });
    } catch (err: any) {
      console.error("Bulk download error:", err);
      setDownloadTask({
        status: "error",
        total: docIds.length,
        current: 0,
        percent: 0,
        currentFile: "",
        errorMsg: err?.message || t('download.failedZip')
      });
    } finally {
      setIsBulkDownloading(false);
    }
  };

  const [docToDelete, setDocToDelete] = useState<number | null>(null);

  const handleConfirmBulkDelete = async () => {
    if (!activeChatId || isBulkDeleting) return;
    setIsBulkDeleting(true);
    try {
      // If docToDelete is set, it means we clicked delete from 3-dots on a specific doc
      const docIds = docToDelete !== null ? [docToDelete] : selectedDocList.map(d => d.id);
      
      if (docIds.length === 0) {
        setIsBulkDeleting(false);
        return;
      }
      
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
        setDocToDelete(null); // Reset after success
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
      : t('right.academicResearchers');
    const pubDateStr = formatReadableDate(paperDetails?.publication_date, paperDetails?.year);
    const journalName = paperDetails?.journal || t('right.scholarlyPublication');
    const citationsCount = paperDetails?.citations !== undefined ? paperDetails.citations : 0;
    const doiStr = paperDetails?.doi || "";
    const cleanAbstract = cleanHtmlAbstract(paperDetails?.abstract) || (isLoadingDetails ? "" : t('right.noAbstractProvided'));
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
      <aside className="w-full lg:w-[460px] h-full bg-app-sidebar border-l border-app-border flex flex-col shrink-0 select-none z-10 transition-all relative text-app-text">
        {/* 1. Header Bar: ← Paper + Circular Close Button */}
        <div className="px-4 py-3 flex items-center justify-between border-b border-app-divider">
          <button
            onClick={() => {
              setViewingDoc(null);
              onClearViewingDoc?.();
            }}
            className="flex items-center gap-2 text-xs font-semibold text-app-text hover:opacity-80 transition-colors cursor-pointer group"
          >
            <ArrowLeft size={16} className="text-app-text-muted group-hover:text-app-text transition-transform group-hover:-translate-x-0.5" />
            <span className="text-sm tracking-tight font-medium">Paper</span>
          </button>

          <button 
            onClick={onClose}
            className="w-7 h-7 rounded-full bg-app-item-hover hover:bg-app-item-active text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer hidden lg:flex"
            title={t('right.close')}
          >
            <X size={14} />
          </button>
        </div>

        {/* 2. Clean 2 Navigation Tabs: Full Text & Original Document */}
        <div className="flex items-center px-4 border-b border-app-divider text-xs font-medium text-app-text-muted gap-5 shrink-0">
          <button
            onClick={() => setActiveTab("preview")}
            className={`py-2.5 transition-colors cursor-pointer border-b-2 font-medium flex items-center gap-1.5 ${
              activeTab === "preview" ? "text-app-text border-blue-500 font-semibold" : "text-app-text-muted hover:text-app-text border-transparent"
            }`}
          >
            <span>{t('right.fullText')}</span>
          </button>
          <button
            onClick={() => setActiveTab("pdf")}
            className={`py-2.5 transition-colors cursor-pointer border-b-2 font-medium flex items-center gap-1.5 ${
              activeTab === "pdf" ? "text-app-text border-blue-500 font-semibold" : "text-app-text-muted hover:text-app-text border-transparent"
            }`}
          >
            <span>{t('right.originalDoc')}</span>
          </button>
        </div>

        {/* 3. Main Body */}
        {activeTab === "preview" ? (
          /* TAB 2: FULL PAPER / IN-APP NATIVE SCROLLABLE DOCUMENT READER */
          <div className="flex-1 flex flex-col min-h-0 bg-app-bg relative overflow-hidden">
            {/* Top Preview Controls Bar */}
            <div className="px-3.5 py-2 bg-app-sidebar border-b border-app-divider flex items-center justify-between text-xs text-app-text-muted shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-2 h-2 rounded-full shrink-0 ${paperDetails?.has_full_pdf ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
                <span className="truncate max-w-[170px] font-mono text-[11px] text-app-text-muted">
                  {viewingDoc.filename}
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                {/* Evidence Passage Navigator (Chevron Up / Down for multiple disjoint matches) */}
                {totalMatches > 1 && (
                  <div className="flex items-center gap-1 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2 py-0.5 mr-1">
                    <span className="text-[10px] font-mono font-semibold text-amber-500">
                      {activeMatchIndex + 1}/{totalMatches}
                    </span>
                    <div className="flex items-center">
                      <button
                        type="button"
                        onClick={() => {
                          const prev = activeMatchIndex > 0 ? activeMatchIndex - 1 : totalMatches - 1;
                          setActiveMatchIndex(prev);
                        }}
                        className="p-0.5 hover:bg-amber-500/20 text-amber-500 hover:text-amber-600 rounded transition-colors"
                        title={t('right.prevEvidence')}
                      >
                        <ChevronUp size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const next = activeMatchIndex < totalMatches - 1 ? activeMatchIndex + 1 : 0;
                          setActiveMatchIndex(next);
                        }}
                        className="p-0.5 hover:bg-amber-500/20 text-amber-500 hover:text-amber-600 rounded transition-colors"
                        title={t('right.nextEvidence')}
                      >
                        <ChevronDown size={13} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* In-App Paper Document Reader Canvas (Fully Scrollable) */}
            <div className="flex-1 p-4 overflow-y-auto custom-scrollbar space-y-4 select-text">
              {isLoadingDetails ? (
                <div className="py-24 flex flex-col items-center justify-center text-center space-y-3">
                  <Loader2 size={24} className="animate-spin text-blue-500" />
                  <p className="text-xs text-app-text-dim">{t('right.loading')}</p>
                </div>
              ) : (paperDetails?.has_full_pdf === false || paperDetails?.is_abstract_only || (paperDetails?.content && (paperDetails.content.length < 3500 || paperDetails.content.includes("NOTBOOKLM SCHOLARLY ARCHIVE") || paperDetails.content.includes("OFFICIAL PUBLICATION ARCHIVE RECORD")))) ? (
                <div className="p-4 sm:p-5 rounded-xl bg-app-card border border-app-border shadow-lg space-y-4">
                  {/* Status Banner for Abstract Only */}
                  <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-2 text-xs text-amber-900 dark:text-amber-200">
                    <div className="flex items-center gap-2 font-semibold text-amber-800 dark:text-amber-100">
                      <Info size={16} className="text-amber-500 shrink-0" />
                      <span>
                        {paperDetails?.is_oa
                          ? t('right.restrictedOA')
                          : t('right.restrictedPaywall')}
                      </span>
                    </div>
                    <p className="text-[11.5px] text-amber-700 dark:text-amber-300/80 leading-relaxed">
                      {paperDetails?.is_oa
                        ? t('right.restrictedOADesc')
                        : t('right.restrictedPaywallDesc')}
                    </p>
                    {landingUrl && (
                      <div className="pt-1">
                        <a
                          href={landingUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-500/20 hover:bg-amber-500/30 text-amber-800 dark:text-amber-100 font-medium text-xs border border-amber-500/30 transition-colors"
                        >
                          <ExternalLink size={13} />
                          <span>{t('right.openOfficial')}</span>
                        </a>
                      </div>
                    )}
                  </div>

                  {/* Paper Title & Authors */}
                  <div className="pb-3 border-b border-app-divider space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold font-mono uppercase bg-amber-500/15 border border-amber-500/30 text-amber-600 dark:text-amber-400">
                        {t('right.metadataAndAbstract')}
                      </span>
                      {paperDetails?.year && (
                        <span className="text-[11px] text-app-text-dim">
                          {paperDetails.year}
                        </span>
                      )}
                    </div>

                    <h2 className="text-sm sm:text-[15px] font-bold text-app-text leading-snug">
                      {title}
                    </h2>

                    {authorsStr && (
                      <p className="text-xs text-app-text-muted">
                        {t('right.by')}{authorsStr}
                      </p>
                    )}
                  </div>

                  {/* Official Abstract Content */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold text-app-text uppercase tracking-wider">
                      {t('right.officialAbstract')}
                    </h3>
                    <div className="text-[12.5px] sm:text-[13px] text-app-text leading-relaxed font-sans whitespace-pre-wrap select-text break-words bg-app-input-surface p-3.5 rounded-lg border border-app-border">
                      {(() => {
                        const targetAbstract = cleanAbstract || paperDetails?.abstract || "No additional abstract text provided.";
                        const res = getHighlightedContent(
                          targetAbstract,
                          groundingHighlight?.sentence,
                          highlightRefsMap,
                          activeMatchIndex,
                          groundingHighlight?.aiQuotes
                        );
                        if (res.matchCount !== totalMatches) {
                          setTimeout(() => setTotalMatches(res.matchCount), 0);
                        }
                        return res.nodes;
                      })()}
                    </div>
                  </div>
                </div>
              ) : paperDetails?.content ? (
                <div className="p-4 sm:p-5 rounded-xl bg-app-card border border-app-border shadow-lg space-y-4">
                  {/* Status Banner for Full Manuscript */}
                  <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-300">
                    <Check size={14} className="text-emerald-500 shrink-0" />
                    <span className="font-medium">{t('right.fullManuscriptVerified')}</span>
                  </div>

                  {/* Paper Sheet Header */}
                  <div className="pb-3 border-b border-app-divider space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold font-mono uppercase bg-blue-500/15 border border-blue-500/30 text-blue-500">
                        {paperDetails.type?.toUpperCase() || "PDF"}
                      </span>
                      {paperDetails.year && (
                        <span className="text-[11px] text-app-text-dim">
                          {paperDetails.year}
                        </span>
                      )}
                    </div>

                    <h2 className="text-sm sm:text-[15px] font-bold text-app-text leading-snug">
                      {title}
                    </h2>

                    {authorsStr && (
                      <p className="text-xs text-app-text-muted">
                        {t('right.by')}{authorsStr}
                      </p>
                    )}
                  </div>

                  {/* Clean Formatted Document Body (Scrolls through the entire file) */}
                  <div className="text-[12.5px] sm:text-[13px] text-app-text leading-relaxed font-sans whitespace-pre-wrap select-text break-words">
                    {(() => {
                      // Strip repeated journal header/footer lines injected by PyMuPDF on every page
                      let cleanedContent = paperDetails.content
                        .replace(/^#\s+[^\n]+\n+/, "")
                        .replace(/##\s+Abstract & Overview\n+/, "");
                      // Remove repeated journal masthead blocks (ISSN, page numbers, author footers, "available online at" lines)
                      cleanedContent = cleanedContent.replace(/\n*(?:Author\s*\d*\s*\|[^\n]*\n?)+/gi, "\n");
                      cleanedContent = cleanedContent.replace(/\n*\*\*_?[A-Za-z]+:.*?Journal.*?_?\*\*[^\n]*\n(?:[^\n]*ISSN[^\n]*\n)?(?:[^\n]*Halaman[^\n]*\n)?(?:[^\n]*available online at[^\n]*\n)?/gi, "\n");
                      cleanedContent = cleanedContent.replace(/\n*_?available online at_?\s*https?:\/\/[^\n]+\n*/gi, "\n");
                      cleanedContent = cleanedContent.replace(/\n{3,}/g, "\n\n");

                      const res = getHighlightedContent(
                        cleanedContent,
                        groundingHighlight?.sentence,
                        highlightRefsMap,
                        activeMatchIndex,
                        groundingHighlight?.aiQuotes
                      );
                      if (res.matchCount !== totalMatches) {
                        setTimeout(() => setTotalMatches(res.matchCount), 0);
                      }
                      return res.nodes;
                    })()}
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-app-card border border-app-border text-center py-10 space-y-2">
                  <FileText size={28} className="text-app-text-dim mx-auto stroke-[1.5]" />
                  <p className="text-xs text-app-text font-medium">{t('right.docIndexed')}</p>
                  <p className="text-[11px] text-app-text-dim max-w-[240px] mx-auto">
                    {t('right.docIndexedDesc')}
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : activeTab === "pdf" ? (
          <div className="flex-1 w-full h-full bg-app-surface overflow-hidden relative">
            {activeChatId && viewingDoc && paperDetails?.has_full_pdf !== false ? (
              <object
                data={`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/stream#toolbar=1&navpanes=0`}
                type="application/pdf"
                className="w-full h-full"
              >
                <div className="flex flex-col items-center justify-center h-full text-center p-6 space-y-3">
                  <FileText size={36} className="text-blue-500 mx-auto stroke-[1.5]" />
                  <p className="text-xs text-app-text font-medium">{t('right.openInNewTab')}</p>
                  <a
                    href={`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/stream`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium inline-flex items-center gap-1.5 shadow-sm transition-colors"
                  >
                    <ExternalLink size={13} />
                    <span>{t('right.openInNewTab')}</span>
                  </a>
                </div>
              </object>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-6 space-y-3">
                <FileText size={36} className="text-amber-500 mx-auto stroke-[1.5]" />
                <div className="space-y-1 max-w-sm">
                  <p className="text-xs text-app-text font-medium">
                    {t('right.originalDocNotAvail')}
                  </p>
                </div>
                {landingUrl && (
                  <a
                    href={landingUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium inline-flex items-center gap-1.5 shadow-sm transition-colors mt-2"
                  >
                    <ExternalLink size={13} />
                    <span>{t('right.openOfficialPublisher')}</span>
                  </a>
                )}
              </div>
            )}
          </div>
        ) : null}

        {/* 4. Consensus-style Bottom Floating Action Toolbar */}
        <div className={`p-3 border-t border-app-divider bg-app-sidebar flex items-center justify-between gap-1.5 shrink-0 select-none transition-opacity ${
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
              title={t('right.askAI')}
            >
              <MessageSquare size={13} />
              <span>{t('right.ask')}</span>
            </button>

            {/* Multi-Format Cite Button (Opens Interactive Citation Modal) */}
            <button
              disabled={isLoadingDetails}
              onClick={() => setIsCiteModalOpen(true)}
              className="h-8 px-2.5 rounded-full bg-app-card hover:bg-app-card-hover disabled:opacity-50 border border-app-border text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
              title={t('right.citePaper')}
            >
              <Quote size={13} />
              <span>{t('action.cite') || 'Cite'}</span>
            </button>

            {/* Copy Link Icon Button */}
            <button
              disabled={isLoadingDetails || !landingUrl}
              onClick={() => copyToClipboard(landingUrl, "link")}
              className="w-8 h-8 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border disabled:opacity-50 text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
              title={copiedLink ? t('right.copiedLink') : t('right.copyLink')}
            >
              {copiedLink ? <Check size={14} className="text-emerald-500" /> : <LinkIcon size={14} />}
            </button>

            {/* Download Icon Button */}
            {activeChatId && (() => {
              const isDownloadable = Boolean(!isLoadingDetails && paperDetails?.has_full_pdf);
              if (!isDownloadable) {
                return (
                  <button
                    disabled
                    className="w-8 h-8 rounded-full bg-app-card border border-app-border text-app-text-dim opacity-30 flex items-center justify-center cursor-not-allowed"
                    title={t('right.downloadNotAvail')}
                  >
                    <Download size={14} />
                  </button>
                );
              }
              return (
                <a
                  href={`${backendUrl}/chats/${activeChatId}/documents/${viewingDoc.id}/download`}
                  download={viewingDoc.filename}
                  className="w-8 h-8 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer shadow-sm"
                  title="Download original manuscript PDF"
                >
                  <Download size={14} />
                </a>
              );
            })()}
          </div>

          {/* Right Side: PDF / External Landing Page Pill - ALWAYS shown */}
          {(() => {
            const pdfLink = landingUrl || `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
            return (
              <a
                href={isLoadingDetails ? undefined : pdfLink}
                target="_blank"
                rel="noopener noreferrer"
                className={`h-8 px-2.5 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text text-xs font-medium flex items-center gap-1.5 transition-colors shrink-0 shadow-sm ${
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
          <div 
            onClick={(e) => {
              e.stopPropagation();
              setIsCiteModalOpen(false);
            }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
          >
            <div 
              onClick={(e) => e.stopPropagation()}
              className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-[530px] p-5 shadow-2xl space-y-3.5 animate-in zoom-in-95 duration-150 text-app-text"
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between pb-2.5 border-b border-app-divider">
                <div className="flex items-center gap-2">
                  <Quote size={16} className="text-blue-500" />
                  <h3 className="text-sm font-semibold text-app-text">Cite this Paper</h3>
                </div>
                <button
                  onClick={() => setIsCiteModalOpen(false)}
                  className="w-7 h-7 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover flex items-center justify-center transition-colors cursor-pointer"
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
                        : "bg-app-item-hover hover:bg-app-item-active text-app-text-muted hover:text-app-text"
                    }`}
                  >
                    {st.label}
                  </button>
                ))}
              </div>

              {/* Fixed-Height Scrollable Citation Content Box */}
              <div className="h-[140px] p-3.5 rounded-xl bg-app-input-surface border border-app-border font-sans text-xs leading-relaxed select-text text-app-text break-words whitespace-pre-wrap overflow-y-auto custom-scrollbar">
                {citations[selectedCitationStyle]}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-1 border-t border-app-divider">
                <div className="flex items-center gap-2">
                  {selectedCitationStyle === "bibtex" && (
                    <button
                      onClick={() => downloadFileText(citations.bibtex, `${doiStr ? doiStr.replace(/[^a-z0-9]/gi, "_") : "paper"}.bib`)}
                      className="px-2.5 py-1.5 rounded-lg bg-app-card hover:bg-app-card-hover border border-app-border text-xs text-app-text-muted hover:text-app-text transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm"
                    >
                      <Download size={13} />
                      <span>Download .bib</span>
                    </button>
                  )}
                  {selectedCitationStyle === "ris" && (
                    <button
                      onClick={() => downloadFileText(citations.ris, `${doiStr ? doiStr.replace(/[^a-z0-9]/gi, "_") : "paper"}.ris`)}
                      className="px-2.5 py-1.5 rounded-lg bg-app-card hover:bg-app-card-hover border border-app-border text-xs text-app-text-muted hover:text-app-text transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm"
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
                  className="bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs rounded-lg px-4 h-8 cursor-pointer flex items-center gap-1.5 shadow-sm transition-colors"
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
    <aside className="w-full lg:w-80 h-full bg-app-sidebar border-l border-app-border flex flex-col shrink-0 select-none z-10 transition-all relative text-app-text">
      {/* 1. Header Bar: Top Fixed Header */}
      <div className="px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-app-text tracking-tight">{t('ui.sources') || "Sources"}</span>
          <span className="px-1.5 py-0.5 rounded-full text-[10.5px] font-mono font-medium bg-app-item-hover text-app-text-muted">
            {documents.length}
          </span>
        </div>
        <button 
          onClick={onClose}
          className="w-7 h-7 rounded-lg bg-app-item-hover hover:bg-app-item-active text-app-text-muted hover:text-app-text flex items-center justify-center transition-colors cursor-pointer"
          title={t('right.close') || "Hide sidebar"}
        >
          <X size={15} />
        </button>
      </div>

      {/* Hidden File Input for Multi-format Document Upload */}
      <input
        ref={fileInputRef}
        type="file"
        id="sources-file-upload"
        className="hidden"
        accept=".pdf,.docx,.doc,.txt,.md,.bib,.bibtex,.ris"
        multiple
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleUploadBatch(Array.from(e.target.files));
          }
          if (e.target) e.target.value = "";
        }}
      />

      {/* 2 & 3. Fixed Controls Area (Add Sources + Toolbar) */}
      <div className="p-3.5 pb-2.5 space-y-2.5 shrink-0 bg-app-sidebar z-10 border-b border-app-divider shadow-sm">
        {/* Prominent '+ Add sources' Button (NotebookLM Style) */}
        <div className="w-full">
          <Button
            variant="outline"
            className="w-full h-11 rounded-full bg-app-card hover:bg-app-card-hover border border-app-border text-app-text font-medium text-sm flex items-center justify-center gap-2 cursor-pointer shadow-sm transition-colors"
            onClick={() => setIsAddSourcesModalOpen(true)}
          >
            <Plus size={18} className="text-app-text-muted" />
            <span>{t('ui.addSources')}</span>
          </Button>
        </div>

        {/* Dynamic Clean Feedback Notification */}
        {cleanFeedback && (
          <div className="w-full px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-medium flex items-center gap-2 animate-in fade-in zoom-in-95 duration-150">
            <Check size={13} className="text-emerald-400 shrink-0" />
            <span className="text-[12px]">{cleanFeedback}</span>
          </div>
        )}

        {/* Action Toolbar (Always-rendered icons with dynamic disabled states) */}
        <div className="w-full flex items-center justify-between pt-1 px-0 text-xs text-app-text-muted relative">
          <div className="flex items-center gap-1">
            {/* Sort Button & Dropdown (Disabled if <= 1 document) */}
            <div className="relative" ref={sortMenuRef}>
              <button 
                onClick={() => {
                  if (documents.length > 1) {
                    setIsSortMenuOpen(prev => !prev);
                  }
                }}
                disabled={documents.length <= 1}
                className={`w-6 h-6 -ml-1 rounded transition-colors flex items-center justify-center ${
                  documents.length > 1
                    ? "text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer"
                    : "text-app-text-dim opacity-30 cursor-not-allowed"
                }`}
                title={documents.length > 1 ? t('right.sortSources') : t('right.addMoreSort')}
              >
                <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" className="opacity-90">
                  <rect x="2" y="3" width="12" height="1.6" rx="0.8" />
                  <rect x="2" y="7.2" width="8" height="1.6" rx="0.8" />
                  <rect x="2" y="11.4" width="4.5" height="1.6" rx="0.8" />
                </svg>
              </button>

              {/* Sort Dropdown Menu (2 Sections with Divider: Criteria & Direction) */}
              {isSortMenuOpen && (
                <div className="absolute left-0 top-7 z-30 w-36 rounded-xl bg-app-dropdown border border-app-border-strong shadow-2xl p-1 text-xs animate-in fade-in zoom-in-95 duration-100 text-app-text">
                  {/* Section 1: Sort Criteria */}
                  <div className="space-y-0.5 pb-0.5">
                    <button
                      onClick={() => { setSortBy("title"); setIsSortMenuOpen(false); }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
                    >
                      <span className={sortBy === "title" ? "text-app-text font-medium" : "text-app-text-muted"}>Title</span>
                      {sortBy === "title" && <Check size={13} className="text-blue-500" strokeWidth={2.5} />}
                    </button>
                    <button
                      onClick={() => { setSortBy("date"); setIsSortMenuOpen(false); }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
                    >
                      <span className={sortBy === "date" ? "text-app-text font-medium" : "text-app-text-muted"}>Date added</span>
                      {sortBy === "date" && <Check size={13} className="text-blue-500" strokeWidth={2.5} />}
                    </button>
                  </div>

                  {/* Section Divider Line */}
                  <div className="border-t border-app-divider my-1" />

                  {/* Section 2: Sort Direction (Ascending / Descending) */}
                  <div className="space-y-0.5 pt-0.5">
                    <button
                      onClick={() => { setSortDirection("asc"); setIsSortMenuOpen(false); }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
                    >
                      <span className={sortDirection === "asc" ? "text-app-text font-medium" : "text-app-text-muted"}>Ascending</span>
                      {sortDirection === "asc" && <Check size={13} className="text-blue-500" strokeWidth={2.5} />}
                    </button>
                    <button
                      onClick={() => { setSortDirection("desc"); setIsSortMenuOpen(false); }}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between transition-colors cursor-pointer text-app-text-muted hover:text-app-text hover:bg-app-item-hover"
                    >
                      <span className={sortDirection === "desc" ? "text-app-text font-medium" : "text-app-text-muted"}>Descending</span>
                      {sortDirection === "desc" && <Check size={13} className="text-blue-500" strokeWidth={2.5} />}
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
                    ? "text-app-text-muted hover:text-emerald-500 hover:bg-emerald-500/10 cursor-pointer"
                    : "text-app-text-dim opacity-30 cursor-not-allowed"
                }`}
                title={t('right.cleanDup')}
              >
                {isCleaningDuplicates ? (
                  <Loader2 size={14} className="animate-spin text-emerald-500" />
                ) : (
                  <Sparkles size={14} />
                )}
              </button>

              {/* Rename Button (Enabled strictly when exactly 1 source is selected) */}
              <button
                onClick={handleOpenRename}
                disabled={selectedCount !== 1}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  selectedCount === 1
                    ? "text-app-text-muted hover:text-blue-500 hover:bg-blue-500/10 cursor-pointer"
                    : selectedCount > 1
                    ? "text-app-text-dim opacity-25 cursor-not-allowed"
                    : "text-app-text-dim opacity-30 cursor-not-allowed"
                }`}
                title={
                  selectedCount === 1
                    ? t('right.renameSelected')
                    : selectedCount > 1
                    ? t('right.renameMultiError').replace('{n}', selectedCount.toString())
                    : t('right.renameSelectOne')
                }
              >
                <Pencil size={14} />
              </button>

              {/* Download Button */}
              {(() => {
                const downloadableSelectedCount = selectedDocList.filter(d => d.has_full_pdf !== false).length;
                const canDownload = selectedCount > 0 && downloadableSelectedCount > 0 && !isBulkDownloading;
                const tooltipText = selectedCount === 0 
                  ? t('right.selectToDownload')
                  : downloadableSelectedCount === 0
                  ? t('right.downloadNotAvail')
                  : selectedCount === 1
                  ? t('right.downloadPdf')
                  : downloadableSelectedCount === selectedCount
                  ? t('right.downloadSelected').replace('{n}', selectedCount.toString())
                  : t('right.downloadSelectedSkip').replace('{n}', downloadableSelectedCount.toString()).replace('{m}', (selectedCount - downloadableSelectedCount).toString());

                return (
                  <button
                    onClick={handleBulkDownload}
                    disabled={!canDownload}
                    className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                      canDownload
                        ? "text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer"
                        : "text-app-text-dim opacity-30 cursor-not-allowed"
                    }`}
                    title={tooltipText}
                  >
                    {isBulkDownloading ? (
                      <Loader2 size={15} className="animate-spin text-blue-500" />
                    ) : (
                      <Download size={15} />
                    )}
                  </button>
                );
              })()}

              {/* Delete Button */}
              <button
                onClick={() => {
                  setDocToDelete(null); // Ensure bulk delete mode uses selected checkboxes
                  setShowBulkDeleteConfirm(true);
                }}
                disabled={selectedCount === 0 || isBulkDeleting}
                className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${
                  selectedCount > 0
                    ? "text-app-text-muted hover:text-red-500 hover:bg-red-500/10 cursor-pointer"
                    : "text-app-text-dim opacity-30 cursor-not-allowed"
                }`}
                title={selectedCount > 0 ? t('right.deleteSelected').replace('{n}', selectedCount.toString()) : t('right.selectToDelete')}
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>

          {/* Select all label and checkbox (Disabled when 0 documents) */}
          <div className={`flex items-center gap-2 pr-0.5 whitespace-nowrap select-none ${
            documents.length === 0 ? "opacity-30 pointer-events-none" : ""
          }`}>
            <span className="text-[11px] font-medium text-app-text-muted select-none">{t('right.selectAll')}</span>
            <button
              type="button"
              onClick={handleToggleSelectAll}
              disabled={documents.length === 0}
              className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
                documents.length === 0 
                  ? "border-app-border-strong bg-transparent cursor-not-allowed"
                  : isAllSelected || isPartiallySelected 
                  ? "bg-blue-600 border-blue-600 text-white cursor-pointer hover:border-gray-300" 
                  : "border-app-border-strong bg-transparent cursor-pointer hover:border-blue-500"
              }`}
              title={documents.length === 0 ? t('right.noSourcesAvail') : isAllSelected ? t('right.unselectAll') : t('right.selectAll')}
            >
              {isAllSelected && documents.length > 0 ? (
                <Check size={10} strokeWidth={3} />
              ) : isPartiallySelected ? (
                <Minus size={10} strokeWidth={3} />
              ) : null}
            </button>
          </div>
        </div>
      </div>

      {/* 4. Scrollable Document List Area ONLY */}
      <div className="px-3.5 pb-3.5 flex-1 flex flex-col overflow-y-auto custom-scrollbar min-h-0 relative">
        {/* 4. Saved Documents / Sources List (Compact height per item, flush left & right align) */}
        <div className="w-full flex-1 space-y-0.5 pt-0.5">
          {sortedDocuments.length === 0 && pendingSources.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center text-app-text-muted px-3">
              <FileText size={30} className="text-app-text-dim mb-2 stroke-[1.5]" />
              <h4 className="text-xs font-semibold text-app-text">{t('ui.noSources')}</h4>
              <p className="text-[11px] text-app-text-dim mt-1 max-w-[220px] leading-relaxed">
                {t('ui.noSourcesDesc')}
              </p>
            </div>
          ) : (
            <>
              {/* Existing indexed documents */}
              {sortedDocuments.map((doc) => {
                const isChecked = selectedDocs[doc.id] !== undefined ? selectedDocs[doc.id] : true;
                const badge = getFileBadgeInfo(doc.filename);
                const docIndex = (documents.findIndex(d => d.id === doc.id) + 1) || doc.index || 1;

                return (
                  <div
                    key={doc.id}
                    onClick={() => setViewingDoc(doc)}
                    className="flex items-center justify-between py-1.5 pl-1 pr-0.5 rounded-lg bg-transparent hover:bg-app-item-hover transition-colors cursor-pointer group"
                  >
                    {/* Left: Clean Monospace Index + Compact Format Badge + File Name */}
                    <div className="flex items-center gap-2 min-w-0 flex-1 mr-1.5">
                      {/* Clean Minimalist Index */}
                      <span 
                        className="w-7 text-left pl-0.5 text-[11px] font-mono font-medium text-app-text-dim group-hover:text-app-text transition-colors shrink-0 select-none tabular-nums"
                        title={`Permanent Reference Index [${docIndex}]`}
                      >
                        {docIndex}.
                      </span>

                      <div className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 ${badge.bg}`}>
                        <span className="text-[7.5px] font-bold tracking-tighter uppercase font-mono">{badge.label}</span>
                      </div>

                      {(() => {
                        let displayTitle = (doc.title || doc.filename.replace(/\.[^/.]+$/, "").replace(/_/g, " ")).replace(/<[^>]+>/g, "").trim();
                        if (displayTitle.length > 8 && displayTitle === displayTitle.toUpperCase()) {
                          displayTitle = displayTitle.toLowerCase().replace(/\b\w/g, (c: string) => c.toUpperCase());
                        }
                        return (
                          <span className="text-[11.5px] text-app-text truncate group-hover:text-blue-500 font-medium transition-colors" title={displayTitle}>
                            {displayTitle}
                          </span>
                        );
                      })()}
                    </div>

                    {/* 3 dots action menu */}
                    <div className="shrink-0 flex items-center relative mr-1 document-action-menu-container">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (activeMenuId === doc.id) {
                            setActiveMenuId(null);
                          } else {
                            setActiveMenuId(doc.id);
                          }
                        }}
                        className={`p-1 rounded-md transition-colors z-20 hover:bg-app-item-active group-hover:opacity-100 ${
                          activeMenuId === doc.id ? "opacity-100 text-app-text bg-app-item-active" : "opacity-0 text-app-text-muted"
                        }`}
                      >
                        <MoreHorizontal size={14} />
                      </button>
                      {/* Dropdown Menu */}
                      {activeMenuId === doc.id && (
                        <div 
                          className="absolute right-0 mt-1 w-36 bg-app-dropdown border border-app-border-strong rounded-xl shadow-xl z-[60] overflow-hidden py-1 animate-in fade-in zoom-in-95 duration-100"
                          ref={(el) => {
                            if (el) {
                                const rect = el.getBoundingClientRect();
                                const windowHeight = window.innerHeight;
                                // If the element is in the bottom half of the screen
                                if (rect.top > windowHeight / 2) {
                                  el.style.top = 'auto';
                                  el.style.bottom = '100%';
                                  el.style.marginBottom = '4px';
                                  el.style.marginTop = '0px';
                                } else {
                                  // If the element is in the top half of the screen
                                  el.style.top = '100%';
                                  el.style.bottom = 'auto';
                                  el.style.marginBottom = '0px';
                                  el.style.marginTop = '4px';
                                }
                            }
                          }}
                        >
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveMenuId(null);
                              setRenamingDoc(doc);
                              setRenameTitleInput(doc.title || doc.filename.replace(/\.[^/.]+$/, "").replace(/_/g, " "));
                              setRenameError(null);
                              setIsRenameModalOpen(true);
                            }}
                            className="w-full text-left px-3 py-1.5 text-xs text-app-text hover:bg-app-item-hover transition-colors flex items-center gap-2"
                          >
                            <Pencil size={13} className="shrink-0" /> {t('action.rename')}
                          </button>
                          <button
                            onClick={async (e) => {
                              e.stopPropagation();
                              setActiveMenuId(null);
                              if (!activeChatId) return;
                              try {
                                const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/${doc.id}/download`);
                                if (res.ok) {
                                  const blob = await res.blob();
                                  const url = window.URL.createObjectURL(blob);
                                  const link = document.createElement("a");
                                  link.href = url;
                                  link.download = doc.filename.endsWith(".pdf") ? doc.filename : `${doc.filename}.pdf`;
                                  document.body.appendChild(link);
                                  link.click();
                                  document.body.removeChild(link);
                                  window.URL.revokeObjectURL(url);
                                } else {
                                  alert("Failed to download document");
                                }
                              } catch (err) {
                                console.error(err);
                              }
                            }}
                            className="w-full text-left px-3 py-1.5 text-xs text-app-text hover:bg-app-item-hover transition-colors flex items-center gap-2"
                          >
                            <Download size={13} className="shrink-0" /> {t('action.download') || "Download"}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveMenuId(null);
                              setDocToDelete(doc.id);
                              setShowBulkDeleteConfirm(true);
                            }}
                            className="w-full text-left px-3 py-1.5 text-xs text-red-500 hover:bg-red-500/10 transition-colors flex items-center gap-2"
                          >
                            <Trash2 size={13} className="shrink-0" /> {t('action.delete')}
                          </button>
                        </div>
                      )}
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
                        isChecked ? "bg-blue-600 border-blue-600 text-white" : "border-app-border-strong bg-transparent"
                      }`}>
                        {isChecked && <Check size={9} strokeWidth={3} />}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Pending Uploading & Resolving Sources (NotebookLM Circular Progress Spinner) */}
              {pendingSources.map((item: PendingSourceItem, pIdx: number) => {
                const badge = getFileBadgeInfo(item.filename);
                const itemNumber = documents.length + pIdx + 1;

                return (
                  <div
                    key={item.id}
                    className="flex items-center justify-between py-1.5 pl-1 pr-0.5 rounded-lg bg-transparent hover:bg-app-item-hover transition-colors select-none group"
                  >
                    {/* Left: Monospace Number + Badge + File / DOI Name */}
                    <div className="flex items-center gap-2 min-w-0 flex-1 mr-1.5">
                      <span 
                        className="w-7 text-left pl-0.5 text-[11px] font-mono font-medium text-app-text-dim shrink-0 select-none tabular-nums"
                      >
                        {itemNumber}.
                      </span>

                      <div className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 ${badge.bg}`}>
                        <span className="text-[7.5px] font-bold tracking-tighter uppercase font-mono">{badge.label}</span>
                      </div>

                      <span 
                        className={`text-[11.5px] truncate font-normal ${
                          item.status === "error" ? "text-red-500 line-through opacity-80" : "text-app-text-muted"
                        }`} 
                        title={item.filename}
                      >
                        {item.filename}
                      </span>
                    </div>

                    {/* Right: Circular Spinner (NotebookLM Ring Loader) or Error Icon */}
                    <div className="flex items-center shrink-0 pr-0.5">
                      {item.status === "uploading" ? (
                        <div className="w-3.5 h-3.5 flex items-center justify-center" title={t('right.uploading')}>
                          <svg className="animate-spin w-3.5 h-3.5 text-blue-400" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                            <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <span title={item.error || t('right.uploadFailed')} className="text-red-400 cursor-help">
                            <AlertCircle size={13} />
                          </span>
                          <button
                            type="button"
                            onClick={() => setInternalPendingSources(prev => prev.filter(p => p.id !== item.id))}
                            className="text-app-text-dim hover:text-app-text p-0.5 rounded cursor-pointer"
                            title={t('right.dismiss')}
                          >
                            <X size={12} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>
      </div>

      {/* Google NotebookLM Style 'Add Sources' Centered Modal Dialog */}
        {isAddSourcesModalOpen && (
          <div 
            onClick={(e) => {
              e.stopPropagation();
              setIsAddSourcesModalOpen(false);
              setDoiInput("");
            }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
          >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-app-modal border border-app-border-strong rounded-3xl w-full max-w-xl p-6 sm:p-7 shadow-2xl space-y-6 animate-in zoom-in-95 duration-150 relative text-app-text"
          >
            {/* Close Button */}
            <button
              onClick={() => {
                setIsAddSourcesModalOpen(false);
                setDoiInput("");
              }}
              className="absolute top-5 right-5 p-1.5 rounded-full hover:bg-app-item-hover text-app-text-muted hover:text-app-text transition-colors cursor-pointer"
              title={t('right.close')}
            >
              <X size={18} />
            </button>

            {/* Modal Header */}
            <div className="space-y-1.5 pr-8">
              <h2 className="text-xl font-bold text-app-text tracking-tight leading-snug">
                {t('ui.addSources')}
              </h2>
              <p className="text-xs text-app-text-muted">
                {t('right.addSourcesModalDesc')}
              </p>
            </div>

            {/* Section 1: Fast DOI Input Bar */}
            <div className="space-y-2">
              <form onSubmit={handleImportDoi} className="relative flex items-center">
                <div className="relative w-full">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-app-text-dim pointer-events-none">
                    <Search size={15} />
                  </div>
                  <input
                    type="text"
                    value={doiInput}
                    onChange={(e) => setDoiInput(e.target.value)}
                    placeholder={t('right.enterDoi')}
                    className="w-full h-11 pl-10 pr-24 rounded-full bg-app-input-surface border border-app-border focus:border-blue-500 text-xs text-app-text placeholder:text-app-text-dim focus:outline-none transition-all"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!doiInput.trim()}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 h-8 px-3.5 rounded-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:cursor-not-allowed shadow-sm"
                >
                  <span>{t('right.import')}</span>
                </button>
              </form>
            </div>

            {/* Section 2: Drag and Drop Dropzone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setIsDraggingOver(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setIsDraggingOver(false);
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setIsDraggingOver(false);
                if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                  handleUploadBatch(Array.from(e.dataTransfer.files));
                }
              }}
              onClick={() => {
                fileInputRef.current?.click();
              }}
              className={`p-8 sm:p-10 rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center text-center space-y-3 ${
                isDraggingOver
                  ? "border-blue-500 bg-blue-500/10 scale-[1.01]"
                  : "border-app-border-strong hover:border-blue-500/50 bg-app-card hover:bg-app-card-hover"
              }`}
            >
              <div className="w-12 h-12 rounded-full bg-app-surface border border-app-border flex items-center justify-center text-app-text-muted">
                <UploadCloud size={24} className="text-app-text-muted" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-app-text">
                  {t('right.dropFiles')}
                </p>
                <p className="text-xs text-app-text-dim">
                  {t('right.supportedFormats')}
                </p>
              </div>
            </div>

            {/* Section 3: Capacity Progress Bar (300 Sources Max) */}
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between text-xs text-app-text-muted">
                <span>{t('right.sourcesCapacity')}</span>
                <span className="font-medium text-app-text font-mono">
                  {documents.length + pendingSources.length} / 300
                </span>
              </div>
              <div className="w-full h-1.5 bg-app-input-surface rounded-full overflow-hidden border border-app-border">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-300"
                  style={{ width: `${Math.min(100, ((documents.length + pendingSources.length) / 300) * 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Centered Modal for Bulk Delete Confirmation */}
      <BulkDeleteModal
        isOpen={showBulkDeleteConfirm}
        selectedCount={docToDelete !== null ? 1 : selectedCount}
        isBulkDeleting={isBulkDeleting}
        onClose={() => {
          setShowBulkDeleteConfirm(false);
          setDocToDelete(null);
        }}
        onConfirm={handleConfirmBulkDelete}
      />

      {/* Centered Modal for Renaming Single Document */}
      <RenameModal
        isOpen={isRenameModalOpen}
        renamingDoc={renamingDoc}
        renameTitleInput={renameTitleInput}
        isSavingRename={isSavingRename}
        onInputChange={setRenameTitleInput}
        onClose={() => setIsRenameModalOpen(false)}
        onSave={handleSaveRename}
      />
    </aside>
  );
}
