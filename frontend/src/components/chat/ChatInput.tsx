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
  SlidersHorizontal,
  Plus
} from "lucide-react";
import { TargetedSource } from "@/app/ChatClient";
import ModelSelector from "@/components/ModelSelector";
import SearchFilterPopover, { SearchFilterState, DEFAULT_SEARCH_FILTER } from "@/components/SearchFilterPopover";
import { useTranslation } from "@/lib/i18n";

export interface Attachment {
  type: "image" | "file";
  filename: string;
  url?: string;
  file?: File;
  previewUrl?: string;
}

export interface ChatInputBoxProps {
  isCentered?: boolean;
  isLoading?: boolean;
  documentsCount: number;
  onToggleRightSidebar?: () => void;
  onSubmit: (text: string, attachments?: Attachment[]) => void;
  onStopGeneration?: () => void;
  queuedPrompts?: string[];
  onRemoveQueuedPrompt?: (index: number) => void;
  onPromoteQueuedPrompt?: (index: number) => void;
  backendUrl: string;
  chatId: string | null;
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
  chatId,
  targetedSource,
  onClearTargetedSource
}: ChatInputBoxProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [filter, setFilter] = useState<SearchFilterState>(DEFAULT_SEARCH_FILTER);
  const [isFilterOpen, setIsFilterOpen] = useState<boolean>(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isDragActive, setIsDragActive] = useState(false);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0 || !chatId) return;
    
    setIsUploading(true);
    const newAttachments = [...attachments];
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append("file", file);
      
      try {
        const res = await fetch(`${backendUrl}/chats/${chatId}/upload_chat_media`, {
          method: "POST",
          body: formData
        });
        
        if (res.ok) {
          const data = await res.json();
          newAttachments.push({
            type: data.attachment.type,
            filename: data.attachment.filename,
            url: data.attachment.url,
            previewUrl: URL.createObjectURL(file)
          });
        }
      } catch (e) {
        console.error("Failed to upload file:", e);
      }
    }
    
    setAttachments(newAttachments);
    setIsUploading(false);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    if (e.clipboardData.files && e.clipboardData.files.length > 0) {
      e.preventDefault();
      handleFileUpload(e.clipboardData.files);
    }
  };

  const handleSend = () => {
    const query = input.trim();
    if (!query && attachments.length === 0) return;

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

    if (filter.languages && filter.languages.length > 0) {
      filterClauses.push(`languages: ${filter.languages.join(", ")}`);
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

    onSubmit(finalMessage, attachments.length > 0 ? attachments : undefined);
    setInput("");
    setAttachments([]);
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
    (filter.languages && filter.languages.length > 0) ||
    filter.fieldsOfStudy.length > 0
  );

  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className={`w-full ${isCentered ? "max-w-2xl mx-auto my-4" : ""}`}>
      {/* Attachments Preview Area */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2 px-1">
          {attachments.map((att, idx) => (
            <div key={idx} className="relative group rounded-xl border border-white/10 bg-[#1e1f22] overflow-hidden flex items-center p-1.5 pr-8 min-w-[120px] max-w-[200px]">
              {att.type === "image" && att.previewUrl ? (
                <div className="w-8 h-8 rounded shrink-0 bg-black/40 overflow-hidden mr-2">
                  <img src={att.previewUrl} alt="preview" className="w-full h-full object-cover" />
                </div>
              ) : (
                <div className="w-8 h-8 rounded shrink-0 bg-white/5 flex items-center justify-center mr-2">
                  <FileText size={16} className="text-gray-400" />
                </div>
              )}
              <span className="text-[11px] text-gray-300 truncate">{att.filename}</span>
              <button 
                onClick={() => removeAttachment(idx)}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded-full bg-black/40 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/60"
              >
                <X size={12} />
              </button>
            </div>
          ))}
          {isUploading && (
            <div className="h-11 px-3 rounded-xl border border-white/5 bg-[#1e1f22]/50 flex items-center justify-center text-[11px] text-gray-400 animate-pulse">
              Uploading...
            </div>
          )}
        </div>
      )}

      {queuedPrompts && queuedPrompts.length > 0 && (
        <div className="mb-2.5 rounded-2xl bg-[#1e1f22] border border-white/10 shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="flex items-center justify-between px-3.5 py-2 border-b border-white/5 bg-[#25262a]">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-semibold text-gray-200">{t('chat.queuedMessages')}</span>
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
                    title={t('chat.switchProcess')}
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
                    title={t('chat.editQueued')}
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemoveQueuedPrompt?.(qIdx)}
                    className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
                    title={t('chat.removeQueued')}
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
            title={t('chat.clearTargeted')}
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div 
        className={`relative flex flex-col rounded-3xl bg-[#1e1f20] border ${isDragActive ? 'border-blue-500 bg-[#25252b]' : 'border-white/10'} shadow-2xl focus-within:border-white/20 transition-all p-3`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2 px-1">
            {attachments.map((att, i) => (
              <div key={i} className="relative group flex items-center bg-black/40 rounded-lg p-1.5 pr-3 border border-white/10 max-w-[200px]">
                {att.type === 'image' && att.previewUrl ? (
                  <img src={att.previewUrl} alt={att.filename} className="w-8 h-8 object-cover rounded mr-2" />
                ) : (
                  <FileText size={20} className="text-gray-400 mx-1 mr-2 shrink-0" />
                )}
                <span className="text-xs text-gray-300 truncate">{att.filename}</span>
                <button 
                  type="button"
                  onClick={() => {
                    const newAtts = [...attachments];
                    newAtts.splice(i, 1);
                    setAttachments(newAtts);
                  }}
                  className="absolute -top-1.5 -right-1.5 p-0.5 bg-gray-800 text-gray-400 hover:text-white hover:bg-red-500/80 rounded-full border border-white/20 opacity-0 group-hover:opacity-100 transition-all"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPaste={handlePaste}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={targetedSource ? t('chat.inputPlaceholderTargeted').replace('{title}', targetedSource.title || targetedSource.filename) : t('chat.inputPlaceholder')}
          rows={1}
          className="w-full bg-transparent text-white placeholder-gray-400 text-[15px] focus:outline-none resize-none px-3 py-2 leading-relaxed custom-scrollbar max-h-[180px]"
        />

        {/* Bottom Actions Row */}
        <div className="flex items-center justify-between pt-2 px-1">
          {/* Left: + Button & ModelSelector */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 rounded-full text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              title={t('chat.attachTitle')}
            >
              <Plus size={20} />
            </button>
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              multiple 
              accept="image/*,.pdf,.txt,.docx" 
              onChange={(e) => handleFileUpload(e.target.files)}
            />
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
              <FileText size={16} className="text-blue-400 fill-blue-400/20" />
              <span>{t('chat.sourcesCount').replace('{count}', documentsCount.toString())}</span>
            </button>

            {isLoading && onStopGeneration ? (
              <button
                type="button"
                onClick={onStopGeneration}
                className="p-2 rounded-full bg-white text-black hover:bg-gray-200 transition-all cursor-pointer shadow-md flex items-center justify-center"
                title={t('chat.stopTitle')}
              >
                <Square size={16} className="fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={(!input.trim() && attachments.length === 0) || isUploading}
                className="p-2 rounded-full bg-white text-black hover:bg-gray-200 disabled:opacity-30 disabled:hover:bg-white transition-all cursor-pointer disabled:cursor-not-allowed shadow-md flex items-center justify-center"
                title={t('chat.sendTitle')}
              >
                <ArrowUp size={18} strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Disclaimer / Caveat with Solid Backdrop */}
      <div className="relative">
        <div className="absolute -top-4 -bottom-6 -left-8 -right-8 bg-[#212121] -z-10 pointer-events-auto"></div>
        <p className="text-center text-[11px] text-gray-400 mt-2 px-2 select-none relative z-10">
          {t('chat.mistakeWarning')}
        </p>
      </div>
    </div>
  );
});
