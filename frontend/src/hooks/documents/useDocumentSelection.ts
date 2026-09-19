import { useState, useMemo } from "react";
import { Document } from "@/stores/documentStore";
import { getFileBadgeInfo } from "@/components/RightSidebar/DocumentReaderUtils";

export function useDocumentSelection(documents: Document[]) {
  const [selectedDocs, setSelectedDocs] = useState<Record<number, boolean>>({});
  
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [isSortMenuOpen, setIsSortMenuOpen] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState<number | null>(null);

  const selectedDocList = useMemo(() => documents.filter(doc => selectedDocs[doc.id] !== false), [documents, selectedDocs]);
  const selectedCount = selectedDocList.length;
  
  const isAllSelected = documents.length > 0 && selectedCount === documents.length;
  const isPartiallySelected = selectedCount > 0 && selectedCount < documents.length;

  const sortedDocuments = useMemo(() => {
    const docs = [...documents];
    docs.sort((a, b) => {
      let cmp = 0;
      if (sortBy === "title") {
        const titleA = (a.title || a.filename).toLowerCase();
        const titleB = (b.title || b.filename).toLowerCase();
        cmp = titleA.localeCompare(titleB);
      } else {
        const dateA = new Date(a.created_at || "").getTime();
        const dateB = new Date(b.created_at || "").getTime();
        cmp = dateA - dateB;
      }
      return sortDirection === "asc" ? cmp : -cmp;
    });
    return docs;
  }, [documents, sortBy, sortDirection]);

  const toggleDocSelection = (docId: number) => {
    setSelectedDocs(prev => {
      const current = prev[docId] !== undefined ? prev[docId] : true;
      return {
        ...prev,
        [docId]: !current
      };
    });
  };

  const handleToggleSelectAll = () => {
    if (documents.length === 0) return;
    if (isAllSelected || isPartiallySelected) {
      // Unselect all (explicitly set to false to override default true)
      const newSelection: Record<number, boolean> = {};
      documents.forEach(doc => { newSelection[doc.id] = false; });
      setSelectedDocs(newSelection);
    } else {
      // Select all (set to true)
      const newSelection: Record<number, boolean> = {};
      documents.forEach(doc => { newSelection[doc.id] = true; });
      setSelectedDocs(newSelection);
    }
  };

  return {
    selectedDocs, setSelectedDocs,
    sortBy, setSortBy,
    sortDirection, setSortDirection,
    isSortMenuOpen, setIsSortMenuOpen,
    activeMenuId, setActiveMenuId,
    selectedDocList, selectedCount,
    isAllSelected, isPartiallySelected,
    sortedDocuments,
    toggleDocSelection, handleToggleSelectAll,
    getFileBadgeInfo
  };
}