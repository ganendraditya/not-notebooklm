import { useState } from "react";
import { UploadCloud, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Document } from "@/app/ChatClient";
import { Sheet, SheetContent, SheetTrigger, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";

interface RightSidebarProps {
  activeChatId: string | null;
  documents: Document[];
  onDocumentAdded: (doc: Document) => void;
  backendUrl: string;
  trigger: React.ReactNode;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function RightSidebar({ 
  activeChatId, 
  documents, 
  onDocumentAdded, 
  backendUrl,
  trigger,
  isOpen,
  onOpenChange
}: RightSidebarProps) {
  const [isUploading, setIsUploading] = useState(false);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0] || !activeChatId) return;
    
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", e.target.files[0]);

    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/upload`, {
        method: "POST",
        body: formData,
      });
      const newDoc = await res.json();
      onDocumentAdded(newDoc);
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  return (
    <Sheet open={isOpen} onOpenChange={onOpenChange}>
      <SheetTrigger>
        {trigger}
      </SheetTrigger>
      <SheetContent className="w-[300px] sm:w-[400px] bg-[#171717] border-l-[#333333]">
        <SheetHeader>
          <SheetTitle className="text-foreground">Sources</SheetTitle>
          <SheetDescription>Upload documents for the AI to analyze.</SheetDescription>
        </SheetHeader>
        
        <div className="mt-6 flex flex-col h-[calc(100vh-120px)]">
          {!activeChatId ? (
            <div className="text-center text-muted-foreground mt-10">
              <p>Create a chat session first to upload documents.</p>
            </div>
          ) : (
            <>
              <div className="border-2 border-dashed border-[#333333] rounded-lg p-6 flex flex-col items-center justify-center text-center">
                <UploadCloud size={32} className="text-muted-foreground mb-4" />
                <p className="text-sm text-foreground mb-2">Upload a PDF document</p>
                <input
                  type="file"
                  id="file-upload"
                  className="hidden"
                  accept=".pdf"
                  onChange={handleFileUpload}
                  disabled={isUploading}
                />
                <label htmlFor="file-upload">
                  <Button variant="outline" className="cursor-pointer border-[#333333] hover:bg-[#2f2f2f]" asChild disabled={isUploading}>
                    <span>{isUploading ? "Uploading..." : "Select File"}</span>
                  </Button>
                </label>
              </div>

              <div className="mt-8 flex-1">
                <h3 className="font-semibold text-sm mb-4 text-muted-foreground uppercase">Uploaded Documents</h3>
                <ScrollArea className="h-full">
                  <div className="space-y-2 pb-10">
                    {documents.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center mt-4">No documents uploaded yet.</p>
                    ) : (
                      documents.map((doc, idx) => (
                        <div key={idx} className="flex items-center p-3 rounded-lg bg-[#2f2f2f] text-sm text-foreground">
                          <FileText size={16} className="mr-3 flex-shrink-0 text-blue-400" />
                          <span className="truncate">{doc.filename}</span>
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
