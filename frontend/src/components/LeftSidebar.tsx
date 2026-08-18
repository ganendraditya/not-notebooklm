import { PlusCircle, Search, Sidebar, MessageSquare, Image, Puzzle, Compass, Map } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatSession } from "@/app/ChatClient";

interface LeftSidebarProps {
  sessions: ChatSession[];
  activeChatId: string | null;
  onSelectChat: (id: string) => void;
  onCreateChat: (title: string) => void;
}

export default function LeftSidebar({ sessions, activeChatId, onSelectChat, onCreateChat }: LeftSidebarProps) {
  return (
    <div className="w-[260px] bg-[#171717] flex flex-col h-full text-sm">
      <div className="p-3 flex items-center justify-between">
        <Button variant="ghost" size="icon" className="h-10 w-10 text-muted-foreground hover:text-foreground">
          <Sidebar size={18} />
        </Button>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" className="h-10 w-10 text-muted-foreground hover:text-foreground">
            <Search size={18} />
          </Button>
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-10 w-10 text-muted-foreground hover:text-foreground"
            onClick={() => onCreateChat("New Chat")}
          >
            <PlusCircle size={18} />
          </Button>
        </div>
      </div>
      
      <div className="px-3 py-2 space-y-1">
        <Button variant="ghost" className="w-full justify-start text-muted-foreground hover:text-foreground">
          <Image className="mr-2" size={16} /> Images
        </Button>
        <Button variant="ghost" className="w-full justify-start text-muted-foreground hover:text-foreground">
          <Puzzle className="mr-2" size={16} /> Plugins
        </Button>
        <Button variant="ghost" className="w-full justify-start text-muted-foreground hover:text-foreground">
          <Compass className="mr-2" size={16} /> Deep research
        </Button>
        <Button variant="ghost" className="w-full justify-start text-muted-foreground hover:text-foreground">
          <Map className="mr-2" size={16} /> Maps
        </Button>
      </div>

      <div className="mt-4 px-4 text-xs font-semibold text-muted-foreground">Today</div>

      <ScrollArea className="flex-1 px-3 mt-2">
        <div className="space-y-1">
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => onSelectChat(session.id)}
              className={`w-full flex items-center text-left px-2 py-2 rounded-lg transition-colors truncate ${
                activeChatId === session.id 
                  ? "bg-[#2f2f2f] text-foreground" 
                  : "text-muted-foreground hover:bg-[#2f2f2f] hover:text-foreground"
              }`}
            >
              <MessageSquare size={16} className="mr-2 flex-shrink-0" />
              <span className="truncate">{session.title}</span>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
