"use client";

import { ArrowLeft, X } from "lucide-react";
import { useTranslation } from "@/lib/i18n";
import LibraryBrowser from "@/components/library/LibraryBrowser";

interface StorageLibraryModalProps {
  isOpen: boolean;
  onClose: () => void;
  category: "all" | "documents" | "images";
  backendUrl: string;
  onSelectChat?: (chatId: string) => void;
}

export default function StorageLibraryModal({
  isOpen,
  onClose,
  category: initialCategory,
  backendUrl,
  onSelectChat
}: StorageLibraryModalProps) {
  const { t } = useTranslation();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-app-bg text-app-text animate-in fade-in duration-200">
      <LibraryBrowser
        key={String(isOpen)}
        initialCategory={initialCategory}
        backendUrl={backendUrl}
        onSelectChat={onSelectChat}
        onItemChatSelect={onClose}
        containerClassName="flex-1 flex flex-col h-full bg-app-bg text-app-text relative overflow-hidden"
        headerLeading={
          <button 
            onClick={onClose} 
            className="p-1.5 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer"
            title={t("ui.back")}
          >
            <ArrowLeft size={18} />
          </button>
        }
        headerTrailing={
          <button 
            onClick={onClose} 
            className="p-1.5 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer"
            title={t("settings.close")}
          >
            <X size={18} />
          </button>
        }
      />
    </div>
  );
}
