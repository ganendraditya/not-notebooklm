"use client";

import React from "react";
import { Document as DocType } from "@/stores/documentStore";
import { Tooltip } from "@/components/ui/tooltip";

export interface CitationContext {
  sentence: string;
  num: number;
  citationKey?: string;
  fullSourceText?: string;
  aiQuotes?: string[];
}

export function isNegativeOrEmptyCitation(val: string): boolean {
  const clean = val.toLowerCase().replace(/[\(\)\[\]]/g, "").trim();
  return (
    !clean ||
    /^(tidak\s+(disebutkan|ada|eksplisit|tersedia)|belum\s+disebutkan|n\/?a|-|\s*)$/i.test(clean) ||
    clean.includes("tidak disebutkan") ||
    clean.includes("tidak terdapat")
  );
}

export function enhanceTableCitations(markdown: string): string {
  if (!markdown || !markdown.includes("|")) return markdown;

  const tagContent = (val: string, docNum: string): string => {
    if (!val.trim() || isNegativeOrEmptyCitation(val) || val.includes(`[${docNum}]`)) {
      return val;
    }
    if (/<br\s*\/?>/i.test(val)) {
      const parts = val.split(/(<br\s*\/?>)/i);
      return parts.map(p => {
        if (/^<br\s*\/?>$/i.test(p)) return p;
        if (p.trim() && !isNegativeOrEmptyCitation(p) && !p.includes(`[${docNum}]`)) {
          return tagContent(p, docNum);
        }
        return p;
      }).join("");
    }
    if (val.includes("•")) {
      const items = val.split("•");
      return items.map(it => {
        if (!it.trim()) return it;
        if (!isNegativeOrEmptyCitation(it) && !it.includes(`[${docNum}]`)) {
          return `${it.trimEnd()} [${docNum}] `;
        }
        return it;
      }).join("•").trimEnd();
    }
    return `${val.trimEnd()} [${docNum}]`;
  };

  const lines = markdown.split("\n");
  let inTable = false;
  let colDocMap: Record<number, string> = {};
  const resultLines: string[] = [];

  for (const line of lines) {
    const stripped = line.trim();
    if (stripped.startsWith("|") && stripped.endsWith("|")) {
      const cells = stripped.slice(1, -1).split("|").map(c => c.trim());
      if (!inTable) {
        inTable = true;
        colDocMap = {};
        cells.forEach((c, idx) => {
          const m = c.match(/\[(\d{1,3})\]/);
          if (m) colDocMap[idx] = m[1];
        });
        resultLines.push(line);
      } else if (cells.every(c => /^:?-+:?$/.test(c))) {
        resultLines.push(line);
      } else {
        if (Object.keys(colDocMap).length > 0) {
          const newCells = cells.map((c, idx) => {
            if (colDocMap[idx]) return tagContent(c, colDocMap[idx]);
            return c;
          });
          resultLines.push(`| ${newCells.join(" | ")} |`);
        } else {
          // Row-mapped document table: if leading cell identifies Document [X], ensure remaining cells have [X]
          const firstCell = cells[0] || "";
          const rowDocMatch = firstCell.match(/\[(\d{1,3})\]/);
          if (rowDocMatch && cells.length > 1) {
            const docNum = rowDocMatch[1];
            const newCells = [firstCell];
            for (let i = 1; i < cells.length; i++) {
              newCells.push(tagContent(cells[i], docNum));
            }
            resultLines.push(`| ${newCells.join(" | ")} |`);
          } else {
            resultLines.push(line);
          }
        }
      }
    } else {
      inTable = false;
      colDocMap = {};
      resultLines.push(line);
    }
  }
  return resultLines.join("\n");
}

function renderTextWithLineBreaks(text: string, keyPrefix: string): React.ReactNode {
  if (!/<br\s*\/?>/i.test(text)) {
    return text;
  }
  const segments = text.split(/<br\s*\/?>/gi);
  return segments.map((seg, sIdx) => (
    <React.Fragment key={`${keyPrefix}-br-${sIdx}`}>
      {sIdx > 0 && <br />}
      {seg}
    </React.Fragment>
  ));
}

export function parseCitationsInReactNode(
  node: React.ReactNode, 
  documents?: DocType[], 
  onOpenDocument?: (doc: DocType, citationContext?: CitationContext) => void,
  activeCitationKey?: string | null,
  parentFullText?: string,
  citationMap?: Record<string, string[]>,
  elementPrefix: string = "node",
  isDocColumn: boolean = false
): React.ReactNode {
  if (typeof node === "string") {
    // Track document numbers seen in this cell to deduplicate repeated badges in document columns
    const seenDocNumsInCell = new Set<number>();
    // Determine the full text available (use parent/container text if node is a partial string)
    const effectiveFullText = parentFullText || node;
    // Support standard and double bracket citations: [1], [[1]], [1]], [1, 2], [1]-[3], [Dokumen 1], [Document 1]
    // Also support fallback prefixes like [M-01], [T-01], [M-1], [T-1], [ref-1], [P-01], Dokumen [1], Dokumen 1:, Paper 1, Source 1, and isolated numbers in parenthesis like (1), (2)
    // Citation numbers correspond to document indices (1 to 500)
    const regex = /(?:\[{1,2}(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*(\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*)\s*\]{1,2}|(?:Dokumen|Document|Paper|Source)\s*(?:\[{1,2}(\d{1,3})\s*\]{1,2}|(\d{1,3})(?::|\b))|\((\d{1,3})\))/gi;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(node)) !== null) {
      const matchIndex = match.index;
      if (matchIndex > lastIndex) {
        parts.push(renderTextWithLineBreaks(node.substring(lastIndex, matchIndex), `${elementPrefix}-pre-${lastIndex}`));
      }

      // Extract precise context sentence/cell text for grounding
      let contextSentence = "";

      if (!node.includes("|") && node.length <= 300) {
        // node is already an isolated cell or local text segment: extract from node directly
        contextSentence = node
          .replace(/(?:\[{1,2}(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*\s*\]{1,2}|(?:Dokumen|Document|Paper|Source)\s*(?:\[{1,2}\d{1,3}\s*\]{1,2}|\d{1,3}(?::|\b))|\(\d{1,3}\))/gi, "")
          .replace(/<[^>]+>/g, " ")
          .replace(/^[|\s*#_:-]+|[|\s*#_:-]+$/g, "")
          .trim();
      } else if (effectiveFullText.includes("|")) {
        // Extract ONLY the specific cell text containing this match, NOT the entire multi-column row!
        const lines = effectiveFullText.split("\n");
        const matchingLine = lines.find(l => l.includes(match![0])) || effectiveFullText;
        const matchingCell = matchingLine
          .split("|")
          .map(c => c.trim())
          .find(c => c.includes(match![0])) || "";
        contextSentence = matchingCell
          .replace(/(?:\[{1,2}(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*\s*\]{1,2}|(?:Dokumen|Document|Paper|Source)\s*(?:\[{1,2}\d{1,3}\s*\]{1,2}|\d{1,3}(?::|\b))|\(\d{1,3}\))/gi, "")
          .replace(/<[^>]+>/g, " ")
          .replace(/^[|\s*#_:-]+|[|\s*#_:-]+$/g, "")
          .trim();
      } else {
        // In individual cell or natural text/paragraphs: find sentence boundaries using effectiveFullText
        const searchBase = effectiveFullText;
        let baseIndex = searchBase.indexOf(node);
        if (baseIndex === -1) {
          baseIndex = 0;
        }
        const actualMatchIndex = baseIndex + matchIndex;
        const textBefore = searchBase.substring(0, actualMatchIndex);
        const textAfter = searchBase.substring(actualMatchIndex + match[0].length);

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
        const sentenceEnd = nextSentenceEnd !== -1 ? actualMatchIndex + match[0].length + nextSentenceEnd + 1 : searchBase.length;
        
        contextSentence = searchBase
          .substring(sentenceStart, sentenceEnd)
          .replace(/(?:\[{1,2}(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*\s*\]{1,2}|(?:Dokumen|Document|Paper|Source)\s*(?:\[{1,2}\d{1,3}\s*\]{1,2}|\d{1,3}(?::|\b))|\(\d{1,3}\))/gi, "")
          .replace(/<[^>]+>/g, " ")
          .replace(/^[|\s*#_:-]+|[|\s*#_:-]+$/g, "")
          .trim();
      }

      // Fallback: If contextSentence is still too short or empty, fallback to effectiveFullText
      if (!contextSentence || contextSentence.length < 3) {
        contextSentence = effectiveFullText
          .replace(/(?:\[{1,2}(?:Dokumen|Document|Doc|Paper|M-|T-|P-|ref-)?\s*\d{1,3}(?:\s*,\s*\d{1,3}|\s*-\s*\d{1,3})*\s*\]{1,2}|(?:Dokumen|Document|Paper|Source)\s*(?:\[{1,2}\d{1,3}\s*\]{1,2}|\d{1,3}(?::|\b))|\(\d{1,3}\))/gi, "")
          .replace(/<[^>]+>/g, " ")
          .replace(/^[|\s*#_:-]+|[|\s*#_:-]+$/g, "")
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

      // In Document/Identity column (Col 0), deduplicate: only render the FIRST button for each document number!
      let effectiveNums = nums;
      if (isDocColumn) {
        effectiveNums = nums.filter(n => !seenDocNumsInCell.has(n));
        effectiveNums.forEach(n => seenDocNumsInCell.add(n));
        if (effectiveNums.length === 0) {
          // Skip redundant trailing duplicate in document identity cell
          lastIndex = regex.lastIndex;
          continue;
        }
      }

      if (effectiveNums.length > 0) {
        // Create context hash from cell/sentence text so each citation button has a globally unique key
        const sentenceSnippet = contextSentence
          ? contextSentence.slice(0, 20).replace(/[^a-zA-Z0-9]/g, "_").toLowerCase()
          : "ctx";

        parts.push(
          <span key={`cite-grp-${elementPrefix}-${matchIndex}-${sentenceSnippet}`} className="inline-flex items-center gap-0.5 mx-0.5 align-baseline not-italic font-normal">
            {effectiveNums.map((num, i) => {
              const doc = documents?.find(d => (d.index ? d.index === num : false)) || documents?.[num - 1];
              const docTitle = doc?.title || doc?.filename.replace(/\.pdf$/i, "") || `Referenced Source [${num}]`;
              const aiQuotesForDoc = citationMap?.[num.toString()] || citationMap?.[`[${num}]`];

              // Key includes elementPrefix, sentenceSnippet, num, matchIndex & i to ensure ONLY the clicked citation turns amber/active
              const citeUniqueKey = `cite-${elementPrefix}-${sentenceSnippet}-${num}-${matchIndex}-${i}`;
              const isSelected = Boolean(activeCitationKey && activeCitationKey === citeUniqueKey);

              const tooltipContent = (
                <div className="flex flex-col gap-1 text-left max-w-[280px] not-italic select-none">
                  <div className="text-[11.5px] font-semibold text-white leading-snug line-clamp-2">
                    <span className="text-blue-400 font-mono font-bold mr-1 inline-block">[{num}]</span>
                    <span>{docTitle}</span>
                  </div>
                  <div className="text-[10px] text-neutral-400 font-normal leading-tight">
                    {isDocColumn 
                      ? "Click to open and read document"
                      : "Click to view source and highlight AI-verified evidence"}
                  </div>
                </div>
              );

              return (
                <Tooltip
                  key={citeUniqueKey}
                  content={tooltipContent}
                  side="top"
                  sideOffset={6}
                  className="p-2 whitespace-normal"
                >
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (doc && onOpenDocument) {
                        if (isDocColumn) {
                          // In Document Identity column: open document cleanly with zero highlights
                          onOpenDocument(doc, undefined);
                        } else {
                          onOpenDocument(doc, {
                            sentence: contextSentence,
                            num: num,
                            citationKey: citeUniqueKey,
                            aiQuotes: aiQuotesForDoc
                          });
                        }
                      }
                    }}
                    className={`inline-flex items-center justify-center min-w-6 px-1 h-5 text-[10px] font-mono font-bold not-italic normal-case tracking-normal rounded cursor-pointer transition-all duration-150 transform hover:scale-105 active:scale-95 select-none shadow-sm ${
                      isSelected
                        ? "bg-amber-400 text-black border border-amber-300 font-extrabold shadow-amber-400/20"
                        : "text-blue-300 hover:text-blue-100 bg-blue-500/15 hover:bg-blue-500/35 border border-blue-500/30 hover:border-blue-400/70"
                    }`}
                    aria-label={`Source [${num}]: ${docTitle}`}
                  >
                    <span className="sr-only">[</span>
                    <span className="not-italic inline-block leading-none">{num}</span>
                    <span className="sr-only">]</span>
                  </button>
                </Tooltip>
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
      parts.push(renderTextWithLineBreaks(node.substring(lastIndex), `${elementPrefix}-post-${lastIndex}`));
    }

    if (parts.length === 0) {
      return renderTextWithLineBreaks(node, `${elementPrefix}-plain`);
    }

    return parts.length === 1 ? parts[0] : parts;
  }

  if (Array.isArray(node)) {
    return node.map((child, idx) => (
      <React.Fragment key={idx}>{parseCitationsInReactNode(child, documents, onOpenDocument, activeCitationKey, parentFullText, citationMap, `${elementPrefix}-${idx}`, isDocColumn)}</React.Fragment>
    ));
  }

  if (React.isValidElement(node)) {
    // If it's a KaTeX math element, do not traverse into its internal MathML/HTML spans
    const className = (node.props as any)?.className;
    if (typeof className === "string" && className.includes("katex")) {
      return node;
    }

    const children = (node.props as any)?.children;
    if (children !== undefined && children !== null) {
      const parsedChildren = parseCitationsInReactNode(
        children,
        documents,
        onOpenDocument,
        activeCitationKey,
        parentFullText,
        citationMap,
        elementPrefix,
        isDocColumn
      );

      // Check if parsedChildren actually contains an interactive citation button
      const hasCitation = (n: React.ReactNode): boolean => {
        if (!n) return false;
        if (Array.isArray(n)) return n.some(hasCitation);
        if (React.isValidElement(n)) {
          if (typeof n.key === "string" && (n.key.startsWith("cite-grp-") || n.key.startsWith("cite-"))) return true;
          if ((n.props as any)?.["aria-label"]?.startsWith?.("Source [")) return true;
          return hasCitation((n.props as any)?.children);
        }
        return false;
      };

      // If this is an <a> tag AND it contains citation button(s), unwrap it to prevent invalid <a target="_blank"><button>
      if (typeof node.type === "string" && node.type.toLowerCase() === "a" && hasCitation(parsedChildren)) {
        return parsedChildren;
      }

      return React.cloneElement(node as React.ReactElement<any>, {
        children: parsedChildren
      });
    }
  }

  return node;
}
