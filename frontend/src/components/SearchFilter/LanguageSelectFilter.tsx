import { Globe, Search, Check } from "lucide-react";
import { type SearchFilterState } from "@/lib/constants/academicFilters";
import { ALL_WORLD_LANGUAGES } from "@/lib/languages";

const ALL_LANGUAGES = ALL_WORLD_LANGUAGES;

interface LanguageSelectFilterProps {
  localFilter: SearchFilterState;
  languageSearch: string;
  setLanguageSearch: (val: string) => void;
  toggleLanguage: (langId: string) => void;
  formatPaperCount: (count?: number) => string;
  t: (key: string) => string;
}

export default function LanguageSelectFilter({ 
  localFilter, 
  languageSearch, 
  setLanguageSearch, 
  toggleLanguage, 
  formatPaperCount,
  t 
}: LanguageSelectFilterProps) {
  const filteredLanguages = ALL_LANGUAGES.filter(lang => 
    lang.label.toLowerCase().includes(languageSearch.toLowerCase()) ||
    lang.id.toLowerCase().includes(languageSearch.toLowerCase()) ||
    lang.countries.toLowerCase().includes(languageSearch.toLowerCase())
  );

  return (
    <div className="space-y-2 pt-2 border-t border-app-divider">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-app-text flex items-center gap-1.5 truncate">
          <Globe size={13} className="text-blue-500 shrink-0" />
          <span className="truncate">
            {localFilter.languages.length ? t('filter.languagesCount').replace('{count}', localFilter.languages.length.toString()) : t('filter.languagesAll')}
          </span>
        </span>
      </div>

      {/* Search Language or Country Input */}
      <div className="relative">
        <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-app-text-dim" />
        <input
          type="text"
          placeholder={t('filter.searchLangPlaceholder')}
          value={languageSearch}
          onChange={(e) => setLanguageSearch(e.target.value)}
          className="w-full bg-app-input-surface border border-app-border rounded-lg pl-7 pr-2.5 py-1.5 text-[11.5px] text-app-text placeholder:text-app-text-dim focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Scrollable Language Grid */}
      <div className="grid grid-cols-2 gap-1.5 max-h-[160px] overflow-y-auto pr-0.5 custom-scrollbar">
        {filteredLanguages.filter(l => l.id !== "all").length === 0 ? (
          <div className="col-span-2 text-center text-xs text-app-text-dim py-3">
            {t('filter.noLangFound')}
          </div>
        ) : (
          filteredLanguages
            .filter(lang => lang.id !== "all")
            .map((lang) => {
              const isChecked = localFilter.languages.includes(lang.id);
              return (
                <button
                  key={lang.id}
                  type="button"
                  onClick={() => toggleLanguage(lang.id)}
                  className={
                    isChecked
                      ? "p-2 rounded-xl border text-left text-[11px] transition-all cursor-pointer flex items-center justify-between gap-1.5 bg-blue-600/20 border-blue-500/70 text-app-text font-medium shadow-sm"
                      : "p-2 rounded-xl border text-left text-[11px] transition-all cursor-pointer flex items-center justify-between gap-1.5 bg-app-item-hover border-app-border hover:bg-app-item-active text-app-text-muted hover:text-app-text"
                  }
                >
                  <div className="flex items-center gap-1.5 truncate min-w-0">
                    <span className="text-xs shrink-0">{lang.flag}</span>
                    <div className="truncate min-w-0 flex-1">
                      <div className="flex items-center gap-1 truncate">
                        <span className="truncate">{lang.label}</span>
                        {lang.papersCount !== undefined && (
                          <span className="text-[9.5px] text-app-text-dim font-mono shrink-0">
                            ({formatPaperCount(lang.papersCount)})
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                    isChecked ? "bg-blue-600 border-blue-500 text-white" : "border-app-border-strong bg-transparent"
                  }`}>
                    {isChecked && <Check size={10} strokeWidth={3} />}
                  </div>
                </button>
              );
            })
        )}
      </div>
    </div>
  );
}