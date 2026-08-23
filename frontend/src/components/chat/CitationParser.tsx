"use client";

import React from "react";
import { Document as DocType } from "@/stores/documentStore";

export interface CitationContext {
  sentence: string;
  num: number;
  citationKey?: string;
  fullSourceText?: string;
  aiQuotes?: string[];
}

export function parseCitationsInReactNode(
  node: React.ReactNode, 
  documents?: DocType[], 
  onOpenDocument?: (doc: DocType, citationContext?: CitationContext) => void,
  activeCitationKey?: string | null,
  parentFullText?: string,
  citationMap?: Record<string, string[]>,
  elementPrefix: string = "node"
): React.ReactNode {
  if (typeof node === "string") {
    // Determine the full text available (use parent/container text if node is a partial string)
    const effectiveFullText = parentFullText || node;
    // Support standard bracket citations: [1], [2], [1, 2], [1]-[3], [Dokumen 1], [Document 1]
    // Also support fallback prefixes like [M-01], [T-01], [M-1], [T-1], [ref-1], [P-01], Dokumen [1], Dokumen 1:, Paper 1, Source 1, and isolated numbers in parenthesis like (1), (2)
    // Citation numbers correspond to document indices (1 to 500)
    const regex = /(?:\[(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*(\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*)\]|(?:Dokumen|Document|Paper|Source)\s*\[?(\d{1,3})\]?(?:\s*:|\b)|\bDokumen\s+(\d{1,3})\b|\((\d{1,3})\))/gi;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(node)) !== null) {
      const matchIndex = match.index;
      if (matchIndex > lastIndex) {
        parts.push(node.substring(lastIndex, matchIndex));
      }

      // Extract precise context sentence/cell text for grounding
      let contextSentence = "";

      if (effectiveFullText.includes("|")) {
        // Inside table: extract the specific cell or current row containing this citation
        const lines = effectiveFullText.split("\n");
        const matchingLine = lines.find(l => l.includes(match![0])) || effectiveFullText;
        contextSentence = matchingLine
          .split("|")
          .map(c => c.trim())
          .filter(c => c.length > 0 && !/^\d+$/.test(c))
          .join(" . ")
          .replace(/(?:\[(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*\]|(?:Dokumen|Document|Paper|Source)\s*\[?\d{1,3}\]?(?:\s*:|\b)|\bDokumen\s+\d{1,3}\b|\(\d{1,3}\))/gi, "")
          .trim();
      } else {
        // In natural text/paragraphs: find sentence boundaries
        const textBefore = node.substring(0, matchIndex);
        const textAfter = node.substring(regex.lastIndex);

        const lastSentenceEnd = Math.max(
          textBefore.lastIndexOf(". "),
          textBefore.lastIndexOf("! "),
          textBefore.lastIndexOf("? "),
          textBefore.lastIndexOf("\n\n"),
          textBefore.lastIndexOf(";\n")
        );
        const sentenceStart = lastSentenceEnd !== -1 ? lastSentenceEnd + 1 : 0;
        
        const nextSentenceEnd = Math.min(
          ...[
            textAfter.indexOf(". "),
            textAfter.indexOf("! "),
            textAfter.indexOf("? "),
            textAfter.indexOf("\n\n"),
            textAfter.indexOf(";\n")
          ].filter(x => x !== -1)
        );
        const sentenceEnd = nextSentenceEnd !== -1 ? regex.lastIndex + nextSentenceEnd + 1 : node.length;
        
        contextSentence = node
          .substring(sentenceStart, sentenceEnd)
          .replace(/(?:\[(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*\]|(?:Dokumen|Document|Paper|Source)\s*\[?\d{1,3}\]?(?:\s*:|\b)|\bDokumen\s+\d{1,3}\b|\(\d{1,3}\))/gi, "")
          .replace(/^[|\s*#_-]+|[|\s*#_-]+$/g, "")
          .trim();
      }

      const rawNumbers = match[1] || match[2] || match[3] || match[4] || "";
      const nums: number[] = [];
      if (rawNumbers.includes("-")) {
        const [startStr, endStr] = rawNumbers.split("-");
        const start = parseInt(startStr.trim(), 10);
        const end = parseInt(endStr.trim(), 10);
        if (!isNaN(start) && !isNaN(end) && start <= end && end - start <= 10) {
          for (let i = start; i <= end; i++) nums.push(i);
        } else if (!isNaN(start)) {
          nums.push(start);
        }
      } else {
        rawNumbers.split(",").forEach(nStr => {
          const n = parseInt(nStr.trim(), 10);
          if (!isNaN(n)) nums.push(n);
        });
      }

      if (nums.length > 0) {
        // Create context hash from cell/sentence text so each citation button has a globally unique key
        const sentenceSnippet = contextSentence
          ? contextSentence.slice(0, 20).replace(/[^a-zA-Z0-9]/g, "_").toLowerCase()
          : "ctx";

        parts.push(
          <span key={`cite-grp-${elementPrefix}-${matchIndex}-${sentenceSnippet}`} className="inline-flex items-center gap-0.5 mx-0.5 align-baseline">
            {nums.map((num, i) => {
              const doc = documents?.find(d => (d.index ? d.index === num : false)) || documents?.[num - 1];
              const docTitle = doc?.filename.replace(/\.pdf$/i, "") || `Referenced Source [${num}]`;
              const aiQuotesForDoc = citationMap?.[num.toString()] || citationMap?.[`[${num}]`];

              // Key includes elementPrefix & unique matchIndex to ensure ONLY the clicked citation turns amber/active
              const citeUniqueKey = `cite-${elementPrefix}-${num}-${matchIndex}-${i}`;
              const isSelected = activeCitationKey === citeUniqueKey;
              return (
                <button
                  key={citeUniqueKey}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (doc && onOpenDocument) {
                      onOpenDocument(doc, {
                        sentence: contextSentence,
                        num: num,
                        citationKey: citeUniqueKey,
                        aiQuotes: aiQuotesForDoc
                      });
                    }
                  }}
                  className={`inline-flex items-center justify-center w-6 h-5 text-[10px] font-mono font-bold rounded cursor-pointer transition-all duration-150 transform hover:scale-105 active:scale-95 select-text shadow-sm ${
                    isSelected
                      ? "bg-amber-400 text-black border border-amber-300 font-extrabold shadow-amber-400/20"
                      : "text-blue-300 hover:text-blue-100 bg-blue-500/15 hover:bg-blue-500/35 border border-blue-500/30 hover:border-blue-400/70"
                  }`}
                  title={`[${num}] ${docTitle}\nClick to view source and highlight AI-verified evidence`}
                >
                  <span className="sr-only">[</span>
                  <span>{num}</span>
                  <span className="sr-only">]</span>
                </button>
              );
            })}
          </span>
        );
      } else {
        parts.push(match[0]);
      }

      lastIndex = regex.lastIndex;
    }

    if (lastIndex < node.length) {
      parts.push(node.substring(lastIndex));
    }

    return parts.length === 1 ? parts[0] : parts;
  }

  if (Array.isArray(node)) {
    return node.map((child, idx) => (
      <React.Fragment key={idx}>{parseCitationsInReactNode(child, documents, onOpenDocument, activeCitationKey, parentFullText, citationMap, `${elementPrefix}-${idx}`)}</React.Fragment>
    ));
  }

  if (React.isValidElement(node) && (node.props as any)?.children) {
    return React.cloneElement(node as React.ReactElement<any>, {
      children: parseCitationsInReactNode((node.props as any).children, documents, onOpenDocument, activeCitationKey, parentFullText, citationMap, elementPrefix)
    });
  }

  return node;
}
