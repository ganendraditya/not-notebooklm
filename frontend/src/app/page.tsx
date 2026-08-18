"use client";

import dynamic from "next/dynamic";

const ChatClient = dynamic(() => import("./ChatClient"), { 
  ssr: false,
  loading: () => (
    <div className="flex h-screen w-screen items-center justify-center bg-[#131314] text-white">
      <div className="flex flex-col items-center gap-3">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        <span className="text-xs text-gray-400 font-medium">Memuat NotbookLM...</span>
      </div>
    </div>
  )
});

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between" suppressHydrationWarning>
      <ChatClient />
    </main>
  );
}
