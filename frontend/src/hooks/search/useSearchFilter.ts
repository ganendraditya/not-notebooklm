import { useState, useEffect } from "react";
import { type SearchFilterState } from "@/lib/constants/academicFilters";

const sanitizeFilter = (raw: Partial<SearchFilterState> | undefined): SearchFilterState => ({
  yearFrom: raw?.yearFrom || "",
  yearTo: raw?.yearTo || "",
  minCitations: raw?.minCitations || "",
  languages: Array.isArray(raw?.languages) 
    ? raw.languages 
    : (raw as any)?.language && (raw as any).language !== "all" 
      ? [(raw as any).language] 
      : [],
  fieldsOfStudy: Array.isArray(raw?.fieldsOfStudy) ? raw.fieldsOfStudy : [],
  scopusQuartiles: Array.isArray(raw?.scopusQuartiles) ? raw.scopusQuartiles : [],
  sintaTiers: Array.isArray(raw?.sintaTiers) ? raw.sintaTiers : [],
  excludePreprints: !!raw?.excludePreprints,
  openAccessOnly: !!raw?.openAccessOnly,
});

export const calculateCount = (f: SearchFilterState | undefined) => {
  if (!f) return 0;
  return (
    (f.yearFrom || f.yearTo ? 1 : 0) +
    (f.minCitations && Number(f.minCitations) > 0 ? 1 : 0) +
    (f.languages?.length || 0) +
    (f.fieldsOfStudy?.length || 0) +
    (f.scopusQuartiles?.length || 0) +
    (f.sintaTiers?.length || 0) +
    (f.excludePreprints ? 1 : 0) +
    (f.openAccessOnly ? 1 : 0)
  );
};

export function useSearchFilter(initialFilter: SearchFilterState) {
  const [localFilter, setLocalFilter] = useState<SearchFilterState>(() => sanitizeFilter(initialFilter));

  // Sync local state on prop change
  useEffect(() => {
    setLocalFilter(sanitizeFilter(initialFilter));
  }, [initialFilter]);

  const toggleField = (fieldId: string) => {
    if (fieldId === "all") {
      setLocalFilter(prev => ({
        ...prev,
        fieldsOfStudy: []
      }));
      return;
    }

    setLocalFilter(prev => {
      const current = prev?.fieldsOfStudy || [];
      const exists = current.includes(fieldId);
      const next = exists 
        ? current.filter(f => f !== fieldId)
        : [...current.filter(f => f !== "all"), fieldId];
      return {
        ...prev,
        fieldsOfStudy: next
      };
    });
  };

  const toggleLanguage = (langId: string) => {
    if (langId === "all") {
      setLocalFilter(prev => ({
        ...prev,
        languages: []
      }));
      return;
    }

    setLocalFilter(prev => {
      const current = prev?.languages || [];
      const exists = current.includes(langId);
      const next = exists 
        ? current.filter(l => l !== langId)
        : [...current.filter(l => l !== "all"), langId];
      return {
        ...prev,
        languages: next
      };
    });
  };

  const toggleScopus = (qId: string) => {
    if (qId === "all") {
      setLocalFilter(prev => ({
        ...prev,
        scopusQuartiles: []
      }));
      return;
    }

    const scopusOrder = ["Q1", "Q2", "Q3", "Q4"];
    const targetIdx = scopusOrder.indexOf(qId);
    if (targetIdx === -1) return;

    setLocalFilter(prev => {
      const current = prev?.scopusQuartiles || [];
      const isExactSetSelected = 
        current.length === targetIdx + 1 && 
        scopusOrder.slice(0, targetIdx + 1).every(id => current.includes(id));

      if (isExactSetSelected) {
        return {
          ...prev,
          scopusQuartiles: []
        };
      }

      return {
        ...prev,
        scopusQuartiles: scopusOrder.slice(0, targetIdx + 1)
      };
    });
  };

  const toggleSinta = (sId: string) => {
    if (sId === "all") {
      setLocalFilter(prev => ({
        ...prev,
        sintaTiers: []
      }));
      return;
    }

    const sintaOrder = ["S1", "S2", "S3", "S4", "S5", "S6"];
    const targetIdx = sintaOrder.indexOf(sId);
    if (targetIdx === -1) return;

    setLocalFilter(prev => {
      const current = prev?.sintaTiers || [];
      const isExactSetSelected = 
        current.length === targetIdx + 1 && 
        sintaOrder.slice(0, targetIdx + 1).every(id => current.includes(id));

      if (isExactSetSelected) {
        return {
          ...prev,
          sintaTiers: []
        };
      }

      return {
        ...prev,
        sintaTiers: sintaOrder.slice(0, targetIdx + 1)
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

  return {
    localFilter,
    setLocalFilter,
    toggleField,
    toggleLanguage,
    toggleScopus,
    toggleSinta,
    setYearPreset
  };
}