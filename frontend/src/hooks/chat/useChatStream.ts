import { useRef } from "react";
import { type ChatMessage, type Attachment } from "@/stores/chatStore";
import { consumeSSEStream } from "@/lib/sse";
import { sendSystemNotification } from "@/lib/notifications";
import { createSmoothTextStreamer } from "@/lib/smoothStreamer";

// Queue now needs to store attachments too
export interface QueuedMessage {
  text: string;
  attachments?: Attachment[];
}

export interface ChatJobState {
  controller: AbortController | null;
  queue: QueuedMessage[];
  isProcessing: boolean;
  status: string | null;
}

export function useChatStream(
  backendUrl: string,
  activeChatIdRef: React.MutableRefObject<string | null>,
  messages: ChatMessage[],
  setMessages: (msgs: ChatMessage[]) => void,
  setIsLoading: (loading: boolean) => void,
  setActiveStatus: (status: string | null) => void,
  setQueuedPrompts: (prompts: string[]) => void,
  bumpSessionToTop: (id: string) => void,
  updateSessionsList: (updater: (prev: any[]) => any[]) => void,
  updateMessagesList: (updater: (prev: ChatMessage[]) => ChatMessage[]) => void,
  updateDocumentsList: (updater: (prev: any[]) => any[]) => void,
  handleEnsureChatSessionRef: React.MutableRefObject<(suggestedTitle?: string) => Promise<string>>
) {
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
      const assistantPlaceholder: ChatMessage = {
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
        isStreaming: true
      };
      updateMessagesList(prev => [...prev, newMsg, assistantPlaceholder]);
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

      let latestAsstMsg: any = null;

      const smoother = createSmoothTextStreamer({
        onUpdate: (displayed) => {
          if (activeChatIdRef.current === targetChatId) {
            updateMessagesList(prev => {
              const lastMsg = prev[prev.length - 1];
              if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMsg, content: displayed }
                ];
              } else {
                return [
                  ...prev,
                  { role: "assistant", content: displayed, created_at: new Date().toISOString(), isStreaming: true }
                ];
              }
            });
          }
        },
        onDone: () => {
          const asstMsg = latestAsstMsg || { role: "assistant", content: "", created_at: new Date().toISOString() };
          if (activeChatIdRef.current === targetChatId) {
            updateMessagesList(prev => {
              const lastMsg = prev[prev.length - 1];
              if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
                return [...prev.slice(0, -1), { ...asstMsg, isStreaming: false }];
              }
              return [...prev, asstMsg];
            });
          }

          // Trigger system / browser notification if user is away in another tab
          const cleanPreview = (asstMsg.content || "")
            .replace(/<!--[\s\S]*?-->/g, "")
            .replace(/\[\^(\d+)\]/g, "")
            .trim();
          sendSystemNotification({
            category: "responses",
            titleKey: "notify.responseCompleteTitle",
            title: "NotbookLM: Response Ready",
            body: cleanPreview,
            bodyKey: "notify.responseCompleteBody",
          });

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
        }
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
        } else if (data.type === "clear_delta" || data.type === "reset_stream") {
          smoother.reset("");
        } else if (data.type === "delta") {
          const chunkText = data.text ?? data.data ?? "";
          if (chunkText) {
            smoother.pushDelta(chunkText);
          }
        } else if (data.type === "done") {
          latestAsstMsg = data.message || { role: "assistant", content: data.data || "", created_at: new Date().toISOString() };
          smoother.finish();
        } else if (data.type === "error") {
          smoother.stop();
          const errorMsg = data.message || { role: "assistant", content: `⚠️ ${data.data || "Error processing request"}`, created_at: new Date().toISOString() };
          if (activeChatIdRef.current === targetChatId) {
            updateMessagesList(prev => [...prev, errorMsg]);
          }
          sendSystemNotification({
            category: "responses",
            titleKey: "notify.errorTitle",
            title: "NotbookLM: An Error Occurred",
            body: data.data,
            bodyKey: "notify.errorBody",
          });
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

  const handleSendMessage = async (text: string, attachments?: Attachment[]) => {
    let currentChatId = activeChatIdRef.current;
    if (!currentChatId) {
      currentChatId = await handleEnsureChatSessionRef.current(text);
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
      currentChatId = await handleEnsureChatSessionRef.current(newContent);
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
    const assistantPlaceholder: ChatMessage = { role: "assistant", content: "", created_at: new Date().toISOString(), isStreaming: true };
    if (activeChatIdRef.current === currentChatId) {
      updateMessagesList(prev => [...prev.slice(0, messageIndex), updatedUserMsg, assistantPlaceholder]);
    }

    let latestAsstMsg: any = null;

    const smoother = createSmoothTextStreamer({
      onUpdate: (displayed) => {
        if (activeChatIdRef.current === currentChatId) {
          updateMessagesList(prev => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
              return [
                ...prev.slice(0, -1),
                { ...lastMsg, content: displayed }
              ];
            } else {
              return [
                ...prev,
                { role: "assistant", content: displayed, created_at: new Date().toISOString(), isStreaming: true }
              ];
            }
          });
        }
      },
      onDone: () => {
        const asstMsg = latestAsstMsg || { role: "assistant", content: "", created_at: new Date().toISOString() };
        if (activeChatIdRef.current === currentChatId) {
          updateMessagesList(prev => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
              return [...prev.slice(0, -1), { ...asstMsg, isStreaming: false }];
            }
            return [...prev, asstMsg];
          });
        }

        const cleanPreview = (asstMsg.content || "")
          .replace(/<!--[\s\S]*?-->/g, "")
          .replace(/\[\^(\d+)\]/g, "")
          .trim();
        sendSystemNotification({
          category: "responses",
          titleKey: "notify.editCompleteTitle",
          title: "NotbookLM: Edit Completed",
          body: cleanPreview,
          bodyKey: "notify.editCompleteBody",
        });

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
      }
    });

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
        } else if (data.type === "clear_delta" || data.type === "reset_stream") {
          smoother.reset("");
        } else if (data.type === "delta") {
          const chunkText = data.text ?? data.data ?? "";
          if (chunkText) {
            smoother.pushDelta(chunkText);
          }
        } else if (data.type === "done") {
          latestAsstMsg = data.message || { role: "assistant", content: data.data || "", created_at: new Date().toISOString() };
          smoother.finish();
        } else if (data.type === "error") {
          smoother.stop();
          const errorMsg = data.message || { role: "assistant", content: `⚠️ ${data.data || "Error processing request"}`, created_at: new Date().toISOString() };
          if (activeChatIdRef.current === currentChatId) {
            updateMessagesList(prev => [...prev, errorMsg]);
          }
          sendSystemNotification({
            category: "responses",
            titleKey: "notify.errorTitle",
            title: "NotbookLM: An Error Occurred",
            body: data.data,
            bodyKey: "notify.editErrorBody",
          });
        }
      });
    } catch (err: any) {
      smoother.stop();
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
    const currentChatId = activeChatIdRef.current;
    // isLoading here is somewhat managed externally by UI check, but we enforce chat ID check
    if (!currentChatId) return;

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

    let latestAsstMsg: any = null;

    const smoother = createSmoothTextStreamer({
      onUpdate: (displayed) => {
        if (activeChatIdRef.current === currentChatId) {
          updateMessagesList(prev => {
            const next = [...prev];
            const target = next[messageIndex];
            if (target && target.role === "assistant") {
              next[messageIndex] = { ...target, content: displayed, isStreaming: true };
            } else {
              next[messageIndex] = { role: "assistant", content: displayed, created_at: new Date().toISOString(), isStreaming: true };
            }
            return next;
          });
        }
      },
      onDone: () => {
        const asstMsg = latestAsstMsg || {
          role: "assistant",
          content: "",
          created_at: new Date().toISOString()
        };
        if (activeChatIdRef.current === currentChatId) {
          updateMessagesList(prev => {
            const next = prev.slice(0, messageIndex + 1);
            if (next[messageIndex]) {
              next[messageIndex] = { ...asstMsg, isStreaming: false };
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

        const cleanPreview = (asstMsg.content || "")
          .replace(/<!--[\s\S]*?-->/g, "")
          .replace(/\[\^(\d+)\]/g, "")
          .trim();
        sendSystemNotification({
          category: "responses",
          titleKey: "notify.regenerateCompleteTitle",
          title: "NotbookLM: Regeneration Ready",
          body: cleanPreview,
          bodyKey: "notify.regenerateCompleteBody",
        });
      }
    });

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
        } else if (data.type === "clear_delta" || data.type === "reset_stream") {
          smoother.reset("");
        } else if (data.type === "delta") {
          const chunkText = data.text ?? data.data ?? "";
          if (chunkText) {
            smoother.pushDelta(chunkText);
          }
        } else if (data.type === "done") {
          latestAsstMsg = data.message || {
            role: "assistant",
            content: data.data || "",
            variants: data.variants,
            active_variant_index: data.active_variant_index,
            created_at: new Date().toISOString()
          };
          smoother.finish();
        }
      });
    } catch (err: any) {
      smoother.stop();
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
    const currentChatId = activeChatIdRef.current;
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

  return {
    getChatJob,
    handleStopGeneration,
    handleRemoveQueuedPrompt,
    handlePromoteQueuedPrompt,
    handleSendMessage,
    handleEditMessage,
    handleRegenerateMessage,
    handleSelectVariant
  };
}