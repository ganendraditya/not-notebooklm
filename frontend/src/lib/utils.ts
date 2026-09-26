import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatExecutionDuration(seconds: number): string {
  const safeSec = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  if (safeSec < 60) {
    return `${safeSec}s`;
  }
  const mins = Math.floor(safeSec / 60);
  const remSec = safeSec % 60;
  return remSec === 0 ? `${mins}m` : `${mins}m ${remSec}s`;
}

export function formatDefaultSessionTitle(date: Date = new Date()): string {
  // Format: "New session 26-09-2026 21.25"
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `New session ${day}-${month}-${year} ${hours}.${minutes}`;
}
