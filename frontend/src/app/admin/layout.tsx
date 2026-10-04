import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Control Dashboard - Not-NotebookLM",
  description: "Dedicated Management Plane for LLM Gateways, S3 Storage, Secret Providers, and System Diagnostics",
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
