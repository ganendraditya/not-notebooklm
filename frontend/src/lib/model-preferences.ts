import { useChatStore, type WorkspaceModel } from "@/stores/chatStore";

export const MODEL_PREFERENCES_KEY = "notbooklm:model-preferences";
export const RECENT_MODEL_LIMIT = 5;

export interface ModelPreferences {
  favorites: string[];
  recent: string[];
}

export function modelKey(model: Pick<WorkspaceModel, "id" | "profile_id">): string {
  return JSON.stringify([model.profile_id, model.id]);
}

function readKeys(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((key): key is string => typeof key === "string"))];
}

export function readModelPreferences(): ModelPreferences {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(MODEL_PREFERENCES_KEY) || "null");
    if (value && typeof value === "object") {
      const stored = value as Partial<Record<keyof ModelPreferences, unknown>>;
      return { favorites: readKeys(stored.favorites), recent: readKeys(stored.recent).slice(0, RECENT_MODEL_LIMIT) };
    }
  } catch {}
  return { favorites: [], recent: [] };
}

export function recordModelSelection(model: WorkspaceModel): void {
  const key = modelKey(model);
  useChatStore.getState().setLastSelectedModelKey(key);
  const preferences = readModelPreferences();
  const recent = [key, ...preferences.recent.filter((item) => item !== key)].slice(0, RECENT_MODEL_LIMIT);
  try {
    localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify({ ...preferences, recent }));
  } catch {}
}
