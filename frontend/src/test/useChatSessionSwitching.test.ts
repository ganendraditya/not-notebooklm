import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChatSession } from "@/hooks/chat/useChatSession";
import { ChatJobState } from "@/hooks/chat/useChatStream";
import { ChatSession, ChatMessage } from "@/stores/chatStore";

describe("useChatSession Chat Switching State Isolation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("restores in-flight streaming messages and prevents stale bleeding when switching back to generating chat", async () => {
    const sessions: ChatSession[] = [
      { id: "chat-1", title: "Chat 1", created_at: new Date().toISOString() },
      { id: "chat-2", title: "Chat 2", created_at: new Date().toISOString() },
    ];
    const setSessions = vi.fn();
    const setActiveChatId = vi.fn();
    const setDocuments = vi.fn();
    const setPendingSources = vi.fn();
    const setMessages = vi.fn();
    const setTargetedSource = vi.fn();
    const setViewingDoc = vi.fn();
    const setQueuedPrompts = vi.fn();
    const setIsLoading = vi.fn();
    const setActiveStatus = vi.fn();
    const setCurrentView = vi.fn();
    const updateSessionsList = vi.fn();
    const activeChatIdRef = { current: "chat-1" as string | null };

    // Chat 1 has an active in-flight job
    const inFlightUserMsg: ChatMessage = { role: "user", content: "Prompt in chat 1", created_at: new Date().toISOString() };
    const inFlightStreamingMsg: ChatMessage = { role: "assistant", content: "Generating response...", created_at: new Date().toISOString(), isStreaming: true };

    const jobsMap = new Map<string, ChatJobState>();
    jobsMap.set("chat-1", {
      controller: new AbortController(),
      queue: [],
      isProcessing: true,
      status: "Thinking...",
      inFlightUserMsg,
      inFlightStreamingMsg,
      baseMessages: [{ role: "user", content: "Initial message", created_at: new Date().toISOString() }],
      lastCompletedMessages: null,
    });
    jobsMap.set("chat-2", {
      controller: null,
      queue: [],
      isProcessing: false,
      status: null,
      inFlightUserMsg: null,
      inFlightStreamingMsg: null,
      baseMessages: [],
      lastCompletedMessages: null,
    });

    const getChatJob = (id: string) => jobsMap.get(id)!;

    // Mock fetch for chat details
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith("/chats/chat-2")) {
        return Promise.resolve(new Response(JSON.stringify({
          id: "chat-2",
          title: "Chat 2",
          documents: [],
          messages: [{ role: "assistant", content: "Chat 2 historical message", created_at: new Date().toISOString() }]
        }), { status: 200 }));
      }
      if (url.endsWith("/chats/chat-1")) {
        return Promise.resolve(new Response(JSON.stringify({
          id: "chat-1",
          title: "Chat 1",
          documents: [],
          messages: [{ role: "user", content: "Initial message", created_at: new Date().toISOString() }]
        }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    });

    const { result, rerender } = renderHook(
      ({ activeId }) =>
        useChatSession(
          "http://localhost:8000",
          sessions,
          setSessions,
          activeId,
          setActiveChatId,
          setDocuments,
          setPendingSources,
          setMessages,
          setTargetedSource,
          setViewingDoc,
          setQueuedPrompts,
          setIsLoading,
          setActiveStatus,
          setCurrentView,
          updateSessionsList,
          getChatJob,
          activeChatIdRef
        ),
      { initialProps: { activeId: "chat-1" as string | null } }
    );

    // 1. Switch to chat-2
    await act(async () => {
      activeChatIdRef.current = "chat-2";
      result.current.handleSelectChat("chat-2");
    });

    rerender({ activeId: "chat-2" });

    // setMessages([]) should be called immediately on switch to clear stale messages before fetch completes
    expect(setMessages).toHaveBeenCalledWith([]);

    // 2. Switch back to chat-1 (which is currently generating)
    await act(async () => {
      activeChatIdRef.current = "chat-1";
      result.current.handleSelectChat("chat-1");
    });

    rerender({ activeId: "chat-1" });

    // It should immediately restore chat-1's in-flight state without waiting for fetch
    expect(setMessages).toHaveBeenCalledWith([
      { role: "user", content: "Initial message", created_at: expect.any(String) },
      inFlightUserMsg,
      inFlightStreamingMsg
    ]);
  });
});
