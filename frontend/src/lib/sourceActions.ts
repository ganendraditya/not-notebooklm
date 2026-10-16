export interface ChatDeleteProposal {
  chatId: string;
  documentIds: number[];
}

export interface ChatSourceRename {
  chatId: string;
  docId: number;
  sourceNumber: number;
  previousTitle: string;
  newTitle: string;
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

export function parseSourceRenameEvent(
  event: unknown,
  expectedChatId: string
): ChatSourceRename | null {
  if (!event || typeof event !== "object") return null;

  const payload = event as Record<string, unknown>;
  if (
    payload.type !== "source_renamed" ||
    payload.chat_id !== expectedChatId ||
    typeof payload.doc_id !== "number" ||
    !Number.isSafeInteger(payload.doc_id) ||
    payload.doc_id <= 0 ||
    typeof payload.source_number !== "number" ||
    !Number.isSafeInteger(payload.source_number) ||
    payload.source_number <= 0 ||
    typeof payload.previous_title !== "string" ||
    typeof payload.new_title !== "string" ||
    !payload.new_title.trim() ||
    payload.new_title.length > 500
  ) {
    return null;
  }

  return {
    chatId: expectedChatId,
    docId: payload.doc_id,
    sourceNumber: payload.source_number,
    previousTitle: payload.previous_title,
    newTitle: payload.new_title,
  };
}
