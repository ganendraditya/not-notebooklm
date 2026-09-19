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
  initialActiveIndex?: number;
}

// Helper: Dynamic semantic grounding matcher for scientific claims & quotes (NotebookLM Style)
// Primary path: AI-decided verbatim quotes from CITATION_MAP. Fallback: Contextual semantic matcher.
function findQuoteSpan(fullText: string, quote: string): [number, number] | null {
  if (!quote || quote.trim().length < 5) return null;
  const rawQ = quote.trim();

  // Tier 1: Exact index
  const exactIdx = fullText.indexOf(rawQ);
  if (exactIdx !== -1) return [exactIdx, exactIdx + rawQ.length];

  // Tier 2: Whitespace-flexible regex
  const escaped = rawQ.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
  try {
    const rx = new RegExp(escaped, "i");
    const m = rx.exec(fullText);
    if (m) return [m.index, m.index + m[0].length];
  } catch (e) {}

  // Tier 3: Markdown-aware regex allowing optional markdown tags (_, *, <u>, </u>) between words
  const cleanQ = rawQ.replace(/<[^>]+>/g, " ").replace(/[*_~`]/g, "").trim();
  const words = cleanQ.split(/\s+/).filter(w => w.length >= 1);
  if (words.length < 3) return null;

  const mdSeparator = "(?:[\\s*_~`]|<[^>]+>)+";
  try {
    const rxFullPattern = words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join(mdSeparator);
    const rxFull = new RegExp(rxFullPattern, "i");
    const m = rxFull.exec(fullText);
    if (m) return [m.index, m.index + m[0].length];
  } catch (e) {}

  // Tier 4: Anchor fallback using head (first 4 words) and tail (last 4 words)
  if (words.length >= 6) {
    try {
      const headPattern = words.slice(0, 4).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join(mdSeparator);
      const tailPattern = words.slice(-4).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join(mdSeparator);
      const rxHead = new RegExp(headPattern, "i");
      const rxTail = new RegExp(tailPattern, "i");
      const mHead = rxHead.exec(fullText);
      if (mHead) {
        const afterHead = fullText.substring(mHead.index);
        const mTail = rxTail.exec(afterHead);
        if (mTail && mTail.index < 4000) {
          const endPos = mHead.index + mTail.index + mTail[0].length;
          return [mHead.index, endPos];
        }
      }
    } catch (e) {}
  }
  return null;
}

export function getHighlightedContent(
  fullText: string, 
  targetQuery?: string, 
  highlightRefsMap?: React.MutableRefObject<Map<number, HTMLElement>>,
  activeMatchIndex: number = 0,
  aiQuotes?: string[]
): HighlightMatchResult {
  if (!fullText) return { nodes: null, matchCount: 0 };

  // Tokenize document text into atomic chunks while strictly preserving all original whitespace and linebreaks
  const rawSentences: string[] = [];
  const chunkOffsets: { start: number; end: number; idx: number }[] = [];
  const tokenRegex = /(?:^\s*#{1,6}\s+[^\n]*\n?|^\s*\*{2}[^\n*]+\*{2}\s*\n?|[\s\S]*?(?:(?<!\b[IVX\d])(?<!\d)(?<!\d\s)[.!?]+(?=\s|$)|\n\s*\n))|[\s\S]+/gm;
  let match;
  let sIdx = 0;
  while ((match = tokenRegex.exec(fullText)) !== null) {
    if (match[0].length > 0) {
      chunkOffsets.push({
        start: match.index,
        end: match.index + match[0].length,
        idx: sIdx++,
      });
      rawSentences.push(match[0]);
    }
  }
  if (rawSentences.length === 0) return { nodes: <span>{fullText}</span>, matchCount: 0 };

  // 0. AI-DRIVEN GROUNDING PATH (PRIMARY):
  // When aiQuotes are explicitly provided (from on-demand Fast LLM or CITATION_MAP),
  // strictly highlight all AI-determined verbatim evidence passages using exact character span detection.
  if (aiQuotes !== undefined && aiQuotes !== null) {
    if (aiQuotes.length === 0) {
      return { nodes: <span>{fullText}</span>, matchCount: 0 };
    }

    const aiHighlightedIndices = new Set<number>();
    const aiClusters: number[][] = [];

    // Locate exact character span of each quote directly within fullText.
    // This perfectly handles multiline table rows and multi-sentence evidence without fragmentation,
    // while completely eliminating false-positive substring matches on short isolated headings (like "Nomor Kendaraan").
    aiQuotes.forEach(quote => {
      const span = findQuoteSpan(fullText, quote);
      if (span) {
        chunkOffsets.forEach(chunk => {
          if (chunk.start < span[1] && chunk.end > span[0]) {
            aiHighlightedIndices.add(chunk.idx);
          }
        });
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
              const m = sentence.match(/^(\s*)([\s\S]*?)(\s*)$/);
              const leadingSpace = m ? m[1] : "";
              const coreText = m ? m[2] : sentence;
              const trailingSpace = m ? m[3] : "";

              if (!coreText) {
                return <span key={idx}>{sentence}</span>;
              }

              const clusterIdx = indexToClusterMap.get(idx) ?? 0;
              const isClusterAnchor = aiClusters[clusterIdx]?.[0] === idx;
              const isActiveCluster = clusterIdx === activeMatchIndex;

              return (
                <React.Fragment key={idx}>
                  {leadingSpace && <span>{leadingSpace}</span>}
                  <mark
                    data-highlight-active={isActiveCluster ? "true" : undefined}
                    data-cluster-index={clusterIdx}
                    ref={(el) => {
                      if (el && isClusterAnchor && highlightRefsMap) {
                        highlightRefsMap.current.set(clusterIdx, el);
                      }
                    }}
                    className={`font-medium px-0.5 py-0 rounded-none inline transition-colors ${
                      isActiveCluster
                        ? "bg-amber-400/60 dark:bg-amber-400/40 text-amber-950 dark:text-amber-100 ring-1 ring-amber-500/60 dark:ring-amber-400/50"
                        : "bg-amber-200/50 dark:bg-amber-500/20 text-amber-950 dark:text-amber-100"
                    }`}
                    title={`AI Grounded Evidence ${clusterIdx + 1} of ${aiClusters.length}`}
                  >
                    {coreText}
                  </mark>
                  {trailingSpace && <span>{trailingSpace}</span>}
                </React.Fragment>
              );
            }
            return <span key={idx}>{sentence}</span>;
          })}
        </>
      );

      return {
        nodes,
        matchCount: aiClusters.length,
        initialActiveIndex: 0
      };
    }
  }

  // 1. DIRECT CLAIM TEXT GROUNDING PATH (FALLBACK):
  // If AI quotes are not present or didn't match, find targetQuery directly in the document text.
  // This handles table cells where the LLM wrote descriptive content from the paper.
  // Uses n-gram sequence matching (language-agnostic, no hardcoded word lists).
  if (targetQuery && targetQuery.trim().length > 20) {
    const directHighlightedIndices = new Set<number>();
    const cleanTarget = targetQuery.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim().replace(/\s+/g, " ");
    const allTargetWords = cleanTarget.split(/\s+/).filter(w => w.length >= 2);

    if (allTargetWords.length >= 4) {
      // Try exact substring match first (very strict — requires full phrase containment)
      rawSentences.forEach((s, idx) => {
        if (/^#{1,6}\s+/i.test(s.trim())) return;
        const sClean = s.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim().replace(/\s+/g, " ");
        if (sClean.length >= 15 && (sClean.includes(cleanTarget) || cleanTarget.includes(sClean))) {
          directHighlightedIndices.add(idx);
        }
      });

      // If no exact substring match, use n-gram sequence matching (language-agnostic)
      // Extract 3-word and 4-word consecutive n-grams from the target text.
      // A sentence that contains many of these n-grams is very likely the source.
      if (directHighlightedIndices.size === 0) {
        const trigrams: string[] = [];
        const quadgrams: string[] = [];
        for (let i = 0; i <= allTargetWords.length - 3; i++) {
          trigrams.push(`${allTargetWords[i]} ${allTargetWords[i+1]} ${allTargetWords[i+2]}`);
          if (i <= allTargetWords.length - 4) {
            quadgrams.push(`${allTargetWords[i]} ${allTargetWords[i+1]} ${allTargetWords[i+2]} ${allTargetWords[i+3]}`);
          }
        }
        const allNgrams = [...quadgrams, ...trigrams];
        if (allNgrams.length === 0) {
          // Not enough words for n-grams — skip direct path
        } else {
          let bestIdx = -1;
          let bestScore = 0;

          rawSentences.forEach((s, idx) => {
            if (/^#{1,6}\s+/i.test(s.trim())) return;
            const sClean = s.toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim().replace(/\s+/g, " ");
            if (sClean.length < 15) return;

            let ngramHits = 0;
            allNgrams.forEach(ng => {
              if (sClean.includes(ng)) ngramHits++;
            });

            // Require at least 30% of n-grams found AND at least 2 n-gram hits
            const ngramRatio = ngramHits / allNgrams.length;
            if (ngramRatio >= 0.30 && ngramHits >= 2 && ngramHits > bestScore) {
              bestScore = ngramHits;
              bestIdx = idx;
            }
          });

          if (bestIdx !== -1) {
            directHighlightedIndices.add(bestIdx);
            // Also include immediately adjacent sentences if they share n-grams (multi-sentence cells)
            [bestIdx - 1, bestIdx + 1].forEach(adj => {
              if (adj >= 0 && adj < rawSentences.length) {
                const adjClean = rawSentences[adj].toLowerCase().replace(/[^a-zA-Z0-9\s]/g, " ").trim().replace(/\s+/g, " ");
                if (adjClean.length < 15 || /^#{1,6}\s+/i.test(rawSentences[adj].trim())) return;
                let adjHits = 0;
                allNgrams.forEach(ng => { if (adjClean.includes(ng)) adjHits++; });
                if (allNgrams.length > 0 && adjHits / allNgrams.length >= 0.20 && adjHits >= 2) {
                  directHighlightedIndices.add(adj);
                }
              }
            });
          }
        }
      }

      // If we found direct matches, render them immediately — no need for aiQuotes fallback
      if (directHighlightedIndices.size > 0) {
        const sortedIndices = Array.from(directHighlightedIndices).sort((a, b) => a - b);
        const directClusters: number[][] = [];
        let curClust: number[] = [];
        sortedIndices.forEach(idx => {
          if (curClust.length === 0) {
            curClust.push(idx);
          } else if (idx === curClust[curClust.length - 1] + 1) {
            curClust.push(idx);
          } else {
            directClusters.push([...curClust]);
            curClust = [idx];
          }
        });
        if (curClust.length > 0) directClusters.push(curClust);

        const indexToClusterMap = new Map<number, number>();
        directClusters.forEach((clust, cIdx) => {
          clust.forEach(idx => indexToClusterMap.set(idx, cIdx));
        });

        const nodes = (
          <>
            {rawSentences.map((sentence, idx) => {
              const isHighlighted = directHighlightedIndices.has(idx);
              if (isHighlighted) {
                const match = sentence.match(/^(\s*)([\s\S]*?)(\s*)$/);
                const leadingSpace = match ? match[1] : "";
                const coreText = match ? match[2] : sentence;
                const trailingSpace = match ? match[3] : "";
                if (!coreText) return <span key={idx}>{sentence}</span>;

                const clusterIdx = indexToClusterMap.get(idx) ?? 0;
                const isClusterAnchor = directClusters[clusterIdx]?.[0] === idx;
                const isActiveCluster = clusterIdx === activeMatchIndex;

                return (
                  <React.Fragment key={idx}>
                    {leadingSpace && <span>{leadingSpace}</span>}
                    <mark
                      data-highlight-active={isActiveCluster ? "true" : undefined}
                      data-cluster-index={clusterIdx}
                      ref={(el) => {
                        if (el && isClusterAnchor && highlightRefsMap) {
                          highlightRefsMap.current.set(clusterIdx, el);
                        }
                      }}
                      className={`font-medium px-0.5 py-0 rounded-none inline transition-colors ${
                        isActiveCluster
                          ? "bg-amber-400/60 dark:bg-amber-400/40 text-amber-950 dark:text-amber-100 ring-1 ring-amber-500/60 dark:ring-amber-400/50"
                          : "bg-amber-200/50 dark:bg-amber-500/20 text-amber-950 dark:text-amber-100"
                      }`}
                      title={`Direct Evidence ${clusterIdx + 1} of ${directClusters.length}`}
                    >
                      {coreText}
                    </mark>
                    {trailingSpace && <span>{trailingSpace}</span>}
                  </React.Fragment>
                );
              }
              return <span key={idx}>{sentence}</span>;
            })}
          </>
        );

        return {
          nodes,
          matchCount: directClusters.length,
          initialActiveIndex: 0
        };
      }
    }
  }

  return { nodes: <span>{fullText}</span>, matchCount: 0 };
}

export const formatReadableDate = (dateStr?: string, yearFallback?: string) => {
  if (!dateStr && !yearFallback) return "";
  if (!dateStr) return yearFallback || "";
  
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
  } catch {
    // fallback
  }
  return dateStr;
};

export interface FileBadge {
  label: string;
  bg: string;
}

export const getFileBadgeInfo = (filename: string, hasFullPdf?: boolean): FileBadge => {
  if (hasFullPdf || filename.toLowerCase().endsWith(".pdf")) {
    return { label: "PDF", bg: "bg-red-600/15 border-red-500/40 text-red-500" };
  }
  if (filename.startsWith("10.") || filename.startsWith("DOI:") || filename.includes("doi.org")) {
    return { label: "DOI", bg: "bg-blue-600/15 border-blue-500/40 text-blue-500" };
  }
  const ext = filename.split(".").pop()?.toLowerCase() || "doc";
  if (ext === "docx" || ext === "doc") {
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




