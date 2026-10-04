"use client";

import { Activity, RefreshCw, Database, Layers, Disc } from "lucide-react";
import type { AdminSystemHealth } from "@/types/admin";

interface SystemHealthTabProps {
  health: AdminSystemHealth | null;
  backendUrl: string;
  onRefresh: () => void;
  isLoading: boolean;
}

export default function SystemHealthTab({ health, onRefresh, isLoading }: SystemHealthTabProps) {
  if (!health) {
    return (
      <div className="py-12 flex flex-col items-center justify-center text-app-text-dim">
        <RefreshCw size={24} className="animate-spin mb-3 text-blue-500" />
        <span className="text-xs">Gathering system diagnostics...</span>
      </div>
    );
  }

  const { database, vector_store, disk } = health;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-app-border pb-4">
        <div>
          <h2 className="text-base font-semibold text-app-text flex items-center gap-2">
            <Activity size={18} className="text-blue-500" />
            System Diagnostics & Resource Health
          </h2>
          <p className="text-xs text-app-text-muted mt-1">
            Authoritative metrics for SQLite metadata store, Qdrant vectors, and local filesystem capacity.
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-app-border hover:bg-app-item-hover text-app-text flex items-center gap-2 cursor-pointer transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          Refresh Stats
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* SQLite Database Stats */}
        <div className="p-4 rounded-xl border border-app-border bg-app-card space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold text-app-text">
            <span className="flex items-center gap-2">
              <Database size={15} className="text-blue-500" />
              {database.engine}
            </span>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400">
              Online
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-app-text-dim">Chat Sessions:</span>
              <span className="font-mono font-medium text-app-text">{database.chat_sessions}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-app-text-dim">Indexed Documents:</span>
              <span className="font-mono font-medium text-app-text">{database.documents}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-app-text-dim">Total Messages:</span>
              <span className="font-mono font-medium text-app-text">{database.messages}</span>
            </div>
          </div>
        </div>

        {/* Qdrant Vector Store Stats */}
        <div className="p-4 rounded-xl border border-app-border bg-app-card space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold text-app-text">
            <span className="flex items-center gap-2">
              <Layers size={15} className="text-purple-500" />
              Qdrant Engine (Rust)
            </span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                vector_store.status === "healthy"
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "bg-rose-500/10 text-rose-400"
              }`}
            >
              {vector_store.status}
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-app-text-dim">Collections Count:</span>
              <span className="font-mono font-medium text-app-text">
                {vector_store.collections.length}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-app-text-dim">Total Indexed Points:</span>
              <span className="font-mono font-medium text-app-text">
                {vector_store.collections.reduce((acc, c) => acc + (c.points_count || 0), 0)}
              </span>
            </div>
          </div>
        </div>

        {/* Disk Space Diagnostics */}
        <div className="p-4 rounded-xl border border-app-border bg-app-card space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold text-app-text">
            <span className="flex items-center gap-2">
              <Disc size={15} className="text-amber-500" />
              Disk Capacity
            </span>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-400">
              {disk.free_gb} GB Free
            </span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-app-text-dim">Used Volume:</span>
              <span className="font-mono font-medium text-app-text">{disk.used_gb} GB</span>
            </div>
            <div className="flex justify-between">
              <span className="text-app-text-dim">Total Volume:</span>
              <span className="font-mono font-medium text-app-text">{disk.total_gb} GB</span>
            </div>
          </div>
        </div>
      </div>

      {/* Qdrant Collections Detail Table */}
      <div className="border border-app-border rounded-xl overflow-hidden bg-app-card">
        <div className="px-4 py-3 border-b border-app-border bg-app-surface text-xs font-semibold text-app-text">
          Active Qdrant Collections
        </div>
        <div className="divide-y divide-app-divider">
          {vector_store.collections.length === 0 ? (
            <div className="p-4 text-xs text-app-text-dim text-center">
              No active collections in Qdrant store yet. Upload a document to initialize.
            </div>
          ) : (
            vector_store.collections.map((col) => (
              <div key={col.name} className="px-4 py-2.5 flex items-center justify-between text-xs">
                <div className="font-mono font-medium text-app-text">{col.name}</div>
                <div className="flex items-center gap-4 text-app-text-muted">
                  <span>
                    Points: <strong className="text-app-text">{col.points_count}</strong>
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 font-mono">
                    {col.status}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
