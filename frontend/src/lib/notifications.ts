// Notification helper using Web Notifications API and optional subtle chime sound

import { getSystemTranslation } from "./i18n";

export type NotificationCategory = "responses" | "tasks" | "downloads";

export const isNotificationSupported = (): boolean => {
  return typeof window !== "undefined" && "Notification" in window;
};

export const getNotificationPermission = (): NotificationPermission => {
  if (!isNotificationSupported()) return "denied";
  return Notification.permission;
};

export const requestNotificationPermission = async (): Promise<NotificationPermission> => {
  if (!isNotificationSupported()) return "denied";
  try {
    const permission = await Notification.requestPermission();
    return permission;
  } catch (e) {
    console.error("Error requesting notification permission:", e);
    return "denied";
  }
};

export const isNotificationCategoryEnabled = (category: NotificationCategory): boolean => {
  if (typeof window === "undefined") return false;
  try {
    if (typeof window.localStorage === "undefined" || !window.localStorage) return true;
    const key = `notbooklm_notify_${category}`;
    const val = window.localStorage.getItem(key);
    // Default to "push" if not set
    return val === null || val === "push";
  } catch {
    return true;
  }
};

/**
 * Plays a pleasant, subtle synthesized ding chime using Web Audio API
 */
export const playNotificationSound = () => {
  if (typeof window === "undefined") return;
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    
    // Create oscillator for chime
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.1); // A5

    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.6);
  } catch {
    // AudioContext might fail if not interacted yet
  }
};

export interface SendNotificationOptions {
  category?: NotificationCategory;
  title?: string;
  titleKey?: string;
  body?: string;
  bodyKey?: string;
  variables?: Record<string, string>;
  icon?: string;
  onClick?: () => void;
  force?: boolean; // if true, notify even if tab is active (e.g. for testing)
}

/**
 * Triggers a native system / OS browser notification and focuses window when clicked.
 */
export const sendSystemNotification = ({
  category = "responses",
  title,
  titleKey,
  body,
  bodyKey,
  variables,
  icon,
  onClick,
  force = false,
}: SendNotificationOptions) => {
  if (typeof window === "undefined") return;

  // Check category setting
  if (!force && !isNotificationCategoryEnabled(category)) {
    return;
  }

  // If user is actively looking at the tab and force is false, no need to spam OS toast
  const isBackgrounded = document.hidden || !document.hasFocus();
  if (!force && !isBackgrounded) {
    return;
  }

  // Play audio alert
  playNotificationSound();

  if (!isNotificationSupported()) return;

  const finalTitle = titleKey
    ? getSystemTranslation(titleKey, variables, title)
    : (title || "NotbookLM");

  const finalBody = body && body.trim()
    ? body
    : (bodyKey ? getSystemTranslation(bodyKey, variables, body) : body);

  if (Notification.permission === "granted") {
    try {
      const notif = new Notification(finalTitle, {
        body: finalBody ? (finalBody.length > 150 ? finalBody.substring(0, 147) + "..." : finalBody) : undefined,
        icon: icon || "/icon",
        silent: false, // let OS make chime if configured
      });

      notif.onclick = () => {
        window.focus();
        try {
          // Focus current window/tab
          if (parent && parent.focus) parent.focus();
        } catch {}
        if (onClick) onClick();
        notif.close();
      };
    } catch (e) {
      console.error("Failed to show native notification:", e);
    }
  }
};
