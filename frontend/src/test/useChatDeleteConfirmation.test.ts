import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useChatDeleteConfirmation } from "@/hooks/chat/useChatDeleteConfirmation";

const documents = [
  { id: 7, filename: "paper-a.pdf", title: "Paper A", created_at: "2026-01-01" },
  { id: 8, filename: "paper-b.pdf", created_at: "2026-01-01" },
];

function makeProps(activeChatIdRef: { current: string | null }, onDocumentsDeleted = vi.fn()) {
  return {
    activeChatId: activeChatIdRef.current,
    activeChatIdRef,
    backendUrl: "http://localhost:8000",
    documents,
    onDocumentsDeleted,
  };
}

describe("useChatDeleteConfirmation", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the resolved sources and Cancel never calls the delete API", () => {
    const activeChatIdRef = { current: "chat-1" };
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useChatDeleteConfirmation(makeProps(activeChatIdRef)));

    act(() => result.current.requestConfirmation({ chatId: "chat-1", documentIds: [7, 8] }));
    expect(result.current.proposal?.sourceNames).toEqual(["Paper A", "paper-b.pdf"]);

    act(() => result.current.cancel());
    expect(result.current.proposal).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not open a proposal when an ID is not in the active workspace", () => {
    const activeChatIdRef = { current: "chat-1" };
    const { result } = renderHook(() => useChatDeleteConfirmation(makeProps(activeChatIdRef)));

    act(() => result.current.requestConfirmation({ chatId: "chat-1", documentIds: [7, 999] }));

    expect(result.current.proposal).toBeNull();
  });

  it("uses the latest source list from a callback captured before a rerender", () => {
    const activeChatIdRef = { current: "chat-1" };
    const addedDocument = {
      id: 9,
      filename: "paper-c.pdf",
      title: "Paper C",
      created_at: "2026-01-01",
    };
    const { result, rerender } = renderHook(
      ({ currentDocuments }) =>
        useChatDeleteConfirmation({
          ...makeProps(activeChatIdRef),
          documents: currentDocuments,
        }),
      { initialProps: { currentDocuments: documents } }
    );
    const callbackCapturedBeforeUpdate = result.current.requestConfirmation;

    rerender({ currentDocuments: [...documents, addedDocument] });
    act(() => callbackCapturedBeforeUpdate({ chatId: "chat-1", documentIds: [9] }));

    expect(result.current.proposal?.sourceNames).toEqual(["Paper C"]);
  });

  it("posts one chat-scoped delete only after confirmation and refreshes on success", async () => {
    const activeChatIdRef = { current: "chat-1" };
    const onDocumentsDeleted = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useChatDeleteConfirmation(makeProps(activeChatIdRef, onDocumentsDeleted))
    );

    act(() => result.current.requestConfirmation({ chatId: "chat-1", documentIds: [7] }));
    expect(fetchMock).not.toHaveBeenCalled();

    await act(async () => result.current.confirm());

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/chats/chat-1/documents/bulk_delete",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ doc_ids: [7] }),
      })
    );
    expect(onDocumentsDeleted).toHaveBeenCalledTimes(1);
    expect(onDocumentsDeleted).toHaveBeenCalledWith([7]);
    expect(result.current.proposal).toBeNull();
  });

  it("ignores a rapid second confirmation while the first request is in flight", async () => {
    const activeChatIdRef = { current: "chat-1" };
    let resolveFetch!: (response: { ok: boolean }) => void;
    const fetchPromise = new Promise<{ ok: boolean }>((resolve) => {
      resolveFetch = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(fetchPromise);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useChatDeleteConfirmation(makeProps(activeChatIdRef)));
    act(() => result.current.requestConfirmation({ chatId: "chat-1", documentIds: [7] }));

    let firstConfirm!: Promise<void>;
    let secondConfirm!: Promise<void>;
    act(() => {
      firstConfirm = result.current.confirm();
      secondConfirm = result.current.confirm();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFetch({ ok: true });
      await Promise.all([firstConfirm, secondConfirm]);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the proposal open and does not refresh when the API fails", async () => {
    const activeChatIdRef = { current: "chat-1" };
    const onDocumentsDeleted = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    const { result } = renderHook(() =>
      useChatDeleteConfirmation(makeProps(activeChatIdRef, onDocumentsDeleted))
    );

    act(() => result.current.requestConfirmation({ chatId: "chat-1", documentIds: [7] }));
    await act(async () => result.current.confirm());

    expect(result.current.hasDeleteError).toBe(true);
    expect(result.current.proposal?.documentIds).toEqual([7]);
    expect(onDocumentsDeleted).not.toHaveBeenCalled();
  });

  it("clears an unconfirmed proposal when the active chat changes", () => {
    const activeChatIdRef = { current: "chat-1" };
    const { result, rerender } = renderHook(
      ({ activeChatId }) => useChatDeleteConfirmation({ ...makeProps(activeChatIdRef), activeChatId }),
      { initialProps: { activeChatId: "chat-1" } }
    );

    act(() => result.current.requestConfirmation({ chatId: "chat-1", documentIds: [7] }));
    activeChatIdRef.current = "chat-2";
    rerender({ activeChatId: "chat-2" });

    expect(result.current.proposal).toBeNull();
    act(() => result.current.requestConfirmation({ chatId: "chat-1", documentIds: [7] }));
    expect(result.current.proposal).toBeNull();
  });
});
