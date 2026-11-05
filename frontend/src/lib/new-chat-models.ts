import { useChatStore } from "@/stores/chatStore";

export const MODEL_REQUIRED_CHATS_KEY = "notbooklm:model-required-chats";

function storedIds(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(MODEL_REQUIRED_CHATS_KEY) || "[]");
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : [];
  } catch { return []; }
}

export function chatRequiresModel(chatId?: string | null): boolean {
  if (!chatId) return true;
  return useChatStore.getState().modelRequiredChatIds.includes(chatId) || storedIds().includes(chatId);
}

export function setChatRequiresModel(chatId: string, required: boolean): void {
  const ids = [...new Set([...useChatStore.getState().modelRequiredChatIds, ...storedIds()])].filter((id) => id !== chatId);
  if (required) ids.push(chatId);
  useChatStore.setState({ modelRequiredChatIds: ids });
  try { localStorage.setItem(MODEL_REQUIRED_CHATS_KEY, JSON.stringify(ids)); } catch {}
}
