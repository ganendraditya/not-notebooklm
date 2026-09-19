import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChatStream } from "@/hooks/chat/useChatStream";
import { ChatMessage } from "@/stores/chatStore";

describe("useChatStream Queue Processing", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
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
    const updateDocumentsList = vi.fn();
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
        updateDocumentsList,
        handleEnsureChatSessionRef
      )
    );

    // 1. Send first message (starts processing)
    await act(async () => {
      await result.current.handleSendMessage("First prompt");
    });

    const job = result.current.getChatJob("chat-1");
    expect(fetchCallCount).toBe(1);
    expect(job.isProcessing).toBe(true);

    // 2. Queue second message while first message is still processing
    await act(async () => {
      await result.current.handleSendMessage("Second prompt");
    });

    expect(job.queue.length).toBe(1);
    expect(job.queue[0].text).toBe("Second prompt");

    // 3. Fast-forward smooth typewriter timers to complete first message onDone
    await act(async () => {
      vi.runAllTimers();
    });

    // 4. Second message should automatically be popped and started via processNextInQueue!
    expect(fetchCallCount).toBe(2);
    expect(job.queue.length).toBe(0);
  });
});
