"use client";

import { useState } from "react";
import { HardDrive, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import type { AdminConfig, TestResult } from "@/types/admin";

interface StorageTabProps {
  config: AdminConfig["storage"];
  backendUrl: string;
  onSaved: () => void;
}

export default function StorageTab({ config, backendUrl, onSaved }: StorageTabProps) {
  const [storageType, setStorageType] = useState<"local" | "s3">(config.storage_type || "local");
  const [endpoint, setEndpoint] = useState(config.s3_endpoint || "");
  const [bucket, setBucket] = useState(config.s3_bucket || "not-notebooklm");
  const [region, setRegion] = useState(config.s3_region || "auto");
  const [accessKey, setAccessKey] = useState("");
  const [secretKey, setSecretKey] = useState("");

  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const handleTestS3 = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${backendUrl}/admin/test/storage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          s3_endpoint: endpoint,
          s3_access_key: accessKey.trim() || undefined,
          s3_secret_key: secretKey.trim() || undefined,
          s3_bucket: bucket,
          s3_region: region,
        }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e) {
      setTestResult({
        success: false,
        message: e instanceof Error ? e.message : "Failed to execute S3 test",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMessage(null);
    try {
      const res = await fetch(`${backendUrl}/admin/config/storage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          storage_type: storageType,
          s3_endpoint: endpoint,
          s3_bucket: bucket,
          s3_region: region,
          s3_access_key: accessKey.trim() || undefined,
          s3_secret_key: secretKey.trim() || undefined,
        }),
      });
      if (!res.ok) throw new Error("Failed to update storage configuration");
      setStatusMessage({ text: "Storage backend settings successfully updated." });
      setAccessKey("");
      setSecretKey("");
      onSaved();
    } catch (e) {
      setStatusMessage({
        text: e instanceof Error ? e.message : "Error saving storage configuration",
        error: true,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="border-b border-app-border pb-4">
        <h2 className="text-base font-semibold text-app-text flex items-center gap-2">
          <HardDrive size={18} className="text-blue-500" />
          Object Storage & Buckets
        </h2>
        <p className="text-xs text-app-text-muted mt-1">
          Store academic PDFs and research assets on local disk or sync to an S3-compatible bucket (Cloudflare R2, MinIO, AWS S3).
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-5">
        <div className="space-y-2">
          <label className="text-xs font-medium text-app-text">Storage Architecture</label>
          <div className="grid grid-cols-2 gap-3 max-w-md">
            <button
              type="button"
              onClick={() => setStorageType("local")}
              className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                storageType === "local"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">Local Filesystem</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">Zero cloud setup, stores in backend/upload</div>
            </button>

            <button
              type="button"
              onClick={() => setStorageType("s3")}
              className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                storageType === "s3"
                  ? "border-blue-500 bg-blue-500/10 text-app-text"
                  : "border-app-border bg-app-input-surface text-app-text-muted hover:text-app-text"
              }`}
            >
              <div className="text-xs font-semibold">S3 Object Storage</div>
              <div className="text-[11px] text-app-text-dim mt-0.5">Cloudflare R2, MinIO, or AWS S3</div>
            </button>
          </div>
        </div>

        {storageType === "s3" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-xs font-medium text-app-text">S3 Endpoint URL</label>
              <input
                type="text"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="https://<account_id>.r2.cloudflarestorage.com or http://localhost:9000"
                required={storageType === "s3"}
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-app-text">Bucket Name</label>
              <input
                type="text"
                value={bucket}
                onChange={(e) => setBucket(e.target.value)}
                placeholder="not-notebooklm"
                required={storageType === "s3"}
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-app-text">Region</label>
              <input
                type="text"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                placeholder="auto or us-east-1"
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="text-xs font-medium text-app-text">S3 Access Key ID</label>
                {config.s3_access_key_masked && (
                  <span className="text-[11px] font-mono text-app-text-dim">
                    {config.s3_access_key_masked}
                  </span>
                )}
              </div>
              <input
                type="password"
                value={accessKey}
                onChange={(e) => setAccessKey(e.target.value)}
                placeholder={config.s3_access_key_masked ? "Leave blank to keep existing" : "Access Key ID"}
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="text-xs font-medium text-app-text">S3 Secret Access Key</label>
                {config.has_s3_secret && (
                  <span className="text-[11px] font-mono text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded">
                    Configured
                  </span>
                )}
              </div>
              <input
                type="password"
                value={secretKey}
                onChange={(e) => setSecretKey(e.target.value)}
                placeholder={config.has_s3_secret ? "Leave blank to keep existing" : "Secret Access Key"}
                className="w-full px-3 py-2 text-xs rounded-lg bg-app-input-surface border border-app-border text-app-text focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>
        )}

        {testResult && (
          <div
            className={`p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
              testResult.success
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                : "bg-rose-500/10 border-rose-500/20 text-rose-400"
            }`}
          >
            {testResult.success ? (
              <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
            ) : (
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium">{testResult.message}</p>
            </div>
          </div>
        )}

        {statusMessage && (
          <div
            className={`p-3 rounded-lg border text-xs flex items-center gap-2 ${
              statusMessage.error
                ? "bg-rose-500/10 border-rose-500/20 text-rose-400"
                : "bg-blue-500/10 border-blue-500/20 text-blue-400"
            }`}
          >
            {statusMessage.error ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
            <span>{statusMessage.text}</span>
          </div>
        )}

        <div className="flex items-center justify-between pt-4 border-t border-app-border">
          {storageType === "s3" ? (
            <button
              type="button"
              onClick={handleTestS3}
              disabled={isTesting || !endpoint}
              className="px-3 py-2 text-xs font-medium rounded-lg border border-app-border hover:bg-app-item-hover text-app-text transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw size={13} className={isTesting ? "animate-spin" : ""} />
              {isTesting ? "Testing Bucket..." : "Test Bucket Access"}
            </button>
          ) : (
            <div />
          )}

          <button
            type="submit"
            disabled={isSaving}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? "Saving..." : "Save Storage Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
