"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle, ChevronRight, Check, Minus } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { ChatSession } from "@/stores/chatStore";
import { useTranslation } from "@/lib/i18n";

export interface StorageSummary {
  uploads_bytes?: number;
  uploads_count?: number;
  qdrant_bytes?: number;
  database_bytes?: number;
  total_bytes: number;
  used_bytes: number;
  file_count: number;
  categories: {
    images: number;
    documents: number;
    others: number;
  };
  category_counts?: {
    images: number;
    documents: number;
    others: number;
  };
}

interface StorageTabProps {
  backendUrl: string;
  sessions: ChatSession[];
  onChatsDeleted: (deletedIds: string[]) => void;
  onAllDataReset: () => void;
  onNavigateToLibrary?: (category: "documents" | "images") => void;
  onClose: () => void;
  setLibraryOpen: (open: boolean) => void;
  setLibraryCategory: (cat: "all" | "documents" | "images") => void;
  isDeleteConfirmOpen: boolean;
  setIsDeleteConfirmOpen: (open: boolean) => void;
  isResetConfirmOpen: boolean;
  setIsResetConfirmOpen: (open: boolean) => void;
  resetConfirmInput: string;
  setResetConfirmInput: (val: string) => void;
  selectedChatIds: string[];
  setSelectedChatIds: (ids: string[]) => void;
  storageSummary: StorageSummary | null;
  fetchStorage: () => void;
}

export default function StorageTab({
  backendUrl,
  sessions,
  onChatsDeleted,
  onAllDataReset,
  onNavigateToLibrary,
  onClose,
  setLibraryOpen,
  setLibraryCategory,
  isDeleteConfirmOpen,
  setIsDeleteConfirmOpen,
  isResetConfirmOpen,
  setIsResetConfirmOpen,
  resetConfirmInput,
  setResetConfirmInput,
  selectedChatIds,
  setSelectedChatIds,
  storageSummary,
  fetchStorage
}: StorageTabProps) {
  const { t } = useTranslation();

  const [isDeletingChats, setIsDeletingChats] = useState(false);
  const [isCleaningOrphans, setIsCleaningOrphans] = useState(false);
  const [cleanReport, setCleanReport] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const handleCleanOrphans = async () => {
    setIsCleaningOrphans(true);
    setCleanReport(null);
    try {
      const res = await fetch(`${backendUrl}/settings/storage/cleanup`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setCleanReport(`Cleaned ${data.deleted_files_count} orphan files (${formatBytes(data.freed_bytes)} freed)`);
        fetchStorage();
      }
    } catch (e) {
      console.error("Failed to clean orphan files:", e);
    } finally {
      setIsCleaningOrphans(false);
    }
  };

  const handleBulkDeleteChats = async () => {
    if (selectedChatIds.length === 0 || isDeletingChats) return;
    setIsDeletingChats(true);
    try {
      const res = await fetch(`${backendUrl}/chats/bulk-delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_ids: selectedChatIds })
      });
      if (res.ok) {
        onChatsDeleted(selectedChatIds);
        setSelectedChatIds([]);
        setIsDeleteConfirmOpen(false);
        fetchStorage();
      }
    } catch (e) {
      console.error("Failed to bulk delete chats:", e);
    } finally {
      setIsDeletingChats(false);
    }
  };

  const handleFactoryReset = async () => {
    if (resetConfirmInput.trim().toLowerCase() !== "reset-all-data" || isResetting) return;
    setIsResetting(true);
    try {
      const res = await fetch(`${backendUrl}/settings/storage/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm_text: "reset-all-data" })
      });
      if (res.ok) {
        setIsResetConfirmOpen(false);
        setResetConfirmInput("");
        onAllDataReset();
        onClose();
      }
    } catch (e) {
      console.error("Failed to factory reset:", e);
    } finally {
      setIsResetting(false);
    }
  };

  const toggleSelectAllChats = () => {
    if (selectedChatIds.length > 0) {
      setSelectedChatIds([]);
    } else {
      setSelectedChatIds(sessions.map(s => s.id));
    }
  };

  const toggleChatSelection = (id: string) => {
    setSelectedChatIds(
      selectedChatIds.includes(id) 
        ? selectedChatIds.filter(cId => cId !== id) 
        : [...selectedChatIds, id]
    );
  };

  return (
    <>
      <div>
        <h3 className="text-sm font-semibold text-app-text">{t('settings.storage')}</h3>

        <div className="space-y-6 mt-4">
          <div className="py-3">
            <div className="text-xs text-app-text-muted font-medium">
              <span className="font-semibold text-app-text">
                {storageSummary ? formatBytes(storageSummary.used_bytes || 0) : "0 B"}
              </span>{" "}
              of {storageSummary ? formatBytes(storageSummary.total_bytes) : "10.0 GB"} {t('settings.used')}
            </div>
            <div className="mt-2.5 w-full bg-app-input-surface rounded-full h-2.5 overflow-hidden flex border border-app-border">
              {storageSummary && (
                <>
                  <Tooltip content={t('settings.filesAndDocuments')} side="top">
                    <div 
                      className="bg-blue-500 h-full transition-all cursor-pointer" 
                      style={{ width: `${Math.max(1, ((storageSummary.used_bytes || 0) / (storageSummary.total_bytes || 10240 * 1024 * 1024)) * 100)}%` }} 
                      aria-label={t('settings.filesAndDocuments')}
                    />
                  </Tooltip>
                </>
              )}
            </div>
          </div>

          {/* Manage Storage Section */}
          <div>
            <div className="mb-2">
              <div className="text-sm font-semibold text-app-text">{t('settings.manageStorage')}</div>
              <div className="text-xs text-app-text-muted mt-0.5">{t('settings.manageStorageDesc')}</div>
            </div>

            <div className="divide-y divide-app-divider">
              {/* Files Row */}
              <button
                onClick={() => {
                  if (onNavigateToLibrary) {
                    onClose();
                    onNavigateToLibrary("documents");
                  } else {
                    setLibraryCategory("documents");
                    setLibraryOpen(true);
                  }
                }}
                className="w-full flex items-center justify-between py-3.5 px-0 hover:bg-app-item-hover transition-colors text-left group cursor-pointer"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-app-text font-medium">
                    {t('settings.filesAndDocuments')}
                  </div>
                  <div className="text-xs text-app-text-muted mt-0.5">
                    {storageSummary ? formatBytes(storageSummary.categories?.documents || 0) : "0 B"} • {t('settings.filesCount', { count: (storageSummary?.category_counts?.documents ?? 0).toString() })}
                  </div>
                </div>
                <ChevronRight size={16} className="text-app-text-dim group-hover:text-app-text transition-colors shrink-0 ml-2" />
              </button>

              {/* Images Row */}
              <button
                onClick={() => {
                  if (onNavigateToLibrary) {
                    onClose();
                    onNavigateToLibrary("images");
                  } else {
                    setLibraryCategory("images");
                    setLibraryOpen(true);
                  }
                }}
                className="w-full flex items-center justify-between py-3.5 px-0 hover:bg-app-item-hover transition-colors text-left group cursor-pointer"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-app-text font-medium">
                    {t('settings.imagesAndMedia')}
                  </div>
                  <div className="text-xs text-app-text-muted mt-0.5">
                    {storageSummary ? formatBytes(storageSummary.categories?.images || 0) : "0 B"} • {t('settings.imagesCount', { count: (storageSummary?.category_counts?.images ?? 0).toString() })}
                  </div>
                </div>
                <ChevronRight size={16} className="text-app-text-dim group-hover:text-app-text transition-colors shrink-0 ml-2" />
              </button>
            </div>
          </div>

          {/* Storage Actions Section */}
          <div className="space-y-6 pt-1">
            {/* Maintenance: Orphan Cleanup */}
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-6">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-app-text">{t('settings.orphanCleanup')}</div>
                  <div className="text-xs text-app-text-muted mt-0.5 leading-relaxed">
                    {t('settings.orphanCleanupDesc')}
                  </div>
                </div>
                <div className="w-36 shrink-0 flex justify-end">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleCleanOrphans}
                    disabled={isCleaningOrphans}
                    className="w-full text-xs border-app-border text-app-text hover:bg-app-item-hover cursor-pointer h-8 whitespace-nowrap px-3"
                  >
                    {isCleaningOrphans ? t('settings.cleaning') : t('settings.cleanOrphans')}
                  </Button>
                </div>
              </div>
              {cleanReport && (
                <div className="text-xs text-emerald-500 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
                  {cleanReport}
                </div>
              )}
            </div>

            {/* Bulk Delete Chats */}
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-6">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-app-text">{t('settings.batchDelete')}</div>
                  <div className="text-xs text-app-text-muted mt-0.5 leading-relaxed">
                    {t('settings.batchDeleteDesc')}
                  </div>
                </div>
                  <div className="w-36 shrink-0 flex justify-end">
                    <Button
                      size="sm"
                      onClick={() => setIsDeleteConfirmOpen(true)}
                      disabled={selectedChatIds.length === 0 || isDeletingChats}
                      className={`w-full text-xs h-8 justify-center whitespace-nowrap px-3 transition-colors ${
                        selectedChatIds.length > 0
                          ? "bg-red-600 hover:bg-red-500 text-white cursor-pointer shadow-sm"
                          : "bg-app-item-hover border border-app-border text-app-text-dim cursor-not-allowed opacity-50"
                      }`}
                    >
                    {isDeletingChats
                      ? t('settings.deleting')
                      : selectedChatIds.length > 0
                      ? `${t('settings.deleteSelected')} (${selectedChatIds.length})`
                      : t('settings.deleteSelected')}
                  </Button>
                </div>
              </div>

              {sessions.length > 0 ? (
                <div className="border border-app-border rounded-xl overflow-hidden bg-transparent">
                  {/* Fixed Header Row */}
                  <div className="flex items-center justify-between px-3 py-2 bg-app-surface text-xs font-medium text-app-text-muted border-b border-app-border select-none">
                    <span>Conversations</span>
                    {(() => {
                      const isAllChatsSelected = selectedChatIds.length === sessions.length && sessions.length > 0;
                      const isPartiallyChatsSelected = selectedChatIds.length > 0 && selectedChatIds.length < sessions.length;
                      return (
                        <div 
                          onClick={toggleSelectAllChats}
                          className="flex items-center gap-2 cursor-pointer group/selectall select-none"
                        >
                          <span className="text-[11px] font-medium text-app-text-muted group-hover/selectall:text-app-text transition-colors select-none">
                            {(isAllChatsSelected || isPartiallyChatsSelected) ? t('right.unselectAll') : t('settings.selectAll')}
                          </span>
                          <button 
                            type="button"
                            className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 cursor-pointer ${
                              isAllChatsSelected || isPartiallyChatsSelected
                                ? "bg-blue-600 border-blue-600 text-white hover:bg-blue-700"
                                : "border-app-border-strong bg-transparent group-hover/selectall:border-gray-500"
                            }`}
                            aria-label={(isAllChatsSelected || isPartiallyChatsSelected) ? t('right.unselectAll') : t('settings.selectAll')}
                          >
                            {isAllChatsSelected ? (
                              <Check size={9} strokeWidth={3} />
                            ) : isPartiallyChatsSelected ? (
                              <Minus size={9} strokeWidth={3} />
                            ) : null}
                          </button>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Scrollable Conversation Rows (Scrollbar strictly starts from header bottomline) */}
                  <div className="max-h-40 overflow-y-auto custom-scrollbar divide-y divide-app-divider">
                    {sessions.map((s) => {
                      const isSelected = selectedChatIds.includes(s.id);
                      return (
                        <div 
                          key={s.id} 
                          onClick={() => toggleChatSelection(s.id)}
                          className="flex items-center justify-between px-3 py-2 hover:bg-app-item-hover text-xs text-app-text cursor-pointer transition-colors select-none"
                        >
                          <span className="truncate pr-3">{s.title}</span>
                          <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors shrink-0 ${
                            isSelected ? "bg-blue-600 border-blue-600 text-white" : "border-app-border-strong bg-transparent"
                          }`}>
                            {isSelected && <Check size={9} strokeWidth={3} />}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-app-text-dim">{t('settings.noConversations')}</div>
              )}
            </div>

            {/* Danger Zone: Factory Reset */}
            <div className="space-y-2 pt-4">
              <div className="flex items-center justify-between gap-6">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-red-500">{t('settings.factoryReset')}</div>
                  <div className="text-xs text-app-text-muted mt-0.5 leading-relaxed">
                    {t('settings.factoryResetDesc')}
                  </div>
                </div>
                <div className="w-36 shrink-0 flex justify-end">
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => setIsResetConfirmOpen(true)}
                    className="w-full text-xs bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30 hover:bg-red-500/20 cursor-pointer h-8 whitespace-nowrap px-3"
                  >
                    {t('settings.factoryReset')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Modal for Bulk Delete */}
      {isDeleteConfirmOpen && (
        <div 
          onClick={(e) => {
            e.stopPropagation();
            setIsDeleteConfirmOpen(false);
          }}
          className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-100"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-app-modal border border-app-border-strong rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 text-app-text"
          >
            <div className="flex items-center gap-2.5 font-semibold text-sm">
              <AlertTriangle size={18} className="text-red-500" />
              <span>Confirm Deletion</span>
            </div>
            <p className="text-xs text-app-text-muted leading-relaxed">
              Are you sure you want to permanently delete {selectedChatIds.length} selected conversation{selectedChatIds.length > 1 ? 's' : ''}? 
              This will also remove all associated files and vector data.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-app-divider">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsDeleteConfirmOpen(false)}
                className="text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer h-8"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={isDeletingChats}
                onClick={handleBulkDeleteChats}
                className="text-xs bg-red-600 hover:bg-red-500 text-white font-medium cursor-pointer h-8"
              >
                {isDeletingChats ? t('settings.deleting') : t('settings.deleteSelected')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal for Factory Reset */}
      {isResetConfirmOpen && (
        <div 
          onClick={(e) => {
            e.stopPropagation();
            if (!isResetting) {
              setIsResetConfirmOpen(false);
              setResetConfirmInput("");
            }
          }}
          className="fixed inset-0 z-60 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-100"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-app-modal border border-red-500/30 rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4 text-app-text"
          >
          <div className="flex items-center gap-2.5 text-red-500 font-semibold text-sm">
            <AlertTriangle size={18} />
            <span>Confirm Factory Reset</span>
          </div>
          <p className="text-xs text-app-text-muted leading-relaxed">
            This will permanently destroy all conversations, uploaded documents, and vector data.
            To confirm, type <span className="font-mono text-red-500 font-bold">reset-all-data</span> below:
          </p>
          <input
            type="text"
            value={resetConfirmInput}
            onChange={(e) => setResetConfirmInput(e.target.value)}
            placeholder="reset-all-data"
            className="w-full bg-app-input-surface border border-app-border focus:border-red-500 rounded-xl px-3 py-2 text-xs text-app-text outline-none font-mono"
          />
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-app-divider">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setIsResetConfirmOpen(false);
                setResetConfirmInput("");
              }}
              className="text-xs text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer h-8"
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={resetConfirmInput.trim().toLowerCase() !== "reset-all-data" || isResetting}
              onClick={handleFactoryReset}
              className="text-xs bg-red-600 hover:bg-red-500 text-white font-medium cursor-pointer h-8"
            >
              {isResetting ? "Resetting..." : "Confirm & Reset All"}
            </Button>
          </div>
        </div>
      </div>
    )}
  </>
  );
}
