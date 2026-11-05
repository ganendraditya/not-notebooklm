import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "System configuration - NotbookLM",
  description: "Configure model connections, file storage, and document search. Inspect configuration sources and system status.",
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-app-bg text-app-text antialiased selection:bg-blue-600 selection:text-white">
      {children}
    </div>
  );
}
