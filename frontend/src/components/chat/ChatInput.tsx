"use client";

import React, { useState, useRef, useEffect, useMemo, memo } from "react";
import { 
  ArrowUp, 
  FileText, 
  Square, 
  X, 
  Plus 
} from "lucide-react";
import { TargetedSource } from "@/stores/documentStore";
import SearchFilterPopover from "@/components/SearchFilterPopover";
import { type SearchFilterState, DEFAULT_SEARCH_FILTER } from "@/lib/constants/academicFilters";
import { useTranslation } from "@/lib/i18n";
import { Tooltip } from "@/components/ui/tooltip";
import { StorageWarningModal } from "./input/StorageWarningModal";
import { QueuedPromptsList } from "./input/QueuedPromptsList";
import { TargetedSourceBadge } from "./input/TargetedSourceBadge";
import { AttachmentPreviewList, type Attachment } from "./input/AttachmentPreviewList";
import { ALLOWED_ATTACHMENT_EXTS } from "./input/fileUtils";

export type { Attachment };

export interface ChatInputBoxProps {
  isCentered?: boolean;
  isLoading?: boolean;
  documentsCount?: number;
  onToggleRightSidebar?: () => void;
  onSubmit: (text: string, attachments?: Attachment[]) => void;
  onStopGeneration?: () => void;
  queuedPrompts?: string[];
  onRemoveQueuedPrompt?: (index: number) => void;
  onPromoteQueuedPrompt?: (index: number) => void;
  backendUrl: string;
  chatId?: string | null;
  onEnsureChatSession?: () => Promise<string>;
  targetedSource?: TargetedSource | null;
  onClearTargetedSource?: () => void;
  onOpenStorage?: () => void;
}

export const ChatInputBox = memo(function ChatInputBox({
  isCentered = false,
  isLoading = false,
  documentsCount = 0,
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
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [storageWarningFile, setStorageWarningFile] = useState<{ filename: string; size: number } | null>(null);
  const [containerWidth, setContainerWidth] = useState(760);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeUploadControllersRef = useRef<Map<string, AbortController>>(new Map());
  const attachmentsRef = useRef<Attachment[]>([]);
  attachmentsRef.current = attachments;

  const revokeBlobUrl = (url?: string) => {
    if (url && url.startsWith("blob:")) {
      try {
        URL.revokeObjectURL(url);
      } catch {
        // ignore
      }
    }
  };

  useEffect(() => {
    const controllers = activeUploadControllersRef.current;
    return () => {
      attachmentsRef.current.forEach(a => revokeBlobUrl(a.previewUrl));
      controllers.forEach(c => c.abort());
      controllers.clear();
    };
  }, []);

  useEffect(() => {
    const controllers = activeUploadControllersRef.current;
    return () => {
      controllers.forEach(c => c.abort());
      controllers.clear();
    };
  }, []);

  useEffect(() => {
    if (!textareaRef.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setContainerWidth(entry.contentRect.width);
        }
      }
    });
    observer.observe(textareaRef.current);
    return () => observer.disconnect();
  }, []);

  const targetedPlaceholder = useMemo(() => {
    if (!targetedSource) return "";
    const rawTitle = (targetedSource.title || targetedSource.filename || "").trim();
    
    // Pixel-perfect dynamic fitting: measure exact rendered DOM text width
    if (typeof window !== "undefined" && textareaRef.current) {
      try {
        const availableWidth = (containerWidth || textareaRef.current.clientWidth) - 40; // 40px safe margin before the right edge

        let measurer = document.getElementById("placeholder-width-measurer") as HTMLSpanElement;
        if (!measurer) {
          measurer = document.createElement("span");
          measurer.id = "placeholder-width-measurer";
          measurer.style.position = "absolute";
          measurer.style.visibility = "hidden";
          measurer.style.whiteSpace = "nowrap";
          measurer.style.top = "-9999px";
          measurer.style.left = "-9999px";
          document.body.appendChild(measurer);
        }

        const style = window.getComputedStyle(textareaRef.current);
        measurer.style.fontFamily = style.fontFamily;
        measurer.style.fontSize = style.fontSize;
        measurer.style.fontWeight = style.fontWeight;
        measurer.style.letterSpacing = style.letterSpacing;

        const measure = (text: string) => {
          measurer.textContent = text;
          return measurer.offsetWidth;
        };

        if (availableWidth > 200) {
          // If the entire title fits, use it completely without cutting off!
          const fullText = t('chat.inputPlaceholderTargeted').replace('{title}', rawTitle).replace(/\.{3}"\s*\.{3}/g, '..."');
          if (measure(fullText) <= availableWidth) {
            return fullText;
          }

          // Otherwise, binary search the maximum title length that fits on a clean word boundary
          let low = 10;
          let high = rawTitle.length;
          let bestTitle = rawTitle.slice(0, 30);

          while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            // Snap to word boundary so it ends on a complete word without broken syllables like "re..."
            let sliceText = rawTitle.slice(0, mid);
            const lastSpace = sliceText.lastIndexOf(" ");
            if (lastSpace > 20 && mid < rawTitle.length) {
              sliceText = sliceText.slice(0, lastSpace);
            }
            const testTitle = sliceText.trimEnd() + "...";
            let testStr = t('chat.inputPlaceholderTargeted').replace('{title}', testTitle);
            testStr = testStr.replace(/\.{3}"\s*\.{3}/g, '..."');

            if (measure(testStr) <= availableWidth) {
              bestTitle = testTitle;
              low = mid + 1; // Try longer
            } else {
              high = mid - 1; // Too wide, shrink
            }
          }

          const finalText = t('chat.inputPlaceholderTargeted').replace('{title}', bestTitle);
          return finalText.replace(/\.{3}"\s*\.{3}/g, '..."');
        }
      } catch {}
    }

    // Fallback for SSR or environments without DOM measurer
    const maxLen = 85;
    const isTruncated = rawTitle.length > maxLen;
    const displayTitle = isTruncated ? `${rawTitle.slice(0, maxLen).trimEnd()}...` : rawTitle;
    const text = t('chat.inputPlaceholderTargeted').replace('{title}', displayTitle);
    return text.replace(/\.{3}"\s*\.{3}/g, '..."');
  }, [targetedSource, t, containerWidth]);

  const showAttachmentError = (msg: string) => {
    setAttachmentError(msg);
    setTimeout(() => {
      setAttachmentError(prev => (prev === msg ? null : prev));
    }, 4000);
  };

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

      const file = item.getAsFile?.();
      if (file) {
        const ext = file.name.split('.').pop()?.toLowerCase() || '';
        if (ALLOWED_ATTACHMENT_EXTS.has(ext)) {
          return true;
        }
      }
    }
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
    setIsDragActive(isValid);
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
    
    const MAX_ATTACHMENTS = 10;
    const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25MB

    if (attachments.length >= MAX_ATTACHMENTS) {
      showAttachmentError(`Maximum ${MAX_ATTACHMENTS} file attachments allowed per prompt.`);
      return;
    }

    const validFiles: File[] = [];
    const remainingSlots = MAX_ATTACHMENTS - attachments.length;

    for (let i = 0; i < files.length; i++) {
      if (validFiles.length >= remainingSlots) {
        break;
      }
      const file = files[i];
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      
      if (file.size > MAX_FILE_SIZE_BYTES) {
        showAttachmentError(`File "${file.name}" exceeds the 25MB maximum size limit.`);
        continue;
      }

      if (ALLOWED_ATTACHMENT_EXTS.has(ext)) {
        validFiles.push(file);
      }
    }

    if (validFiles.length === 0) return;

    // 1. Instant Optimistic Staging: Immediately render all files with individual loading spinners
    const stagedAttachments: Attachment[] = validFiles.map((file, idx) => {
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      const isImg = ["jpg", "jpeg", "png", "webp", "gif"].includes(ext);
      return {
        id: `staged-${Date.now()}-${idx}-${Math.random().toString(36).slice(2, 6)}`,
        type: isImg ? "image" : "file",
        filename: file.name,
        size: file.size,
        file: file,
        previewUrl: isImg ? URL.createObjectURL(file) : undefined,
        isUploading: true
      };
    });

    setAttachments(prev => [...prev, ...stagedAttachments]);
    setIsUploading(true);

    let targetChatId = chatId;
    if (!targetChatId && onEnsureChatSession) {
      try {
        targetChatId = await onEnsureChatSession();
      } catch (err) {
        console.error("Failed to ensure chat session for attachment:", err);
      }
    }
    
    if (!targetChatId) {
      stagedAttachments.forEach(s => revokeBlobUrl(s.previewUrl));
      setAttachments(prev => prev.filter(a => !stagedAttachments.some(s => s.id === a.id)));
      setIsUploading(false);
      return;
    }

    // 2. Concurrent Uploads with per-file completion tracking
    await Promise.all(
      stagedAttachments.map(async (staged) => {
        const file = staged.file!;
        const controller = new AbortController();
        activeUploadControllersRef.current.set(staged.id!, controller);
        const formData = new FormData();
        formData.append("file", file);

        try {
          const res = await fetch(`${backendUrl}/chats/${targetChatId}/upload_chat_media`, {
            method: "POST",
            body: formData,
            signal: controller.signal
          });

          if (res.ok) {
            const data = await res.json();
            setAttachments(prev => prev.map(a => {
              if (a.id === staged.id) {
                return {
                  ...a,
                  type: data.attachment.type,
                  filename: data.attachment.filename,
                  url: data.attachment.url,
                  size: data.attachment.size || file.size,
                  previewUrl: a.previewUrl || (data.attachment.type === "image" ? `${backendUrl}${data.attachment.url}` : undefined),
                  isUploading: false
                };
              }
              return a;
            }));

            if (data.storage_full || data.attachment?.chat_only) {
              setStorageWarningFile({
                filename: data.attachment.filename,
                size: data.attachment.size || file.size
              });
            }
          } else {
            revokeBlobUrl(staged.previewUrl);
            setAttachments(prev => prev.filter(a => a.id !== staged.id));
            showAttachmentError(`Failed to upload "${file.name}".`);
          }
        } catch (e: any) {
          revokeBlobUrl(staged.previewUrl);
          if (e.name !== "AbortError") {
            console.error("Failed to upload file:", e);
            showAttachmentError(`Failed to upload "${file.name}".`);
          }
          setAttachments(prev => prev.filter(a => a.id !== staged.id));
        } finally {
          activeUploadControllersRef.current.delete(staged.id!);
        }
      })
    );

    setIsUploading(false);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    if (e.clipboardData.files && e.clipboardData.files.length > 0) {
      e.preventDefault();
      handleFileUpload(e.clipboardData.files);
    }
  };

  const handleSend = () => {
    if (isLoading || isUploading || attachments.some(a => a.isUploading)) return;
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

    const readyAttachments = attachments.filter(a => !a.isUploading && Boolean(a.url));
    onSubmit(finalMessage, readyAttachments.length > 0 ? readyAttachments : undefined);
    setInput("");
    attachments.forEach(a => revokeBlobUrl(a.previewUrl));
    setAttachments([]);
    onClearTargetedSource?.();
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const removeAttachment = (index: number) => {
    const attToRemove = attachments[index];
    if (attToRemove) {
      if (attToRemove.id && activeUploadControllersRef.current.has(attToRemove.id)) {
        activeUploadControllersRef.current.get(attToRemove.id)?.abort();
        activeUploadControllersRef.current.delete(attToRemove.id);
      }
      if (attToRemove.previewUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(attToRemove.previewUrl);
      }
    }
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className={`w-full ${isCentered ? "my-4" : ""}`}>
      {/* Storage Limit Exceeded Modal */}
      <StorageWarningModal 
        file={storageWarningFile} 
        onClose={() => setStorageWarningFile(null)} 
        onOpenStorage={onOpenStorage} 
      />

      {/* Queued Prompts Bar */}
      <QueuedPromptsList
        queuedPrompts={queuedPrompts}
        onPromoteQueuedPrompt={onPromoteQueuedPrompt}
        onRemoveQueuedPrompt={onRemoveQueuedPrompt}
        onEditQueuedPrompt={(text, idx) => {
          setInput(text);
          onRemoveQueuedPrompt?.(idx);
          textareaRef.current?.focus();
        }}
      />

      {/* Attachment Error Banner */}
      {attachmentError && (
        <div className="mb-2 px-3.5 py-2 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center justify-between gap-2 text-xs text-red-400 animate-in fade-in slide-in-from-bottom-1 duration-150">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-semibold text-red-300">Notice:</span>
            <span className="truncate">{attachmentError}</span>
          </div>
          <button
            type="button"
            onClick={() => setAttachmentError(null)}
            className="p-1 text-red-400/70 hover:text-red-300 rounded hover:bg-red-500/20 transition-colors shrink-0"
          >
            <X size={13} />
          </button>
        </div>
      )}

      {/* Focused Document Badge */}
      <TargetedSourceBadge 
        targetedSource={targetedSource ?? null} 
        onClearTargetedSource={onClearTargetedSource} 
      />

      {/* Main Input Container */}
      <div 
        className={`relative flex flex-col rounded-3xl bg-app-input border ${isDragActive ? 'border-blue-500 bg-blue-500/5' : 'border-app-border-strong'} shadow-2xl focus-within:border-blue-500/50 transition-all p-3`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Staged Attachments */}
        <AttachmentPreviewList
          attachments={attachments}
          onRemoveAttachment={removeAttachment}
        />

        <textarea
          id="chat-input-textarea"
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
          placeholder={targetedSource ? targetedPlaceholder : t('chat.inputPlaceholder')}
          rows={1}
          className="w-full bg-transparent text-app-text placeholder-app-text-dim text-[15px] focus:outline-none resize-none px-3 py-2 leading-relaxed custom-scrollbar max-h-[180px]"
        />

        {/* Bottom Actions Row */}
        <div className="flex items-center justify-between gap-1.5 pt-2 px-1 w-full min-w-0">
          {/* Left: File Attach Button */}
          <div className="flex items-center gap-1 min-w-0">
            <Tooltip content={t('chat.attachTitle')} side="top">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-1.5 rounded-full text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors shrink-0 cursor-pointer"
                aria-label={t('chat.attachTitle')}
              >
                <Plus size={20} />
              </button>
            </Tooltip>
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              multiple 
              accept=".pdf,.docx,.doc,.txt,.md,.csv,.tsv,.bib,.bibtex,.ris,image/jpeg,image/png,image/webp,image/gif" 
              onChange={(e) => handleFileUpload(e.target.files)}
            />
          </div>

          {/* Right: Filter, Sources Badge, and Send/Stop Button */}
          <div className="flex items-center gap-1 sm:gap-1.5 shrink-0 ml-1">
            <SearchFilterPopover
              isOpen={isFilterOpen}
              onClose={() => setIsFilterOpen(false)}
              onToggle={() => setIsFilterOpen(prev => !prev)}
              filter={filter}
              onApplyFilter={setFilter}
            />

            <Tooltip content={t('chat.sourcesCount').replace('{count}', documentsCount.toString())} side="top">
              <button 
                type="button"
                onClick={onToggleRightSidebar}
                className="relative px-3 py-1.5 rounded-full bg-app-item-hover hover:bg-app-item-active text-app-text text-xs font-medium border border-app-border transition-colors cursor-pointer shrink-0 flex items-center justify-center gap-1.5"
                aria-label={t('chat.sourcesCount').replace('{count}', documentsCount.toString())}
              >
                <FileText size={15} className="text-blue-500 fill-blue-500/20 shrink-0" />
                <span>{t('chat.sourcesCount').replace('{count}', documentsCount.toString())}</span>
              </button>
            </Tooltip>

            {isLoading && onStopGeneration ? (
              <Tooltip content={t('chat.stopTitle')} side="top">
                <button
                  type="button"
                  onClick={onStopGeneration}
                  className="p-2 rounded-full bg-app-text text-app-bg hover:opacity-90 transition-all cursor-pointer shadow-md flex items-center justify-center shrink-0"
                  aria-label={t('chat.stopTitle')}
                >
                  <Square size={16} className="fill-current" />
                </button>
              </Tooltip>
            ) : (
              <Tooltip content={t('chat.sendTitle')} side="top">
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={(!input.trim() && attachments.length === 0) || isUploading || attachments.some(a => a.isUploading)}
                  className="p-2 rounded-full bg-app-text text-app-bg hover:opacity-90 disabled:opacity-30 disabled:hover:opacity-30 transition-all cursor-pointer disabled:cursor-not-allowed shadow-md flex items-center justify-center shrink-0"
                  aria-label={t('chat.sendTitle')}
                >
                  <ArrowUp size={18} strokeWidth={2.5} />
                </button>
              </Tooltip>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Disclaimer / Caveat */}
      <div className="relative">
        <p className="text-center text-[11px] text-app-text-dim mt-2 px-2 select-none relative z-10">
          {t('chat.mistakeWarning')}
        </p>
      </div>
    </div>
  );
});
