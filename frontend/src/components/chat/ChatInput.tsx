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
  Plus,
  FileArchive,
  FileSpreadsheet
} from "lucide-react";
import { TargetedSource } from "@/stores/documentStore";
import ModelSelector from "@/components/ModelSelector";
import SearchFilterPopover, { SearchFilterState, DEFAULT_SEARCH_FILTER } from "@/components/SearchFilterPopover";
import { useTranslation } from "@/lib/i18n";

const ALLOWED_ATTACHMENT_EXTS = new Set([
  "pdf", "docx", "doc", "txt", "md", "csv", "tsv", "bib", "bibtex", "ris",
  "jpg", "jpeg", "png", "webp", "gif"
]);

export interface Attachment {
  type: "image" | "file";
  filename: string;
  url?: string;
  size?: number;
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
  onEnsureChatSession?: () => Promise<string>;
  targetedSource?: TargetedSource | null;
  onClearTargetedSource?: () => void;
  onOpenStorage?: () => void;
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
  onEnsureChatSession,
  targetedSource,
  onClearTargetedSource,
  onOpenStorage
}: ChatInputBoxProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [filter, setFilter] = useState<SearchFilterState>(DEFAULT_SEARCH_FILTER);
  const [isFilterOpen, setIsFilterOpen] = useState<boolean>(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [storageWarningFile, setStorageWarningFile] = useState<{ filename: string; size: number } | null>(null);
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

  const checkHasValidFiles = (e: React.DragEvent) => {
    if (!e.dataTransfer || !e.dataTransfer.items) return false;
    for (let i = 0; i < e.dataTransfer.items.length; i++) {
      const item = e.dataTransfer.items[i];
      if (item.kind !== "file") continue;
      
      // If item type is available (e.g. image/png, application/pdf)
      const mime = (item.type || "").toLowerCase();
      if (
        mime.startsWith("image/") ||
        mime.includes("pdf") ||
        mime.includes("word") ||
        mime.includes("text") ||
        mime.includes("csv")
      ) {
        return true;
      }

      // Check file name extension from item if available as a File (some browsers)
      const file = item.getAsFile?.();
      if (file) {
        const ext = file.name.split('.').pop()?.toLowerCase() || '';
        if (ALLOWED_ATTACHMENT_EXTS.has(ext)) {
          return true;
        }
      }
    }
    // Fallback: if browser hides item details during dragover, check files if present
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        const ext = e.dataTransfer.files[i].name.split('.').pop()?.toLowerCase() || '';
        if (ALLOWED_ATTACHMENT_EXTS.has(ext)) {
          return true;
        }
      }
      return false;
    }
    return false;
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    const isValid = checkHasValidFiles(e);
    if (isValid) {
      setIsDragActive(true);
    } else {
      setIsDragActive(false);
    }
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
    if (!files || files.length === 0) return;
    
    // Filter only supported formats
    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      if (ALLOWED_ATTACHMENT_EXTS.has(ext)) {
        validFiles.push(file);
      }
    }

    if (validFiles.length === 0) return;

    let targetChatId = chatId;
    if (!targetChatId && onEnsureChatSession) {
      try {
        targetChatId = await onEnsureChatSession();
      } catch (err) {
        console.error("Failed to ensure chat session for attachment:", err);
      }
    }
    
    if (!targetChatId) return;
    
    setIsUploading(true);
    const newAttachments = [...attachments];
    
    for (let i = 0; i < validFiles.length; i++) {
      const file = validFiles[i];
      const formData = new FormData();
      formData.append("file", file);
      
      try {
        const res = await fetch(`${backendUrl}/chats/${targetChatId}/upload_chat_media`, {
          method: "POST",
          body: formData
        });
        
        if (res.ok) {
          const data = await res.json();
          newAttachments.push({
            type: data.attachment.type,
            filename: data.attachment.filename,
            url: data.attachment.url,
            size: data.attachment.size || file.size,
            previewUrl: URL.createObjectURL(file)
          });
          
          if (data.storage_full || data.attachment?.chat_only) {
            setStorageWarningFile({
              filename: data.attachment.filename,
              size: data.attachment.size || file.size
            });
          }
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

  const formatFileSize = (bytes: number): string => {
    if (!bytes || bytes <= 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <div className={`w-full ${isCentered ? "max-w-2xl mx-auto my-4" : ""}`}>
      {/* Storage Limit Exceeded Modal / Card */}
      {storageWarningFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-[#1e1f20] border border-white/10 rounded-2xl w-full max-w-md p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150 relative text-left"
          >
            <div className="flex items-start justify-between">
              <h3 className="text-base font-semibold text-white">File added to chat only</h3>
              <button
                type="button"
                onClick={() => setStorageWarningFile(null)}
                className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <p className="text-sm text-gray-300 leading-relaxed">
              You don&apos;t have enough storage space left to save this file. Remove files to create space.
            </p>

            <div className="flex items-center justify-between p-3 rounded-xl bg-[#141415] border border-white/10">
              <div className="flex items-center gap-3 min-w-0 pr-3">
                <div className="p-2 rounded-lg bg-white/5 border border-white/10 shrink-0">
                  <FileText size={18} className="text-gray-300" />
                </div>
                <span className="text-sm font-medium text-white truncate">
                  {storageWarningFile.filename}
                </span>
              </div>
              <span className="text-xs text-gray-400 font-mono shrink-0">
                {formatFileSize(storageWarningFile.size)}
              </span>
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() => {
                  setStorageWarningFile(null);
                  onOpenStorage?.();
                }}
                className="px-4 py-2 text-xs font-medium text-white bg-[#2a2b2e] hover:bg-[#35373b] border border-white/10 rounded-full transition-colors cursor-pointer shadow-sm"
              >
                Manage storage
              </button>
            </div>
          </div>
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
            {attachments.map((att, i) => {
              const ext = att.filename.split('.').pop()?.toLowerCase() || '';
              const isWord = ['docx', 'doc'].includes(ext);
              const isPdf = ext === 'pdf';
              const isZip = ['zip', 'rar', '7z', 'tar', 'gz'].includes(ext);
              const isSheet = ['xlsx', 'xls', 'csv', 'tsv'].includes(ext);

              return (
                <div key={i} className="relative group flex items-center bg-[#25262b] rounded-2xl p-2 pr-3.5 border border-white/10 max-w-[260px] shadow-sm">
                  {att.type === 'image' && att.previewUrl ? (
                    <img src={att.previewUrl} alt={att.filename} className="w-8 h-8 object-cover rounded-xl mr-2.5 shrink-0" />
                  ) : isWord ? (
                    <div className="w-8 h-8 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-xs mr-2.5 shrink-0">
                      W
                    </div>
                  ) : isPdf ? (
                    <div className="w-8 h-8 rounded-xl bg-red-600/20 border border-red-500/30 flex items-center justify-center text-red-400 font-bold text-[10px] mr-2.5 shrink-0">
                      PDF
                    </div>
                  ) : isZip ? (
                    <div className="w-8 h-8 rounded-xl bg-amber-600/20 border border-amber-500/30 flex items-center justify-center text-amber-400 mr-2.5 shrink-0">
                      <FileArchive size={16} />
                    </div>
                  ) : isSheet ? (
                    <div className="w-8 h-8 rounded-xl bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mr-2.5 shrink-0">
                      <FileSpreadsheet size={16} />
                    </div>
                  ) : (
                    <div className="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-gray-300 mr-2.5 shrink-0">
                      <FileText size={16} />
                    </div>
                  )}
                  <div className="flex flex-col min-w-0 pr-1">
                    <span className="text-xs text-gray-200 font-medium truncate">{att.filename}</span>
                    {att.size && att.size > 0 ? (
                      <span className="text-[10px] text-gray-400 font-mono">{formatFileSize(att.size)}</span>
                    ) : null}
                  </div>
                  <button 
                    type="button"
                    onClick={() => {
                      const newAtts = [...attachments];
                      newAtts.splice(i, 1);
                      setAttachments(newAtts);
                    }}
                    className="absolute -top-1.5 -right-1.5 p-1 bg-[#1e1f20] text-gray-400 hover:text-white hover:bg-red-500/80 rounded-full border border-white/20 opacity-0 group-hover:opacity-100 transition-all cursor-pointer shadow-md"
                  >
                    <X size={12} />
                  </button>
                </div>
              );
            })}
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
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 px-1">
          {/* Left: + Button & ModelSelector */}
          <div className="flex items-center gap-1 min-w-0">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 rounded-full text-gray-400 hover:text-white hover:bg-white/10 transition-colors shrink-0"
              title={t('chat.attachTitle')}
            >
              <Plus size={20} />
            </button>
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              multiple 
              accept=".pdf,.docx,.doc,.txt,.md,.csv,.tsv,.bib,.bibtex,.ris,image/jpeg,image/png,image/webp,image/gif" 
              onChange={(e) => handleFileUpload(e.target.files)}
            />
            <ModelSelector backendUrl={backendUrl} />
          </div>

          {/* Right: Filter, Sources Badge, and Send/Stop Button */}
          <div className="flex items-center gap-1.5 sm:gap-2 ml-auto shrink-0">
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
              className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-gray-300 text-xs font-medium border border-white/5 transition-colors cursor-pointer"
            >
              <FileText size={15} className="text-blue-400 fill-blue-400/20 shrink-0" />
              <span className="hidden sm:inline">{t('chat.sourcesCount').replace('{count}', documentsCount.toString())}</span>
              <span className="sm:hidden">{documentsCount}</span>
            </button>

            {isLoading && onStopGeneration ? (
              <button
                type="button"
                onClick={onStopGeneration}
                className="p-2 rounded-full bg-white text-black hover:bg-gray-200 transition-all cursor-pointer shadow-md flex items-center justify-center shrink-0"
                title={t('chat.stopTitle')}
              >
                <Square size={16} className="fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={(!input.trim() && attachments.length === 0) || isUploading}
                className="p-2 rounded-full bg-white text-black hover:bg-gray-200 disabled:opacity-30 disabled:hover:bg-white transition-all cursor-pointer disabled:cursor-not-allowed shadow-md flex items-center justify-center shrink-0"
                title={t('chat.sendTitle')}
              >
                <ArrowUp size={18} strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Disclaimer / Caveat */}
      <div className="relative">
        <p className="text-center text-[11px] text-gray-400 mt-2 px-2 select-none relative z-10">
          {t('chat.mistakeWarning')}
        </p>
      </div>
    </div>
  );
});
