"use client";

import React, { useState, useRef, useEffect, memo } from "react";
import { 
  ArrowUp, 
  ArrowRight,
  FileText, 
  Pencil,
  Square,
  X,
  Trash2,
  SlidersHorizontal
} from "lucide-react";
import { TargetedSource } from "@/app/ChatClient";
import ModelSelector from "@/components/ModelSelector";
import SearchFilterPopover, { SearchFilterState, DEFAULT_SEARCH_FILTER } from "@/components/SearchFilterPopover";

export interface ChatInputBoxProps {
  isCentered?: boolean;
  isLoading?: boolean;
  documentsCount: number;
  onToggleRightSidebar?: () => void;
  onSubmit: (text: string) => void;
  onStopGeneration?: () => void;
  queuedPrompts?: string[];
  onRemoveQueuedPrompt?: (index: number) => void;
  onPromoteQueuedPrompt?: (index: number) => void;
  backendUrl: string;
  targetedSource?: TargetedSource | null;
  onClearTargetedSource?: () => void;
}

export const ChatInputBox = memo(function ChatInputBox({
  isCentered = false,
  isLoading = false,
  documentsCount,
  onToggleRightSidebar,
  onSubmit,
  onStopGeneration,
  queuedPrompts = [],
  onRemoveQueuedPrompt,
  onPromoteQueuedPrompt,
  backendUrl,
  targetedSource,
  onClearTargetedSource
}: ChatInputBoxProps) {
  const [input, setInput] = useState("");
  const [filter, setFilter] = useState<SearchFilterState>(DEFAULT_SEARCH_FILTER);
  const [isFilterOpen, setIsFilterOpen] = useState<boolean>(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleSend = () => {
    const query = input.trim();
    if (!query) return;

    const filterClauses: string[] = [];
    if (filter.yearFrom && filter.yearTo) {
      filterClauses.push(`years ${filter.yearFrom}-${filter.yearTo}`);
    } else if (filter.yearFrom) {
      filterClauses.push(`from ${filter.yearFrom} onwards`);
    } else if (filter.yearTo) {
      filterClauses.push(`up to ${filter.yearTo}`);
    }

    if (filter.minCitations && Number(filter.minCitations) > 0) {
      filterClauses.push(`minimum ${filter.minCitations} citations`);
    }

    if (filter.scopusQuartiles && filter.scopusQuartiles.length > 0) {
      filterClauses.push(`Scopus ${filter.scopusQuartiles.join("/")}`);
    }

    if (filter.sintaTiers && filter.sintaTiers.length > 0) {
      filterClauses.push(`SINTA ${filter.sintaTiers.join("/")}`);
    }

    if (filter.excludePreprints) {
      filterClauses.push("exclude preprints");
    }

    if (filter.openAccessOnly) {
      filterClauses.push("open access only");
    }

    if (filter.language && filter.language !== "all") {
      filterClauses.push(`language: ${filter.language}`);
    }

    if (filter.fieldsOfStudy && filter.fieldsOfStudy.length > 0) {
      filterClauses.push(`discipline: ${filter.fieldsOfStudy.join(", ")}`);
    }

    let finalMessage = query;
    if (targetedSource) {
      finalMessage = `[Focused Document: "${targetedSource.title || targetedSource.filename}"]\n${query}`;
    }
    if (filterClauses.length > 0) {
      finalMessage = `${finalMessage}\n[Filter Preferences: ${filterClauses.join(", ")}]`;
    }

    onSubmit(finalMessage);
    setInput("");
    onClearTargetedSource?.();
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const isCustomized = Boolean(
    filter.yearFrom ||
    filter.yearTo ||
    (filter.minCitations && Number(filter.minCitations) > 0) ||
    filter.scopusQuartiles.length > 0 ||
    filter.sintaTiers.length > 0 ||
    filter.excludePreprints ||
    filter.openAccessOnly ||
    (filter.language && filter.language !== "all") ||
    filter.fieldsOfStudy.length > 0
  );

  return (
    <div className={`w-full ${isCentered ? "max-w-2xl mx-auto my-4" : "max-w-3xl mx-auto"}`}>
      {queuedPrompts && queuedPrompts.length > 0 && (
        <div className="mb-2.5 rounded-2xl bg-[#1e1f22] border border-white/10 shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="flex items-center justify-between px-3.5 py-2 border-b border-white/5 bg-[#25262a]">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-semibold text-gray-200">Queued Messages</span>
              <span className="px-1.5 py-0.2 rounded-full bg-white/10 text-gray-300 text-[11px] font-mono font-medium">
                {queuedPrompts.length}
              </span>
              <span className="text-[11px] text-gray-400 font-normal hidden sm:inline">
                Sends after agent finishes working
              </span>
            </div>
          </div>

          <div className="p-2 space-y-1 divide-y divide-white/5">
            {queuedPrompts.map((qText, qIdx) => (
              <div 
                key={qIdx}
                className="flex items-center justify-between gap-3 px-2 py-1.5 group rounded-lg hover:bg-white/[0.03] transition-colors"
              >
                <p className="text-xs text-gray-200 truncate flex-1 font-normal select-text">
                  {qText}
                </p>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => onPromoteQueuedPrompt?.(qIdx)}
                    className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                    title="Switch & process now (stop current task)"
                  >
                    <ArrowRight size={14} className="text-blue-400" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setInput(qText);
                      onRemoveQueuedPrompt?.(qIdx);
                      textareaRef.current?.focus();
                    }}
                    className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
                    title="Edit queued message"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemoveQueuedPrompt?.(qIdx)}
                    className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
                    title="Remove from queue"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {targetedSource && (
        <div className="mb-2 px-3 py-1.5 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-between gap-2 animate-in fade-in duration-200">
          <div className="flex items-center gap-2 min-w-0">
            <FileText size={14} className="text-blue-400 shrink-0" />
            <span className="text-xs text-blue-200 truncate">
              Focusing on: <strong className="font-semibold text-white">{targetedSource.title || targetedSource.filename}</strong>
            </span>
          </div>
          <button
            type="button"
            onClick={onClearTargetedSource}
            className="p-1 text-gray-400 hover:text-white rounded-md hover:bg-white/10 transition-colors shrink-0"
            title="Clear focused document"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div className="relative flex flex-col rounded-3xl bg-[#1e1f20] border border-white/10 shadow-2xl focus-within:border-white/20 transition-all p-3">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={targetedSource ? `Ask anything about "${targetedSource.title || targetedSource.filename}"...` : "Start typing, ask questions, or search papers..."}
          rows={1}
          className="w-full bg-transparent text-white placeholder-gray-400 text-[15px] focus:outline-none resize-none px-3 py-2 leading-relaxed custom-scrollbar max-h-[180px]"
        />

        {/* Bottom Actions Row */}
        <div className="flex items-center justify-between pt-2 px-1">
          {/* Left: Only ModelSelector */}
          <div className="flex items-center">
            <ModelSelector backendUrl={backendUrl} />
          </div>

          {/* Right: Filter, Sources Badge, and Send/Stop Button */}
          <div className="flex items-center gap-2">
            <SearchFilterPopover
              isOpen={isFilterOpen}
              onClose={() => setIsFilterOpen(false)}
              onToggle={() => setIsFilterOpen(prev => !prev)}
              filter={filter}
              onApplyFilter={setFilter}
            />

            <button 
              type="button"
              onClick={onToggleRightSidebar}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-gray-300 text-xs font-medium border border-white/5 transition-colors cursor-pointer"
            >
              <FileText size={12} className="text-blue-400" />
              <span>{documentsCount} sources</span>
            </button>

            {isLoading && onStopGeneration ? (
              <button
                type="button"
                onClick={onStopGeneration}
                className="p-2 rounded-full bg-white text-black hover:bg-gray-200 transition-all cursor-pointer shadow-md flex items-center justify-center"
                title="Stop generation"
              >
                <Square size={16} className="fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim()}
                className="p-2 rounded-full bg-white text-black hover:bg-gray-200 disabled:opacity-30 disabled:hover:bg-white transition-all cursor-pointer disabled:cursor-not-allowed shadow-md flex items-center justify-center"
                title="Send message"
              >
                <ArrowUp size={18} strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});
