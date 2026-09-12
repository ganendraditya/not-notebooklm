import { create } from 'zustand';

export interface Document {
  id: number;
  filename: string;
  title?: string;
  doi?: string;
  created_at: string;
  index?: number;
  has_full_pdf?: boolean;
  is_oa?: boolean;
  content?: string;
}

export interface TargetedSource {
  id: number;
  filename: string;
  title?: string;
}

export interface CitationGroundingHighlight {
  docId: number;
  sentence: string;
  num?: number;
  citationKey?: string;
  aiQuotes?: string[];
  clickId?: number;
}

export interface PendingSourceItem {
  id: string;
  filename: string;
  type: "file" | "doi";
  doi?: string;
  status: "uploading" | "error";
  error?: string;
}

interface DocumentStore {
  documents: Document[];
  pendingSources: PendingSourceItem[];
  targetedSource: TargetedSource | null;
  viewingDoc: Document | null;
  groundingHighlight: CitationGroundingHighlight | null;

  setDocuments: (documents: Document[]) => void;
  setPendingSources: (sources: PendingSourceItem[]) => void;
  setTargetedSource: (source: TargetedSource | null) => void;
  setViewingDoc: (doc: Document | null) => void;
  setGroundingHighlight: (highlight: CitationGroundingHighlight | null) => void;
  
  addDocument: (doc: Document) => void;
  updateDocumentsList: (updater: (prev: Document[]) => Document[]) => void;
  updatePendingSourcesList: (updater: (prev: PendingSourceItem[]) => PendingSourceItem[]) => void;
  cancelPendingItem: (id: string) => void;
}

const cancelCallbacksMap = new Map<string, () => void>();

export const registerPendingCancelCallback = (id: string, cb: () => void) => {
  cancelCallbacksMap.set(id, cb);
};

export const unregisterPendingCancelCallback = (id: string) => {
  cancelCallbacksMap.delete(id);
};

export const useDocumentStore = create<DocumentStore>((set) => ({
  documents: [],
  pendingSources: [],
  targetedSource: null,
  viewingDoc: null,
  groundingHighlight: null,

  setDocuments: (documents) => set({ documents }),
  setPendingSources: (pendingSources) => set({ pendingSources }),
  setTargetedSource: (targetedSource) => set({ targetedSource }),
  setViewingDoc: (viewingDoc) => set({ viewingDoc }),
  setGroundingHighlight: (groundingHighlight) => set({ groundingHighlight }),
  
  addDocument: (doc) => set((state) => ({ documents: [...state.documents, doc] })),
  updateDocumentsList: (updater) => set((state) => ({ documents: updater(state.documents) })),
  updatePendingSourcesList: (updater) => set((state) => ({ pendingSources: updater(state.pendingSources) })),
  cancelPendingItem: (id: string) => {
    const cb = cancelCallbacksMap.get(id);
    if (cb) {
      try {
        cb();
      } catch (e) {
        console.error("Cancel callback error:", e);
      }
    }
    cancelCallbacksMap.delete(id);
    set((state) => ({ pendingSources: state.pendingSources.filter((p) => p.id !== id) }));
  }
}));