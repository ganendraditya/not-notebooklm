import { useState, useRef, useEffect } from "react";
import { ArrowUp, Plus, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatSession, ChatMessage } from "@/app/ChatClient";
import RightSidebar from "@/components/RightSidebar";

interface ChatAreaProps {
  activeChatId: string | null;
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  // Passing these so we can render RightSidebar as a Sheet inside ChatArea
  documents: any[];
  onDocumentAdded: (doc: any) => void;
  backendUrl: string;
}

export default function ChatArea({ 
  activeChatId, messages, onSendMessage, 
  documents, onDocumentAdded, backendUrl 
}: ChatAreaProps) {
  const [input, setInput] = useState("");
  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const isChatEmpty = !activeChatId || messages.length === 0;

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 flex flex-col h-full bg-[#212121] relative overflow-hidden">
      
      {isChatEmpty ? (
        <div className="flex-1 flex flex-col items-center justify-center px-4 pb-[10vh]">
          <h2 className="text-3xl font-semibold mb-6 text-foreground">Not NotebookLM</h2>
        </div>
      ) : (
        <ScrollArea className="flex-1 px-4 sm:px-6">
          <div className="max-w-3xl mx-auto space-y-6 pb-32 pt-8">
            {messages.map((msg, idx) => (
              <div 
                key={idx} 
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div 
                  className={`max-w-[80%] rounded-2xl px-5 py-3 ${
                    msg.role === 'user' 
                      ? 'bg-[#2f2f2f] text-foreground' 
                      : 'bg-transparent text-foreground'
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed text-[15px]">{msg.content}</p>
                </div>
              </div>
            ))}
            <div ref={endOfMessagesRef} />
          </div>
        </ScrollArea>
      )}

      <div className={`absolute left-0 right-0 px-4 transition-all duration-300 ${
        isChatEmpty 
          ? "top-1/2 -translate-y-1/2 mt-10" 
          : "bottom-0 bg-gradient-to-t from-[#212121] via-[#212121] to-transparent pb-4 pt-8"
      }`}>
        <div className="max-w-3xl mx-auto flex items-center gap-2 bg-[#2f2f2f] rounded-full p-2">
          <RightSidebar 
            activeChatId={activeChatId} 
            documents={documents} 
            onDocumentAdded={onDocumentAdded} 
            backendUrl={backendUrl}
            isOpen={isSidebarOpen}
            onOpenChange={setIsSidebarOpen}
            trigger={
              <div className="cursor-pointer p-2 rounded-full text-muted-foreground hover:text-foreground hover:bg-white/10 transition-colors">
                <Plus size={20} />
              </div>
            }
          />
          <Input 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && input.trim()) {
                onSendMessage(input.trim());
                setInput("");
              }
            }}
            placeholder="Ask anything..." 
            className="flex-1 bg-transparent border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-2 shadow-none"
          />
          {input.trim() ? (
            <Button 
              size="icon" 
              className="rounded-full h-8 w-8 bg-white text-black hover:bg-gray-200"
              onClick={() => {
                if (input.trim()) {
                  onSendMessage(input.trim());
                  setInput("");
                }
              }}
            >
              <ArrowUp size={18} />
            </Button>
          ) : (
            <Button variant="ghost" size="icon" className="rounded-full h-8 w-8 text-muted-foreground hover:text-foreground">
              <Mic size={20} />
            </Button>
          )}
        </div>
        {!isChatEmpty && (
          <p className="text-center text-xs text-muted-foreground mt-2">Not NotebookLM can make mistakes. Check important info.</p>
        )}
      </div>
    </div>
  );
}
