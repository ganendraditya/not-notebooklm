import { useEffect, useState } from "react";
import type { WorkspaceModel } from "@/stores/chatStore";

export const MODEL_PREFERENCES_KEY = "notbooklm:model-preferences";
const RECENT_LIMIT = 5;

interface ModelPreferences {
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

function readPreferences(): ModelPreferences {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(MODEL_PREFERENCES_KEY) || "null");
    if (value && typeof value === "object") {
      const stored = value as Partial<Record<keyof ModelPreferences, unknown>>;
      return { favorites: readKeys(stored.favorites), recent: readKeys(stored.recent).slice(0, RECENT_LIMIT) };
    }
  } catch {}
  return { favorites: [], recent: [] };
}

export function useModelPreferences() {
  const [preferences, setPreferences] = useState<ModelPreferences>({ favorites: [], recent: [] });
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setPreferences(readPreferences());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify(preferences));
    } catch {}
  }, [preferences, hydrated]);

  const toggleFavorite = (model: WorkspaceModel) => {
    const key = modelKey(model);
    setPreferences((previous) => ({
      ...previous,
      favorites: previous.favorites.includes(key)
        ? previous.favorites.filter((favorite) => favorite !== key)
        : [...previous.favorites, key],
    }));
  };

  const recordRecent = (model: WorkspaceModel) => {
    const key = modelKey(model);
    setPreferences((previous) => ({
      ...previous,
      recent: [key, ...previous.recent.filter((recent) => recent !== key)].slice(0, RECENT_LIMIT),
    }));
  };

  return { ...preferences, toggleFavorite, recordRecent };
}
