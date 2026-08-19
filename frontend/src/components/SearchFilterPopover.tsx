"use client";

import { useState, useEffect, useRef } from "react";
import { 
  X, 
  SlidersHorizontal, 
  RotateCcw, 
  Check, 
  Calendar, 
  Globe, 
  GraduationCap, 
  Award, 
  Search,
  BookOpen,
  Filter
} from "lucide-react";

export interface SearchFilterState {
  yearFrom: string;
  yearTo: string;
  minCitations: string; // "" (default: 0 / any), or "1", "10", "50", etc.
  language: string; // "all" or specific ISO code
  fieldsOfStudy: string[];
  scopusQuartiles: string[]; // ["Q1", "Q2", "Q3", "Q4"]
  sintaTiers: string[]; // ["S1", "S2", "S3", "S4", "S5", "S6"]
  excludePreprints: boolean;
  openAccessOnly: boolean;
}

export const DEFAULT_SEARCH_FILTER: SearchFilterState = {
  yearFrom: "",
  yearTo: "",
  minCitations: "",
  language: "all",
  fieldsOfStudy: [],
  scopusQuartiles: [],
  sintaTiers: [],
  excludePreprints: false,
  openAccessOnly: false,
};

// 19 Official Level-0 Top-Level Domains from OpenAlex Taxonomy
const OPENALEX_DOMAINS = [
  { id: "Computer Science", label: "Computer Science & AI", icon: "💻" },
  { id: "Engineering", label: "Engineering & Technology", icon: "⚙️" },
  { id: "Medicine", label: "Medicine & Health", icon: "🩺" },
  { id: "Mathematics", label: "Mathematics & Statistics", icon: "📐" },
  { id: "Physics", label: "Physics", icon: "⚛️" },
  { id: "Chemistry", label: "Chemistry", icon: "🧪" },
  { id: "Biology", label: "Biology & Life Sciences", icon: "🧬" },
  { id: "Materials Science", label: "Materials Science", icon: "🔬" },
  { id: "Environmental Science", label: "Environmental Science", icon: "🌿" },
  { id: "Geology", label: "Geology & Earth Sciences", icon: "🌍" },
  { id: "Geography", label: "Geography & GIS", icon: "🗺️" },
  { id: "Economics", label: "Economics & Econometrics", icon: "📈" },
  { id: "Business", label: "Business & Management", icon: "💼" },
  { id: "Psychology", label: "Psychology & Cognitive", icon: "🧠" },
  { id: "Sociology", label: "Sociology & Social Science", icon: "👥" },
  { id: "Political Science", label: "Political Science & Law", icon: "⚖️" },
  { id: "Philosophy", label: "Philosophy & Ethics", icon: "📜" },
  { id: "History", label: "History & Archaeology", icon: "🏛️" },
  { id: "Art", label: "Art & Humanities", icon: "🎨" },
];

import { ALL_WORLD_LANGUAGES, LanguageItem } from "@/lib/languages";

const ALL_LANGUAGES = ALL_WORLD_LANGUAGES;

const SCOPUS_QUARTILES = [
  { id: "Q1", label: "Q1", desc: "Top 25%" },
  { id: "Q2", label: "Q2", desc: "Top 50%" },
  { id: "Q3", label: "Q3", desc: "Top 75%" },
  { id: "Q4", label: "Q4", desc: "Bottom 25%" },
];

const SINTA_TIERS = [
  { id: "S1", label: "SINTA 1" },
  { id: "S2", label: "SINTA 2" },
  { id: "S3", label: "SINTA 3" },
  { id: "S4", label: "SINTA 4" },
  { id: "S5", label: "SINTA 5" },
  { id: "S6", label: "SINTA 6" },
];

interface SearchFilterPopoverProps {
  filter: SearchFilterState;
  onApplyFilter: (newFilter: SearchFilterState) => void;
  isOpen: boolean;
  onClose: () => void;
  onToggle: () => void;
}

const sanitizeFilter = (raw: Partial<SearchFilterState> | undefined): SearchFilterState => ({
  yearFrom: raw?.yearFrom || "",
  yearTo: raw?.yearTo || "",
  minCitations: raw?.minCitations || "",
  language: raw?.language || "all",
  fieldsOfStudy: Array.isArray(raw?.fieldsOfStudy) ? raw.fieldsOfStudy : [],
  scopusQuartiles: Array.isArray(raw?.scopusQuartiles) ? raw.scopusQuartiles : [],
  sintaTiers: Array.isArray(raw?.sintaTiers) ? raw.sintaTiers : [],
  excludePreprints: !!raw?.excludePreprints,
  openAccessOnly: !!raw?.openAccessOnly,
});

const formatPaperCount = (count?: number) => {
  if (!count) return "";
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(0)}k`;
  return count.toString();
};

export default function SearchFilterPopover({
  filter,
  onApplyFilter,
  isOpen,
  onClose,
  onToggle,
}: SearchFilterPopoverProps) {
  const [localFilter, setLocalFilter] = useState<SearchFilterState>(() => sanitizeFilter(filter));
  const [domainSearch, setDomainSearch] = useState<string>("");
  const [languageSearch, setLanguageSearch] = useState<string>("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Sync local state on prop change
  useEffect(() => {
    setLocalFilter(sanitizeFilter(filter));
  }, [filter]);

  // Click outside & Escape key listeners
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  // Calculate applied filter badge count
  const calculateCount = (f: SearchFilterState | undefined) => {
    if (!f) return 0;
    return (
      (f.yearFrom || f.yearTo ? 1 : 0) +
      (f.minCitations && Number(f.minCitations) > 0 ? 1 : 0) +
      (f.language && f.language !== "all" ? 1 : 0) +
      (f.fieldsOfStudy?.length || 0) +
      (f.scopusQuartiles?.length || 0) +
      (f.sintaTiers?.length || 0) +
      (f.excludePreprints ? 1 : 0) +
      (f.openAccessOnly ? 1 : 0)
    );
  };

  const appliedCount = calculateCount(filter);
  const activeLocalCount = calculateCount(localFilter);

  const handleReset = () => {
    setLocalFilter(DEFAULT_SEARCH_FILTER);
  };

  const handleApply = () => {
    onApplyFilter(localFilter);
    onClose();
  };

  const toggleField = (fieldId: string) => {
    setLocalFilter(prev => {
      const current = prev?.fieldsOfStudy || [];
      const exists = current.includes(fieldId);
      return {
        ...prev,
        fieldsOfStudy: exists 
          ? current.filter(f => f !== fieldId)
          : [...current, fieldId]
      };
    });
  };

  const toggleScopus = (qId: string) => {
    setLocalFilter(prev => {
      const current = prev?.scopusQuartiles || [];
      const exists = current.includes(qId);
      return {
        ...prev,
        scopusQuartiles: exists
          ? current.filter(q => q !== qId)
          : [...current, qId]
      };
    });
  };

  const toggleSinta = (sId: string) => {
    setLocalFilter(prev => {
      const current = prev?.sintaTiers || [];
      const exists = current.includes(sId);
      return {
        ...prev,
        sintaTiers: exists
          ? current.filter(s => s !== sId)
          : [...current, sId]
      };
    });
  };

  const setYearPreset = (from: string, to: string) => {
    setLocalFilter(prev => ({
      ...prev,
      yearFrom: from,
      yearTo: to
    }));
  };

  const filteredDomains = OPENALEX_DOMAINS.filter(d => 
    d.label.toLowerCase().includes(domainSearch.toLowerCase()) ||
    d.id.toLowerCase().includes(domainSearch.toLowerCase())
  );

  const filteredLanguages = ALL_LANGUAGES.filter(lang => 
    lang.label.toLowerCase().includes(languageSearch.toLowerCase()) ||
    lang.id.toLowerCase().includes(languageSearch.toLowerCase()) ||
    lang.countries.toLowerCase().includes(languageSearch.toLowerCase())
  );

  const selectedLanguageObj = ALL_LANGUAGES.find(l => l.id === localFilter.language) || ALL_LANGUAGES[0];

  return (
    <div className="relative inline-block text-left select-none" ref={containerRef}>
      {/* Trigger Button (Pill in Chat Input Bar) */}
      <button
        type="button"
        onClick={onToggle}
        className={
          appliedCount > 0 
            ? "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs transition-all cursor-pointer shrink-0 bg-blue-600/20 hover:bg-blue-600/30 border-blue-500/50 text-blue-300 font-medium shadow-sm" 
            : "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs transition-all cursor-pointer shrink-0 bg-white/5 hover:bg-white/10 border-white/5 text-gray-300 hover:text-white font-medium"
        }
        title="Filter search & research papers"
      >
        <SlidersHorizontal size={12} className={appliedCount > 0 ? "text-blue-400" : "text-gray-400"} />
        <span>Filter</span>
        {appliedCount > 0 && (
          <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-blue-500 text-white text-[10px] font-mono font-semibold">
            {appliedCount}
          </span>
        )}
      </button>

      {/* Floating Popover Card Opening Upwards */}
      {isOpen && (
        <div className="absolute bottom-full right-0 mb-2.5 w-[360px] sm:w-[440px] rounded-2xl bg-[#1c1d21] border border-white/15 shadow-2xl z-50 p-4 backdrop-blur-2xl animate-in fade-in zoom-in-95 duration-150 text-gray-200">
          
          {/* Header Bar */}
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
                <SlidersHorizontal size={15} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white leading-tight">
                  Search & Paper Filters
                </h3>
                <span className="text-[11px] text-gray-400">
                  OpenAlex & Crossref Academic Engine
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="h-7 w-7 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors cursor-pointer"
              title="Close (Esc)"
            >
              <X size={15} />
            </button>
          </div>

          {/* Scrollable Body */}
          <div className="py-3 space-y-4 max-h-[420px] overflow-y-auto pr-1 custom-scrollbar">
            
            {/* 1. Year Range Filter */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                  <Calendar size={13} className="text-blue-400" />
                  Year Range
                </span>
                {(localFilter.yearFrom || localFilter.yearTo) && (
                  <button
                    type="button"
                    onClick={() => setYearPreset("", "")}
                    className="text-[11px] text-blue-400 hover:underline cursor-pointer"
                  >
                    Reset years
                  </button>
                )}
              </div>

              <div className="grid grid-cols-3 gap-1.5 text-[11px]">
                <button
                  type="button"
                  onClick={() => setYearPreset("2023", "2026")}
                  className={
                    localFilter.yearFrom === "2023" && localFilter.yearTo === "2026"
                      ? "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-white font-medium shadow-sm"
                      : "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-white/5 border-white/10 hover:bg-white/10 text-gray-300"
                  }
                >
                  3 Yrs (2023–26)
                </button>
                <button
                  type="button"
                  onClick={() => setYearPreset("2020", "2026")}
                  className={
                    localFilter.yearFrom === "2020" && localFilter.yearTo === "2026"
                      ? "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-white font-medium shadow-sm"
                      : "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-white/5 border-white/10 hover:bg-white/10 text-gray-300"
                  }
                >
                  5 Yrs (2020–26)
                </button>
                <button
                  type="button"
                  onClick={() => setYearPreset("2015", "2026")}
                  className={
                    localFilter.yearFrom === "2015" && localFilter.yearTo === "2026"
                      ? "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-white font-medium shadow-sm"
                      : "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-white/5 border-white/10 hover:bg-white/10 text-gray-300"
                  }
                >
                  10 Yrs (2015–26)
                </button>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="number"
                  placeholder="From (e.g. 2018)"
                  value={localFilter.yearFrom}
                  onChange={(e) => setLocalFilter(prev => ({ ...prev, yearFrom: e.target.value }))}
                  className="w-full bg-[#131417] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500"
                />
                <span className="text-gray-400 text-xs">-</span>
                <input
                  type="number"
                  placeholder="To (2026)"
                  value={localFilter.yearTo}
                  onChange={(e) => setLocalFilter(prev => ({ ...prev, yearTo: e.target.value }))}
                  className="w-full bg-[#131417] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* 2. Minimum Citations Filter */}
            <div className="space-y-2 pt-2 border-t border-white/10">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                  <Award size={13} className="text-amber-400" />
                  Minimum Citations
                </span>
                {localFilter.minCitations && Number(localFilter.minCitations) > 0 && (
                  <button
                    type="button"
                    onClick={() => setLocalFilter(prev => ({ ...prev, minCitations: "" }))}
                    className="text-[11px] text-blue-400 hover:underline cursor-pointer"
                  >
                    Reset (Any)
                  </button>
                )}
              </div>

              {/* Preset citation chips */}
              <div className="grid grid-cols-4 gap-1.5 text-[11px]">
                {[
                  { label: "Any (0+)", value: "" },
                  { label: "1+ Citation", value: "1" },
                  { label: "10+ Citations", value: "10" },
                  { label: "50+ Citations", value: "50" },
                ].map((preset) => {
                  const isSelected = localFilter.minCitations === preset.value || (!localFilter.minCitations && preset.value === "");
                  return (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => setLocalFilter(prev => ({ ...prev, minCitations: preset.value }))}
                      className={
                        isSelected
                          ? "py-1 px-1.5 rounded-lg border text-center transition-colors cursor-pointer bg-amber-500/20 border-amber-500/70 text-amber-300 font-semibold shadow-sm text-[11px]"
                          : "py-1 px-1.5 rounded-lg border text-center transition-colors cursor-pointer bg-white/5 border-white/10 hover:bg-white/10 text-gray-300 text-[11px]"
                      }
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>

              {/* Custom numeric input */}
              <div className="flex items-center gap-2 pt-0.5">
                <span className="text-[11px] text-gray-400 shrink-0">Custom min:</span>
                <input
                  type="number"
                  min="0"
                  placeholder="e.g. 5, 20, 100"
                  value={localFilter.minCitations}
                  onChange={(e) => setLocalFilter(prev => ({ ...prev, minCitations: e.target.value }))}
                  className="w-full bg-[#131417] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            {/* 2. Journal Indexing & Reputation (Scopus & SINTA) */}
            <div className="space-y-2.5 pt-2 border-t border-white/10">
              <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                <Award size={13} className="text-yellow-400" />
                Journal Indexing & Reputation
              </span>

              {/* Scopus Quartiles Chips */}
              <div className="space-y-1">
                <div className="text-[11px] text-gray-400 font-medium">🏆 Scopus Quartile:</div>
                <div className="grid grid-cols-4 gap-1.5">
                  {SCOPUS_QUARTILES.map((sc) => {
                    const isChecked = localFilter.scopusQuartiles.includes(sc.id);
                    return (
                      <button
                        key={sc.id}
                        type="button"
                        onClick={() => toggleScopus(sc.id)}
                        className={
                          isChecked
                            ? "py-1.5 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-yellow-500/20 border-yellow-500/70 text-yellow-300 font-semibold shadow-sm flex items-center justify-center gap-1 text-xs"
                            : "py-1.5 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-white/5 border-white/10 hover:bg-white/10 text-gray-300 text-xs"
                        }
                        title={`Scopus ${sc.label} (${sc.desc})`}
                      >
                        {isChecked && <Check size={11} className="text-yellow-400" />}
                        <span>{sc.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* SINTA Indonesia Chips */}
              <div className="space-y-1 pt-1">
                <div className="text-[11px] text-gray-400 font-medium">🇮🇩 National Accreditation (SINTA):</div>
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
                            ? "py-1 rounded-md border text-center transition-colors cursor-pointer bg-red-500/20 border-red-500/70 text-red-300 font-semibold shadow-sm text-[11px]"
                            : "py-1 rounded-md border text-center transition-colors cursor-pointer bg-white/5 border-white/10 hover:bg-white/10 text-gray-300 text-[11px]"
                        }
                      >
                        {st.id}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* 3. On/Off Toggles (Exclude Preprints & Open Access) */}
            <div className="space-y-2 pt-2 border-t border-white/10">
              <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                <BookOpen size={13} className="text-blue-400" />
                Manuscript & Access Preferences
              </span>

              <div className="space-y-1.5">
                {/* Toggle: Exclude Preprints */}
                <div 
                  onClick={() => setLocalFilter(prev => ({ ...prev, excludePreprints: !prev.excludePreprints }))}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-white/5 hover:bg-white/[0.08] border border-white/10 cursor-pointer transition-colors"
                >
                  <div>
                    <div className="text-xs font-medium text-white flex items-center gap-1.5">
                      <span>🚫 Exclude Preprints</span>
                    </div>
                    <div className="text-[10px] text-gray-400">
                      Exclude unreviewed drafts (arXiv, bioRxiv, SSRN)
                    </div>
                  </div>

                  {/* iOS/Linear Style Animated Toggle Switch */}
                  <div 
                    className={
                      localFilter.excludePreprints 
                        ? "w-9 h-5 rounded-full bg-blue-600 p-0.5 transition-colors shrink-0 flex items-center" 
                        : "w-9 h-5 rounded-full bg-white/15 p-0.5 transition-colors shrink-0 flex items-center"
                    }
                  >
                    <div 
                      className={
                        localFilter.excludePreprints 
                          ? "w-4 h-4 rounded-full bg-white shadow-md transform translate-x-4 transition-transform duration-200" 
                          : "w-4 h-4 rounded-full bg-gray-300 shadow-md transform translate-x-0 transition-transform duration-200"
                      } 
                    />
                  </div>
                </div>

                {/* Toggle: Open Access Only */}
                <div 
                  onClick={() => setLocalFilter(prev => ({ ...prev, openAccessOnly: !prev.openAccessOnly }))}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-white/5 hover:bg-white/[0.08] border border-white/10 cursor-pointer transition-colors"
                >
                  <div>
                    <div className="text-xs font-medium text-white flex items-center gap-1.5">
                      <span>🔓 Open Access Only</span>
                    </div>
                    <div className="text-[10px] text-gray-400">
                      Only find papers with free & legal full-text PDF
                    </div>
                  </div>

                  <div 
                    className={
                      localFilter.openAccessOnly 
                        ? "w-9 h-5 rounded-full bg-blue-600 p-0.5 transition-colors shrink-0 flex items-center" 
                        : "w-9 h-5 rounded-full bg-white/15 p-0.5 transition-colors shrink-0 flex items-center"
                    }
                  >
                    <div 
                      className={
                        localFilter.openAccessOnly 
                          ? "w-4 h-4 rounded-full bg-white shadow-md transform translate-x-4 transition-transform duration-200" 
                          : "w-4 h-4 rounded-full bg-gray-300 shadow-md transform translate-x-0 transition-transform duration-200"
                      } 
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* 4. Language Selector (Searchable & Scrollable with 36+ World Languages & Countries) */}
            <div className="space-y-2 pt-2 border-t border-white/10">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5 truncate">
                  <Globe size={13} className="text-blue-400 shrink-0" />
                  <span className="truncate">
                    Language: <span className="text-blue-400 font-medium">{selectedLanguageObj.flag} {selectedLanguageObj.label}</span>
                  </span>
                </span>
                {localFilter.language !== "all" && (
                  <button
                    type="button"
                    onClick={() => setLocalFilter(prev => ({ ...prev, language: "all" }))}
                    className="text-[11px] text-blue-400 hover:underline cursor-pointer shrink-0 ml-2"
                  >
                    Reset language
                  </button>
                )}
              </div>

              {/* Search Language or Country Input */}
              <div className="relative">
                <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search language or country (e.g. Indonesian, Japan, Germany)..."
                  value={languageSearch}
                  onChange={(e) => setLanguageSearch(e.target.value)}
                  className="w-full bg-[#131417] border border-white/10 rounded-lg pl-7 pr-2.5 py-1.5 text-[11.5px] text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Scrollable Language Grid */}
              <div className="grid grid-cols-2 gap-1.5 max-h-[160px] overflow-y-auto pr-0.5 custom-scrollbar">
                {filteredLanguages.length === 0 ? (
                  <div className="col-span-2 text-center text-xs text-gray-500 py-3">
                    No languages or countries found
                  </div>
                ) : (
                  filteredLanguages.map((lang) => {
                    const isSelected = localFilter.language === lang.id;
                    return (
                      <button
                        key={lang.id}
                        type="button"
                        onClick={() => setLocalFilter(prev => ({ ...prev, language: lang.id }))}
                        className={
                          isSelected
                            ? "p-2 rounded-xl border text-left text-[11px] transition-all cursor-pointer flex items-center justify-between gap-1.5 bg-blue-600/20 border-blue-500/70 text-white font-medium shadow-sm"
                            : "p-2 rounded-xl border text-left text-[11px] transition-all cursor-pointer flex items-center justify-between gap-1.5 bg-white/5 border-white/10 hover:bg-white/10 text-gray-300 hover:text-white"
                        }
                      >
                        <div className="flex items-center gap-1.5 truncate min-w-0">
                          <span className="text-xs shrink-0">{lang.flag}</span>
                          <div className="truncate min-w-0 flex-1">
                            <div className="flex items-center gap-1 truncate">
                              <span className="truncate">{lang.label}</span>
                              {lang.papersCount !== undefined && (
                                <span className="text-[9.5px] text-gray-500 font-mono shrink-0">
                                  ({formatPaperCount(lang.papersCount)})
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        {isSelected && <Check size={11} className="text-blue-400 shrink-0 ml-1" />}
                      </button>
                    );
                  })
                )}
              </div>
            </div>

            {/* 5. 19 OpenAlex Top-Level Domains */}
            <div className="space-y-2 pt-2 border-t border-white/10">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                  <GraduationCap size={13} className="text-blue-400" />
                  Fields of Study ({localFilter.fieldsOfStudy.length ? `${localFilter.fieldsOfStudy.length} selected` : "All Domains"})
                </span>
                {localFilter.fieldsOfStudy.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setLocalFilter(prev => ({ ...prev, fieldsOfStudy: [] }))}
                    className="text-[11px] text-blue-400 hover:underline cursor-pointer"
                  >
                    Clear selection
                  </button>
                )}
              </div>

              {/* Search Domain Input */}
              <div className="relative">
                <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search fields (e.g. AI, Medicine, Physics)..."
                  value={domainSearch}
                  onChange={(e) => setDomainSearch(e.target.value)}
                  className="w-full bg-[#131417] border border-white/10 rounded-lg pl-7 pr-2.5 py-1.5 text-[11.5px] text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-1.5 max-h-[160px] overflow-y-auto pr-0.5 custom-scrollbar">
                {filteredDomains.map((f) => {
                  const isChecked = localFilter.fieldsOfStudy.includes(f.id);
                  return (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => toggleField(f.id)}
                      className={
                        isChecked 
                          ? "p-2 rounded-xl border text-left text-[11px] transition-all cursor-pointer flex items-center justify-between gap-1.5 bg-blue-600/20 border-blue-500/70 text-white font-medium shadow-sm"
                          : "p-2 rounded-xl border text-left text-[11px] transition-all cursor-pointer flex items-center justify-between gap-1.5 bg-white/5 border-white/10 hover:bg-white/10 text-gray-300 hover:text-white"
                      }
                    >
                      <div className="flex items-center gap-1.5 truncate">
                        <span className="text-xs">{f.icon}</span>
                        <span className="truncate">{f.label}</span>
                      </div>
                      {isChecked && <Check size={11} className="text-blue-400 shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>

          </div>

          {/* Footer Action Buttons */}
          <div className="pt-3 border-t border-white/10 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={handleReset}
              className="px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-white hover:bg-white/10 flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <RotateCcw size={12} />
              <span>Reset</span>
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 rounded-lg text-xs text-gray-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApply}
                className="px-4 py-1.5 rounded-lg text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors cursor-pointer shadow flex items-center gap-1.5"
              >
                <span>Apply</span>
                {activeLocalCount > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full bg-white/20 text-white text-[10px] font-mono">
                    {activeLocalCount}
                  </span>
                )}
              </button>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
