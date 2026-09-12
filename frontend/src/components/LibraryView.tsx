"use client";

import { Sidebar } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { useTranslation } from "@/lib/i18n";
import LibraryBrowser, { type LibraryItem } from "@/components/library/LibraryBrowser";

export type { LibraryItem };

interface LibraryViewProps {
  initialCategory?: "all" | "documents" | "images";
  backendUrl: string;
  isSidebarOpen: boolean;
  onOpenSidebar: () => void;
  onSelectChat?: (chatId: string) => void;
}

export default function LibraryView({
  initialCategory = "all",
  backendUrl,
  isSidebarOpen,
  onOpenSidebar,
  onSelectChat
}: LibraryViewProps) {
  const { t } = useTranslation();

  return (
    <LibraryBrowser
      initialCategory={initialCategory}
      backendUrl={backendUrl}
      onSelectChat={onSelectChat}
      containerClassName="flex-1 flex flex-col h-full bg-app-bg text-app-text relative overflow-hidden"
      headerLeading={
        !isSidebarOpen && onOpenSidebar ? (
          <Tooltip content={t("chat.openSidebar")} side="bottom">
            <button
              type="button"
              className="w-7 h-7 text-app-text-muted hover:text-app-text hover:bg-app-item-hover rounded-lg cursor-pointer flex items-center justify-center transition-colors hidden lg:flex"
              onClick={onOpenSidebar}
              aria-label={t("chat.openSidebar")}
            >
              <Sidebar size={15} />
            </button>
          </Tooltip>
        ) : null
      }
    />
  );
}
