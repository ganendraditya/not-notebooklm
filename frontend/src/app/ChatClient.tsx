"use client";

import { useState, useEffect, useRef } from "react";
import { Sparkles, Settings } from "lucide-react";
import LeftSidebar from "@/components/LeftSidebar";
import ChatArea from "@/components/ChatArea";
import RightSidebar from "@/components/RightSidebar";
import SettingsModal from "@/components/SettingsModal";
import LibraryView from "@/components/LibraryView";
import SearchChatsView from "@/components/SearchChatsView";
import { useTranslation } from "@/lib/i18n";
import { consumeSSEStream } from "@/lib/sse";
import { useChatStore, type ChatSession, type ChatMessage } from "@/stores/chatStore";
import { useDocumentStore, type Document, type PendingSourceItem } from "@/stores/documentStore";
import { useUIStore } from "@/stores/uiStore";
import type { Attachment } from "@/stores/chatStore";

export default function ChatClient() {
  const { t } = useTranslation();
  
  // Zustand Stores
  const { 
    sessions, setSessions, activeChatId, setActiveChatId, 
    messages, setMessages, isLoading, setIsLoading,
    activeStatus, setActiveStatus, queuedPrompts, setQueuedPrompts,
    bumpSessionToTop, updateMessagesList, updateSessionsList
  } = useChatStore();

  const {
    documents, setDocuments, pendingSources, setPendingSources,
    targetedSource, setTargetedSource, viewingDoc, setViewingDoc,
    groundingHighlight, setGroundingHighlight, addDocument,
    updateDocumentsList, updatePendingSourcesList
  } = useDocumentStore();

  const {
    isSettingsOpen, setIsSettingsOpen, currentView, setCurrentView,
    libraryInitialCategory, setLibraryInitialCategory
  } = useUIStore();
  
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Fetch all sessions on mount & auto-select the latest active chat if none selected
  useEffect(() => {
    fetch(`${backendUrl}/chats`)
      .then(res => res.json())
      .then(data => {
        const hydrated = (data || []).map((s: ChatSession) => ({
          ...s,
          is_pinned: Boolean(s.is_pinned)
        }));
        setSessions(hydrated);
        if (hydrated.length > 0 && !activeChatId) {
          handleSelectChat(hydrated[0].id);
        }
      })
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
    
    // Initial placeholder title while AI generates the smart topic name
    let title = (suggestedTitle || "New Research").trim();
    title = title.replace(/^(find|search|look up|get|paper on|journal about|research on|tolong carikan|cariin)\s+/i, "");
    if (title.length > 30) {
      title = title.substring(0, 30) + "...";
    }
    if (!title) title = "New Research";
    title = title.charAt(0).toUpperCase() + title.slice(1);

    try {
      const res = await fetch(`${backendUrl}/chats`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title })
      });
      const newChat = await res.json();
      activeChatIdRef.current = newChat.id;
      setSessions([newChat, ...sessions]);
      setActiveChatId(newChat.id);
      return newChat.id;
    } catch (err) {
      console.error("Failed to auto-create chat session:", err);
      throw err;
    }
  };

  const activeChatIdRef = useRef<string | null>(null);
  useEffect(() => {
    activeChatIdRef.current = activeChatId;
  }, [activeChatId]);

  // Queue now needs to store attachments too
  interface QueuedMessage {
    text: string;
    attachments?: Attachment[];
  }

  // Per-chat background generation tracker
  interface ChatJobState {
    controller: AbortController | null;
    queue: QueuedMessage[];
    isProcessing: boolean;
    status: string | null;
  }
  const chatJobsRef = useRef<Map<string, ChatJobState>>(new Map());

  const getChatJob = (chatId: string): ChatJobState => {
    if (!chatJobsRef.current.has(chatId)) {
      chatJobsRef.current.set(chatId, {
        controller: null,
        queue: [],
        isProcessing: false,
        status: null,
      });
    }
    return chatJobsRef.current.get(chatId)!;
  };

  const handleStopGeneration = () => {
    const currentChatId = activeChatIdRef.current;
    if (!currentChatId) return;

    const job = getChatJob(currentChatId);
    if (job.controller) {
      job.controller.abort();
      job.controller = null;
    }
    job.queue = [];
    job.isProcessing = false;
    job.status = null;

    setQueuedPrompts([]);
    setIsLoading(false);
    setActiveStatus(null);
  };

  const handleRemoveQueuedPrompt = (index: number) => {
    const currentChatId = activeChatIdRef.current;
    if (!currentChatId) return;
    const job = getChatJob(currentChatId);
    job.queue = job.queue.filter((_, i) => i !== index);
    setQueuedPrompts(job.queue.map(q => q.text));
  };

  const handlePromoteQueuedPrompt = async (index: number) => {
    const currentChatId = activeChatIdRef.current;
    if (!currentChatId) return;
    const job = getChatJob(currentChatId);
    const promptToPromote = job.queue[index];
    if (!promptToPromote) return;

    // 1. Remove this item from the queue list
    job.queue = job.queue.filter((_, i) => i !== index);
    setQueuedPrompts(job.queue.map(q => q.text));

    // 2. Abort current ongoing generation for this chat
    if (job.controller) {
      job.controller.abort();
      job.controller = null;
    }

    // 3. Put the promoted prompt as next and start processing immediately
    job.queue = [promptToPromote, ...job.queue];
    job.isProcessing = false;
    setIsLoading(false);

    await processNextInQueue(currentChatId);
  };

  const processNextInQueue = async (targetChatId: string) => {
    const job = getChatJob(targetChatId);
    if (job.queue.length === 0) {
      job.isProcessing = false;
      job.status = null;
      if (activeChatIdRef.current === targetChatId) {
        setIsLoading(false);
        setActiveStatus(null);
        setQueuedPrompts([]);
      }
      return;
    }

    const nextMessage = job.queue.shift()!;
    job.isProcessing = true;
    job.status = "Analyzing query & reasoning...";

    if (activeChatIdRef.current === targetChatId) {
      setQueuedPrompts(job.queue.map(q => q.text));
      setIsLoading(true);
      setActiveStatus(job.status);
      const newMsg: ChatMessage = { 
        role: "user", 
        content: nextMessage.text, 
        created_at: new Date().toISOString(),
        attachments: nextMessage.attachments
      };
      setMessages([...messages, newMsg]);
    }

    const controller = new AbortController();
    job.controller = controller;

    try {
      bumpSessionToTop(targetChatId);

      const res = await fetch(`${backendUrl}/chats/${targetChatId}/message_stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          message: nextMessage.text,
          attachments: nextMessage.attachments
        }),
        signal: controller.signal
      });

      await consumeSSEStream(res, (data: any) => {
        if (data.type === "title_update" && data.title) {
          const updatedTitle = data.title;
          updateSessionsList(prev => prev.map(s => s.id === targetChatId ? { ...s, title: updatedTitle } : s));
          if (activeChatIdRef.current === targetChatId) {
            document.title = `${updatedTitle} - NotbookLM`;
          }
        } else if (data.type === "status") {
          const statusText = data.text || data.data;
          if (statusText) {
            job.status = statusText;
            if (activeChatIdRef.current === targetChatId) {
              setActiveStatus(statusText);
            }
          }
        } else if (data.type === "done") {
          const asstMsg = data.message || { role: "assistant", content: data.data || "", created_at: new Date().toISOString() };
          if (activeChatIdRef.current === targetChatId) {
            updateMessagesList(prev => [...prev, asstMsg]);
          }

          // Check if response contains an action payload like deleting documents
          const actionMatch = asstMsg.content?.match(/<!-- SOURCES_ACTION:\s*([\s\S]*?)\s*-->/);
          if (actionMatch) {
            try {
              const actionObj = JSON.parse(actionMatch[1]);
              if (actionObj.action === "bulk_delete" && actionObj.deleted_doc_ids) {
                const idSet = new Set(actionObj.deleted_doc_ids);
                if (activeChatIdRef.current === targetChatId) {
                  updateDocumentsList(prev => {
                    const remaining = prev.filter(d => !idSet.has(d.id));
                    return remaining.map((doc, idx) => ({ ...doc, index: idx + 1 }));
                  });
                }
              }
            } catch (e) {
              console.error("Failed to parse sources action:", e);
            }
          }
        } else if (data.type === "error") {
          const errorMsg = data.message || { role: "assistant", content: `⚠️ ${data.data || "Error processing request"}`, created_at: new Date().toISOString() };
          if (activeChatIdRef.current === targetChatId) {
            updateMessagesList(prev => [...prev, errorMsg]);
          }
        }
      });
    } catch (err: any) {
      if (err?.name === "AbortError") {
        console.log(`Generation stopped by user for chat ${targetChatId}`);
        if (activeChatIdRef.current === targetChatId) {
          updateMessagesList(prev => [
            ...prev,
            { role: "assistant", content: "*(Response generation stopped by user)*", created_at: new Date().toISOString() }
          ]);
        }
        return; // Halt further queued processing on user abort
      } else {
        console.error("Failed to send queued message:", err);
        if (activeChatIdRef.current === targetChatId) {
          updateMessagesList(prev => [
            ...prev,
            { role: "assistant", content: "⚠️ Sorry, an error occurred while connecting to the AI server.", created_at: new Date().toISOString() }
          ]);
        }
      }
    } finally {
      if (job.controller === controller) {
        job.controller = null;
      }
      job.status = null;
      if (activeChatIdRef.current === targetChatId) {
        setActiveStatus(null);
      }
      // Recursively process the next message in queue for this chat
      if (job.queue.length > 0) {
        await processNextInQueue(targetChatId);
      } else {
        job.isProcessing = false;
        if (activeChatIdRef.current === targetChatId) {
          setIsLoading(false);
        }
      }
    }
  };

  const handleSendMessage = async (text: string, attachments?: Attachment[]) => {
    let currentChatId = activeChatIdRef.current;
    if (!currentChatId) {
      currentChatId = await handleEnsureChatSession(text);
    }
    if (!currentChatId) return;

    const job = getChatJob(currentChatId);

    if (job.isProcessing) {
      // If AI is currently generating for this chat, add to queue
      job.queue.push({ text, attachments });
      if (activeChatIdRef.current === currentChatId) {
        setQueuedPrompts(job.queue.map(q => q.text));
      }
      return;
    }

    job.queue.push({ text, attachments });
    if (activeChatIdRef.current === currentChatId) {
      setQueuedPrompts(job.queue.map(q => q.text));
    }

    await processNextInQueue(currentChatId);
  };

  const handleEditMessage = async (messageIndex: number, newContent: string) => {
    let currentChatId = activeChatIdRef.current;
    if (!currentChatId) {
      currentChatId = await handleEnsureChatSession(newContent);
    }
    if (!currentChatId) return;

    const job = getChatJob(currentChatId);

    // Abort any ongoing request and clear pending queue on edit
    if (job.controller) {
      job.controller.abort();
      job.controller = null;
    }
    job.queue = [];
    job.isProcessing = true;
    job.status = "Analyzing query & reasoning...";

    if (activeChatIdRef.current === currentChatId) {
      setQueuedPrompts([]);
      setIsLoading(true);
      setActiveStatus(job.status);
    }

    const controller = new AbortController();
    job.controller = controller;

    bumpSessionToTop(currentChatId);

    // Optimistically update message list: keep messages up to messageIndex, replace at messageIndex, remove subsequent responses
    const updatedUserMsg: ChatMessage = { role: "user", content: newContent, created_at: new Date().toISOString() };
    if (activeChatIdRef.current === currentChatId) {
      updateMessagesList(prev => [...prev.slice(0, messageIndex), updatedUserMsg]);
    }

    try {
      const res = await fetch(`${backendUrl}/chats/${currentChatId}/edit_message_stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_index: messageIndex,
          message: newContent
        }),
        signal: controller.signal
      });

      await consumeSSEStream(res, (data: any) => {
        if (data.type === "status") {
          const statusText = data.text || data.data;
          if (statusText) {
            job.status = statusText;
            if (activeChatIdRef.current === currentChatId) {
              setActiveStatus(statusText);
            }
          }
        } else if (data.type === "done") {
          const asstMsg = data.message || { role: "assistant", content: data.data || "", created_at: new Date().toISOString() };
          if (activeChatIdRef.current === currentChatId) {
            updateMessagesList(prev => [...prev, asstMsg]);
          }

          const actionMatch = asstMsg.content?.match(/<!-- SOURCES_ACTION:\s*([\s\S]*?)\s*-->/);
          if (actionMatch) {
            try {
              const actionObj = JSON.parse(actionMatch[1]);
              if (actionObj.action === "bulk_delete" && actionObj.deleted_doc_ids) {
                const idSet = new Set(actionObj.deleted_doc_ids);
                if (activeChatIdRef.current === currentChatId) {
                  updateDocumentsList(prev => {
                    const remaining = prev.filter(d => !idSet.has(d.id));
                    return remaining.map((doc, idx) => ({ ...doc, index: idx + 1 }));
                  });
                }
              }
            } catch (e) {
              console.error("Failed to parse sources action:", e);
            }
          }
        } else if (data.type === "error") {
          const errorMsg = data.message || { role: "assistant", content: `⚠️ ${data.data || "Error processing request"}`, created_at: new Date().toISOString() };
          if (activeChatIdRef.current === currentChatId) {
            updateMessagesList(prev => [...prev, errorMsg]);
          }
        }
      });
    } catch (err: any) {
      if (err?.name === "AbortError") {
        console.log(`Edit request aborted for chat ${currentChatId}`);
      } else {
        console.error("Failed to edit message:", err);
        if (activeChatIdRef.current === currentChatId) {
          updateMessagesList(prev => [
            ...prev,
            { role: "assistant", content: "⚠️ Sorry, an error occurred while editing the message.", created_at: new Date().toISOString() }
          ]);
        }
      }
    } finally {
      if (job.controller === controller) {
        job.controller = null;
      }
      job.isProcessing = false;
      job.status = null;
      if (activeChatIdRef.current === currentChatId) {
        setActiveStatus(null);
        setIsLoading(false);
      }
    }
  };

  const handleRegenerateMessage = async (messageIndex: number) => {
    const currentChatId = activeChatId;
    if (!currentChatId || isLoading) return;

    const job = getChatJob(currentChatId);
    if (job.isProcessing) return;

    job.isProcessing = true;
    job.status = "Regenerating response...";
    if (activeChatIdRef.current === currentChatId) {
      setIsLoading(true);
      setActiveStatus(job.status);
      // Truncate all messages below the regenerating message and blank out target slot
      updateMessagesList(prev => {
        const next = prev.slice(0, messageIndex + 1);
        if (next[messageIndex]) {
          next[messageIndex] = {
            ...next[messageIndex],
            content: ""
          };
        }
        return next;
      });
    }

    const controller = new AbortController();
    job.controller = controller;

    bumpSessionToTop(currentChatId);

    try {
      const res = await fetch(`${backendUrl}/chats/${currentChatId}/regenerate_stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_index: messageIndex
        }),
        signal: controller.signal
      });

      await consumeSSEStream(res, (data: any) => {
        if (data.type === "status") {
          const statusText = data.text || data.data;
          if (statusText) {
            job.status = statusText;
            if (activeChatIdRef.current === currentChatId) {
              setActiveStatus(statusText);
            }
          }
        } else if (data.type === "done") {
          const asstMsg = data.message || {
            role: "assistant",
            content: data.data || "",
            variants: data.variants,
            active_variant_index: data.active_variant_index,
            created_at: new Date().toISOString()
          };
          if (activeChatIdRef.current === currentChatId) {
            updateMessagesList(prev => {
              const next = prev.slice(0, messageIndex + 1);
              if (next[messageIndex]) {
                next[messageIndex] = asstMsg;
              } else {
                next.push(asstMsg);
              }
              return next;
            });
          }

          const actionMatch = asstMsg.content?.match(/<!-- SOURCES_ACTION:\s*([\s\S]*?)\s*-->/);
          if (actionMatch) {
            try {
              const actionObj = JSON.parse(actionMatch[1]);
              if (actionObj.action === "bulk_delete" && actionObj.deleted_doc_ids) {
                const idSet = new Set(actionObj.deleted_doc_ids);
                if (activeChatIdRef.current === currentChatId) {
                  updateDocumentsList(prev => {
                    const remaining = prev.filter(d => !idSet.has(d.id));
                    return remaining.map((doc, idx) => ({ ...doc, index: idx + 1 }));
                  });
                }
              }
            } catch (e) {
              console.error("Failed to parse SOURCES_ACTION in regenerated response:", e);
            }
          }
        }
      });
    } catch (err: any) {
      if (err?.name === "AbortError") {
        console.log(`Regenerate request aborted for chat ${currentChatId}`);
      } else {
        console.error("Failed to regenerate message:", err);
      }
    } finally {
      if (job.controller === controller) {
        job.controller = null;
      }
      job.isProcessing = false;
      job.status = null;
      if (activeChatIdRef.current === currentChatId) {
        setActiveStatus(null);
        setIsLoading(false);
      }
    }
  };

  const handleSelectVariant = async (messageIndex: number, variantIndex: number) => {
    const currentChatId = activeChatId;
    if (!currentChatId) return;

    updateMessagesList(prev => {
      const next = [...prev];
      const msg = { ...next[messageIndex] };
      if (msg.variants && msg.variants[variantIndex] !== undefined) {
        msg.active_variant_index = variantIndex;
        msg.content = msg.variants[variantIndex];
        next[messageIndex] = msg;
      }
      return next;
    });

    try {
      await fetch(`${backendUrl}/chats/${currentChatId}/select_variant`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_index: messageIndex,
          variant_index: variantIndex
        })
      });
    } catch (e) {
      console.error("Failed to persist selected variant:", e);
    }
  };

  const handleCreateChat = () => {
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

  const handleSelectChat = (id: string) => {
    setCurrentView("chat");
    if (activeChatId === id) return;

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

  const handleBulkDocumentsDeleted = (docIds: number[]) => {
    const idSet = new Set(docIds);
    updateDocumentsList(prev => {
      const remaining = prev.filter(d => !idSet.has(d.id));
      return remaining.map((doc, idx) => ({ ...doc, index: idx + 1 }));
    });
  };

  const handleDocumentAdded = (doc: Document, targetChatId?: string) => {
    // Only append to the visible documents list if the user is currently viewing the target chat
    if (!targetChatId || targetChatId === activeChatIdRef.current) {
      updateDocumentsList(prev => {
        if (prev.some(d => d.id === doc.id)) return prev;
        return [...prev, doc];
      });
      // Remove matching pending item by doi or filename matching
      updatePendingSourcesList(prev => prev.filter(p => {
        if (p.doi && doc.doi && p.doi.toLowerCase().trim() === doc.doi.toLowerCase().trim()) return false;
        const normP = (p.filename || "").toLowerCase().replace(/\.pdf$/i, "").replace(/[^a-z0-9]/g, "");
        const normDocFn = (doc.filename || "").toLowerCase().replace(/\.pdf$/i, "").replace(/[^a-z0-9]/g, "");
        const normDocTitle = (doc.title || "").toLowerCase().replace(/\.pdf$/i, "").replace(/[^a-z0-9]/g, "");
        if (normP && (normP === normDocFn || normP === normDocTitle || normDocFn.includes(normP) || normP.includes(normDocFn))) {
          return false;
        }
        return true;
      }));
    }
  };

  const handleAddPendingSources = (items: PendingSourceItem[]) => {
    updatePendingSourcesList(prev => [...prev, ...items]);
  };

  const handleResolvePendingSource = (pendingId: string) => {
    updatePendingSourcesList(prev => prev.filter(p => p.id !== pendingId));
  };

  const handleDocumentUpdated = (updatedDoc: Document) => {
    updateDocumentsList(prev => prev.map(d => d.id === updatedDoc.id ? { ...d, title: updatedDoc.title } : d));
    if (viewingDoc && viewingDoc.id === updatedDoc.id) {
      setViewingDoc({ ...viewingDoc, title: updatedDoc.title });
    }
  };

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);
  const [mobileTab, setMobileTab] = useState<"menu" | "chat" | "sources">("chat");

  return (
    <div className="flex flex-col h-screen w-full overflow-hidden bg-app-bg text-app-text">
      {/* Mobile/Tablet NotebookLM Top Header Bar (< lg) */}
      <div className="lg:hidden shrink-0 bg-app-sidebar border-b border-app-border z-50 flex flex-col">
        {/* Row 1: Brand / Active Chat Title + Settings Gear Icon */}
        <div className="px-4 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0 pr-2">
            <div className="p-1 rounded-md bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm flex items-center justify-center shrink-0">
              <Sparkles size={14} />
            </div>
            <span className="text-sm font-semibold text-app-text truncate">
              {currentView === "library" 
                ? "Library" 
                : currentView === "search" 
                ? "Search" 
                : (activeChatId ? (sessions.find(s => s.id === activeChatId)?.title || "NotbookLM") : "NotbookLM")}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-1.5 rounded-lg text-app-text-muted hover:text-app-text hover:bg-app-item-hover transition-colors cursor-pointer"
              title="Settings"
            >
              <Settings size={17} />
            </button>
          </div>
        </div>

        {/* Row 2: 3 Tabs (Menu | Chat | Sources) */}
        <div className="flex items-center justify-around text-xs font-medium border-t border-app-divider">
          {/* 1. Left Tab: Menu */}
          <button
            onClick={() => {
              setMobileTab("menu");
              setIsSidebarOpen(true);
            }}
            className={`flex-1 py-2.5 text-center relative transition-colors cursor-pointer ${
              mobileTab === "menu" ? "text-app-text font-semibold" : "text-app-text-muted hover:text-app-text"
            }`}
          >
            <span>{t('nav.menu')}</span>
            {mobileTab === "menu" && (
              <div className="absolute bottom-0 inset-x-4 h-0.5 bg-blue-500 rounded-full"></div>
            )}
          </button>

          {/* 2. Middle Tab: Dynamic Label (Chat | Library | Search) */}
          <button
            onClick={() => {
              setMobileTab("chat");
            }}
            className={`flex-1 py-2.5 text-center relative transition-colors cursor-pointer ${
              mobileTab === "chat" ? "text-app-text font-semibold" : "text-app-text-muted hover:text-app-text"
            }`}
          >
            <span>
              {currentView === "library" ? t('nav.library') : currentView === "search" ? t('nav.search') : t('nav.chat')}
            </span>
            {mobileTab === "chat" && (
              <div className="absolute bottom-0 inset-x-4 h-0.5 bg-blue-500 rounded-full"></div>
            )}
          </button>

          {/* 3. Right Tab: Sources (Disabled & Dimmed when on Library / Search view) */}
          {currentView === "chat" ? (
            <button
              onClick={() => {
                setMobileTab("sources");
                setIsRightSidebarOpen(true);
              }}
              className={`flex-1 py-2.5 text-center relative transition-colors cursor-pointer ${
                mobileTab === "sources" ? "text-app-text font-semibold" : "text-app-text-muted hover:text-app-text"
              }`}
            >
              <span>{t('nav.sources')}</span>
              {mobileTab === "sources" && (
                <div className="absolute bottom-0 inset-x-4 h-0.5 bg-blue-500 rounded-full"></div>
              )}
            </button>
          ) : (
            <div
              className="flex-1 py-2.5 text-center relative text-app-text-dim cursor-not-allowed select-none opacity-40"
              title={t('nav.sourcesDisabledTooltip')}
            >
              <span>{t('nav.sources')}</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex min-w-0 h-full overflow-hidden relative">
        {/* Left Sidebar: Chat Sessions (Shown on desktop if open, or when mobileTab is 'menu' on smaller screens) */}
        {(isSidebarOpen || mobileTab === "menu") && (
          <div className={`h-full min-w-0 ${mobileTab === "menu" ? "w-full z-40 lg:w-auto" : "hidden lg:block"}`}>
            <LeftSidebar 
              sessions={sessions} 
              activeChatId={activeChatId} 
              currentView={currentView}
              onSelectChat={(id) => {
                handleSelectChat(id);
                setCurrentView("chat");
                setMobileTab("chat");
              }}
              onCreateChat={() => {
                handleCreateChat();
                setCurrentView("chat");
                setMobileTab("chat");
              }}
              onOpenLibrary={(cat) => {
                setLibraryInitialCategory(cat || "all");
                setCurrentView("library");
                setMobileTab("chat");
              }}
              onOpenSearch={() => {
                setCurrentView("search");
                setMobileTab("chat");
              }}
              onDeleteChat={handleDeleteChat}
              onRenameChat={handleRenameChat}
              onTogglePinChat={handleTogglePinChat}
              onToggleSidebar={() => {
                setIsSidebarOpen(false);
                setMobileTab("chat");
              }}
              onOpenSettings={() => setIsSettingsOpen(true)}
            />
          </div>
        )}
        
        {/* Center View: Main Chat Area, Library View, or Search View */}
        {currentView === "library" ? (
          <LibraryView
            initialCategory={libraryInitialCategory}
            backendUrl={backendUrl}
            isSidebarOpen={isSidebarOpen}
            onOpenSidebar={() => setIsSidebarOpen(true)}
            onSelectChat={handleSelectChat}
          />
        ) : currentView === "search" ? (
          <SearchChatsView
            sessions={sessions}
            backendUrl={backendUrl}
            isSidebarOpen={isSidebarOpen}
            onOpenSidebar={() => setIsSidebarOpen(true)}
            onSelectChat={handleSelectChat}
          />
        ) : (
          <div className={`flex-1 flex min-w-0 h-full overflow-hidden ${mobileTab === "menu" ? "hidden lg:flex" : "flex"}`}>
            <div className={`flex-1 h-full min-w-0 ${mobileTab === "sources" ? "hidden lg:flex" : "flex"}`}>
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
                onDocumentAdded={handleDocumentAdded}
                onAddPendingSources={handleAddPendingSources}
                onResolvePendingSource={handleResolvePendingSource}
                onOpenDocument={(doc, citationContext) => {
                  setViewingDoc(doc);
                  if (citationContext) {
                    setGroundingHighlight({
                      docId: doc.id,
                      sentence: citationContext.sentence,
                      num: citationContext.num,
                      citationKey: citationContext.citationKey,
                      aiQuotes: citationContext.aiQuotes,
                      clickId: Date.now()
                    });
                  } else {
                    setGroundingHighlight(null);
                  }
                  setIsRightSidebarOpen(true);
                  setMobileTab("sources");
                }}
                onEnsureChatSession={handleEnsureChatSession}
                backendUrl={backendUrl}
                isSidebarOpen={isSidebarOpen}
                onOpenSidebar={() => {
                  setIsSidebarOpen(true);
                  setMobileTab("menu");
                }}
                isRightSidebarOpen={isRightSidebarOpen}
                onToggleRightSidebar={() => {
                  if (typeof window !== "undefined" && window.innerWidth < 1024) {
                    setMobileTab(prev => (prev === "sources" ? "chat" : "sources"));
                    setIsRightSidebarOpen(true);
                  } else {
                    setIsRightSidebarOpen(prev => !prev);
                  }
                }}
                targetedSource={targetedSource}
                onClearTargetedSource={() => setTargetedSource(null)}
                activeStatus={activeStatus}
                activeCitationKey={groundingHighlight?.citationKey}
                onRenameChat={handleRenameChat}
                onDeleteChat={handleDeleteChat}
                onTogglePinChat={handleTogglePinChat}
                isPinned={sessions.find(s => s.id === activeChatId)?.is_pinned}
                chatTitle={sessions.find(s => s.id === activeChatId)?.title}
                onRegenerateMessage={handleRegenerateMessage}
                onSelectVariant={handleSelectVariant}
                onOpenStorage={() => setIsSettingsOpen(true)}
              />
            </div>

            {/* Right Sidebar: Sources Panel (NotebookLM Style) */}
            {(isRightSidebarOpen || mobileTab === "sources") && (
              <div className={`h-full min-w-0 ${mobileTab === "chat" ? "hidden lg:block" : "w-full lg:w-auto"}`}>
                <RightSidebar 
                  activeChatId={activeChatId} 
                  documents={documents} 
                  pendingSources={pendingSources}
                  onDocumentAdded={handleDocumentAdded} 
                  onDocumentUpdated={handleDocumentUpdated}
                  onDocumentDeleted={(id) => {
                    updateDocumentsList(prev => prev.filter(d => d.id !== id));
                    if (targetedSource?.id === id) setTargetedSource(null);
                    if (viewingDoc?.id === id) setViewingDoc(null);
                  }}
                  onBulkDocumentsDeleted={(ids) => {
                    handleBulkDocumentsDeleted(ids);
                    if (targetedSource && ids.includes(targetedSource.id)) setTargetedSource(null);
                    if (viewingDoc && ids.includes(viewingDoc.id)) setViewingDoc(null);
                  }}
                  onEnsureChatSession={handleEnsureChatSession}
                  onAskAboutDocument={(doc, paperTitle) => {
                    setTargetedSource({ id: doc.id, filename: doc.filename, title: paperTitle });
                    setMobileTab("chat");
                  }}
                  externalViewingDoc={viewingDoc}
                  groundingHighlight={groundingHighlight}
                  onClearGroundingHighlight={() => setGroundingHighlight(null)}
                  onClearViewingDoc={() => {
                    setViewingDoc(null);
                    setGroundingHighlight(null);
                  }}
                  backendUrl={backendUrl}
                  onClose={() => {
                    setIsRightSidebarOpen(false);
                    setGroundingHighlight(null);
                    setMobileTab("chat");
                  }}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Global Settings & Storage Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        backendUrl={backendUrl}
        sessions={sessions}
        onNavigateToLibrary={(cat) => {
          setLibraryInitialCategory(cat);
          setCurrentView("library");
        }}
        onChatsDeleted={(deletedIds) => {
          updateSessionsList(prev => prev.filter(s => !deletedIds.includes(s.id)));
          if (activeChatId && deletedIds.includes(activeChatId)) {
            const remaining = sessions.filter(s => !deletedIds.includes(s.id));
            if (remaining.length > 0) {
              handleSelectChat(remaining[0].id);
            } else {
              handleCreateChat();
            }
          }
        }}
        onAllDataReset={() => {
          setSessions([]);
          setDocuments([]);
          setMessages([]);
          setActiveChatId(null);
          setViewingDoc(null);
          setGroundingHighlight(null);
          handleCreateChat();
        }}
      />
    </div>
  );
}
