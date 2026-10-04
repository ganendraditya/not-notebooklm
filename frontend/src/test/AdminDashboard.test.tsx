import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AdminPage from "@/app/admin/page";

const mockConfig = {
  llm: {
    base_url: "http://localhost:20128/v1",
    api_key_masked: "sk-...1234",
    has_api_key: true,
    model: "gpt-4o",
    fast_model: "gpt-4o-mini",
    fallback_model: null,
    temperature: 0.1,
  },
  storage: {
    storage_type: "local",
    s3_endpoint: "",
    s3_bucket: "not-notebooklm",
    s3_region: "auto",
    s3_access_key_masked: "",
    has_s3_secret: false,
    is_configured: false,
  },
  secrets: {
    active_provider: "local",
    infisical_project_id: "",
    infisical_env: "dev",
    doppler_project: "",
    doppler_config: "dev",
  },
  embedding: {
    provider: "local",
    gemini_model: "models/gemini-embedding-001",
    gemini_key_masked: "",
    has_gemini_key: false,
    local_model: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    local_dimensions: 384,
    hybrid_bm25_enabled: true,
  },
};

const mockHealth = {
  status: "ok",
  database: {
    engine: "SQLite WAL",
    chat_sessions: 4,
    documents: 12,
    messages: 38,
  },
  vector_store: {
    status: "healthy",
    collections: [
      { name: "not_notebooklm_fastembed", points_count: 140, status: "ready" },
    ],
  },
  disk: {
    total_gb: 500.0,
    free_gb: 120.0,
    used_gb: 380.0,
  },
};

describe("AdminPage Control Dashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/admin/config")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockConfig),
        });
      }
      if (url.includes("/admin/system/health")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHealth),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: "success" }),
      });
    });
  });

  it("renders Control Dashboard header with port indicator", async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText("NotbookLM Control Dashboard")).toBeInTheDocument();
      expect(screen.getByText("Port 2027")).toBeInTheDocument();
    });
  });

  it("switches across tabs cleanly without errors", async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText("Model Gateways & BYOK")).toBeInTheDocument();
    });

    // Click Storage tab
    fireEvent.click(screen.getByRole("button", { name: /Storage & S3/i }));
    expect(screen.getByText("Object Storage & Buckets")).toBeInTheDocument();

    // Click Secrets tab
    fireEvent.click(screen.getByRole("button", { name: /Secret Vaults/i }));
    expect(screen.getByText("Secret Providers & Vaults")).toBeInTheDocument();

    // Click Embedding Engine tab
    fireEvent.click(screen.getByRole("button", { name: /Embedding Engine/i }));
    expect(screen.getByText("Embedding Engine & Vector Dimensions")).toBeInTheDocument();

    // Click System Health tab
    fireEvent.click(screen.getByRole("button", { name: /System Health/i }));
    expect(screen.getByText("System Diagnostics & Resource Health")).toBeInTheDocument();
    expect(screen.getByText("SQLite WAL")).toBeInTheDocument();
    expect(screen.getByText("not_notebooklm_fastembed")).toBeInTheDocument();
  });
});
