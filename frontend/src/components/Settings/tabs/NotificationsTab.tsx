"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "@/lib/i18n";
import {
  isNotificationSupported,
  getNotificationPermission,
  requestNotificationPermission,
  sendSystemNotification
} from "@/lib/notifications";
import { Bell, BellRing, AlertCircle, CheckCircle2 } from "lucide-react";

export default function NotificationsTab() {
  const { t } = useTranslation();

  // Notifications State - Initialize permission synchronously when available in browser to avoid flash of "default" UI
  const [notifyResponses, setNotifyResponses] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("notbooklm_notify_responses") || "push";
    }
    return "push";
  });
  const [notifyTasks, setNotifyTasks] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("notbooklm_notify_tasks") || "push";
    }
    return "push";
  });
  const [notifyDownloads, setNotifyDownloads] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("notbooklm_notify_downloads") || "push";
    }
    return "push";
  });
  const [permission, setPermission] = useState<NotificationPermission>(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      return Notification.permission;
    }
    return "default";
  });
  const [isSupported, setIsSupported] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return "Notification" in window;
    }
    return true;
  });
  const [testSent, setTestSent] = useState<boolean>(false);

  // Load preferences and permission status
  useEffect(() => {
    setIsSupported(isNotificationSupported());
    if (isNotificationSupported()) {
      setPermission(getNotificationPermission());
    }
  }, []);

  const handleRequestPermission = async () => {
    const res = await requestNotificationPermission();
    setPermission(res);
  };

  const handleTestNotification = async () => {
    if (permission !== "granted") {
      const res = await requestNotificationPermission();
      setPermission(res);
      if (res !== "granted") return;
    }

    sendSystemNotification({
      titleKey: "notify.testTitle",
      title: t("notify.testTitle") || "NotbookLM AI",
      bodyKey: "notify.testBody",
      body: t("notify.testBody") || "Browser & system notifications are active and working properly! ✨",
      force: true
    });

    setTestSent(true);
    setTimeout(() => setTestSent(false), 3000);
  };

  const handleNotifyResponsesChange = async (val: string) => {
    setNotifyResponses(val);
    try { localStorage.setItem("notbooklm_notify_responses", val); } catch {}
    if (val === "push" && permission === "default") {
      const res = await requestNotificationPermission();
      setPermission(res);
    }
  };

  const handleNotifyTasksChange = async (val: string) => {
    setNotifyTasks(val);
    try { localStorage.setItem("notbooklm_notify_tasks", val); } catch {}
    if (val === "push" && permission === "default") {
      const res = await requestNotificationPermission();
      setPermission(res);
    }
  };

  const handleNotifyDownloadsChange = async (val: string) => {
    setNotifyDownloads(val);
    try { localStorage.setItem("notbooklm_notify_downloads", val); } catch {}
    if (val === "push" && permission === "default") {
      const res = await requestNotificationPermission();
      setPermission(res);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-app-text">{t("settings.notifications")}</h3>
        {isSupported && (
          <button
            type="button"
            onClick={handleTestNotification}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors border border-blue-500/20"
          >
            <BellRing size={13} />
            <span>{testSent ? t("settings.notifications.sent") || "Sent!" : t("settings.notifications.test") || "Test Notification"}</span>
          </button>
        )}
      </div>

      {/* Permission Status Banner */}
      {!isSupported ? (
        <div className="mt-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-xs flex items-start gap-2">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          <span>{t("settings.notifications.notSupported") || "This browser does not support Web Notifications API."}</span>
        </div>
      ) : permission === "denied" ? (
        <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-start gap-2">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold block mb-0.5">{t("settings.notifications.denied") || "Notification permission is blocked in the browser."}</span>
            <span>{t("settings.notifications.deniedDesc") || "Open the lock icon / site settings in your browser URL bar and change notifications to Allow."}</span>
          </div>
        </div>
      ) : permission === "default" ? (
        <div className="mt-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Bell size={16} className="shrink-0" />
            <span>{t("settings.notifications.prompt") || "Enable system / browser notification permission so alerts appear on your device."}</span>
          </div>
          <button
            type="button"
            onClick={handleRequestPermission}
            className="shrink-0 font-medium underline hover:text-blue-300"
          >
            {t("settings.notifications.allow") || "Allow"}
          </button>
        </div>
      ) : (
        <div className="mt-3 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle2 size={15} className="shrink-0" />
          <span>{t("settings.notifications.granted") || "System / browser notification permission is active."}</span>
        </div>
      )}

      <div className="divide-y divide-app-divider mt-4">
        {/* Responses */}
        <div className="flex items-center justify-between gap-6 py-3">
          <div className="min-w-0 flex-1 pr-2">
            <h4 className="text-sm font-medium text-app-text truncate">
              {t("settings.notifications.responses")}
            </h4>
            <p className="text-xs text-app-text-muted mt-0.5 leading-relaxed break-words">
              {t("settings.notifications.responses.desc")}
            </p>
          </div>
          <select
            value={notifyResponses}
            onChange={(e) => handleNotifyResponsesChange(e.target.value)}
            className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer"
          >
            <option value="push">{t("settings.notifications.push")}</option>
            <option value="off">{t("settings.notifications.off")}</option>
          </select>
        </div>

        {/* Tasks & Queue */}
        <div className="flex items-center justify-between gap-6 py-3">
          <div className="min-w-0 flex-1 pr-2">
            <h4 className="text-sm font-medium text-app-text truncate">
              {t("settings.notifications.tasks")}
            </h4>
            <p className="text-xs text-app-text-muted mt-0.5 leading-relaxed break-words">
              {t("settings.notifications.tasks.desc")}
            </p>
          </div>
          <select
            value={notifyTasks}
            onChange={(e) => handleNotifyTasksChange(e.target.value)}
            className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer"
          >
            <option value="push">{t("settings.notifications.push")}</option>
            <option value="off">{t("settings.notifications.off")}</option>
          </select>
        </div>

        {/* Downloads & Exports */}
        <div className="flex items-center justify-between gap-6 py-3">
          <div className="min-w-0 flex-1 pr-2">
            <h4 className="text-sm font-medium text-app-text truncate">
              {t("settings.notifications.downloads")}
            </h4>
            <p className="text-xs text-app-text-muted mt-0.5 leading-relaxed break-words">
              {t("settings.notifications.downloads.desc")}
            </p>
          </div>
          <select
            value={notifyDownloads}
            onChange={(e) => handleNotifyDownloadsChange(e.target.value)}
            className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer"
          >
            <option value="push">{t("settings.notifications.push")}</option>
            <option value="off">{t("settings.notifications.off")}</option>
          </select>
        </div>
      </div>
    </div>
  );
}
