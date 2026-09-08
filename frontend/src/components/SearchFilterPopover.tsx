"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslation } from "@/lib/i18n";
import { Portal } from "@/components/ui/Portal";
import { Tooltip } from "@/components/ui/tooltip";
import { 
  X, 
  SlidersHorizontal, 
  RotateCcw, 
  Award, 
  BookOpen
} from "lucide-react";

import {
  type SearchFilterState,
  DEFAULT_SEARCH_FILTER,
  SCOPUS_QUARTILES,
  SINTA_TIERS
} from "@/lib/constants/academicFilters";

import YearRangeFilter from "./SearchFilter/YearRangeFilter";
import DomainSelectFilter from "./SearchFilter/DomainSelectFilter";
import LanguageSelectFilter from "./SearchFilter/LanguageSelectFilter";
import { useSearchFilter, calculateCount } from "@/hooks/search/useSearchFilter";

interface SearchFilterPopoverProps {
  filter: SearchFilterState;
  onApplyFilter: (newFilter: SearchFilterState) => void;
  isOpen: boolean;
  onClose: () => void;
  onToggle: () => void;
}

export default function SearchFilterPopover({
  filter,
  onApplyFilter,
  isOpen,
  onClose,
  onToggle,
}: SearchFilterPopoverProps) {
  const { t } = useTranslation();
  
  const {
    localFilter,
    setLocalFilter,
    toggleField,
    toggleLanguage,
    toggleScopus,
    toggleSinta,
    setYearPreset
  } = useSearchFilter(filter);

  const [domainSearch, setDomainSearch] = useState<string>("");
  const [languageSearch, setLanguageSearch] = useState<string>("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Escape key listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  const appliedCount = calculateCount(filter);
  const activeLocalCount = calculateCount(localFilter);

  const handleReset = () => {
    setLocalFilter(DEFAULT_SEARCH_FILTER);
  };

  const handleApply = () => {
    onApplyFilter(localFilter);
    onClose();
  };

  const formatPaperCount = (count?: number) => {
    if (!count) return "";
    if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
    if (count >= 1_000) return `${(count / 1_000).toFixed(0)}k`;
    return count.toString();
  };

  return (
    <div className="relative inline-block text-left select-none text-app-text" ref={containerRef}>
      {/* Trigger Button: Always display pill with Text + Icon */}
      <Tooltip content={appliedCount > 0 ? `${t('filter.button')} (${appliedCount})` : t('filter.button')} side="top">
        <button
          type="button"
          onClick={onToggle}
          className={
            appliedCount > 0 
              ? "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs transition-all cursor-pointer shrink-0 bg-blue-600/20 hover:bg-blue-600/30 border-blue-500/50 text-blue-500 font-medium shadow-sm" 
              : "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs transition-all cursor-pointer shrink-0 bg-app-item-hover hover:bg-app-item-active border-app-border text-app-text-muted hover:text-app-text font-medium"
          }
          aria-label={t('filter.button')}
        >
          <SlidersHorizontal size={13} className={appliedCount > 0 ? "text-blue-500" : "text-app-text-dim"} />
          <span>{t('filter.button')}</span>
          {appliedCount > 0 && (
            <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-blue-500 text-white text-[10px] font-mono font-semibold">
              {appliedCount}
            </span>
          )}
        </button>
      </Tooltip>

      {/* Centered Modal Overlay (Option 1: Centered Dialog with Backdrop) */}
      {isOpen && (
        <Portal>
          <div 
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150 text-app-text"
          >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg max-h-[85vh] rounded-2xl bg-app-modal border border-app-border-strong shadow-2xl overflow-hidden flex flex-col p-4 sm:p-5 backdrop-blur-2xl animate-in zoom-in-95 duration-150 text-app-text"
          >
            {/* Header Bar */}
            <div className="flex items-center justify-between pb-3 border-b border-app-divider shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0">
                  <SlidersHorizontal size={15} />
                </div>
                <div className="flex flex-col justify-between h-8 py-0.5">
                  <h3 className="text-xs sm:text-sm font-semibold text-app-text leading-none">
                    {t('filter.title')}
                  </h3>
                  <span className="text-[11px] text-app-text-muted leading-none">
                    {t('filter.desc')}
                  </span>
                </div>
              </div>

              <Tooltip content={t('right.close') ? `${t('right.close')} (Esc)` : "Close (Esc)"} side="bottom">
                <button
                  type="button"
                  onClick={onClose}
                  className="h-7 w-7 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover flex items-center justify-center transition-colors cursor-pointer"
                  aria-label={t('right.close') ? `${t('right.close')} (Esc)` : "Close (Esc)"}
                >
                  <X size={15} />
                </button>
              </Tooltip>
            </div>

            {/* Scrollable Body */}
            <div className="py-3 space-y-4 max-h-[60vh] overflow-y-auto pr-1 custom-scrollbar">
            
            {/* 1. Year Range Filter */}
            <YearRangeFilter 
              localFilter={localFilter} 
              setLocalFilter={setLocalFilter} 
              setYearPreset={setYearPreset} 
              t={t} 
            />

            {/* 2. Minimum Citations Filter */}
            <div className="space-y-2 pt-2 border-t border-app-divider">
              <span className="text-xs font-semibold text-app-text flex items-center gap-1.5">
                <Award size={13} className="text-blue-500" />
                {t('filter.minCitations')}
              </span>

              {/* Preset citation chips */}
              <div className="grid grid-cols-4 gap-1.5 text-[11px]">
                {[
                  { label: "10+", value: "10" },
                  { label: "25+", value: "25" },
                  { label: "50+", value: "50" },
                  { label: "100+", value: "100" },
                ].map((preset) => {
                  const isSelected = localFilter.minCitations === preset.value;
                  return (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => setLocalFilter(prev => ({ 
                        ...prev, 
                        minCitations: prev.minCitations === preset.value ? "" : preset.value 
                      }))}
                      className={
                        isSelected
                          ? "py-1 px-1 rounded-lg border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-app-text font-semibold shadow-sm text-[11px]"
                          : "py-1 px-1 rounded-lg border text-center transition-colors cursor-pointer bg-app-item-hover border-app-border hover:bg-app-item-active text-app-text-muted hover:text-app-text text-[11px]"
                      }
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>

              {/* Custom numeric input */}
              <div className="flex items-center gap-2 pt-0.5">
                <span className="text-[11px] text-app-text-dim shrink-0">{t('filter.customMin')}</span>
                <input
                  type="number"
                  min="0"
                  placeholder="e.g. 5, 20, 100"
                  value={localFilter.minCitations}
                  onChange={(e) => setLocalFilter(prev => ({ ...prev, minCitations: e.target.value }))}
                  className="w-full bg-app-input-surface border border-app-border rounded-lg px-2.5 py-1.5 text-xs text-app-text placeholder:text-app-text-dim focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            {/* 3. Journal Indexing & Reputation (Scopus & SINTA) */}
            <div className="space-y-2.5 pt-2 border-t border-app-divider">
              <span className="text-xs font-semibold text-app-text flex items-center gap-1.5">
                <Award size={13} className="text-blue-500" />
                {t('filter.journalReputation')}
              </span>

              {/* Scopus Quartiles Chips */}
              <div className="space-y-1">
                <div className="text-[11px] text-app-text-muted font-medium">{t('filter.scopusQuartile')}</div>
                <div className="grid grid-cols-4 gap-1.5">
                  {SCOPUS_QUARTILES.map((sc) => {
                    const isChecked = localFilter.scopusQuartiles.includes(sc.id);
                    return (
                      <Tooltip key={sc.id} content={`Scopus ${sc.label} (${sc.desc})`} side="top">
                        <button
                          type="button"
                          onClick={() => toggleScopus(sc.id)}
                          className={
                            isChecked
                              ? "py-1.5 px-1.5 rounded-lg border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-app-text font-semibold shadow-sm text-xs w-full"
                              : "py-1.5 px-1.5 rounded-lg border text-center transition-colors cursor-pointer bg-app-item-hover border-app-border hover:bg-app-item-active text-app-text-muted hover:text-app-text text-xs w-full"
                          }
                          aria-label={`Scopus ${sc.label} (${sc.desc})`}
                        >
                          {sc.label}
                        </button>
                      </Tooltip>
                    );
                  })}
                </div>
              </div>

              {/* SINTA Indonesia Chips */}
              <div className="space-y-1 pt-1">
                <div className="text-[11px] text-app-text-muted font-medium">National Accreditation (SINTA):</div>
                <div className="grid grid-cols-6 gap-1 text-[11px]">
                  {SINTA_TIERS.map((st) => {
                    const isChecked = localFilter.sintaTiers.includes(st.id);
                    return (
                      <button
                        key={st.id}
                        type="button"
                        onClick={() => toggleSinta(st.id)}
                        className={
                          isChecked
                            ? "py-1 rounded-md border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-app-text font-semibold shadow-sm text-[11px]"
                            : "py-1 rounded-md border text-center transition-colors cursor-pointer bg-app-item-hover border-app-border hover:bg-app-item-active text-app-text-muted hover:text-app-text text-[11px]"
                        }
                      >
                        {st.id}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* 4. On/Off Toggles (Exclude Preprints & Open Access) */}
            <div className="space-y-2 pt-2 border-t border-app-divider">
              <span className="text-xs font-semibold text-app-text flex items-center gap-1.5">
                <BookOpen size={13} className="text-blue-500" />
                {t('filter.manuscriptAccess')}
              </span>

              <div className="space-y-1.5">
                {/* Toggle: Exclude Preprints */}
                <div 
                  onClick={() => setLocalFilter(prev => ({ ...prev, excludePreprints: !prev.excludePreprints }))}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-app-card hover:bg-app-card-hover border border-app-border cursor-pointer transition-colors"
                >
                  <div>
                    <div className="text-xs font-medium text-app-text flex items-center gap-1.5">
                      <span>{t('filter.excludePreprints')}</span>
                    </div>
                    <div className="text-[10px] text-app-text-dim">
                      {t('filter.excludePreprintsDesc')}
                    </div>
                  </div>

                  {/* Animated Toggle Switch */}
                  <div 
                    className={
                      localFilter.excludePreprints 
                        ? "w-9 h-5 rounded-full bg-blue-600 p-0.5 transition-colors shrink-0 flex items-center" 
                        : "w-9 h-5 rounded-full bg-app-item-active p-0.5 transition-colors shrink-0 flex items-center"
                    }
                  >
                    <div 
                      className={
                        localFilter.excludePreprints 
                          ? "w-4 h-4 rounded-full bg-white shadow-md transform translate-x-4 transition-transform duration-200" 
                          : "w-4 h-4 rounded-full bg-app-text-dim shadow-md transform translate-x-0 transition-transform duration-200"
                      } 
                    />
                  </div>
                </div>

                {/* Toggle: Open Access Only */}
                <div 
                  onClick={() => setLocalFilter(prev => ({ ...prev, openAccessOnly: !prev.openAccessOnly }))}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-app-card hover:bg-app-card-hover border border-app-border cursor-pointer transition-colors"
                >
                  <div>
                    <div className="text-xs font-medium text-app-text flex items-center gap-1.5">
                      <span>{t('filter.openAccessOnly')}</span>
                    </div>
                    <div className="text-[10px] text-app-text-dim">
                      {t('filter.openAccessOnlyDesc')}
                    </div>
                  </div>

                  <div 
                    className={
                      localFilter.openAccessOnly 
                        ? "w-9 h-5 rounded-full bg-blue-600 p-0.5 transition-colors shrink-0 flex items-center" 
                        : "w-9 h-5 rounded-full bg-app-item-active p-0.5 transition-colors shrink-0 flex items-center"
                    }
                  >
                    <div 
                      className={
                        localFilter.openAccessOnly 
                          ? "w-4 h-4 rounded-full bg-white shadow-md transform translate-x-4 transition-transform duration-200" 
                          : "w-4 h-4 rounded-full bg-app-text-dim shadow-md transform translate-x-0 transition-transform duration-200"
                      } 
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* 5. Language Selector (Multi-select Checkboxes) */}
            <LanguageSelectFilter
              localFilter={localFilter}
              languageSearch={languageSearch}
              setLanguageSearch={setLanguageSearch}
              toggleLanguage={toggleLanguage}
              formatPaperCount={formatPaperCount}
              t={t}
            />

            {/* 6. Fields of Study (Multi-select Checkboxes) */}
            <DomainSelectFilter 
              localFilter={localFilter}
              domainSearch={domainSearch}
              setDomainSearch={setDomainSearch}
              toggleField={toggleField}
              t={t}
            />

          </div>

            {/* Footer Action Buttons */}
            <div className="pt-3 border-t border-app-divider flex items-center justify-between gap-2 shrink-0">
              <button
                type="button"
                onClick={handleReset}
                className="px-3 py-1.5 rounded-lg text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <RotateCcw size={12} />
                <span>{t('filter.clear')}</span>
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3 py-1.5 rounded-lg text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer"
                >
                  {t('action.cancel')}
                </button>
                <button
                  type="button"
                  onClick={handleApply}
                  className="px-4 py-1.5 rounded-lg text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors cursor-pointer shadow flex items-center gap-1.5"
                >
                  <span>{t('filter.apply')}</span>
                  {activeLocalCount > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full bg-white/20 text-white text-[10px] font-mono">
                      {activeLocalCount}
                    </span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
        </Portal>
      )}
    </div>
  );
}
