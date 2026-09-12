import { Calendar } from "lucide-react";
import { type SearchFilterState } from "@/lib/constants/academicFilters";

interface YearRangeFilterProps {
  localFilter: SearchFilterState;
  setLocalFilter: React.Dispatch<React.SetStateAction<SearchFilterState>>;
  setYearPreset: (from: string, to: string) => void;
  t: (key: string) => string;
}

export default function YearRangeFilter({ localFilter, setLocalFilter, setYearPreset, t }: YearRangeFilterProps) {
  const currentYear = new Date().getFullYear();
  const y3 = String(currentYear - 3);
  const y5 = String(currentYear - 5);
  const y10 = String(currentYear - 10);
  const yCurrent = String(currentYear);

  const is3Selected = localFilter.yearFrom === y3 && localFilter.yearTo === yCurrent;
  const is5Selected = localFilter.yearFrom === y5 && localFilter.yearTo === yCurrent;
  const is10Selected = localFilter.yearFrom === y10 && localFilter.yearTo === yCurrent;

  return (
    <div className="space-y-2">
      <span className="text-xs font-semibold text-app-text flex items-center gap-1.5">
        <Calendar size={13} className="text-blue-500" />
        {t('filter.year')}
      </span>

      <div className="grid grid-cols-3 gap-1.5 text-[11px]">
        <button
          type="button"
          onClick={() => setYearPreset(is3Selected ? "" : y3, is3Selected ? "" : yCurrent)}
          className={
            is3Selected
              ? "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-app-text font-medium shadow-sm"
              : "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-app-item-hover border-app-border hover:bg-app-item-active text-app-text-muted hover:text-app-text"
          }
        >
          {t('filter.past3years')}
        </button>
        <button
          type="button"
          onClick={() => setYearPreset(is5Selected ? "" : y5, is5Selected ? "" : yCurrent)}
          className={
            is5Selected
              ? "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-app-text font-medium shadow-sm"
              : "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-app-item-hover border-app-border hover:bg-app-item-active text-app-text-muted hover:text-app-text"
          }
        >
          {t('filter.past5years')}
        </button>
        <button
          type="button"
          onClick={() => setYearPreset(is10Selected ? "" : y10, is10Selected ? "" : yCurrent)}
          className={
            is10Selected
              ? "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-blue-600/30 border-blue-500 text-app-text font-medium shadow-sm"
              : "py-1 px-2 rounded-lg border text-center transition-colors cursor-pointer bg-app-item-hover border-app-border hover:bg-app-item-active text-app-text-muted hover:text-app-text"
          }
        >
          {t('filter.past10years')}
        </button>
      </div>

      <div className="flex items-center gap-2 pt-1">
        <input
          type="number"
          placeholder={t('filter.from')}
          value={localFilter.yearFrom}
          onChange={(e) => setLocalFilter(prev => ({ ...prev, yearFrom: e.target.value }))}
          className="w-full bg-app-input-surface border border-app-border rounded-lg px-2.5 py-1.5 text-xs text-app-text placeholder:text-app-text-dim focus:outline-none focus:border-blue-500"
        />
        <span className="text-app-text-dim text-xs">-</span>
        <input
          type="number"
          placeholder={t('filter.to')}
          value={localFilter.yearTo}
          onChange={(e) => setLocalFilter(prev => ({ ...prev, yearTo: e.target.value }))}
          className="w-full bg-app-input-surface border border-app-border rounded-lg px-2.5 py-1.5 text-xs text-app-text placeholder:text-app-text-dim focus:outline-none focus:border-blue-500"
        />
      </div>
    </div>
  );
}
