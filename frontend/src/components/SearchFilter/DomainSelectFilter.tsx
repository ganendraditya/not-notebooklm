import { Search, GraduationCap, Check } from "lucide-react";
import { type SearchFilterState, OPENALEX_DOMAINS } from "@/lib/constants/academicFilters";

interface DomainSelectFilterProps {
  localFilter: SearchFilterState;
  domainSearch: string;
  setDomainSearch: (val: string) => void;
  toggleField: (fieldId: string) => void;
  t: (key: string) => string;
}

export default function DomainSelectFilter({ localFilter, domainSearch, setDomainSearch, toggleField, t }: DomainSelectFilterProps) {
  const filteredDomains = OPENALEX_DOMAINS.filter(d => 
    d.label.toLowerCase().includes(domainSearch.toLowerCase()) ||
    d.id.toLowerCase().includes(domainSearch.toLowerCase())
  );

  return (
    <div className="space-y-2 pt-2 border-t border-app-divider">
      <span className="text-xs font-semibold text-app-text flex items-center gap-1.5">
        <GraduationCap size={13} className="text-blue-500" />
        {localFilter.fieldsOfStudy.length ? t('filter.fieldsCount').replace('{count}', localFilter.fieldsOfStudy.length.toString()) : t('filter.fieldsAll')}
      </span>

      {/* Search Domain Input */}
      <div className="relative">
        <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-app-text-dim" />
        <input
          type="text"
          placeholder={t('filter.searchFieldPlaceholder')}
          value={domainSearch}
          onChange={(e) => setDomainSearch(e.target.value)}
          className="w-full bg-app-input-surface border border-app-border rounded-lg pl-7 pr-2.5 py-1.5 text-[11.5px] text-app-text placeholder:text-app-text-dim focus:outline-none focus:border-blue-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-1.5 max-h-[160px] overflow-y-auto pr-0.5 custom-scrollbar">
        {filteredDomains.length === 0 ? (
          <div className="col-span-2 text-center text-xs text-app-text-dim py-3">
            {t('filter.noFieldFound')}
          </div>
        ) : (
          filteredDomains.map((f) => {
            const isChecked = localFilter.fieldsOfStudy.includes(f.id);
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => toggleField(f.id)}
                className={
                  isChecked 
                    ? "p-2 rounded-xl border text-left text-[11px] transition-all cursor-pointer flex items-center justify-between gap-1.5 bg-blue-600/20 border-blue-500/70 text-app-text font-medium shadow-sm"
                    : "p-2 rounded-xl border text-left text-[11px] transition-all cursor-pointer flex items-center justify-between gap-1.5 bg-app-item-hover border-app-border hover:bg-app-item-active text-app-text-muted hover:text-app-text"
                }
              >
                <div className="flex items-center gap-1.5 truncate">
                  <span className="text-xs">{f.icon}</span>
                  <span className="truncate">{t(`filter.field.${f.id}`) || f.label}</span>
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