"use client";

import * as React from "react";
import { Tooltip as BaseTooltip } from "@base-ui/react";
import { cn } from "@/lib/utils";

export interface TooltipProps {
  content?: React.ReactNode;
  children: React.ReactElement;
  side?: "top" | "bottom" | "left" | "right";
  sideOffset?: number;
  align?: "start" | "center" | "end";
  className?: string;
  delay?: number;
  disabled?: boolean;
}

/**
 * Universal, accessible, floating-ui based Tooltip for Not-NotebookLM.
 * Provides consistent styling across the entire system.
 */
export function Tooltip({
  content,
  children,
  side = "top",
  sideOffset = 6,
  align = "center",
  className,
  delay = 200,
  disabled = false,
}: TooltipProps) {
  if (!content || disabled) {
    return children;
  }

  const trigger = React.isValidElement(children) ? (
    <BaseTooltip.Trigger render={children} />
  ) : (
    <BaseTooltip.Trigger>{children}</BaseTooltip.Trigger>
  );

  return (
    <BaseTooltip.Provider delay={delay} closeDelay={80}>
      <BaseTooltip.Root disabled={disabled}>
        {trigger}
        <BaseTooltip.Portal>
          <BaseTooltip.Positioner
            side={side}
            sideOffset={sideOffset}
            align={align}
            className="z-[9999] pointer-events-none"
          >
            <BaseTooltip.Popup
              className={cn(
                "px-2.5 py-1 text-[11px] font-medium text-white bg-neutral-900/95 dark:bg-neutral-800/95 backdrop-blur-xs border border-white/10 rounded-md shadow-lg transition-opacity duration-150 select-none whitespace-nowrap leading-none",
                className
              )}
            >
              {content}
            </BaseTooltip.Popup>
          </BaseTooltip.Positioner>
        </BaseTooltip.Portal>
      </BaseTooltip.Root>
    </BaseTooltip.Provider>
  );
}
