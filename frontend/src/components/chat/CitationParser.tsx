"use client";

import React from "react";
import { Document as DocType } from "@/app/ChatClient";

export interface CitationContext {
  sentence: string;
  num: number;
}

export function parseCitationsInReactNode(
  node: React.ReactNode, 
  documents?: DocType[], 
  onOpenDocument?: (doc: DocType, citationContext?: CitationContext) => void,
  activeCitationNum?: number | null
): React.ReactNode {
  if (typeof node === "string") {
    // Support standard bracket citations: [1], [2], [1, 2], [1]-[3], and parenthesis citations: (1), (2), (1, 2)
    const regex = /(?:\[|\()(\d+(?:\s*,\s*\d+|\s*-\s*\d+)*)(?:\]|\))/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(node)) !== null) {
      const matchIndex = match.index;
      if (matchIndex > lastIndex) {
        parts.push(node.substring(lastIndex, matchIndex));
      }

      // Extract the full sentence / clause context for grounding & auto-highlighting in paper panel
      const textBefore = node.substring(0, matchIndex);
      const textAfter = node.substring(regex.lastIndex);
      
      // Find sentence boundary before match (. ! ? \n)
      const lastSentenceEnd = Math.max(
        textBefore.lastIndexOf(". "),
        textBefore.lastIndexOf("! "),
        textBefore.lastIndexOf("? "),
        textBefore.lastIndexOf("\n")
      );
      const sentenceStart = lastSentenceEnd !== -1 ? lastSentenceEnd + 2 : 0;
      
      // Find sentence boundary after match
      const nextSentenceEnd = Math.min(
        ...[textAfter.indexOf(". "), textAfter.indexOf("! "), textAfter.indexOf("? "), textAfter.indexOf("\n")].filter(x => x !== -1)
      );
      const sentenceEnd = nextSentenceEnd !== -1 ? regex.lastIndex + nextSentenceEnd + 1 : node.length;
      
      const contextSentence = node.substring(sentenceStart, sentenceEnd).replace(/(?:\[|\()\d+(?:\s*,\s*\d+|\s*-\s*\d+)*(?:\]|\))/g, "").trim();

      const rawNumbers = match[1];
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
        parts.push(
          <span key={`cite-group-${matchIndex}`} className="inline-flex items-center gap-0.5 mx-0.5 align-baseline">
            {nums.map((num, i) => {
              const doc = documents?.find(d => (d.index ? d.index === num : false)) || documents?.[num - 1];
              const docTitle = doc?.filename.replace(/\.pdf$/i, "") || `Referenced Source [${num}]`;

              const isSelected = activeCitationNum === num;
              return (
                <button
                  key={`pill-${num}-${i}`}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (doc && onOpenDocument) {
                      onOpenDocument(doc, {
                        sentence: contextSentence,
                        num: num
                      });
                    }
                  }}
                  className={`inline-flex items-center justify-center w-6 h-5 text-[10px] font-mono font-bold rounded cursor-pointer transition-all duration-150 transform hover:scale-105 active:scale-95 select-text shadow-sm ${
                    isSelected
                      ? "bg-amber-400 text-black border border-amber-300 font-extrabold shadow-amber-400/20"
                      : "text-blue-300 hover:text-blue-100 bg-blue-500/15 hover:bg-blue-500/35 border border-blue-500/30 hover:border-blue-400/70"
                  }`}
                  title={`[${num}] ${docTitle}\nClick to view source and highlight referenced excerpt`}
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
      <React.Fragment key={idx}>{parseCitationsInReactNode(child, documents, onOpenDocument, activeCitationNum)}</React.Fragment>
    ));
  }

  if (React.isValidElement(node) && (node.props as any)?.children) {
    return React.cloneElement(node as React.ReactElement<any>, {
      children: parseCitationsInReactNode((node.props as any).children, documents, onOpenDocument, activeCitationNum)
    });
  }

  return node;
}
