"use client";

import React from "react";
import { 
  FileText, 
  X, 
  FileArchive, 
  FileSpreadsheet,
  Loader2
} from "lucide-react";
import { formatFileSize } from "./fileUtils";
import { useTranslation } from "@/lib/i18n";

export interface Attachment {
  id?: string;
  type: "image" | "file";
  filename: string;
  url?: string;
  size?: number;
  file?: File;
  previewUrl?: string;
  isUploading?: boolean;
  error?: string;
}

interface AttachmentPreviewListProps {
  attachments: Attachment[];
  onRemoveAttachment: (index: number) => void;
}

export function AttachmentPreviewList({
  attachments,
  onRemoveAttachment
}: AttachmentPreviewListProps) {
  const { t } = useTranslation();
  if (!attachments || attachments.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mb-2.5 px-0.5 w-full">
      {attachments.map((att, i) => {
        const ext = att.filename.split(".").pop()?.toLowerCase() || "";
        const isWord = ["docx", "doc"].includes(ext);
        const isPdf = ext === "pdf";
        const isZip = ["zip", "rar", "7z", "tar", "gz"].includes(ext);
        const isSheet = ["xlsx", "xls", "csv", "tsv"].includes(ext);

        return (
          <div 
            key={att.id || i} 
            className={`relative group flex items-center bg-app-card rounded-2xl p-2 pr-3.5 border transition-colors min-w-0 shadow-sm ${
              att.isUploading ? "border-blue-500/40 bg-app-card/90" : "border-app-border"
            }`}
          >
            {att.type === "image" && att.previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={att.previewUrl} alt={att.filename} className="w-8 h-8 object-cover rounded-lg mr-2.5 shrink-0" />
            ) : isWord ? (
              <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-500 font-bold text-xs mr-2.5 shrink-0">
                W
              </div>
            ) : isPdf ? (
              <div className="w-8 h-8 rounded-lg bg-red-600/20 border border-red-500/30 flex items-center justify-center text-red-500 font-bold text-[10px] mr-2.5 shrink-0">
                PDF
              </div>
            ) : isZip ? (
              <div className="w-8 h-8 rounded-lg bg-amber-600/20 border border-amber-500/30 flex items-center justify-center text-amber-500 mr-2.5 shrink-0">
                <FileArchive size={16} />
              </div>
            ) : isSheet ? (
              <div className="w-8 h-8 rounded-lg bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center text-emerald-500 mr-2.5 shrink-0">
                <FileSpreadsheet size={16} />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-lg bg-app-item-hover border border-app-border flex items-center justify-center text-app-text-muted mr-2.5 shrink-0">
                <FileText size={16} />
              </div>
            )}
            <div className="flex flex-col min-w-0 pr-1 text-left items-start flex-1">
              <span className="text-xs text-app-text font-medium truncate w-full text-left" title={att.filename}>
                {att.filename}
              </span>
              {att.isUploading ? (
                <span className="flex items-center gap-1 text-[10px] text-blue-500 font-medium select-none">
                  <Loader2 size={10} className="animate-spin shrink-0" />
                  <span>{t('chat.uploading') || "Uploading..."}</span>
                </span>
              ) : att.size && att.size > 0 ? (
                <span className="text-[10px] text-app-text-dim font-mono text-left">
                  {formatFileSize(att.size)}
                </span>
              ) : null}
            </div>
            <button 
              type="button"
              onClick={() => onRemoveAttachment(i)}
              className={`absolute -top-1.5 -right-1.5 p-1 bg-app-card text-app-text-muted hover:text-white hover:bg-red-500 rounded-full border border-app-border transition-all cursor-pointer shadow-md ${
                att.isUploading ? "opacity-70 group-hover:opacity-100" : "opacity-0 group-hover:opacity-100"
              }`}
              title="Remove attachment"
              aria-label="Remove attachment"
            >
              <X size={12} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
