import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getSystemTranslation,
  setGlobalLanguage,
  registerLoadedLocale,
} from "../lib/i18n";
import { sendSystemNotification } from "../lib/notifications";
import idLocale from "../lib/i18n/locales/id.json";

describe("Notifications & i18n Localization", () => {
  beforeEach(() => {
    // Reset language to English and register Indonesian locale
    setGlobalLanguage("en");
    registerLoadedLocale("id", idLocale as Record<string, string>);
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.clear();
      }
    } catch {}
  });

  describe("getSystemTranslation", () => {
    it("translates notification title and body in English", () => {
      setGlobalLanguage("en");
      expect(getSystemTranslation("notify.responseCompleteTitle")).toBe("NotbookLM: Response Ready");
      expect(getSystemTranslation("notify.responseCompleteBody")).toBe("AI has finished generating your response.");
      expect(getSystemTranslation("notify.downloadCompleteTitle")).toBe("NotbookLM: Download Complete");
    });

    it("translates notification title and body in Indonesian", () => {
      setGlobalLanguage("id");
      expect(getSystemTranslation("notify.responseCompleteTitle")).toBe("NotbookLM: Jawaban Selesai");
      expect(getSystemTranslation("notify.responseCompleteBody")).toBe("AI telah selesai menyusun jawaban Anda.");
      expect(getSystemTranslation("notify.downloadCompleteTitle")).toBe("NotbookLM: Unduhan Selesai");
    });

    it("interpolates variables in notification templates correctly", () => {
      setGlobalLanguage("en");
      const enBody = getSystemTranslation("notify.downloadCompleteBody", { count: "5" });
      expect(enBody).toBe("ZIP archive ready for download (5 documents).");

      setGlobalLanguage("id");
      const idBody = getSystemTranslation("notify.downloadCompleteBody", { count: "12" });
      expect(idBody).toBe("Arsip ZIP siap diunduh (12 dokumen).");
    });

    it("falls back to English when a key does not exist in the requested language", () => {
      setGlobalLanguage("id");
      // Use an English fallback text or unmapped key
      const fallback = getSystemTranslation("nonexistent.key", undefined, "Default Fallback");
      expect(fallback).toBe("Default Fallback");
    });
  });

  describe("sendSystemNotification", () => {
    it("dispatches native browser notification with localized title and body in English", () => {
      setGlobalLanguage("en");

      const notificationSpy = vi.fn();
      (window as any).Notification = notificationSpy;
      (window as any).Notification.permission = "granted";

      sendSystemNotification({
        category: "responses",
        titleKey: "notify.responseCompleteTitle",
        bodyKey: "notify.responseCompleteBody",
        force: true,
      });

      expect(notificationSpy).toHaveBeenCalledWith(
        "NotbookLM: Response Ready",
        expect.objectContaining({
          body: "AI has finished generating your response.",
        })
      );
    });

    it("dispatches native browser notification with localized title and body in Indonesian", () => {
      setGlobalLanguage("id");

      const notificationSpy = vi.fn();
      (window as any).Notification = notificationSpy;
      (window as any).Notification.permission = "granted";

      sendSystemNotification({
        category: "responses",
        titleKey: "notify.responseCompleteTitle",
        bodyKey: "notify.responseCompleteBody",
        force: true,
      });

      expect(notificationSpy).toHaveBeenCalledWith(
        "NotbookLM: Jawaban Selesai",
        expect.objectContaining({
          body: "AI telah selesai menyusun jawaban Anda.",
        })
      );
    });

    it("formats download notification with variable interpolation", () => {
      setGlobalLanguage("id");

      const notificationSpy = vi.fn();
      (window as any).Notification = notificationSpy;
      (window as any).Notification.permission = "granted";

      sendSystemNotification({
        category: "downloads",
        titleKey: "notify.downloadCompleteTitle",
        bodyKey: "notify.downloadCompleteBody",
        variables: { count: "8" },
        force: true,
      });

      expect(notificationSpy).toHaveBeenCalledWith(
        "NotbookLM: Unduhan Selesai",
        expect.objectContaining({
          body: "Arsip ZIP siap diunduh (8 dokumen).",
        })
      );
    });
  });
});
