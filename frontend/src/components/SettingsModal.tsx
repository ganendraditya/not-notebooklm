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
  const [isCleaningOrphans, setIsCleaningOrphans] = useState(false);
  const [cleanReport, setCleanReport] = useState<string | null>(null);
  
  // General Tab Settings State
  const [appearance, setAppearance] = useState<string>("system");
  const [contrast, setContrast] = useState<string>("default");
  const [accentColor, setAccentColor] = useState<string>("default");

  // Notifications State
  const [notifyResponses, setNotifyResponses] = useState<string>("push");
  const [notifyTasks, setNotifyTasks] = useState<string>("push");
  const [notifyDownloads, setNotifyDownloads] = useState<string>("push");

  // Reset to 'general' tab whenever the modal is reopened
  useEffect(() => {
    if (isOpen) {
      setActiveTab("general");
    }
  }, [isOpen]);

  // Load preferences from localStorage
  useEffect(() => {
    try {
      const savedAppearance = localStorage.getItem("notbooklm_appearance");
      if (savedAppearance) setAppearance(savedAppearance);

      const savedContrast = localStorage.getItem("notbooklm_contrast");
      if (savedContrast) setContrast(savedContrast);

      const savedAccent = localStorage.getItem("notbooklm_accent");
      if (savedAccent) setAccentColor(savedAccent);

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
    setAppearance(val);
    try { localStorage.setItem("notbooklm_appearance", val); } catch {}
  };

  const handleContrastChange = (val: string) => {
    setContrast(val);
    try { localStorage.setItem("notbooklm_contrast", val); } catch {}
  };

  const handleAccentChange = (val: string) => {
    setAccentColor(val);
    try { localStorage.setItem("notbooklm_accent", val); } catch {}
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

  const accentColorMap: Record<string, string> = {
    default: "bg-blue-500",
    blue: "bg-blue-500",
    violet: "bg-purple-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
    zinc: "bg-zinc-400"
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
    if (selectedChatIds.length === sessions.length) {
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
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-150"
    >
      <div 
        onClick={(e) => e.stopPropagation()}
        className="bg-[#212124] border border-white/10 rounded-2xl w-full max-w-2xl h-[580px] max-h-[85vh] shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#1b1c1e] shrink-0">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-white">{t('settings.title')}</h2>
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body: Two-column layout with sidebar tabs */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Settings Left Tab Menu */}
          <div className="w-48 bg-[#18181b] border-r border-white/5 p-2 space-y-1 shrink-0 overflow-y-auto custom-scrollbar">
            <button
              onClick={() => setActiveTab("general")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
                activeTab === "general" 
                  ? "bg-white/10 text-white shadow-sm" 
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
              }`}
            >
              <Settings size={15} className={activeTab === "general" ? "text-blue-400" : "text-gray-400"} />
              <span>{t('settings.general')}</span>
            </button>

            <button
              onClick={() => setActiveTab("storage")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
                activeTab === "storage" 
                  ? "bg-white/10 text-white shadow-sm" 
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
              }`}
            >
              <HardDrive size={15} className={activeTab === "storage" ? "text-blue-400" : "text-gray-400"} />
              <span>{t('settings.storage')}</span>
            </button>

            <button
              onClick={() => setActiveTab("notifications")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
                activeTab === "notifications" 
                  ? "bg-white/10 text-white shadow-sm" 
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
              }`}
            >
              <Bell size={15} className={activeTab === "notifications" ? "text-blue-400" : "text-gray-400"} />
              <span>{t('settings.notifications')}</span>
            </button>
          </div>

          {/* Settings Tab Content */}
          <div className="flex-1 p-6 overflow-y-auto custom-scrollbar min-h-0">
            {/* TAB: GENERAL */}
            {activeTab === "general" && (
              <div>
                <h3 className="text-sm font-semibold text-white">{t('settings.general')}</h3>

                <div className="divide-y divide-white/5 mt-4">
                  {/* Appearance */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <span className="min-w-0 flex-1 text-sm text-gray-200 truncate">{t('settings.appearance')}</span>
                    <select 
                      value={appearance}
                      onChange={(e) => handleAppearanceChange(e.target.value)}
                      className="shrink-0 w-44 bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                    >
                      <option value="system">{t('settings.appearance.system')}</option>
                      <option value="dark">{t('settings.appearance.dark')}</option>
                      <option value="light">{t('settings.appearance.light')}</option>
                    </select>
                  </div>

                  {/* Contrast */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <span className="min-w-0 flex-1 text-sm text-gray-200 truncate">{t('settings.contrast')}</span>
                    <select 
                      value={contrast}
                      onChange={(e) => handleContrastChange(e.target.value)}
                      className="shrink-0 w-44 bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                    >
                      <option value="system">{t('settings.contrast.system')}</option>
                      <option value="default">{t('settings.contrast.default')}</option>
                      <option value="high">{t('settings.contrast.high')}</option>
                    </select>
                  </div>

                  {/* Accent Color */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <span className="min-w-0 flex-1 text-sm text-gray-200 truncate">{t('settings.accent')}</span>
                    <div className="shrink-0 flex items-center gap-2">
                      <div className={`w-2.5 h-2.5 rounded-full ${accentColorMap[accentColor] || "bg-blue-500"} shrink-0`}></div>
                      <select 
                        value={accentColor}
                        onChange={(e) => handleAccentChange(e.target.value)}
                        className="w-44 bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                      >
                        <option value="default">{t('settings.accent.default')}</option>
                        <option value="blue">{t('settings.accent.blue')}</option>
                        <option value="violet">{t('settings.accent.violet')}</option>
                        <option value="emerald">{t('settings.accent.emerald')}</option>
                        <option value="amber">{t('settings.accent.amber')}</option>
                        <option value="rose">{t('settings.accent.rose')}</option>
                        <option value="zinc">{t('settings.accent.zinc')}</option>
                      </select>
                    </div>
                  </div>

                  {/* Language */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <span className="min-w-0 flex-1 text-sm text-gray-200 truncate">{t('settings.language')}</span>
                    <select 
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="shrink-0 w-44 bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer truncate"
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
                <h3 className="text-sm font-semibold text-white">{t('settings.notifications')}</h3>

                <div className="divide-y divide-white/5 mt-4">
                  {/* Responses */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <div className="min-w-0 flex-1 pr-2">
                      <h4 className="text-sm font-medium text-gray-200 truncate">{t('settings.notifications.responses')}</h4>
                      <p className="text-xs text-gray-400 mt-0.5 leading-relaxed break-words">{t('settings.notifications.responses.desc')}</p>
                    </div>
                    <select 
                      value={notifyResponses}
                      onChange={(e) => handleNotifyResponsesChange(e.target.value)}
                      className="shrink-0 w-44 bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                    >
                      <option value="push">{t('settings.notifications.push')}</option>
                      <option value="off">{t('settings.notifications.off')}</option>
                    </select>
                  </div>

                  {/* Tasks & Queue */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <div className="min-w-0 flex-1 pr-2">
                      <h4 className="text-sm font-medium text-gray-200 truncate">{t('settings.notifications.tasks')}</h4>
                      <p className="text-xs text-gray-400 mt-0.5 leading-relaxed break-words">{t('settings.notifications.tasks.desc')}</p>
                    </div>
                    <select 
                      value={notifyTasks}
                      onChange={(e) => handleNotifyTasksChange(e.target.value)}
                      className="shrink-0 w-44 bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer"
                    >
                      <option value="push">{t('settings.notifications.push')}</option>
                      <option value="off">{t('settings.notifications.off')}</option>
                    </select>
                  </div>

                  {/* Downloads & Exports */}
                  <div className="flex items-center justify-between gap-6 py-3">
                    <div className="min-w-0 flex-1 pr-2">
                      <h4 className="text-sm font-medium text-gray-200 truncate">{t('settings.notifications.downloads')}</h4>
                      <p className="text-xs text-gray-400 mt-0.5 leading-relaxed break-words">{t('settings.notifications.downloads.desc')}</p>
                    </div>
                    <select 
                      value={notifyDownloads}
                      onChange={(e) => handleNotifyDownloadsChange(e.target.value)}
                      className="shrink-0 w-44 bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer"
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
                <h3 className="text-sm font-semibold text-white">{t('settings.storage')}</h3>

                <div className="space-y-6 mt-4">
                  <div className="py-3">
                    <div className="text-xs text-gray-300 font-medium">
                      <span className="font-semibold text-white">
                        {storageSummary ? formatBytes(storageSummary.used_bytes || 0) : "0 B"}
                      </span>{" "}
                      of {storageSummary ? formatBytes(storageSummary.total_bytes) : "10.0 GB"} {t('settings.used')}
                    </div>
                    <div className="mt-2.5 w-full bg-[#18181b] rounded-full h-2.5 overflow-hidden flex border border-white/10">
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
                      <div className="text-sm font-semibold text-white">{t('settings.manageStorage')}</div>
                      <div className="text-xs text-gray-400 mt-0.5">{t('settings.manageStorageDesc')}</div>
                    </div>

                    <div className="divide-y divide-white/5">
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
                        className="w-full flex items-center justify-between py-3.5 px-0 hover:bg-white/[0.03] transition-colors text-left group cursor-pointer"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="text-sm text-gray-200 group-hover:text-white font-medium">
                            {t('settings.filesAndDocuments')}
                          </div>
                          <div className="text-xs text-gray-400 mt-0.5">
                            {storageSummary ? formatBytes(storageSummary.categories?.documents || 0) : "0 B"} • {t('settings.filesCount', { count: (storageSummary?.category_counts?.documents ?? 0).toString() })}
                          </div>
                        </div>
                        <ChevronRight size={16} className="text-gray-500 group-hover:text-gray-300 transition-colors shrink-0 ml-2" />
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
                        className="w-full flex items-center justify-between py-3.5 px-0 hover:bg-white/[0.03] transition-colors text-left group cursor-pointer"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="text-sm text-gray-200 group-hover:text-white font-medium">
                            {t('settings.imagesAndMedia')}
                          </div>
                          <div className="text-xs text-gray-400 mt-0.5">
                            {storageSummary ? formatBytes(storageSummary.categories?.images || 0) : "0 B"} • {t('settings.imagesCount', { count: (storageSummary?.category_counts?.images ?? 0).toString() })}
                          </div>
                        </div>
                        <ChevronRight size={16} className="text-gray-500 group-hover:text-gray-300 transition-colors shrink-0 ml-2" />
                      </button>
                    </div>
                  </div>

                  {/* Storage Actions Section */}
                  <div className="space-y-6 pt-1">
                    {/* Maintenance: Orphan Cleanup */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-6">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-200">{t('settings.orphanCleanup')}</div>
                          <div className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                            {t('settings.orphanCleanupDesc')}
                          </div>
                        </div>
                        <div className="w-36 shrink-0 flex justify-end">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={handleCleanOrphans}
                            disabled={isCleaningOrphans}
                            className="w-full text-xs border-white/10 text-gray-200 hover:bg-white/10 hover:text-white cursor-pointer h-8 whitespace-nowrap px-3"
                          >
                            {isCleaningOrphans ? t('settings.cleaning') : t('settings.cleanOrphans')}
                          </Button>
                        </div>
                      </div>
                      {cleanReport && (
                        <div className="text-xs text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
                          {cleanReport}
                        </div>
                      )}
                    </div>

                    {/* Bulk Delete Chats */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-6">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-200">{t('settings.batchDelete')}</div>
                          <div className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                            {t('settings.batchDeleteDesc')}
                          </div>
                        </div>
                        <div className="w-36 shrink-0 flex justify-end">
                          <Button
                            size="sm"
                            onClick={handleBulkDeleteChats}
                            disabled={selectedChatIds.length === 0 || isDeletingChats}
                            className={`w-full text-xs h-8 justify-center whitespace-nowrap px-3 transition-colors ${
                              selectedChatIds.length > 0
                                ? "bg-red-600 hover:bg-red-500 text-white cursor-pointer shadow-sm"
                                : "bg-white/5 border border-white/10 text-gray-500 cursor-not-allowed opacity-50"
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
                        <div className="border border-white/10 rounded-xl overflow-hidden divide-y divide-white/5 bg-transparent">
                          <div className="flex items-center justify-between px-3 py-2 bg-white/[0.02] text-xs font-medium text-gray-300">
                            <span>Conversations</span>
                            <div className="flex items-center shrink-0 pr-[8px]">
                              <input 
                                type="checkbox"
                                checked={selectedChatIds.length === sessions.length && sessions.length > 0}
                                onChange={toggleSelectAllChats}
                                className="rounded cursor-pointer accent-blue-500 shrink-0"
                              />
                            </div>
                          </div>
                          <div className="max-h-40 overflow-y-auto custom-scrollbar divide-y divide-white/5">
                            {sessions.map((s) => (
                              <label 
                                key={s.id} 
                                className="flex items-center justify-between px-3 py-2 hover:bg-white/5 text-xs text-gray-300 cursor-pointer transition-colors"
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
                        <div className="text-xs text-gray-400">{t('settings.noConversations')}</div>
                      )}
                    </div>

                    {/* Danger Zone: Factory Reset */}
                    <div className="space-y-2 pt-4">
                      <div className="flex items-center justify-between gap-6">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-red-400">{t('settings.factoryReset')}</div>
                          <div className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                            {t('settings.factoryResetDesc')}
                          </div>
                        </div>
                        <div className="w-36 shrink-0 flex justify-end">
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => setIsResetConfirmOpen(true)}
                            className="w-full text-xs bg-red-950/60 text-red-400 border border-red-500/30 hover:bg-red-900 hover:text-white cursor-pointer h-8 whitespace-nowrap px-3"
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

      {/* Confirmation Modal for Factory Reset */}
      {isResetConfirmOpen && (
        <div 
          onClick={(e) => e.stopPropagation()}
          className="fixed inset-0 z-60 flex items-center justify-center bg-black/80 p-4 animate-in fade-in duration-100"
        >
          <div className="bg-[#28292c] border border-red-500/30 rounded-2xl w-full max-w-sm p-5 shadow-2xl space-y-4">
            <div className="flex items-center gap-2.5 text-red-400 font-semibold text-sm">
              <AlertTriangle size={18} />
              <span>Confirm Factory Reset</span>
            </div>
            <p className="text-xs text-gray-300 leading-relaxed">
              This will permanently destroy all conversations, uploaded documents, and vector data.
              To confirm, type <span className="font-mono text-red-300 font-bold">reset-all-data</span> below:
            </p>
            <input
              type="text"
              value={resetConfirmInput}
              onChange={(e) => setResetConfirmInput(e.target.value)}
              placeholder="reset-all-data"
              className="w-full bg-[#18181b] border border-white/15 focus:border-red-500 rounded-xl px-3 py-2 text-xs text-white outline-none font-mono"
            />
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsResetConfirmOpen(false);
                  setResetConfirmInput("");
                }}
                className="text-xs text-gray-400 hover:text-white cursor-pointer h-8"
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
