import React, { useState } from "react";
import { Quote, X, Download, Copy, Check, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Portal } from "@/components/ui/Portal";
import { Tooltip } from "@/components/ui/tooltip";
import { useTranslation } from "@/lib/i18n";
import { CitationFormats } from "@/hooks/useCitationGenerator";

interface CitationModalProps {
  isOpen: boolean;
  onClose: () => void;
  citations: CitationFormats;
  doiStr: string;
  hasAuthors?: boolean;
  hasYear?: boolean;
}

export function CitationModal({ isOpen, onClose, citations, doiStr, hasAuthors = true, hasYear = true }: CitationModalProps) {
  const { t } = useTranslation();
  const [selectedCitationStyle, setSelectedCitationStyle] = useState<"apa" | "ieee" | "harvard" | "mla" | "chicago" | "bibtex" | "ris">("apa");
  const [copiedCitationKey, setCopiedCitationKey] = useState<string | null>(null);

  if (!isOpen) return null;

  const downloadFileText = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Portal>
      <div 
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      >
      <div 
        onClick={(e) => e.stopPropagation()}
        className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-[530px] p-5 shadow-2xl space-y-3.5 animate-in zoom-in-95 duration-150 text-app-text"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-2.5 border-b border-app-divider">
          <div className="flex items-center gap-2">
            <Quote size={16} className="text-blue-500" />
            <h3 className="text-sm font-semibold text-app-text">{t('right.citeThis') || "Cite this Paper"}</h3>
          </div>
          <Tooltip content={t('right.close') || "Close"} side="bottom">
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover flex items-center justify-center transition-colors cursor-pointer"
              aria-label={t('right.close') || "Close"}
            >
              <X size={14} />
            </button>
          </Tooltip>
        </div>

        {/* Incomplete Metadata Warning Notice */}
        {(!hasAuthors || !hasYear) && (
          <div className="flex items-start gap-2.5 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-500 dark:text-amber-400">
            <AlertCircle size={15} className="shrink-0 mt-0.5 text-amber-500" />
            <span className="leading-snug">
              {t('right.citationIncompleteNotice') || "Incomplete metadata: Author or publication year could not be verified automatically. Please review before citing in formal research."}
            </span>
          </div>
        )}

        {/* Citation Format Tabs (Clean, Scrollable & Compact) */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar text-xs font-medium">
          {[
            { id: "apa", label: "APA 7th" },
            { id: "ieee", label: "IEEE" },
            { id: "harvard", label: "Harvard" },
            { id: "mla", label: "MLA 9th" },
            { id: "chicago", label: "Chicago" },
            { id: "bibtex", label: "BibTeX" },
            { id: "ris", label: "RIS" },
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => setSelectedCitationStyle(st.id as any)}
              className={`px-2.5 py-1.5 rounded-lg whitespace-nowrap transition-colors cursor-pointer text-xs ${
                selectedCitationStyle === st.id
                  ? "bg-blue-600 text-white font-semibold shadow-sm"
                  : "bg-app-item-hover hover:bg-app-item-active text-app-text-muted hover:text-app-text"
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>

        {/* Fixed-Height Scrollable Citation Content Box */}
        <div className="h-[140px] p-3.5 rounded-xl bg-app-input-surface border border-app-border font-sans text-xs leading-relaxed select-text text-app-text break-words whitespace-pre-wrap overflow-y-auto custom-scrollbar">
          {citations[selectedCitationStyle]}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-1 border-t border-app-divider">
          <div className="flex items-center gap-2">
            {selectedCitationStyle === "bibtex" && (
              <button
                onClick={() => downloadFileText(citations.bibtex, `${doiStr ? doiStr.replace(/[^a-z0-9]/gi, "_") : "paper"}.bib`)}
                className="px-2.5 py-1.5 rounded-lg bg-app-card hover:bg-app-card-hover border border-app-border text-xs text-app-text-muted hover:text-app-text transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm"
              >
                <Download size={13} />
                <span>{t('right.downloadBib') || "Download .bib"}</span>
              </button>
            )}
            {selectedCitationStyle === "ris" && (
              <button
                onClick={() => downloadFileText(citations.ris, `${doiStr ? doiStr.replace(/[^a-z0-9]/gi, "_") : "paper"}.ris`)}
                className="px-2.5 py-1.5 rounded-lg bg-app-card hover:bg-app-card-hover border border-app-border text-xs text-app-text-muted hover:text-app-text transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm"
              >
                <Download size={13} />
                <span>{t('right.downloadRis') || "Download .ris"}</span>
              </button>
            )}
          </div>

          <Button
            size="sm"
            onClick={() => {
              const text = citations[selectedCitationStyle];
              navigator.clipboard.writeText(text);
              setCopiedCitationKey(selectedCitationStyle);
              setTimeout(() => setCopiedCitationKey(null), 2000);
            }}
            className={`h-8 px-4 text-xs font-medium transition-colors shadow-sm gap-1.5 ${
              copiedCitationKey === selectedCitationStyle
                ? "bg-emerald-600 hover:bg-emerald-600 text-white"
                : "bg-blue-600 hover:bg-blue-700 text-white"
            }`}
          >
            {copiedCitationKey === selectedCitationStyle ? (
              <><Check size={14} /><span>{t('chat.copied')}</span></>
            ) : (
              <><Copy size={14} /><span>{t('right.copyCitation') || "Copy Citation"}</span></>
            )}
          </Button>
        </div>
      </div>
    </div>
    </Portal>
  );
}