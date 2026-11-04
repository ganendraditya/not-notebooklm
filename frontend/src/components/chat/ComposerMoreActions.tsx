"use client";

import type { RefObject } from "react";
import { Menu } from "@base-ui/react/menu";
import { Ellipsis, FileText, SlidersHorizontal } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

interface ComposerMoreActionsProps {
  triggerRef: RefObject<HTMLButtonElement | null>;
  filterCount: number;
  documentsCount: number;
  onOpenFilter: () => void;
  onToggleSources?: () => void;
}

export function ComposerMoreActions({
  triggerRef, filterCount, documentsCount, onOpenFilter, onToggleSources,
}: ComposerMoreActionsProps) {
  const { t } = useTranslation();
  const filterLabel = filterCount > 0 ? `${t("filter.button")} (${filterCount})` : t("filter.button");

  return (
    <Menu.Root>
      <Menu.Trigger
        ref={triggerRef}
        aria-label={filterCount > 0 ? `${t("chat.moreActions")}, ${filterLabel}` : t("chat.moreActions")}
        title={t("chat.moreActions")}
        className="relative flex h-11 w-11 sm:h-8 sm:w-8 pointer-coarse:h-11 pointer-coarse:w-11 shrink-0 items-center justify-center rounded-full text-app-text-muted hover:bg-app-item-hover hover:text-app-text data-popup-open:bg-app-item-hover cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-text"
      >
        <Ellipsis size={18} aria-hidden="true" />
        {filterCount > 0 && <span aria-hidden="true" className="absolute -right-1 -top-1 rounded-full bg-blue-600 px-1.5 text-[10px] font-semibold text-white">{filterCount}</span>}
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner side="top" align="end" sideOffset={8} collisionPadding={12} className="z-50">
          <Menu.Popup className="min-w-48 max-w-[calc(100vw-24px)] rounded-xl border border-app-border-strong bg-app-dropdown p-1.5 text-app-text shadow-lg focus-visible:outline-2 focus-visible:outline-app-text">
            <Menu.Item
              onClick={onOpenFilter}
              className="flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer data-highlighted:bg-app-item-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-app-text"
            >
              <SlidersHorizontal size={16} aria-hidden="true" />{filterLabel}
            </Menu.Item>
            <Menu.Item
              onClick={onToggleSources}
              disabled={!onToggleSources}
              className="flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer data-highlighted:bg-app-item-hover data-disabled:opacity-50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-app-text"
            >
              <FileText size={16} aria-hidden="true" />{t("chat.sourcesCount", { count: String(documentsCount) })}
            </Menu.Item>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
