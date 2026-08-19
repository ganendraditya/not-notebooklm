"use client";

import React from "react";
import { Document as DocType } from "@/app/ChatClient";

export function parseCitationsInReactNode(
  node: React.ReactNode, 
  documents?: DocType[], 
  onOpenDocument?: (doc: DocType) => void
): React.ReactNode {
  if (typeof node === "string") {
    const regex = /\[(\d+(?:\s*,\s*\d+|\s*-\s*\d+)*)\]/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(node)) !== null) {
      const matchIndex = match.index;
      if (matchIndex > lastIndex) {
        parts.push(node.substring(lastIndex, matchIndex));
      }

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

              return (
                <button
                  key={`pill-${num}-${i}`}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (doc && onOpenDocument) {
                      onOpenDocument(doc);
                    }
                  }}
                  className="inline-flex items-center justify-center px-1.5 py-0 min-w-[20px] h-[19px] text-[10.5px] font-mono font-bold text-blue-300 hover:text-blue-100 bg-blue-500/15 hover:bg-blue-500/35 border border-blue-500/30 hover:border-blue-400/70 rounded-full cursor-pointer transition-all duration-150 transform hover:scale-110 active:scale-95 select-none shadow-sm"
                  title={`[${num}] ${docTitle}\nClick to open paper details in panel`}
                >
                  {num}
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
      <React.Fragment key={idx}>{parseCitationsInReactNode(child, documents, onOpenDocument)}</React.Fragment>
    ));
  }

  if (React.isValidElement(node) && (node.props as any)?.children) {
    return React.cloneElement(node as React.ReactElement<any>, {
      children: parseCitationsInReactNode((node.props as any).children, documents, onOpenDocument)
    });
  }

  return node;
}
