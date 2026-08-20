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
  ChevronUp,
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
  onDocumentAdded: (doc: Document, targetChatId?: string) => void;
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

      // Check for exact substring match first — only quote-in-sentence direction
      // (sentence-in-quote would match any short fragment that happens to appear in a long quote)
      let foundExact = false;
      rawSentences.forEach((s, idx) => {
        const sClean = s.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim().replace(/\s+/g, " ");
        if (sClean.length >= 15 && sClean.includes(cleanQuote)) {
          aiHighlightedIndices.add(idx);
          foundExact = true;
        }
      });

      if (!foundExact) {
        // High-precision keyword overlap with numeric bonus
        let bestSentenceIdx = -1;
        let highestScore = 0;

        rawSentences.forEach((s, idx) => {
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

          // Require at least 60% word overlap (up from 50%) to reduce false positives on generic sentences
          if (wordRatio >= 0.60 && combinedScore > highestScore) {
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
                  className={`font-medium px-0.5 py-0.5 rounded-sm inline leading-relaxed transition-all box-decoration-clone ${
                    isActiveCluster
                      ? "bg-amber-400/40 text-amber-100 ring-2 ring-amber-400/50 shadow-sm"
                      : "bg-amber-400/20 text-amber-200/90 border-b border-amber-400/30"
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
    // Skip very short lines (single chars, roman numerals, table separators)
    if (s.trim().length < 8) {
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
    const threshold = Math.max(14, maxSingleScore * 0.60);
    
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

  // Fallback: If no match above threshold, highlight best matching sentence ONLY if it scored > 0
  if (highlightedIndices.size === 0) {
    let fallbackIdx = -1;
    let bestScore = 0; // Must have at least some score to be highlighted
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
              className={`font-medium px-0.5 py-0.5 rounded-sm inline leading-relaxed transition-all box-decoration-clone ${
                isActiveCluster
                  ? "bg-amber-400/40 text-amber-100 ring-2 ring-amber-400/50 shadow-sm"
                  : "bg-amber-400/20 text-amber-200/90 border-b border-amber-400/30"
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

  // Fetch document details when viewingDoc is set
  useEffect(() => {
    if (!viewingDoc || !activeChatId) {
      setPaperDetails(null);
      return;
    }
    setIsLoadingDetails(true);
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
        onDocumentAdded(newDoc, currentChatId);
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
                  {cleanAbstract}
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
                  {cleanAbstract}
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
                <span className="truncate max-w-[170px] font-mono text-[11px] text-gray-300">
                  {viewingDoc.filename}
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                {/* Evidence Passage Navigator (Chevron Up / Down for multiple disjoint matches) */}
                {totalMatches > 1 && (
                  <div className="flex items-center gap-1 bg-amber-400/10 border border-amber-400/30 rounded-lg px-2 py-0.5 mr-1">
                    <span className="text-[10px] font-mono font-semibold text-amber-300">
                      {activeMatchIndex + 1}/{totalMatches}
                    </span>
                    <div className="flex items-center">
                      <button
                        type="button"
                        onClick={() => {
                          const prev = activeMatchIndex > 0 ? activeMatchIndex - 1 : totalMatches - 1;
                          setActiveMatchIndex(prev);
                        }}
                        className="p-0.5 hover:bg-amber-400/20 text-amber-300 hover:text-white rounded transition-colors"
                        title="Previous evidence section"
                      >
                        <ChevronUp size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const next = activeMatchIndex < totalMatches - 1 ? activeMatchIndex + 1 : 0;
                          setActiveMatchIndex(next);
                        }}
                        className="p-0.5 hover:bg-amber-400/20 text-amber-300 hover:text-white rounded transition-colors"
                        title="Next evidence section"
                      >
                        <ChevronDown size={13} />
                      </button>
                    </div>
                  </div>
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
                        <p className="font-semibold text-amber-100">
                          {paperDetails.is_oa
                            ? "Publication Brief & Abstract (Direct Download Restricted / HTTP 403)"
                            : "Publication Brief & Abstract (Full Manuscript Paywalled)"}
                        </p>
                        <p className="text-[11.5px] text-amber-300/80 mt-0.5">
                          {paperDetails.is_oa
                            ? "This paper is Open Access, but automatic PDF retrieval was restricted by the publisher repository (HTTP 403 / Bot Challenge). Displaying verified academic metadata and official author abstract."
                            : "Full publisher manuscript is protected by publisher paywall. Displaying verified academic metadata and official author abstract."}
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
