import { useRef, useEffect, useCallback } from "react";
import { type ChatSession, type ChatMessage } from "@/stores/chatStore";
import { type Document, type PendingSourceItem, type TargetedSource } from "@/stores/documentStore";
import { type ChatJobState } from "./useChatStream";

export function useChatSession(
  backendUrl: string,
  sessions: ChatSession[],
  setSessions: (sessions: ChatSession[]) => void,
  activeChatId: string | null,
  setActiveChatId: (id: string | null) => void,
  setDocuments: (docs: Document[]) => void,
  setPendingSources: (sources: PendingSourceItem[]) => void,
  setMessages: (messages: ChatMessage[]) => void,
  setTargetedSource: (source: TargetedSource | null) => void,
  setViewingDoc: (doc: Document | null) => void,
  setQueuedPrompts: (prompts: string[]) => void,
  setIsLoading: (loading: boolean) => void,
  setActiveStatus: (status: string | null) => void,
  setCurrentView: (view: "chat" | "library" | "search") => void,
  updateSessionsList: (updater: (prev: ChatSession[]) => ChatSession[]) => void,
  getChatJob: (id: string) => ChatJobState,
  activeChatIdRef: React.MutableRefObject<string | null>
) {

  useEffect(() => {
    activeChatIdRef.current = activeChatId;
  }, [activeChatId, activeChatIdRef]);

  const pendingSessionCreationRef = useRef<Promise<string> | null>(null);
  const handleSelectChatRef = useRef<(id: string) => void>(() => {});

  const handleSelectChat = useCallback((id: string) => {
    setCurrentView("chat");
    try {
      localStorage.setItem("last_active_chat_id", id);
    } catch {}
    if (activeChatId === id) {
      setViewingDoc(null);
      return;
    }

    setActiveChatId(id);
    setViewingDoc(null);
    setPendingSources([]);

    // Sync loading & queue state for the selected chat
    const job = getChatJob(id);
    setIsLoading(job.isProcessing);
    setActiveStatus(job.status);
    setQueuedPrompts(job.queue.map(q => q.text));

    fetch(`${backendUrl}/chats/${id}`)
        .then(res => res.json())
        .then(data => {
          // Only apply if user is still looking at this chat and not currently in active streaming
          if (activeChatIdRef.current === id) {
            const currentJob = getChatJob(id);
            setDocuments(data.documents || []);
            if (!currentJob.isProcessing) {
              setMessages(data.messages || []);
            }
          }
        })
        .catch(err => {
          console.error("Failed to fetch chat details:", err);
          // Fallback to query all documents if detail endpoint fails
          fetch(`${backendUrl}/chats`)
            .then(r => r.json())
            .then(sList => {
              try {
                const pinnedStorage = JSON.parse(localStorage.getItem("pinned_chats") || "[]") as string[];
                const pinnedSet = new Set(pinnedStorage);
                setSessions((sList || []).map((s: ChatSession) => ({
                  ...s,
                  is_pinned: pinnedSet.has(s.id)
                })));
              } catch {
                setSessions(sList || []);
              }
            });
        });
  }, [
    activeChatId,
    backendUrl,
    setCurrentView,
    setActiveChatId,
    setViewingDoc,
    setPendingSources,
    getChatJob,
    setIsLoading,
    setActiveStatus,
    setQueuedPrompts,
    activeChatIdRef,
    setDocuments,
    setMessages,
    setSessions
  ]);

  useEffect(() => {
    handleSelectChatRef.current = handleSelectChat;
  }, [handleSelectChat]);

  // Fetch all sessions on mount & restore the last active chat (or New Chat)
  useEffect(() => {
    fetch(`${backendUrl}/chats`)
      .then(res => res.json())
      .then(data => {
        const hydrated = (data || []).map((s: ChatSession) => ({
          ...s,
          is_pinned: Boolean(s.is_pinned)
        }));
        setSessions(hydrated);

        if (!activeChatId && handleSelectChatRef.current) {
          let savedChatId: string | null = null;
          try {
            savedChatId = localStorage.getItem("last_active_chat_id");
          } catch {}

          if (savedChatId && hydrated.some((s: ChatSession) => s.id === savedChatId)) {
            // Restore the exact chat the user was viewing before refresh
            handleSelectChatRef.current(savedChatId);
          } else if (savedChatId === "") {
            // User was intentionally on New Chat before refresh, stay on New Chat
          } else if (hydrated.length > 0) {
            // Fallback for first-time visitors who haven't selected anything yet
            handleSelectChatRef.current(hydrated[0].id);
          }
        }
      })
      .catch(err => console.error("Failed to fetch sessions:", err));
    // Intentionally run once on component mount to hydrate sessions from persistent storage
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Dynamically update document title based on active chat
  useEffect(() => {
    if (activeChatId) {
      const activeSession = sessions.find(s => s.id === activeChatId);
      if (activeSession && activeSession.title) {
        document.title = `${activeSession.title} - NotbookLM`;
      } else {
        document.title = "NotbookLM";
      }
    } else {
      document.title = "NotbookLM";
    }
  }, [activeChatId, sessions]);

  const handleEnsureChatSession = async (suggestedTitle?: string): Promise<string> => {
    // Fast path: session already active (check both ref and state)
    if (activeChatIdRef.current) return activeChatIdRef.current;
    if (activeChatId) return activeChatId;

    // Mutex: If a session creation request is already in-flight, await the same promise
    if (pendingSessionCreationRef.current) {
      return await pendingSessionCreationRef.current;
    }

    pendingSessionCreationRef.current = (async () => {
      try {
        // Initial placeholder title while AI generates the smart topic name
        let title = (suggestedTitle || "New Research").trim();
        title = title.replace(/^(find|search|look up|get|paper on|journal about|research on|tolong carikan|cariin)\s+/i, "");
        if (title.length > 30) {
          title = title.substring(0, 30) + "...";
        }
        if (!title) title = "New Research";
        title = title.charAt(0).toUpperCase() + title.slice(1);

        const res = await fetch(`${backendUrl}/chats`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title })
        });
        const newChat = await res.json();
        try {
          localStorage.setItem("last_active_chat_id", newChat.id);
        } catch {}
        activeChatIdRef.current = newChat.id;
        updateSessionsList(prev => [newChat, ...prev.filter(s => s.id !== newChat.id)]);
        setActiveChatId(newChat.id);
        return newChat.id as string;
      } catch (err) {
        console.error("Failed to auto-create chat session:", err);
        throw err;
      } finally {
        pendingSessionCreationRef.current = null;
      }
    })();

    return await pendingSessionCreationRef.current;
  };

  const handleCreateChat = () => {
    try {
      localStorage.setItem("last_active_chat_id", "");
    } catch {}
    activeChatIdRef.current = null;
    pendingSessionCreationRef.current = null;
    setActiveChatId(null);
    setDocuments([]);
    setPendingSources([]);
    setMessages([]);
    setTargetedSource(null);
    setViewingDoc(null);
    setQueuedPrompts([]);
    setIsLoading(false);
    setActiveStatus(null);
    setCurrentView("chat");
  };

  const handleDeleteChat = async (id: string) => {
    try {
      await fetch(`${backendUrl}/chats/${id}`, { method: "DELETE" });
      updateSessionsList(prev => prev.filter(s => s.id !== id));
      if (activeChatId === id) {
        handleCreateChat();
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  const handleRenameChat = async (id: string, newTitle: string) => {
    try {
      const res = await fetch(`${backendUrl}/chats/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle })
      });
      if (res.ok) {
        const updated = await res.json();
        updateSessionsList(prev => prev.map(s => s.id === id ? { ...s, title: updated.title } : s));
      }
    } catch (err) {
      console.error("Failed to rename chat:", err);
    }
  };

  const handleTogglePinChat = async (id: string) => {
    const targetSession = sessions.find(s => s.id === id);
    const nextPinnedState = targetSession ? !targetSession.is_pinned : true;

    // Optimistic UI update
    updateSessionsList(prev => prev.map(s => s.id === id ? { ...s, is_pinned: nextPinnedState } : s));

    try {
      const res = await fetch(`${backendUrl}/chats/${id}/pin`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_pinned: nextPinnedState })
      });
      if (!res.ok) {
        // Revert on failure
        updateSessionsList(prev => prev.map(s => s.id === id ? { ...s, is_pinned: !nextPinnedState } : s));
      }
    } catch (e) {
      console.error("Failed to sync pinned chat state to backend:", e);
      updateSessionsList(prev => prev.map(s => s.id === id ? { ...s, is_pinned: !nextPinnedState } : s));
    }
  };

  return {
    activeChatIdRef,
    handleEnsureChatSession,
    handleCreateChat,
    handleSelectChat,
    handleDeleteChat,
    handleRenameChat,
    handleTogglePinChat
  };
}