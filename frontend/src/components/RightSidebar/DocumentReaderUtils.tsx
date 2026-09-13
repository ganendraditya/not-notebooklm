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
  // If Gemini provided exact verbatim quote(s) via CITATION_MAP, match against them directly!
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
      // If one or more quotes are relevant to the clicked cell, include them
      if (maxScore > 0) {
        selectedQuotes = scoredQuotes.filter(sq => sq.score >= maxScore * 0.6).map(sq => sq.quote);
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
        // Skip title and section headings in matches
        if (/^#{1,6}\s+/i.test(s.trim())) return;
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
          // Never highlight headings or titles on quote matching
          if (/^#{1,6}\s+/i.test(s.trim())) return;
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
              const match = sentence.match(/^(\s*)([\s\S]*?)(\s*)$/);
              const leadingSpace = match ? match[1] : "";
              const coreText = match ? match[2] : sentence;
              const trailingSpace = match ? match[3] : "";

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

  // 2. FALLBACK CONTEXTUAL SEMANTIC GROUNDING PATH:
  // Identify if query contains explicit metrics, ratios, or evaluation terms
  const hasMetricOrData = Boolean(
    targetQuery && (
      /\d+(?:[,.]\d+)?%?|\b\d+:\d+\b|\bakurasi\b|\bmetode\b|\bhasil\b|\bdataset\b|\bsensitivitas\b|\bspesifisitas\b|\bpresisi\b|\brecall\b/i.test(targetQuery)
    )
  );

  // Guard against conversational fluff / empty queries unless numerical/metric data is present
  const isGenericCitationQuery = !targetQuery || (
    targetQuery.trim().length < 3 && !hasMetricOrData
  ) || (
    /^(?:berdasarkan|dokumen|referensi|sumber|menurut|daftar\s+pustaka|sitasi\s+rujukan|paper|jurnal|artikel|kesimpulan|rincian)\b/i.test(targetQuery.trim()) &&
    !hasMetricOrData
  ) || (
    /^\s*(?:santoso|rahma|et\s+al|dr\.|prof\.)/i.test(targetQuery.trim()) && targetQuery.length < 80
  );

  if (isGenericCitationQuery) {
    return { nodes: <span>{fullText}</span>, matchCount: 0 };
  }

  // Identify sections and bibliography in the document to contextualize grounding
  type SectionCategory = "RELATED_WORK" | "METHODOLOGY" | "RESULTS" | "LIMITATIONS" | "FUTURE_WORK" | "CONCLUSION" | "REFERENCES" | "GENERAL";
  let activeSection: SectionCategory = "GENERAL";
  const sentenceSections: SectionCategory[] = [];
  let refSectionIndex = -1;

  for (let i = 0; i < rawSentences.length; i++) {
    const sTrim = rawSentences[i].trim();
    if (/^(?:#{1,6}\s+|\*{0,2}(?:[IVX\d]+[\.\s]+|[A-Z\s]{4,}:|\d+\.)\s*)([A-Z\s]{3,})/i.test(sTrim)) {
      const sLower = sTrim.toLowerCase();
      if (/reference|daftar\s+pustaka|bibliography/i.test(sLower)) {
        activeSection = "REFERENCES";
        if (refSectionIndex === -1) refSectionIndex = i;
      } else if (/future|saran|rekomendasi|future\s+direction|pengembangan\s+selanjutnya/i.test(sLower)) {
        activeSection = "FUTURE_WORK";
      } else if (/limitation|limitasi|keterbatasan|kelemahan/i.test(sLower)) {
        activeSection = "LIMITATIONS";
      } else if (/conclusion|kesimpulan/i.test(sLower)) {
        activeSection = "CONCLUSION";
      } else if (/result|hasil|evaluasi|evaluation|performance|pembahasan|finding/i.test(sLower)) {
        activeSection = "RESULTS";
      } else if (/method|metodologi|metode|proposed|arsitektur|framework|system\s+design/i.test(sLower)) {
        activeSection = "METHODOLOGY";
      } else if (/related\s+work|literature|tinjauan\s+pustaka|penelitian\s+terkait/i.test(sLower)) {
        activeSection = "RELATED_WORK";
      }
    }
    sentenceSections.push(activeSection);
  }

  // Common stopwords in Indonesian and English
  const stopWords = new Set([
    "yang", "dari", "pada", "untuk", "dengan", "adalah", "dalam", "ini", "itu", "dan", "atau", "oleh", "ke", "di",
    "the", "and", "for", "with", "this", "that", "from", "using", "paper", "berikut", "tabel", "rekapitulasi",
    "dokumen", "terdapat", "adanya", "sebagai", "juga", "dapat", "akan", "telah", "namun", "serta", "karena",
    "bisa", "lebih", "secara", "seperti", "yaitu", "yakni", "merupakan", "berdasarkan", "parameter", "metode",
    "hasil", "nilai", "sebesar", "ketika", "menggunakan"
  ]);

  // Normalize query & strip LaTeX delimiters ($C=10$, \gamma=1 -> c=10, gamma=1) and diacritics
  const normQuery = (targetQuery || "")
    .toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/\$([^$]+)\$/g, "$1")
    .replace(/\\(?:gamma|alpha|beta|sigma|lambda|theta)\b/gi, (m) => m.substring(1));
  
  // Extract explicit numerical metrics with decimals or %: e.g. "69,15%", "84.37%", "0.87", "77%"
  const rawMetricMatches = (normQuery.match(/\b\d+[,.]\d+%?|\b\d+%/g) || []);
  const metricsSet = new Set(
    rawMetricMatches.map(m => m.toLowerCase().replace(/,/g, ".").replace(/%/g, ""))
  );

  // Extract split ratios: e.g. "90:10", "80:20", "60:40"
  const ratioMatches = (normQuery.match(/\b\d+\s*:\s*\d+\b/g) || []).map(r => r.replace(/\s+/g, ""));

  // Extract explicit integer numbers >= 3 digits (e.g. 1500 from "1.500" or 900), excluding 4-digit publication years (1900-2099)
  const rawNumberMatches = (normQuery.match(/\b\d+(?:[.,]\d+)?\b/g) || [])
    .map(n => n.replace(/[.,]/g, ""))
    .filter(n => n.length >= 3 && !metricsSet.has(n) && !/^(?:19|20)\d{2}$/.test(n));
  const numberSet = new Set(rawNumberMatches);

  // Extract parameter bindings: e.g. "c=10", "gamma=1", "k=5", "fold=10"
  const paramBindings = (normQuery.match(/\b[a-z_]+\s*=\s*\d+(?:[,.]\d+)?\b/g) || []).map(p => p.replace(/\s+/g, ""));

  // Extract model/algorithm/parameter specific terms: e.g. "svm", "rbf", "gamma", "tfidf", "kernel", "logistic", "naive"
  const cleanTokens = normQuery
    .replace(/[^a-zA-Z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(w => w.length >= 2 && !stopWords.has(w) && !/^\d+$/.test(w));

  // Extract explicit benchmark dataset or model entities: e.g. "dada-2000", "yolov8", "resnet-50", "imagenet-1k", "swin-t"
  const datasetModelMatches = (normQuery.match(/\b[a-z]{2,}[-_]?\d+[a-z\d]*\b/gi) || [])
    .map(e => e.toLowerCase());

  // Academic bilingual cognate synonym mapping (Indonesian <-> English)
  const COGNATE_SYNONYMS: Record<string, string[]> = {
    inkonsistensi: ["inconsist", "inconsistency", "inconsistent"],
    inkonsisten: ["inconsist", "inconsistent"],
    anotasi: ["annotat", "annotation", "label"],
    label: ["label", "annotation", "annotat"],
    cuplikan: ["video", "clip", "footage", "frame", "game"],
    game: ["game", "video game"],
    bahaya: ["risk", "danger", "hazard", "incident", "accident", "near-miss"],
    kecelakaan: ["accident", "crash", "collision", "incident", "near-miss"],
    klasifikasi: ["classif", "classification"],
    segmentasi: ["segment", "segmentation"],
    deteksi: ["detect", "detection"],
    evaluasi: ["evaluat", "evaluation"],
    kuantitatif: ["quantitat"],
    kualitatif: ["qualitat"],
    komparasi: ["compar"],
    distribusi: ["distribut"],
    akurasi: ["accura", "accuracy"],
    presisi: ["precis", "precision"],
    arsitektur: ["architect", "architecture"],
    metodologi: ["method", "methodology"],
    metode: ["method"],
    sintetis: ["synth", "synthetic"],
    translasi: ["translat", "translation"],
    modifikasi: ["modif", "modification"],
    oklusi: ["occlu", "occlusion"],
    trajektori: ["traject", "trajectory"],
  };

  // Extract keyphrases (2-word & 3-word n-grams)
  const queryPhrases: string[] = [];
  for (let i = 0; i < cleanTokens.length - 1; i++) {
    queryPhrases.push(`${cleanTokens[i]} ${cleanTokens[i + 1]}`);
    if (i < cleanTokens.length - 2) {
      queryPhrases.push(`${cleanTokens[i]} ${cleanTokens[i + 1]} ${cleanTokens[i + 2]}`);
    }
  }

  // Detect intent category of the query to align with corresponding paper sections
  let queryIntent: SectionCategory = "GENERAL";
  if (/(?:rekomendasi|future|saran|pengembangan|arah|ke depan|eksplorasi|penambahan|perluasan|integrasi\s+variabel|potensi)/i.test(normQuery)) {
    queryIntent = "FUTURE_WORK";
  } else if (/(?:limitasi|kelemahan|keterbatasan|kendala|belum|anjlok|turun\s+drastis|minim|rentan|terbatas|kekurangan|inkonsistensi|salah\s+kelas|salah\s+label)/i.test(normQuery)) {
    queryIntent = "LIMITATIONS";
  } else if (/(?:akurasi|map|presisi|recall|f1|mse|temuan|kinerja|hasil|persentase|berhasil)/i.test(normQuery)) {
    queryIntent = "RESULTS";
  } else if (/(?:metode|pendekatan|arsitektur|algoritma|model|dcnn|yolo|kalman|classifier|haar|pbas)/i.test(normQuery)) {
    queryIntent = "METHODOLOGY";
  }

  // Calculate scores for each sentence with semantic entity weighting
  let maxSingleScore = 0;
  let bestSentenceIdx = -1;
  const sentenceScores = rawSentences.map((s, idx) => {
    if (refSectionIndex !== -1 && idx >= refSectionIndex) {
      return 0;
    }

    const sec = sentenceSections[idx] || "GENERAL";
    if (sec === "REFERENCES") {
      return 0;
    }

    const sTrim = s.trim();
    const sLower = s.toLowerCase();
    
    // Ignore bibliography, page numbers, journal header lines, URL lines, and short metadata fragments
    if (/https?:\/\/|doi\.org|\bvol(?:ume)?\s*\d+|\bp-issn\b|\be-issn\b|\bissn\b|\bhalaman\b|\bavailable online\b|\.ac\.id|\.org\/index/i.test(sLower)) {
      return 0;
    }
    // Skip markdown headings (e.g. # Document Title, ## Section Header), author blocks, and short fragments
    if (/^#{1,6}\s+/i.test(sTrim)) {
      return 0;
    }
    if (idx < 15 && (/^Billy Gunawan|Universitas|Fakultas Teknik|Nanawi|@gmail|@informatics/i.test(sTrim))) {
      return 0;
    }
    if (sTrim.length < 10) {
      return 0;
    }

    const sNormalizedDiacritics = sLower.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const sNormalizedNumbers = sNormalizedDiacritics
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

    // 2. Exact Decimal/Percentage/Value Metric match
    // Matches "0,87", "0.87", "87%", "87", "0,88", "0.88", "77.78"
    metricsSet.forEach(m => {
      const mComma = m.replace(/\./g, ",");
      const isDecimalMatch = sNormalizedNumbers.includes(m) || sLower.includes(mComma);
      if (isDecimalMatch) {
        score += 40;
      } else if (m.startsWith("0.")) {
        // Convert decimal to percentage or integer representation: e.g. 0.87 -> 87% / 87
        const pctInt = `${Math.round(parseFloat(m) * 100)}`;
        if (sNormalizedNumbers.includes(`${pctInt}%`) || sClean.includes(pctInt)) {
          score += 40;
        }
      } else if (/^\d+$/.test(m) && parseInt(m, 10) > 10) {
        // Integer percentage representation: e.g. 87 -> 0.87 or 87%
        const decVal = (parseInt(m, 10) / 100).toFixed(2);
        if (sNormalizedNumbers.includes(decVal) || sLower.includes(decVal.replace(/\./g, ","))) {
          score += 40;
        }
      }
    });

    // 3. Split ratio match (e.g. "90:10" matching "90:10" or "90% data latih dan 10% data uji") (Weight: 30 points)
    ratioMatches.forEach(r => {
      const parts = r.split(":");
      if (sLower.includes(r) || (parts.length === 2 && sNormalizedNumbers.includes(parts[0]) && sNormalizedNumbers.includes(parts[1]))) {
        score += 30;
      }
    });

    // 4. Integer count match (e.g. 1500 or 900) (Weight: 35 points)
    numberSet.forEach(n => {
      const nWithDot = n.length === 4 ? `${n[0]}.${n.slice(1)}` : n;
      if (sClean.includes(n) || sLower.includes(nWithDot)) {
        score += 35;
      }
    });

    // 5. Specific keyphrase n-grams (e.g. "akurasi tertinggi", "model terbaik", "kata positif", "sentimen netral")
    queryPhrases.forEach(ph => {
      if (sClean.includes(ph)) {
        score += 20;
      }
    });

    // 6. Benchmark Dataset or Named Model entities match (Weight: 40 points)
    datasetModelMatches.forEach(entity => {
      const normEntity = entity.replace(/[-_]/g, " ");
      if (sLower.includes(entity) || sClean.includes(entity) || sClean.includes(normEntity)) {
        score += 40;
      }
    });

    // 7. Academic bilingual cognate synonym match (Indonesian <-> English) (Weight: 15 points each)
    Object.entries(COGNATE_SYNONYMS).forEach(([indoKey, engTargets]) => {
      if (normQuery.includes(indoKey)) {
        for (const target of engTargets) {
          if (sClean.includes(target) || sLower.includes(target)) {
            score += 15;
            break;
          }
        }
      }
    });

    // 8. Domain Entity / Model / Sentiment keywords (Weight: 6 points)
    cleanTokens.forEach(w => {
      if (sWords.has(w) || sClean.includes(w)) {
        score += 6;
      }
    });

    // 9. Section Intent Alignment: Prioritize sections matching the claim's semantic purpose
    // (e.g., prevent recommendations from grounding on past papers in "Related Work")
    if (score > 0) {
      if (queryIntent === "FUTURE_WORK") {
        if (sec === "RELATED_WORK") return 0; // Strictly prohibit literature review for future work!
        if (sec === "FUTURE_WORK") score += 60;
        else if (sec === "CONCLUSION") score += 25;
        else if (sec === "METHODOLOGY") score = Math.max(0, score - 30);
      } else if (queryIntent === "LIMITATIONS") {
        if (sec === "RELATED_WORK") return 0; // Strictly prohibit literature review for limitations!
        if (sec === "LIMITATIONS") score += 60;
        else if (sec === "CONCLUSION") score += 20;
      } else if (queryIntent === "RESULTS") {
        if (sec === "RESULTS") score += 40;
        else if (sec === "RELATED_WORK") score = Math.max(0, score - 30);
      } else if (queryIntent === "METHODOLOGY") {
        if (sec === "METHODOLOGY") score += 35;
        else if (sec === "RELATED_WORK") score = Math.max(0, score - 20);
      }
    }

    if (score > maxSingleScore) {
      maxSingleScore = score;
      bestSentenceIdx = idx;
    }

    return score;
  });

  // Dynamic Focused Evidence Selection (NotebookLM Style):
  const highlightedIndices = new Set<number>();
  const clusters: number[][] = [];

  const hasHardEvidence = hasMetricOrData || metricsSet.size > 0 || ratioMatches.length > 0 || numberSet.size > 0 || paramBindings.length > 0 || datasetModelMatches.length > 0;
  const minRequiredScore = hasHardEvidence ? 20 : 40;

  if (maxSingleScore >= minRequiredScore) {
    // Selectivity threshold: Keep top evidence sentences matching query claims
    // (must be within 70% of maxSingleScore to retain valid secondary evidence clusters for 1/2, 1/3 navigation)
    const threshold = Math.max(minRequiredScore, maxSingleScore * 0.70);
    
    // Pick candidate sentences meeting threshold
    const candidateIndices: number[] = [];
    sentenceScores.forEach((sc, idx) => {
      if (sc >= threshold) {
        candidateIndices.push(idx);
      }
    });

    // Group candidates into initial clusters
    const initialClusters: number[][] = [];
    let curClust: number[] = [];
    candidateIndices.forEach(idx => {
      if (curClust.length === 0) {
        curClust.push(idx);
      } else if (idx === curClust[curClust.length - 1] + 1) {
        curClust.push(idx);
      } else {
        initialClusters.push(curClust);
        curClust = [idx];
      }
    });
    if (curClust.length > 0) {
      initialClusters.push(curClust);
    }

    // Rank clusters by peak sentence score
    initialClusters.sort((a, b) => {
      const maxA = Math.max(...a.map(i => sentenceScores[i] || 0));
      const maxB = Math.max(...b.map(i => sentenceScores[i] || 0));
      return maxB - maxA;
    });

    // Keep up to the top 3 highest-scoring qualified clusters (e.g. Abstract, Methodology, Results)
    // to enable interactive arrow navigation (1/2, 1/3) while preventing fragmented low-confidence scatter
    const peakScore = Math.max(...(initialClusters[0]?.map(i => sentenceScores[i] || 0) || [0]));
    const qualifiedClusters = initialClusters.filter(clust => {
      const clustPeak = Math.max(...clust.map(i => sentenceScores[i] || 0));
      return clustPeak >= Math.max(minRequiredScore, peakScore * 0.70);
    });
    const topClusters = (qualifiedClusters.length > 0 ? qualifiedClusters : initialClusters).slice(0, 3);
    topClusters.forEach(clust => {
      clust.forEach(idx => highlightedIndices.add(idx));
    });
  }

  // Fallback: If no match above threshold, highlight best matching sentence ONLY if it scored >= minRequiredScore (strict significance)
  if (highlightedIndices.size === 0 && bestSentenceIdx !== -1 && maxSingleScore >= minRequiredScore) {
    highlightedIndices.add(bestSentenceIdx);
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
          const match = sentence.match(/^(\s*)([\s\S]*?)(\s*)$/);
          const leadingSpace = match ? match[1] : "";
          const coreText = match ? match[2] : sentence;
          const trailingSpace = match ? match[3] : "";

          if (!coreText) {
            return <span key={idx}>{sentence}</span>;
          }

          const clusterIdx = indexToClusterMap.get(idx) ?? 0;
          const isClusterAnchor = clusters[clusterIdx]?.[0] === idx;
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
                title={`Evidence Match ${clusterIdx + 1} of ${clusters.length}`}
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

  // Find which cluster contains the highest scoring evidence sentence
  let bestClusterIndex = 0;
  clusters.forEach((clust, cIdx) => {
    if (clust.includes(bestSentenceIdx)) {
      bestClusterIndex = cIdx;
    }
  });

  return {
    nodes,
    matchCount: clusters.length,
    initialActiveIndex: bestClusterIndex
  };
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

export const getFileBadgeInfo = (filename: string): FileBadge => {
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




