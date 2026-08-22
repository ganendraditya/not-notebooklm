"use client";

import { useState, useEffect } from "react";
import { 
  X, 
  HardDrive, 
  Cpu, 
  Trash2, 
  Sparkles, 
  AlertTriangle, 
  Check, 
  RefreshCw,
  Database,
  Layers,
  FileText,
  Sliders,
  Settings,
  Bell,
  Palette
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatSession } from "@/app/ChatClient";
import { useTranslation, languages } from "@/lib/i18n";
import StorageLibraryModal from "./StorageLibraryModal";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  backendUrl: string;
  sessions: ChatSession[];
  onChatsDeleted: (deletedIds: string[]) => void;
  onAllDataReset: () => void;
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
}

interface ModelItem {
  id: string;
  name: string;
  provider: string;
  model_name: string;
  description: string;
  active: boolean;
}

export default function SettingsModal({
  isOpen,
  onClose,
  backendUrl,
  sessions,
  onChatsDeleted,
  onAllDataReset,
}: SettingsModalProps) {
  const { t, language, setLanguage } = useTranslation();
  const [activeTab, setActiveTab] = useState<"general" | "storage" | "notifications" | "models" | "rag">("general");
  
  // Storage State
  const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);
  const [isLoadingStorage, setIsLoadingStorage] = useState(false);
  const [selectedChatIds, setSelectedChatIds] = useState<string[]>([]);
  const [isDeletingChats, setIsDeletingChats] = useState(false);
  const [isCleaningOrphans, setIsCleaningOrphans] = useState(false);
  const [cleanReport, setCleanReport] = useState<string | null>(null);
  
  // Reset Confirmation State
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [resetConfirmInput, setResetConfirmInput] = useState("");
  const [isResetting, setIsResetting] = useState(false);

  // Models State
  const [modelsList, setModelsList] = useState<ModelItem[]>([]);
  const [currentProvider, setCurrentProvider] = useState<string>("");
  const [isSwitchingModel, setIsSwitchingModel] = useState(false);
  const [modelToast, setModelToast] = useState<string | null>(null);

  // Library View State
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryCategory, setLibraryCategory] = useState<"all" | "files" | "images">("all");

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

  const fetchModels = async () => {
    try {
      const res = await fetch(`${backendUrl}/llm/models`);
      if (res.ok) {
        const data = await res.json();
        setModelsList(data.models || []);
        setCurrentProvider(data.current_provider || "");
      }
    } catch (e) {
      console.error("Failed to fetch models:", e);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStorage();
      fetchModels();
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

  const handleSelectProvider = async (provider: string, modelName?: string) => {
    if (isSwitchingModel) return;
    setIsSwitchingModel(true);
    try {
      const res = await fetch(`${backendUrl}/llm/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, model_name: modelName })
      });
      if (res.ok) {
        setCurrentProvider(provider);
        setModelToast(`Switched active provider to ${provider}`);
        setTimeout(() => setModelToast(null), 2500);
        fetchModels();
      }
    } catch (e) {
      console.error("Failed to select provider:", e);
    } finally {
      setIsSwitchingModel(false);
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
        className="bg-[#212124] border border-white/10 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-150"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#1b1c1e]">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-white">{t('settings.title')}</h2>
            {modelToast && (
              <span className="text-xs text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full animate-in fade-in">
                {modelToast}
              </span>
            )}
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body: Two-column layout with sidebar tabs */}
        <div className="flex flex-1 min-h-[420px] overflow-hidden">
          {/* Settings Left Tab Menu */}
          <div className="w-48 bg-[#18181b] border-r border-white/5 p-2 space-y-1 shrink-0">
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

            <button
              onClick={() => setActiveTab("models")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
                activeTab === "models" 
                  ? "bg-white/10 text-white shadow-sm" 
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
              }`}
            >
              <Cpu size={15} className={activeTab === "models" ? "text-blue-400" : "text-gray-400"} />
              <span>{t('settings.models')}</span>
            </button>

            <button
              onClick={() => setActiveTab("rag")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer ${
                activeTab === "rag" 
                  ? "bg-white/10 text-white shadow-sm" 
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
              }`}
            >
              <Sliders size={15} className={activeTab === "rag" ? "text-blue-400" : "text-gray-400"} />
              <span>{t('settings.rag')}</span>
            </button>
          </div>

          {/* Settings Tab Content */}
          <div className="flex-1 p-6 overflow-y-auto custom-scrollbar space-y-6">
            {/* TAB: GENERAL */}
            {activeTab === "general" && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-white">{t('settings.general')}</h3>
                </div>

                <div className="space-y-4">
                  {/* Appearance */}
                  <div className="flex items-center justify-between py-2 border-b border-white/5">
                    <span className="text-sm text-gray-200">{t('settings.appearance')}</span>
                    <select className="bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer">
                      <option value="system">{t('settings.appearance.system')}</option>
                      <option value="dark">{t('settings.appearance.dark')}</option>
                      <option value="light">{t('settings.appearance.light')}</option>
                    </select>
                  </div>

                  {/* Contrast */}
                  <div className="flex items-center justify-between py-2 border-b border-white/5">
                    <span className="text-sm text-gray-200">{t('settings.contrast')}</span>
                    <select className="bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer">
                      <option value="system">{t('settings.contrast.system')}</option>
                      <option value="default">{t('settings.contrast.default')}</option>
                      <option value="high">{t('settings.contrast.high')}</option>
                    </select>
                  </div>

                  {/* Accent Color */}
                  <div className="flex items-center justify-between py-2 border-b border-white/5">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-200">{t('settings.accent')}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                      <select className="bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer">
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
                  <div className="flex items-center justify-between py-2 border-b border-white/5">
                    <span className="text-sm text-gray-200">{t('settings.language')}</span>
                    <select 
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer max-w-[200px]"
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
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-white">{t('settings.notifications')}</h3>
                </div>

                <div className="space-y-4">
                  {/* Responses */}
                  <div className="flex items-start justify-between py-3 border-b border-white/5">
                    <div className="space-y-1 max-w-[70%]">
                      <h4 className="text-sm font-medium text-gray-200">{t('settings.notifications.responses')}</h4>
                      <p className="text-xs text-gray-400">{t('settings.notifications.responses.desc')}</p>
                    </div>
                    <select className="bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer">
                      <option value="push">{t('settings.notifications.push')}</option>
                      <option value="off">{t('settings.notifications.off')}</option>
                    </select>
                  </div>

                  {/* Tasks & Queue */}
                  <div className="flex items-start justify-between py-3 border-b border-white/5">
                    <div className="space-y-1 max-w-[70%]">
                      <h4 className="text-sm font-medium text-gray-200">{t('settings.notifications.tasks')}</h4>
                      <p className="text-xs text-gray-400">{t('settings.notifications.tasks.desc')}</p>
                    </div>
                    <select className="bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer">
                      <option value="push">{t('settings.notifications.push')}</option>
                      <option value="off">{t('settings.notifications.off')}</option>
                    </select>
                  </div>

                  {/* Downloads & Exports */}
                  <div className="flex items-start justify-between py-3 border-b border-white/5">
                    <div className="space-y-1 max-w-[70%]">
                      <h4 className="text-sm font-medium text-gray-200">{t('settings.notifications.downloads')}</h4>
                      <p className="text-xs text-gray-400">{t('settings.notifications.downloads.desc')}</p>
                    </div>
                    <select className="bg-[#18181b] border border-white/10 text-xs text-white rounded-lg px-3 py-1.5 outline-none cursor-pointer">
                      <option value="push">{t('settings.notifications.push')}</option>
                      <option value="off">{t('settings.notifications.off')}</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* TAB: STORAGE & MEDIA */}
            {activeTab === "storage" && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-white">{t('settings.storageOverview')}</h3>
                  <div className="mt-2 w-full bg-[#18181b] rounded-full h-4 overflow-hidden flex border border-white/10">
                    {storageSummary && (
                      <>
                        <div 
                          className="bg-blue-500 h-full" 
                          style={{ width: `${Math.max(1, ((storageSummary.used_bytes || 0) / (10240 * 1024 * 1024)) * 100)}%` }} 
                          title={t('settings.filesAndDocuments')}
                        ></div>
                        <div 
                          className="bg-indigo-500 h-full" 
                          style={{ width: `${Math.max(1, ((storageSummary.qdrant_bytes || 0) / (10240 * 1024 * 1024)) * 100)}%` }}
                          title="Vector DB"
                        ></div>
                        <div 
                          className="bg-purple-500 h-full" 
                          style={{ width: `${Math.max(1, ((storageSummary.database_bytes || 0) / (10240 * 1024 * 1024)) * 100)}%` }}
                          title="Database"
                        ></div>
                      </>
                    )}
                  </div>
                  <div className="flex justify-between text-[11px] text-gray-400 mt-1.5 px-1">
                    <span>
                      {storageSummary ? formatBytes(storageSummary.total_bytes) : "0 B"} {t('settings.used')}
                    </span>
                    <span>10.0 GB {t('settings.limit')} (SQLite)</span>
                  </div>
                </div>

                {/* Storage Cards */}
                {storageSummary ? (
                  <div className="grid grid-cols-2 gap-3">
                    <button 
                      onClick={() => {
                        setLibraryCategory("files");
                        setLibraryOpen(true);
                      }}
                      className="bg-[#18181b] border border-white/5 hover:border-white/20 hover:bg-white/5 transition-all rounded-xl p-4 text-left group flex flex-col justify-between min-h-[90px]"
                    >
                      <div className="flex items-center justify-between text-gray-400 text-xs">
                        <span className="group-hover:text-gray-200 transition-colors">{t('settings.filesAndDocuments')}</span>
                        <FileText size={14} className="text-blue-400" />
                      </div>
                      <div>
                        <div className="text-xl font-bold text-white mt-2">
                          {formatBytes(storageSummary.categories?.documents || 0)}
                        </div>
                        <div className="text-[11px] text-gray-500 mt-1">
                          {t('settings.clickToView')}
                        </div>
                      </div>
                    </button>

                    <button 
                      onClick={() => {
                        setLibraryCategory("images");
                        setLibraryOpen(true);
                      }}
                      className="bg-[#18181b] border border-white/5 hover:border-white/20 hover:bg-white/5 transition-all rounded-xl p-4 text-left group flex flex-col justify-between min-h-[90px]"
                    >
                      <div className="flex items-center justify-between text-gray-400 text-xs">
                        <span className="group-hover:text-gray-200 transition-colors">{t('settings.imagesAndMedia')}</span>
                        <Layers size={14} className="text-indigo-400" />
                      </div>
                      <div>
                        <div className="text-xl font-bold text-white mt-2">
                          {formatBytes(storageSummary.categories?.images || 0)}
                        </div>
                        <div className="text-[11px] text-gray-500 mt-1">
                          {t('settings.clickToView')}
                        </div>
                      </div>
                    </button>
                  </div>
                ) : (
                  <div className="text-xs text-gray-400 py-4 text-center">{t('settings.loadingStorage')}</div>
                )}

                {/* Maintenance Actions */}
                <div className="space-y-3 pt-2 border-t border-white/10">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-white">{t('settings.orphanCleanup')}</div>
                      <div className="text-[11px] text-gray-400">
                        {t('settings.orphanCleanupDesc')}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleCleanOrphans}
                      disabled={isCleaningOrphans}
                      className="text-xs border-white/10 text-gray-200 hover:bg-white/10 hover:text-white cursor-pointer h-8"
                    >
                      {isCleaningOrphans ? t('settings.cleaning') : t('settings.cleanOrphans')}
                    </Button>
                  </div>
                  {cleanReport && (
                    <div className="text-xs text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
                      {cleanReport}
                    </div>
                  )}
                </div>

                {/* Bulk Delete Chats */}
                <div className="space-y-3 pt-4 border-t border-white/10">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-white">{t('settings.batchDelete')}</div>
                      <div className="text-[11px] text-gray-400">
                        {t('settings.batchDeleteDesc')}
                      </div>
                    </div>
                    {selectedChatIds.length > 0 && (
                      <Button
                        size="sm"
                        onClick={handleBulkDeleteChats}
                        disabled={isDeletingChats}
                        className="text-xs bg-red-600 hover:bg-red-500 text-white cursor-pointer h-8"
                      >
                        {isDeletingChats ? t('settings.deleting') : `${t('settings.deleteSelected')} (${selectedChatIds.length})`}
                      </Button>
                    )}
                  </div>

                  {sessions.length > 0 ? (
                    <div className="bg-[#18181b] border border-white/5 rounded-xl p-2 max-h-40 overflow-y-auto custom-scrollbar space-y-1">
                      <div className="flex items-center justify-between px-2 py-1 border-b border-white/5 text-[11px] text-gray-400">
                        <span>{t('settings.selectAll')} ({sessions.length})</span>
                        <input 
                          type="checkbox"
                          checked={selectedChatIds.length === sessions.length && sessions.length > 0}
                          onChange={toggleSelectAllChats}
                          className="rounded cursor-pointer"
                        />
                      </div>
                      {sessions.map((s) => (
                        <label 
                          key={s.id} 
                          className="flex items-center justify-between px-2 py-1.5 rounded-lg hover:bg-white/5 text-xs text-gray-300 cursor-pointer"
                        >
                          <span className="truncate max-w-[340px]">{s.title}</span>
                          <input 
                            type="checkbox"
                            checked={selectedChatIds.includes(s.id)}
                            onChange={() => toggleChatSelection(s.id)}
                            className="rounded cursor-pointer"
                          />
                        </label>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400">{t('settings.noConversations')}</div>
                  )}
                </div>

                {/* Danger Zone: Factory Reset */}
                <div className="pt-4 border-t border-red-500/20 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-red-400">{t('settings.factoryReset')}</div>
                      <div className="text-[11px] text-gray-400">
                        {t('settings.factoryResetDesc')}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => setIsResetConfirmOpen(true)}
                      className="text-xs bg-red-950/60 text-red-400 border border-red-500/30 hover:bg-red-900 hover:text-white cursor-pointer h-8"
                    >
                      {t('settings.factoryReset')}
                    </Button>
                  </div>
                  
                  {isResetConfirmOpen && (
                    <div className="mt-3 p-3 bg-red-950/30 border border-red-500/20 rounded-xl space-y-3">
                      <p className="text-xs text-red-300">
                        {t('settings.dangerWarning')}
                      </p>
                      <input
                        type="text"
                        value={resetConfirmInput}
                        onChange={(e) => setResetConfirmInput(e.target.value)}
                        placeholder={t('settings.typeToConfirm').replace('{text}', 'reset-all-data')}
                        className="w-full bg-black/40 border border-red-500/30 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-red-500/60"
                      />
                      <div className="flex items-center justify-end gap-2">
                        <Button 
                          size="sm" 
                          variant="ghost" 
                          onClick={() => { setIsResetConfirmOpen(false); setResetConfirmInput(""); }}
                          className="h-7 text-xs text-gray-400 hover:text-white cursor-pointer"
                        >
                          {t('action.cancel')}
                        </Button>
                        <Button 
                          size="sm" 
                          onClick={handleFactoryReset}
                          disabled={resetConfirmInput.trim().toLowerCase() !== "reset-all-data" || isResetting}
                          className="h-7 text-xs bg-red-600 hover:bg-red-500 text-white cursor-pointer disabled:opacity-50"
                        >
                          {isResetting ? t('settings.resetting') : t('settings.resetNow')}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 2: MODELS & AI */}
            {activeTab === "models" && (
              <div className="space-y-5">
                <div>
                  <h3 className="text-sm font-semibold text-white">{t('settings.activeLlm')}</h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {t('settings.activeLlmDesc')}
                  </p>
                </div>

                <div className="space-y-2.5">
                  {modelsList.map((m) => {
                    const isActive = currentProvider.toLowerCase() === m.id.toLowerCase();
                    return (
                      <div
                        key={m.id}
                        onClick={() => handleSelectProvider(m.id, m.model_name)}
                        className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start justify-between gap-3 ${
                          isActive 
                            ? "bg-[#27282d] border-blue-500 shadow-md" 
                            : "bg-[#18181b] border-white/5 hover:border-white/15"
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-white">{m.name}</span>
                            {isActive && (
                              <span className="text-[10px] bg-blue-500/20 text-blue-400 font-medium px-2 py-0.5 rounded-full border border-blue-500/30 flex items-center gap-1">
                                <Check size={10} /> Active
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-gray-400 leading-relaxed">
                            {m.description}
                          </p>
                        </div>
                        <input
                          type="radio"
                          name="llm_provider"
                          checked={isActive}
                          onChange={() => handleSelectProvider(m.id, m.model_name)}
                          className="mt-1 cursor-pointer"
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* TAB 3: RAG PARAMETERS */}
            {activeTab === "rag" && (
              <div className="space-y-5">
                <div>
                  <h3 className="text-sm font-semibold text-white">{t('settings.retrievalGrounding')}</h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {t('settings.retrievalGroundingDesc')}
                  </p>
                </div>

                <div className="space-y-4 bg-[#18181b] border border-white/5 rounded-xl p-4">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-gray-200">{t('settings.citationThreshold')}</span>
                      <span className="text-gray-400">20% {t('settings.fuzzyMatch')}</span>
                    </div>
                    <p className="text-[11px] text-gray-400">
                      {t('settings.citationThresholdDesc')}
                    </p>
                  </div>

                  <div className="space-y-1.5 pt-3 border-t border-white/5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-gray-200">{t('settings.localEmbeddings')}</span>
                      <span className="text-emerald-400 font-mono">BAAI/bge-small-en-v1.5</span>
                    </div>
                    <p className="text-[11px] text-gray-400">
                      {t('settings.localEmbeddingsDesc')}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-white/10 bg-[#1b1c1e] flex justify-end">
          <Button
            size="sm"
            onClick={onClose}
            className="text-xs bg-white/10 hover:bg-white/15 text-white cursor-pointer px-4 h-8"
          >
            {t('settings.close')}
          </Button>
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
