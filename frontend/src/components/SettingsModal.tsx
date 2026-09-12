"use client";

import { useState, useEffect, useCallback } from "react";
import { 
  X, 
  HardDrive, 
  Settings, 
  Bell
} from "lucide-react";
import { ChatSession } from "@/stores/chatStore";
import { useTranslation } from "@/lib/i18n";
import { Tooltip } from "@/components/ui/tooltip";
import StorageLibraryModal from "./StorageLibraryModal";
import GeneralTab from "./Settings/tabs/GeneralTab";
import NotificationsTab from "./Settings/tabs/NotificationsTab";
import StorageTab, { type StorageSummary } from "./Settings/tabs/StorageTab";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  backendUrl: string;
  sessions: ChatSession[];
  onChatsDeleted: (deletedIds: string[]) => void;
  onAllDataReset: () => void;
  onNavigateToLibrary?: (category: "documents" | "images") => void;
}

export default function SettingsModal({
  isOpen,
  onClose,
  backendUrl,
  sessions,
  onChatsDeleted,
  onAllDataReset,
  onNavigateToLibrary,
}: SettingsModalProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"general" | "storage" | "notifications">("general");
  
    // Storage State
    const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);
    const [selectedChatIds, setSelectedChatIds] = useState<string[]>([]);
    const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  // Reset Confirmation State
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [resetConfirmInput, setResetConfirmInput] = useState("");

  // Library View State
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryCategory, setLibraryCategory] = useState<"all" | "documents" | "images">("all");

    // Reset state in the background when the modal is closed to prevent flickering on reopen
    useEffect(() => {
    if (!isOpen) {
      setActiveTab("general");
      setSelectedChatIds([]);
      setIsDeleteConfirmOpen(false);
      setIsResetConfirmOpen(false);
      setResetConfirmInput("");
    }
  }, [isOpen]);

  const fetchStorage = useCallback(async () => {
    try {
      const res = await fetch(`${backendUrl}/storage/summary`);
      if (res.ok) {
        const data = await res.json();
        setStorageSummary(data);
      }
    } catch (e) {
      console.error("Failed to fetch storage summary:", e);
    }
  }, [backendUrl]);

  useEffect(() => {
    if (isOpen) {
      fetchStorage();
    }
  }, [isOpen, fetchStorage]);

  if (!isOpen) return null;

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150 text-app-text"
      >
      <div 
        onClick={(e) => e.stopPropagation()}
        className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-2xl h-[580px] max-h-[85vh] shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-app-border bg-app-sidebar shrink-0">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-app-text">{t('settings.title')}</h2>
          </div>
          <Tooltip content={t('settings.close') || "Close"} side="bottom">
            <button 
              onClick={onClose}
              className="p-1 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer"
              aria-label={t('settings.close') || "Close"}
            >
              <X size={18} />
            </button>
          </Tooltip>
        </div>

        {/* Modal Body: Two-column layout with sidebar tabs */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Settings Left Tab Menu */}
          <div className="w-48 bg-app-sidebar border-r border-app-divider p-2 space-y-1 shrink-0 overflow-y-auto custom-scrollbar">
            <button
              onClick={() => setActiveTab("general")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
                activeTab === "general" 
                  ? "bg-app-item-active text-app-text shadow-sm" 
                  : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
              }`}
            >
              <Settings size={15} className={activeTab === "general" ? "text-blue-500" : "text-app-text-dim"} />
              <span>{t('settings.general')}</span>
            </button>

            <button
              onClick={() => setActiveTab("storage")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
                activeTab === "storage" 
                  ? "bg-app-item-active text-app-text shadow-sm" 
                  : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
              }`}
            >
              <HardDrive size={15} className={activeTab === "storage" ? "text-blue-500" : "text-app-text-dim"} />
              <span>{t('settings.storage')}</span>
            </button>

            <button
              onClick={() => setActiveTab("notifications")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
                activeTab === "notifications" 
                  ? "bg-app-item-active text-app-text shadow-sm" 
                  : "text-app-text-muted hover:bg-app-item-hover hover:text-app-text"
              }`}
            >
              <Bell size={15} className={activeTab === "notifications" ? "text-blue-500" : "text-app-text-dim"} />
              <span>{t('settings.notifications')}</span>
            </button>
          </div>

          {/* Settings Tab Content */}
          <div className="flex-1 p-6 overflow-y-auto custom-scrollbar min-h-0 bg-app-modal">
            {/* TAB: GENERAL */}
            {activeTab === "general" && <GeneralTab />}

            {/* TAB: NOTIFICATIONS */}
            {activeTab === "notifications" && <NotificationsTab />}

            {/* TAB: STORAGE & MEDIA */}
            {activeTab === "storage" && (
              <StorageTab
                backendUrl={backendUrl}
                sessions={sessions}
                onChatsDeleted={onChatsDeleted}
                onAllDataReset={onAllDataReset}
                onNavigateToLibrary={onNavigateToLibrary}
                onClose={onClose}
                setLibraryOpen={setLibraryOpen}
                setLibraryCategory={setLibraryCategory}
                isDeleteConfirmOpen={isDeleteConfirmOpen}
                setIsDeleteConfirmOpen={setIsDeleteConfirmOpen}
                isResetConfirmOpen={isResetConfirmOpen}
                setIsResetConfirmOpen={setIsResetConfirmOpen}
                resetConfirmInput={resetConfirmInput}
                setResetConfirmInput={setResetConfirmInput}
                selectedChatIds={selectedChatIds}
                setSelectedChatIds={setSelectedChatIds}
                storageSummary={storageSummary}
                fetchStorage={fetchStorage}
              />
            )}
          </div>
          </div>
        </div>
  
      {/* Storage Library View Overlay */}
      {libraryOpen && (
        <StorageLibraryModal
          isOpen={libraryOpen}
          onClose={() => {
            setLibraryOpen(false);
            fetchStorage(); // Refresh storage stats when closing library
          }}
          category={libraryCategory}
          backendUrl={backendUrl}
        />
      )}
    </div>
  );
}
