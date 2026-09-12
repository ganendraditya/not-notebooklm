import { create } from 'zustand';

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at?: string;
  is_pinned?: boolean;
}

export interface Attachment {
  type: "image" | "file";
  filename: string;
  url?: string;
}

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  role: MessageRole;
  content: string;
  created_at: string;
  attachments?: Attachment[];
  variants?: string[];
  active_variant_index?: number;
  isStreaming?: boolean;
}

interface ChatStore {
  sessions: ChatSession[];
  activeChatId: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  activeStatus: string | null;
  queuedPrompts: string[];
  
  setSessions: (sessions: ChatSession[]) => void;
  setActiveChatId: (id: string | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  setIsLoading: (isLoading: boolean) => void;
  setActiveStatus: (status: string | null) => void;
  setQueuedPrompts: (prompts: string[]) => void;
  
  bumpSessionToTop: (chatId: string) => void;
  addMessage: (message: ChatMessage) => void;
  updateMessage: (index: number, partialMessage: Partial<ChatMessage>) => void;
  updateMessagesList: (updater: (prev: ChatMessage[]) => ChatMessage[]) => void;
  updateSessionsList: (updater: (prev: ChatSession[]) => ChatSession[]) => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  sessions: [],
  activeChatId: null,
  messages: [],
  isLoading: false,
  activeStatus: null,
  queuedPrompts: [],

  setSessions: (sessions) => set({ sessions }),
  setActiveChatId: (activeChatId) => set({ activeChatId }),
  setMessages: (messages) => set({ messages }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setActiveStatus: (activeStatus) => set({ activeStatus }),
  setQueuedPrompts: (queuedPrompts) => set({ queuedPrompts }),

  bumpSessionToTop: (chatId) => set((state) => {
    const idx = state.sessions.findIndex(s => s.id === chatId);
    if (idx <= 0) return state;
    const target = { ...state.sessions[idx], updated_at: new Date().toISOString() };
    const rest = state.sessions.filter((_, i) => i !== idx);
    return { sessions: [target, ...rest] };
  }),

  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (index, partialMessage) => set((state) => {
    const newMessages = [...state.messages];
    if (newMessages[index]) {
      newMessages[index] = { ...newMessages[index], ...partialMessage };
    }
    return { messages: newMessages };
  }),
  updateMessagesList: (updater) => set((state) => ({ messages: updater(state.messages) })),
  updateSessionsList: (updater) => set((state) => ({ sessions: updater(state.sessions) }))
}));