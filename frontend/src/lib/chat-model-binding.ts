import { useChatStore, type WorkspaceModel } from "@/stores/chatStore";
import { recordModelSelection } from "./model-preferences";
import { setChatRequiresModel } from "./new-chat-models";

const pendingUpdates = new Map<string, Promise<void>>();

export function pendingChatModelUpdate(chatId: string): Promise<void> | undefined {
  return pendingUpdates.get(chatId);
}

export function persistChatModel(backendUrl: string, chatId: string, model: WorkspaceModel, remember = false): Promise<void> {
  const pending = pendingUpdates.get(chatId);
  if (pending) return pending;
  const store = useChatStore.getState();
  const previous = store.sessions.find((session) => session.id === chatId);
  store.updateSessionModel(chatId, model.id, model.profile_id);
  const request = Promise.resolve().then(async () => {
    try {
      const response = await fetch(`${backendUrl}/chats/${chatId}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: model.id, profile_id: model.profile_id }),
      });
      if (!response.ok) throw new Error(`Failed to bind chat model: ${response.status}`);
      if (remember) recordModelSelection(model);
      setChatRequiresModel(chatId, false);
    } catch (error) {
      useChatStore.getState().updateSessionModel(chatId, previous?.model ?? null, previous?.profile_id ?? null);
      throw error;
    } finally {
      pendingUpdates.delete(chatId);
      useChatStore.setState((state) => ({ modelUpdatingChatIds: state.modelUpdatingChatIds.filter((id) => id !== chatId) }));
    }
  });
  pendingUpdates.set(chatId, request);
  useChatStore.setState((state) => ({ modelUpdatingChatIds: [...state.modelUpdatingChatIds, chatId] }));
  return request;
}
