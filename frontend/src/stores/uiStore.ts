import { create } from 'zustand';

type ViewState = "chat" | "library" | "search";
type LibraryCategory = "all" | "documents" | "images";

interface UIStore {
  isSettingsOpen: boolean;
  currentView: ViewState;
  libraryInitialCategory: LibraryCategory;

  setIsSettingsOpen: (isOpen: boolean) => void;
  setCurrentView: (view: ViewState) => void;
  setLibraryInitialCategory: (category: LibraryCategory) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  isSettingsOpen: false,
  currentView: "chat",
  libraryInitialCategory: "all",

  setIsSettingsOpen: (isSettingsOpen) => set({ isSettingsOpen }),
  setCurrentView: (currentView) => set({ currentView }),
  setLibraryInitialCategory: (libraryInitialCategory) => set({ libraryInitialCategory })
}));