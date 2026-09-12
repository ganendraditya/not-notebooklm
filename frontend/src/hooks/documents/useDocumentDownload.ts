import { useState } from "react";
import { Document } from "@/stores/documentStore";
import { consumeSSEStream } from "@/lib/sse";
import { DownloadTask } from "@/components/DownloadManager";
import { sendSystemNotification } from "@/lib/notifications";
import { getSystemTranslation } from "@/lib/i18n";

export function useDocumentDownload({
  activeChatId,
  backendUrl,
  t,
}: {
  activeChatId: string | null;
  backendUrl: string;
  t?: (key: string, variables?: Record<string, string>) => string;
}) {
  const [isBulkDownloading, setIsBulkDownloading] = useState(false);
  const [downloadTask, setDownloadTask] = useState<DownloadTask | null>(null);

  const tr = (key: string, vars?: Record<string, string>, fallback?: string) => {
    return t ? t(key, vars) : getSystemTranslation(key, vars, fallback);
  };

  const downloadFileText = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleBulkDownload = async (docsToDownload: Document[]) => {
    if (!activeChatId || docsToDownload.length === 0 || isBulkDownloading) return;
    setIsBulkDownloading(true);
    const docIds = docsToDownload.map(d => d.id);

    if (docIds.length === 1) {
      try {
        const doc = docsToDownload[0];
        const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/${doc.id}/download`);
        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          setDownloadTask({
            status: "error",
            total: 1,
            current: 0,
            percent: 0,
            currentFile: doc.filename,
            errorMsg: errJson.detail || tr("notify.downloadUnavailable", undefined, "Full manuscript PDF is not available for download.")
          });
          return;
        }
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = doc.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        console.error("Single download error:", err);
      } finally {
        setIsBulkDownloading(false);
      }
      return;
    }

    setDownloadTask({
      status: "preparing",
      total: docIds.length,
      current: 0,
      percent: 0,
      currentFile: "Menyiapkan kompresi..."
    });

    try {
      const res = await fetch(`${backendUrl}/chats/${activeChatId}/documents/bulk_download_stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_ids: docIds })
      });

      if (!res.ok) {
        throw new Error("Failed to start zip stream");
      }

      await consumeSSEStream(res, (data: any) => {
        if (!data) return;
        if (data.type === "progress") {
          setDownloadTask(prev => ({
            ...prev!,
            status: "zipping",
            current: data.current,
            total: data.total,
            percent: data.percent ?? Math.round((data.current / data.total) * 100),
            currentFile: data.filename || tr("notify.downloadProcessing", undefined, "Processing file..."),
            downloadedCount: data.downloaded_count,
            skippedCount: data.skipped_count,
            totalSizeMb: data.total_size_mb
          }));
        } else if (data.type === "complete") {
          const zipUrl = `${backendUrl}${data.download_url}`;
          setDownloadTask({
            status: "complete",
            total: data.total,
            current: data.total,
            percent: 100,
            currentFile: data.filename || "Download.zip",
            downloadedCount: data.downloaded_count,
            skippedCount: data.skipped_count,
            totalSizeMb: data.total_size_mb
          });

          const docCount = String(data.downloaded_count ?? data.total);
          sendSystemNotification({
            category: "downloads",
            titleKey: "notify.downloadCompleteTitle",
            title: "NotbookLM: Download Complete",
            bodyKey: "notify.downloadCompleteBody",
            variables: { count: docCount },
            body: `ZIP archive ready for download (${docCount} documents).`
          });
          
          const link = document.createElement("a");
          link.href = zipUrl;
          link.setAttribute("download", "");
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } else if (data.type === "error") {
          const errorMsg = data.message || data.detail || tr("notify.downloadFailedBody", undefined, "Failed to compress documents.");
          setDownloadTask({
            status: "error",
            total: docIds.length,
            current: 0,
            percent: 0,
            currentFile: "",
            errorMsg: errorMsg
          });
          sendSystemNotification({
            category: "downloads",
            titleKey: "notify.downloadFailedTitle",
            title: "NotbookLM: Download Failed",
            body: errorMsg,
            bodyKey: "notify.downloadFailedBody"
          });
        }
      });
    } catch (err: any) {
      console.error("Bulk download SSE error:", err);
      setDownloadTask({
        status: "error",
        total: docIds.length,
        current: 0,
        percent: 0,
        currentFile: "",
        errorMsg: err.message || tr("notify.downloadInterrupted", undefined, "Connection interrupted while downloading.")
      });
    } finally {
      setIsBulkDownloading(false);
    }
  };

  return {
    isBulkDownloading,
    setIsBulkDownloading,
    downloadTask, setDownloadTask,
    downloadFileText,
    handleBulkDownload
  };
}