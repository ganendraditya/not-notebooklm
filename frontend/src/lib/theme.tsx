"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type AppearanceMode = "system" | "dark" | "light";

interface ThemeContextType {
  appearance: AppearanceMode;
  resolvedTheme: "dark" | "light";
  setAppearance: (mode: AppearanceMode) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  appearance: "system",
  resolvedTheme: "dark",
  setAppearance: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [appearance, setAppearanceState] = useState<AppearanceMode>("system");
  const [resolvedTheme, setResolvedTheme] = useState<"dark" | "light">("dark");

  const applyTheme = (mode: AppearanceMode) => {
    if (typeof window === "undefined") return;
    const isDark =
      mode === "dark" ||
      (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);

    const root = document.documentElement;
    if (isDark) {
      root.classList.add("dark");
      root.classList.remove("light");
      setResolvedTheme("dark");
    } else {
      root.classList.remove("dark");
      root.classList.add("light");
      setResolvedTheme("light");
    }
  };

  useEffect(() => {
    let initialMode: AppearanceMode = "system";
    try {
      const saved = localStorage.getItem("notbooklm_appearance") as AppearanceMode;
      if (saved === "dark" || saved === "light" || saved === "system") {
        initialMode = saved;
      }
    } catch {}

    setAppearanceState(initialMode);
    applyTheme(initialMode);

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      try {
        const current = (localStorage.getItem("notbooklm_appearance") as AppearanceMode) || "system";
        if (current === "system") {
          applyTheme("system");
        }
      } catch {
        applyTheme("system");
      }
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, []);

  const setAppearance = (mode: AppearanceMode) => {
    setAppearanceState(mode);
    try {
      localStorage.setItem("notbooklm_appearance", mode);
    } catch {}
    applyTheme(mode);
  };

  return (
    <ThemeContext.Provider value={{ appearance, resolvedTheme, setAppearance }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
