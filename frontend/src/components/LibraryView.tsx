"use client";

import { Sidebar } from "lucide-react";
import { Button } from "@/components/ui/button";
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
        <Tooltip content={t("ui.openSidebar")} side="bottom">
          <Button
            variant="ghost"
            size="icon"
            className={`h-8 w-8 text-app-text-muted hover:text-app-text hover:bg-app-item-hover cursor-pointer mr-1 ${isSidebarOpen ? "hidden" : "flex"}`}
            onClick={onOpenSidebar}
            aria-label={t("ui.openSidebar")}
          >
            <Sidebar size={18} />
          </Button>
        </Tooltip>
      }
    />
  );
}
