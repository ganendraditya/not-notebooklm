export interface ChatDeleteProposal {
  chatId: string;
  documentIds: number[];
}

export function parseChatDeleteProposal(
  content: string | null | undefined,
  expectedChatId: string
): ChatDeleteProposal | null {
  const actionMatch = content?.match(/<!-- SOURCES_ACTION:\s*([\s\S]*?)\s*-->/);
  if (!actionMatch) return null;

  try {
    const parsed: unknown = JSON.parse(actionMatch[1]);
    if (!parsed || typeof parsed !== "object") return null;

    const action = parsed as Record<string, unknown>;
    if (
      action.action !== "confirm_delete" ||
      action.chat_id !== expectedChatId ||
      !Array.isArray(action.doc_ids) ||
      action.doc_ids.length === 0 ||
      !action.doc_ids.every((id) => typeof id === "number" && Number.isSafeInteger(id) && id > 0)
    ) {
      return null;
    }

    return {
      chatId: expectedChatId,
      documentIds: [...new Set(action.doc_ids as number[])],
    };
  } catch {
    return null;
  }
}
