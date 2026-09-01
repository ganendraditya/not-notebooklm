"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "@/lib/i18n";

export default function NotificationsTab() {
  const { t } = useTranslation();

  // Notifications State
  const [notifyResponses, setNotifyResponses] = useState<string>("push");
  const [notifyTasks, setNotifyTasks] = useState<string>("push");
  const [notifyDownloads, setNotifyDownloads] = useState<string>("push");

  // Load preferences from localStorage
  useEffect(() => {
    try {
      const savedNotifyResponses = localStorage.getItem("notbooklm_notify_responses");
      if (savedNotifyResponses) setNotifyResponses(savedNotifyResponses);

      const savedNotifyTasks = localStorage.getItem("notbooklm_notify_tasks");
      if (savedNotifyTasks) setNotifyTasks(savedNotifyTasks);

      const savedNotifyDownloads = localStorage.getItem("notbooklm_notify_downloads");
      if (savedNotifyDownloads) setNotifyDownloads(savedNotifyDownloads);
    } catch {
      // LocalStorage access denied/restricted
    }
  }, []);

  const handleNotifyResponsesChange = (val: string) => {
    setNotifyResponses(val);
    try { localStorage.setItem("notbooklm_notify_responses", val); } catch {}
  };

  const handleNotifyTasksChange = (val: string) => {
    setNotifyTasks(val);
    try { localStorage.setItem("notbooklm_notify_tasks", val); } catch {}
  };

  const handleNotifyDownloadsChange = (val: string) => {
    setNotifyDownloads(val);
    try { localStorage.setItem("notbooklm_notify_downloads", val); } catch {}
  };

  return (
    <div>
      <h3 className="text-sm font-semibold text-app-text">{t("settings.notifications")}</h3>

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
