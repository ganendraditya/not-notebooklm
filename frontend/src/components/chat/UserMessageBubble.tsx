"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface UserMessageBubbleProps {
  content: string;
  maxCollapsedHeight?: number;
}

export function UserMessageBubble({ 
  content, 
  maxCollapsedHeight = 180 
}: UserMessageBubbleProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [canExpand, setCanExpand] = useState(false);
  const textRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (textRef.current) {
      // If content height exceeds threshold by at least 25px, enable collapsible controls
      const scrollH = textRef.current.scrollHeight;
      setCanExpand(scrollH > maxCollapsedHeight + 20);
    }
  }, [content, maxCollapsedHeight]);

  return (
    <div className="relative group/bubble flex flex-col items-end w-full">
      <div
        onClick={() => {
          if (canExpand && !isExpanded) {
            setIsExpanded(true);
          }
        }}
        className={`bg-app-user-bubble text-app-text px-4 py-2.5 rounded-2xl rounded-tr-sm text-[15px] leading-relaxed shadow-sm border border-app-border transition-all duration-200 relative overflow-hidden break-words [word-break:break-word] whitespace-pre-wrap flex flex-col ${
          canExpand && !isExpanded ? "cursor-pointer hover:border-app-border-strong" : ""
        }`}
        style={{
          maxHeight: !isExpanded && canExpand ? `${maxCollapsedHeight}px` : undefined,
        }}
      >
        <div ref={textRef} className={canExpand && !isExpanded ? "pb-6" : ""}>
          {content}
        </div>

        {/* Gradient fade overlay with embedded toggle button when collapsed */}
        {canExpand && !isExpanded && (
          <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-[var(--color-app-user-bubble)] via-[var(--color-app-user-bubble)]/90 to-transparent flex items-end justify-end px-3 pb-1.5 pointer-events-auto">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(true);
              }}
              className="inline-flex items-center gap-1 text-[12px] font-medium text-app-text-muted hover:text-app-text transition-colors cursor-pointer bg-app-user-bubble hover:bg-app-item-hover px-2.5 py-1 rounded-full border border-app-border shadow-xs"
            >
              <span>Show more</span>
              <ChevronDown size={13} />
            </button>
          </div>
        )}

        {/* Show less button inside bubble when expanded (no border line, exact matching styling) */}
        {canExpand && isExpanded && (
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(false);
              }}
              className="inline-flex items-center gap-1 text-[12px] font-medium text-app-text-muted hover:text-app-text transition-colors cursor-pointer bg-app-user-bubble hover:bg-app-item-hover px-2.5 py-1 rounded-full border border-app-border shadow-xs"
            >
              <span>Show less</span>
              <ChevronUp size={13} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

