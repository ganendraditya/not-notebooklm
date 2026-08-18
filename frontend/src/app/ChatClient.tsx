"use client";

import { useState, useEffect } from "react";
import LeftSidebar from "@/components/LeftSidebar";
import ChatArea from "@/components/ChatArea";
import RightSidebar from "@/components/RightSidebar";

// Types
export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
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
  
  const backendUrl = "http://localhost:8000";

  // Fetch all sessions on mount
  useEffect(() => {
    fetch(`${backendUrl}/chats`)
      .then(res => res.json())
      .then(data => setSessions(data))
      .catch(err => console.error("Failed to fetch sessions:", err));
  }, []);

  // Fetch chat details when active chat changes
  useEffect(() => {
    if (activeChatId) {
      fetch(`${backendUrl}/chats/${activeChatId}`)
        .then(res => res.json())
        .then(data => {
          setDocuments(data.documents || []);
          setMessages(data.messages || []);
        })
        .catch(err => console.error("Failed to fetch chat details:", err));
    } else {
      setDocuments([]);
      setMessages([]);
    }
  }, [activeChatId]);

  const handleCreateChat = async (title: string) => {
    try {
      const res = await fetch(`${backendUrl}/chats`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title })
      });
      const newChat = await res.json();
      setSessions([newChat, ...sessions]);
      setActiveChatId(newChat.id);
    } catch (err) {
      console.error("Failed to create chat:", err);
    }
  };

  const handleSendMessage = async (message: string) => {
    let currentChatId = activeChatId;
    
    // If no active chat, create one automatically first (like ChatGPT)
    if (!currentChatId) {
      try {
        const title = message.length > 30 ? message.substring(0, 30) + "..." : message;
        const res = await fetch(`${backendUrl}/chats`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title })
        });
        const newChat = await res.json();
        setSessions(prev => [newChat, ...prev]);
        setActiveChatId(newChat.id);
        currentChatId = newChat.id;
      } catch (err) {
        console.error("Failed to create chat:", err);
        return;
      }
    }
    
    // Optimistically add user message
    const newMsg: ChatMessage = { role: "user", content: message, created_at: new Date().toISOString() };
    setMessages(prev => [...prev, newMsg]);

    try {
      const res = await fetch(`${backendUrl}/chats/${currentChatId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });
      const assistantMsg = await res.json();
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      console.error("Failed to send message:", err);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#212121]">
      {/* Left Sidebar: Chat History */}
      <LeftSidebar 
        sessions={sessions} 
        activeChatId={activeChatId} 
        onSelectChat={setActiveChatId}
        onCreateChat={handleCreateChat}
      />
      
      {/* Center: Main Chat Area */}
      <ChatArea 
        activeChatId={activeChatId} 
        messages={messages} 
        onSendMessage={handleSendMessage} 
        documents={documents}
        onDocumentAdded={(doc) => setDocuments([...documents, doc])}
        backendUrl={backendUrl}
      />
    </div>
  );
}
