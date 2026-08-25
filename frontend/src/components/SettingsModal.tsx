"use client";

import { useState, useEffect } from "react";
import { 
  X, 
  HardDrive, 
  Trash2, 
  Sparkles, 
  AlertTriangle, 
  Check, 
  RefreshCw, 
  Database, 
  Layers, 
  FileText, 
  Settings, 
  Bell, 
  Palette,
  ChevronRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatSession } from "@/stores/chatStore";
import { useTranslation, languages } from "@/lib/i18n";
import StorageLibraryModal from "./StorageLibraryModal";

import { useTheme, type AppearanceMode } from "@/lib/theme";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  backendUrl: string;
  sessions: ChatSession[];
  onChatsDeleted: (deletedIds: string[]) => void;
  onAllDataReset: () => void;
  onNavigateToLibrary?: (category: "documents" | "images") => void;
}

interface StorageSummary {
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

export default function SettingsModal({
  isOpen,
  onClose,
  backendUrl,
  sessions,
  onChatsDeleted,
  onAllDataReset,
  onNavigateToLibrary,
}: SettingsModalProps) {
  const { t, language, setLanguage } = useTranslation();
  const [activeTab, setActiveTab] = useState<"general" | "storage" | "notifications">("general");
  
    // Storage State
    const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);
    const [isLoadingStorage, setIsLoadingStorage] = useState(false);
    const [selectedChatIds, setSelectedChatIds] = useState<string[]>([]);
    const [isDeletingChats, setIsDeletingChats] = useState(false);
    const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
    const [isCleaningOrphans, setIsCleaningOrphans] = useState(false);
  const [cleanReport, setCleanReport] = useState<string | null>(null);
  
  // General Tab Settings State from ThemeContext
  const { appearance, setAppearance } = useTheme();

  // Notifications State
  const [notifyResponses, setNotifyResponses] = useState<string>("push");
  const [notifyTasks, setNotifyTasks] = useState<string>("push");
  const [notifyDownloads, setNotifyDownloads] = useState<string>("push");

    // Reset state in the background when the modal is closed to prevent flickering on reopen
    useEffect(() => {
      if (!isOpen) {
        setActiveTab("general");
        setSelectedChatIds([]);
        setCleanReport(null);
        setIsDeleteConfirmOpen(false);
        setIsResetConfirmOpen(false);
        setResetConfirmInput("");
      }
    }, [isOpen]);

  // Load preferences from localStorage
  useEffect(() => {
    try {
      const savedNotifyResponses = localStorage.getItem("notbooklm_notify_responses");
      if (savedNotifyResponses) setNotifyResponses(savedNotifyResponses);

      const savedNotifyTasks = localStorage.getItem("notbooklm_notify_tasks");
      if (savedNotifyTasks) setNotifyTasks(savedNotifyTasks);

      const savedNotifyDownloads = localStorage.getItem("notbooklm_notify_downloads");
      if (savedNotifyDownloads) setNotifyDownloads(savedNotifyDownloads);
    } catch {
      // LocalStorage access denied/restricted
    }
  }, []);

  const handleAppearanceChange = (val: string) => {
    setAppearance(val as AppearanceMode);
  };

  const handleNotifyResponsesChange = (val: string) => {
    setNotifyResponses(val);
    try { localStorage.setItem("notbooklm_notify_responses", val); } catch {}
  };

  const handleNotifyTasksChange = (val: string) => {
    setNotifyTasks(val);
    try { localStorage.setItem("notbooklm_notify_tasks", val); } catch {}
  };

  const handleNotifyDownloadsChange = (val: string) => {
    setNotifyDownloads(val);
    try { localStorage.setItem("notbooklm_notify_downloads", val); } catch {}
  };

  // Reset Confirmation State
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [resetConfirmInput, setResetConfirmInput] = useState("");
  const [isResetting, setIsResetting] = useState(false);

  // Library View State
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryCategory, setLibraryCategory] = useState<"all" | "documents" | "images">("all");

  const fetchStorage = async () => {
    setIsLoadingStorage(true);
    try {
      const res = await fetch(`${backendUrl}/storage/summary`);
      if (res.ok) {
        const data = await res.json();
        setStorageSummary(data);
      }
    } catch (e) {
      console.error("Failed to fetch storage summary:", e);
    } finally {
      setIsLoadingStorage(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStorage();
    }
  }, [isOpen]);

  if (!isOpen) return null;

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
    setSelectedChatIds(prev => 
      prev.includes(id) ? prev.filter(cId => cId !== id) : [...prev, id]
    );
  };

    return (
      <div 
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-150 text-app-text"
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
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
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
            {activeTab === "general" && (
              <div>
                <h3 className="text-sm font-semibold text-app-text">{t('settings.general')}</h3>

                <div className="divide-y divide-app-divider mt-4">
                  {/* Appearance */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <span className="min-w-0 flex-1 text-sm text-app-text truncate">{t('settings.appearance')}</span>
                    <select 
                      value={appearance}
                      onChange={(e) => handleAppearanceChange(e.target.value)}
                      className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                    >
                      <option value="system">{t('settings.appearance.system')}</option>
                      <option value="dark">{t('settings.appearance.dark')}</option>
                      <option value="light">{t('settings.appearance.light')}</option>
                    </select>
                  </div>

                  {/* Language */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <span className="min-w-0 flex-1 text-sm text-app-text truncate">{t('settings.language')}</span>
                    <select 
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer truncate"
                    >
                      <option value="auto">{t('language.auto')}</option>
                      {languages.map(lang => (
                        <option key={lang.code} value={lang.code}>
                          {lang.name} ({lang.nativeName})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* TAB: NOTIFICATIONS */}
            {activeTab === "notifications" && (
              <div>
                <h3 className="text-sm font-semibold text-app-text">{t('settings.notifications')}</h3>

                <div className="divide-y divide-app-divider mt-4">
                  {/* Responses */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <div className="min-w-0 flex-1 pr-2">
                      <h4 className="text-sm font-medium text-app-text truncate">{t('settings.notifications.responses')}</h4>
                      <p className="text-xs text-app-text-muted mt-0.5 leading-relaxed break-words">{t('settings.notifications.responses.desc')}</p>
                    </div>
                    <select 
                      value={notifyResponses}
                      onChange={(e) => handleNotifyResponsesChange(e.target.value)}
                      className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                    >
                      <option value="push">{t('settings.notifications.push')}</option>
                      <option value="off">{t('settings.notifications.off')}</option>
                    </select>
                  </div>

                  {/* Tasks & Queue */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <div className="min-w-0 flex-1 pr-2">
                      <h4 className="text-sm font-medium text-app-text truncate">{t('settings.notifications.tasks')}</h4>
                      <p className="text-xs text-app-text-muted mt-0.5 leading-relaxed break-words">{t('settings.notifications.tasks.desc')}</p>
                    </div>
                    <select 
                      value={notifyTasks}
                      onChange={(e) => handleNotifyTasksChange(e.target.value)}
                      className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                    >
                      <option value="push">{t('settings.notifications.push')}</option>
                      <option value="off">{t('settings.notifications.off')}</option>
                    </select>
                  </div>

                  {/* Downloads & Exports */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <div className="min-w-0 flex-1 pr-2">
                      <h4 className="text-sm font-medium text-app-text truncate">{t('settings.notifications.downloads')}</h4>
                      <p className="text-xs text-app-text-muted mt-0.5 leading-relaxed break-words">{t('settings.notifications.downloads.desc')}</p>
                    </div>
                    <select 
                      value={notifyDownloads}
                      onChange={(e) => handleNotifyDownloadsChange(e.target.value)}
                      className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                    >
                      <option value="push">{t('settings.notifications.push')}</option>
                      <option value="off">{t('settings.notifications.off')}</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* TAB: STORAGE & MEDIA */}
            {activeTab === "storage" && (
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
                          <div 
                            className="bg-blue-500 h-full transition-all" 
                            style={{ width: `${Math.max(1, ((storageSummary.used_bytes || 0) / (storageSummary.total_bytes || 10240 * 1024 * 1024)) * 100)}%` }} 
                            title={t('settings.filesAndDocuments')}
                          ></div>
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
                        <div className="border border-app-border rounded-xl overflow-hidden divide-y divide-app-divider bg-transparent">
                            <div className="flex items-center justify-between px-3 py-2 bg-app-surface text-xs font-medium text-app-text-muted">
                              <span>Conversations</span>
                              <div className="flex items-center shrink-0 pr-[8px]">
                                <input 
                                  type="checkbox"
                                  checked={selectedChatIds.length === sessions.length && sessions.length > 0}
                                  ref={input => {
                                    if (input) {
                                      input.indeterminate = selectedChatIds.length > 0 && selectedChatIds.length < sessions.length;
                                    }
                                  }}
                                  onChange={toggleSelectAllChats}
                                  className="rounded cursor-pointer accent-blue-500 shrink-0"
                                />
                              </div>
                            </div>
                            <div className="max-h-40 overflow-y-auto custom-scrollbar divide-y divide-app-divider">
                            {sessions.map((s) => (
                              <label 
                                key={s.id} 
                                className="flex items-center justify-between px-3 py-2 hover:bg-app-item-hover text-xs text-app-text cursor-pointer transition-colors"
                              >
                                <span className="truncate pr-3">{s.title}</span>
                                <input 
                                  type="checkbox"
                                  checked={selectedChatIds.includes(s.id)}
                                  onChange={() => toggleChatSelection(s.id)}
                                  className="rounded cursor-pointer accent-blue-500 shrink-0"
                                />
                              </label>
                            ))}
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
            )}
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
