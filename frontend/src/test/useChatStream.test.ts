import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChatStream } from "@/hooks/chat/useChatStream";
import { ChatMessage } from "@/stores/chatStore";
import { useDocumentStore } from "@/stores/documentStore";

describe("useChatStream Queue Processing", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    useDocumentStore.getState().setDocuments([]);
  });

  it("automatically processes subsequent queued messages when current stream finishes", async () => {
    const activeChatIdRef = { current: "chat-1" };
    const messages: ChatMessage[] = [];
    const setMessages = vi.fn();
    const setIsLoading = vi.fn();
    const setActiveStatus = vi.fn();
    const setQueuedPrompts = vi.fn();
    const bumpSessionToTop = vi.fn();
    const updateSessionsList = vi.fn();
    const updateMessagesList = vi.fn();
    const handleEnsureChatSessionRef = { current: vi.fn().mockResolvedValue("chat-1") };

    // Mock fetch to simulate SSE stream response
    let fetchCallCount = 0;
    const fetchMock = vi.fn().mockImplementation(() => {
      fetchCallCount++;
      const ssePayload =
        "data: {\"type\": \"delta\", \"text\": \"Hello\"}\n\n" +
        "data: {\"type\": \"done\", \"data\": \"Hello World\", \"message\": {\"role\": \"assistant\", \"content\": \"Hello World\"}}\n\n";

      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(ssePayload));
          controller.close();
        },
      });

      return Promise.resolve(new Response(stream, { status: 200 }));
    });
    global.fetch = fetchMock;
    useDocumentStore.getState().setDocuments([
      { id: 7, filename: "first.pdf", title: "First", created_at: "2026-01-01" },
    ]);

    const { result } = renderHook(() =>
      useChatStream(
        "http://localhost:8000",
        activeChatIdRef,
        messages,
        setMessages,
        setIsLoading,
        setActiveStatus,
        setQueuedPrompts,
        bumpSessionToTop,
        updateSessionsList,
        updateMessagesList,
        handleEnsureChatSessionRef
      )
    );

    // 1. Send first message (starts processing)
    await act(async () => {
      await result.current.handleSendMessage("First prompt");
    });

    useDocumentStore.getState().setDocuments([
      { id: 19, filename: "second.pdf", title: "Second", created_at: "2026-01-01" },
    ]);

    const job = result.current.getChatJob("chat-1");
    expect(fetchCallCount).toBe(1);
    expect(job.isProcessing).toBe(true);

    // 2. Queue second message while first message is still processing
    await act(async () => {
      await result.current.handleSendMessage("Second prompt");
    });

    expect(job.queue.length).toBe(1);
    expect(job.queue[0].text).toBe("Second prompt");
    expect(job.queue[0].sourceSnapshot).toEqual([
      { docId: 19, title: "Second", filename: "second.pdf" },
    ]);

    // 3. Fast-forward smooth typewriter timers to complete first message onDone
    await act(async () => {
      vi.runAllTimers();
    });

    // 4. Second message should automatically be popped and started via processNextInQueue!
    expect(fetchCallCount).toBe(2);
    expect(job.queue.length).toBe(0);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).source_snapshot).toEqual([
      { doc_id: 7, title: "First", filename: "first.pdf" },
    ]);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).source_snapshot).toEqual([
      { doc_id: 19, title: "Second", filename: "second.pdf" },
    ]);
  });

  it.each(["send", "edit", "regenerate"] as const)(
    "raises a chat-scoped delete proposal after %s completes",
    async (operation) => {
      const activeChatIdRef = { current: "chat-1" };
      const onDeleteProposal = vi.fn();
      const content = '<!-- SOURCES_ACTION: {"action":"confirm_delete","chat_id":"chat-1","doc_ids":[7]} -->';
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(
            `data: ${JSON.stringify({
              type: "done",
              message: { role: "assistant", content, created_at: "2026-01-01" },
            })}\n\n`
          ));
          controller.close();
        },
      });
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream, { status: 200 })));

      const { result } = renderHook(() =>
        useChatStream(
          "http://localhost:8000",
          activeChatIdRef,
          [],
          vi.fn(),
          vi.fn(),
          vi.fn(),
          vi.fn(),
          vi.fn(),
          vi.fn(),
          vi.fn(),
          { current: vi.fn().mockResolvedValue("chat-1") },
          onDeleteProposal
        )
      );

      await act(async () => {
        if (operation === "send") await result.current.handleSendMessage("remove Paper A");
        if (operation === "edit") await result.current.handleEditMessage(0, "remove Paper A");
        if (operation === "regenerate") await result.current.handleRegenerateMessage(0);
      });

      expect(onDeleteProposal).toHaveBeenCalledExactlyOnceWith({
        chatId: "chat-1",
        documentIds: [7],
      });
    }
  );

  it("forwards a committed source rename event from a normal send", async () => {
    const activeChatIdRef = { current: "chat-1" };
    const onSourceRenamed = vi.fn();
    const payload = [
      {
        type: "source_renamed",
        chat_id: "chat-1",
        doc_id: 947,
        source_number: 2,
        previous_title: "Paper B",
        new_title: "Evaluation Dataset",
      },
      {
        type: "done",
        data: "Renamed source 2.",
        message: { role: "assistant", content: "Renamed source 2." },
      },
    ].map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(payload));
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(new Response(stream, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useChatStream(
        "http://localhost:8000",
        activeChatIdRef,
        [],
        vi.fn(),
        vi.fn(),
        vi.fn(),
        vi.fn(),
        vi.fn(),
        vi.fn(),
        vi.fn(),
        { current: vi.fn().mockResolvedValue("chat-1") },
        undefined,
        onSourceRenamed,
      )
    );

    await act(async () => {
      await result.current.handleSendMessage("Rename paper 2 to Evaluation Dataset");
    });
    await act(async () => {
      vi.runAllTimers();
    });

    expect(onSourceRenamed).toHaveBeenCalledExactlyOnceWith({
      chatId: "chat-1",
      docId: 947,
      sourceNumber: 2,
      previousTitle: "Paper B",
      newTitle: "Evaluation Dataset",
    });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ source_snapshot: [] });
  });
});
