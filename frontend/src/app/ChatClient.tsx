"use client";

import { useState, useEffect, useRef } from "react";
import LeftSidebar from "@/components/LeftSidebar";
import ChatArea from "@/components/ChatArea";
import RightSidebar from "@/components/RightSidebar";

// Types
export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at?: string;
}

export interface Document {
  id: number;
  filename: string;
  created_at: string;
}

export interface ChatMessage {
  role: string;
  content: string;
  created_at: string;
}

export default function ChatClient() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  
  const backendUrl = "http://localhost:8000";

  const bumpSessionToTop = (chatId: string) => {
    setSessions(prev => {
      const idx = prev.findIndex(s => s.id === chatId);
      if (idx <= 0) return prev; // Already at top or not found
      const target = { ...prev[idx], updated_at: new Date().toISOString() };
      const rest = prev.filter((_, i) => i !== idx);
      return [target, ...rest];
    });
  };

  // Fetch all sessions on mount
  useEffect(() => {
    fetch(`${backendUrl}/chats`)
      .then(res => res.json())
      .then(data => setSessions(data))
      .catch(err => console.error("Failed to fetch sessions:", err));
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
    if (activeChatId) return activeChatId;
    
    // Auto generate clean title from search query or paper name
    let title = (suggestedTitle || "Riset Baru").trim();
    title = title.replace(/^(cariin|carikan|cari|tolong cari|paper|jurnal tentang|minta paper)\s+/i, "");
    if (title.length > 35) {
      title = title.substring(0, 35) + "...";
    }
    if (!title) title = "Riset Baru";
    title = title.charAt(0).toUpperCase() + title.slice(1);

    try {
      const res = await fetch(`${backendUrl}/chats`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title })
      });
      const newChat = await res.json();
      setSessions(prev => [newChat, ...prev]);
      setActiveChatId(newChat.id);
      return newChat.id;
    } catch (err) {
      console.error("Failed to auto-create chat session:", err);
      throw err;
    }
  };

  const [queuedPrompts, setQueuedPrompts] = useState<string[]>([]);
  const messageQueueRef = useRef<string[]>([]);
  const isProcessingRef = useRef<boolean>(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    messageQueueRef.current = [];
    setQueuedPrompts([]);
    isProcessingRef.current = false;
    setIsLoading(false);
  };

  const handleRemoveQueuedPrompt = (index: number) => {
    setQueuedPrompts(prev => prev.filter((_, i) => i !== index));
    messageQueueRef.current = messageQueueRef.current.filter((_, i) => i !== index);
  };

  const handlePromoteQueuedPrompt = async (index: number) => {
    const promptToPromote = queuedPrompts[index];
    if (!promptToPromote) return;

    // 1. Remove this item from the queue list
    const remainingQueued = queuedPrompts.filter((_, i) => i !== index);
    setQueuedPrompts(remainingQueued);
    messageQueueRef.current = remainingQueued;

    // 2. Abort current ongoing generation
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    // 3. Put the promoted prompt as next and start processing immediately
    messageQueueRef.current = [promptToPromote, ...remainingQueued];
    isProcessingRef.current = false;
    setIsLoading(false);

    await processNextInQueue();
  };

  const processNextInQueue = async () => {
    if (messageQueueRef.current.length === 0) {
      isProcessingRef.current = false;
      setIsLoading(false);
      return;
    }

    const nextMessage = messageQueueRef.current.shift()!;
    setQueuedPrompts(prev => prev.slice(1));
    isProcessingRef.current = true;
    setIsLoading(true);

    // Optimistically add the user message into the chat stream WHEN IT ACTUALLY STARTS PROCESSING!
    const newMsg: ChatMessage = { role: "user", content: nextMessage, created_at: new Date().toISOString() };
    setMessages(prev => [...prev, newMsg]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let currentChatId = activeChatId;
    try {
      if (!currentChatId) {
        currentChatId = await handleEnsureChatSession(nextMessage);
      }
      bumpSessionToTop(currentChatId);

      const res = await fetch(`${backendUrl}/chats/${currentChatId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: nextMessage }),
        signal: controller.signal
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const assistantMsg = await res.json();
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      if (err?.name === "AbortError") {
        console.log("Generation stopped by user");
        setMessages(prev => [
          ...prev,
          { role: "assistant", content: "*(Pembuatan respon dihentikan oleh pengguna)*", created_at: new Date().toISOString() }
        ]);
        return; // Halt further queued processing on user abort
      } else {
        console.error("Failed to send queued message:", err);
        setMessages(prev => [
          ...prev,
          { role: "assistant", content: "⚠️ Maaf, terjadi kesalahan saat menghubungi server AI.", created_at: new Date().toISOString() }
        ]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      // Recursively process the next message in queue if still processing
      if (isProcessingRef.current) {
        await processNextInQueue();
      }
    }
  };

  const handleSendMessage = async (message: string) => {
    if (isProcessingRef.current) {
      // If AI is currently generating, add to the floating queue state without inserting into the chat stream yet
      messageQueueRef.current.push(message);
      setQueuedPrompts(prev => [...prev, message]);
      return;
    }

    messageQueueRef.current.push(message);
    await processNextInQueue();
  };

  const handleEditMessage = async (messageIndex: number, newContent: string) => {
    // Abort any ongoing request and clear pending queue on edit
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    messageQueueRef.current = [];
    isProcessingRef.current = true;
    setIsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let currentChatId = activeChatId;
    if (!currentChatId) {
      currentChatId = await handleEnsureChatSession(newContent);
    }

    if (!currentChatId) {
      isProcessingRef.current = false;
      setIsLoading(false);
      return;
    }
    bumpSessionToTop(currentChatId);

    // Optimistically update message list: keep messages up to messageIndex, replace at messageIndex, remove subsequent responses
    const updatedUserMsg: ChatMessage = { role: "user", content: newContent, created_at: new Date().toISOString() };
    setMessages(prev => [...prev.slice(0, messageIndex), updatedUserMsg]);

    try {
      const res = await fetch(`${backendUrl}/chats/${currentChatId}/edit_message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_index: messageIndex,
          message: newContent
        }),
        signal: controller.signal
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const assistantMsg = await res.json();
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      if (err?.name === "AbortError") {
        console.log("Edit request aborted");
      } else {
        console.error("Failed to edit message:", err);
        setMessages(prev => [
          ...prev,
          { role: "assistant", content: "⚠️ Maaf, terjadi kesalahan saat mengedit pesan.", created_at: new Date().toISOString() }
        ]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      isProcessingRef.current = false;
      setIsLoading(false);
    }
  };

  const handleCreateChat = () => {
    handleStopGeneration();
    setActiveChatId(null);
    setDocuments([]);
    setMessages([]);
  };

  const handleSelectChat = (id: string) => {
    handleStopGeneration();
    setActiveChatId(id);
    fetch(`${backendUrl}/chats/${id}`)
        .then(res => res.json())
        .then(data => {
          setDocuments(data.documents || []);
          setMessages(data.messages || []);
        })
        .catch(err => console.error("Failed to fetch chat details:", err));
  };

  const handleDeleteChat = async (id: string) => {
    try {
      await fetch(`${backendUrl}/chats/${id}`, { method: "DELETE" });
      setSessions(prev => prev.filter(s => s.id !== id));
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
        setSessions(prev => prev.map(s => s.id === id ? { ...s, title: updated.title } : s));
      }
    } catch (err) {
      console.error("Failed to rename chat:", err);
    }
  };

  const handleBulkDocumentsDeleted = (docIds: number[]) => {
    const idSet = new Set(docIds);
    setDocuments(prev => prev.filter(d => !idSet.has(d.id)));
  };

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#212121]">
      {/* Left Sidebar: Chat History */}
      {isSidebarOpen && (
        <LeftSidebar 
          sessions={sessions} 
          activeChatId={activeChatId} 
          onSelectChat={handleSelectChat}
          onCreateChat={handleCreateChat}
          onDeleteChat={handleDeleteChat}
          onRenameChat={handleRenameChat}
          onToggleSidebar={() => setIsSidebarOpen(false)}
        />
      )}
      
      {/* Center: Main Chat Area */}
      <ChatArea 
        activeChatId={activeChatId} 
        messages={messages} 
        isLoading={isLoading}
        onSendMessage={handleSendMessage} 
        onEditMessage={handleEditMessage}
        onStopGeneration={handleStopGeneration}
        queuedPrompts={queuedPrompts}
        onRemoveQueuedPrompt={handleRemoveQueuedPrompt}
        onPromoteQueuedPrompt={handlePromoteQueuedPrompt}
        documents={documents}
        onDocumentAdded={(doc) => setDocuments(prev => [...prev, doc])}
        onEnsureChatSession={handleEnsureChatSession}
        backendUrl={backendUrl}
        isSidebarOpen={isSidebarOpen}
        onOpenSidebar={() => setIsSidebarOpen(true)}
        isRightSidebarOpen={isRightSidebarOpen}
        onToggleRightSidebar={() => setIsRightSidebarOpen(prev => !prev)}
      />

      {/* Right Sidebar: Sources Panel (NotebookLM Style) */}
      {isRightSidebarOpen && (
        <RightSidebar 
          activeChatId={activeChatId} 
          documents={documents} 
          onDocumentAdded={(doc) => setDocuments(prev => [...prev, doc])} 
          onDocumentDeleted={(id) => setDocuments(prev => prev.filter(d => d.id !== id))}
          onBulkDocumentsDeleted={handleBulkDocumentsDeleted}
          onEnsureChatSession={handleEnsureChatSession}
          backendUrl={backendUrl}
          onClose={() => setIsRightSidebarOpen(false)}
        />
      )}
    </div>
  );
}
