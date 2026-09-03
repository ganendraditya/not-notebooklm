import { ReactNode } from "react";
import React from "react";

export const cleanHtmlAbstract = (raw?: string): string => {
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

export interface HighlightMatchResult {
  nodes: React.ReactNode;
  matchCount: number;
}

// Helper: Dynamic semantic grounding matcher for scientific claims & quotes (NotebookLM Style)
// Primary path: AI-decided verbatim quotes from CITATION_MAP. Fallback: Contextual semantic matcher.
export function getHighlightedContent(
  fullText: string, 
  targetQuery?: string, 
  highlightRefsMap?: React.MutableRefObject<Map<number, HTMLElement>>,
  activeMatchIndex: number = 0,
  aiQuotes?: string[]
): HighlightMatchResult {
  if (!fullText) return { nodes: null, matchCount: 0 };

  // 0. GUARD: Ignore conversational fluff / bibliography / generic introductory clauses
  const isGenericCitationQuery = !targetQuery || targetQuery.trim().length < 5 || (
    /^(?:berdasarkan|dokumen|referensi|sumber|menurut|daftar\s+pustaka|sitasi\s+rujukan|paper|jurnal|artikel|kesimpulan|rincian)\b/i.test(targetQuery.trim()) &&
    !/\d+[,.]\d+%?|\b\d+%\b|\bakurasi\b|\bmetode\b|\bhasil\b|\bdataset\b|\bsensitivitas\b|\bspesifisitas\b/i.test(targetQuery)
  ) || (
    /^\s*(?:santoso|rahma|et\s+al|dr\.|prof\.)/i.test(targetQuery.trim()) && targetQuery.length < 80
  );

  if (isGenericCitationQuery) {
    return { nodes: <span>{fullText}</span>, matchCount: 0 };
  }

  // Tokenize document text into atomic chunks while strictly preserving all original whitespace and linebreaks
  const rawSentences: string[] = [];
  // Match sentence chunks ending in punctuation (.!?) or linebreaks, capturing the delimiter to preserve formatting
  const tokenRegex = /(?:[\s\S]*?(?:(?<!\d)(?<!\d\s)[.!?]+(?=\s|$)|[\r\n]+))|[\s\S]+/g;
  let match;
  while ((match = tokenRegex.exec(fullText)) !== null) {
    if (match[0].length > 0) {
      rawSentences.push(match[0]);
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
          // ponytail: numeric bonus â€” upgrade path: use decimal-aware matching (e.g. "92.23" as single token)
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

export const formatReadableDate = (dateStr?: string, yearFallback?: string) => {
  if (!dateStr && !yearFallback) return "Recent publication";
  if (!dateStr) return yearFallback || new Date().getFullYear().toString();
  
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




