import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AdminPage from "@/app/admin/page";
import LLMTab from "@/app/admin/components/LLMTab";
import type { AdminPersistence } from "@/types/admin";

const mockConfig = {
  llm: {
    base_url: "http://localhost:20128/v1",
    api_key_masked: "sk-...1234",
    has_api_key: true,
    model: "gpt-4o",
    fast_model: "gpt-4o-mini",
    fallback_model: null,
    temperature: 0.1,
    profiles: [
      {
        id: "default",
        name: "Default Gateway",
        base_url: "http://localhost:20128/v1",
        api_key_masked: "sk-...1234",
        has_api_key: true,
      }
    ],
    primary_profile_id: "default",
    fast_profile_id: "default",
    fallback_profile_id: "default",
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

function servePersistence(persistence?: AdminPersistence, failReranker = false) {
  global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => Promise.resolve({
    ok: !(failReranker && init?.method === "POST" && url.endsWith("/config/reranker")),
    json: async () => init?.method === "POST"
      ? { status: "success", persistence }
      : url.includes("/admin/config") ? { ...mockConfig, persistence } : mockHealth,
  }));
}

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
      expect(screen.getByText("Universal OpenAI-Compatible Gateway Vault")).toBeInTheDocument();
    });

    // Click Storage tab
    fireEvent.click(screen.getByRole("button", { name: /Storage & S3/i }));
    expect(screen.getByText("Object Storage & Buckets")).toBeInTheDocument();

    // Click Secrets tab
    fireEvent.click(screen.getByRole("button", { name: /Secret Vaults/i }));
    expect(screen.getByText("Secret Providers & Vaults")).toBeInTheDocument();

    // Click Embedding Engine tab
    fireEvent.click(screen.getByRole("button", { name: /Embedding Engine/i }));
    expect(screen.getByText("Universal Embedding Vault & Reranker Manager")).toBeInTheDocument();
    expect(screen.getByText("Cross-Encoder Reranker Manager")).toBeInTheDocument();

    // Click System Health tab
    fireEvent.click(screen.getByRole("button", { name: /System Health/i }));
    expect(screen.getByText("System Diagnostics & Resource Health")).toBeInTheDocument();
    expect(screen.getByText("SQLite WAL")).toBeInTheDocument();
    expect(screen.getByText("not_notebooklm_fastembed")).toBeInTheDocument();
  });

  it("opens and handles Add Gateway modal dialogs and secret visibility toggles", async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText("Universal OpenAI-Compatible Gateway Vault")).toBeInTheDocument();
    });

    // 1. Open Add OpenAI Compatible Modal
    const addOpenAiBtn = screen.getByRole("button", { name: /Add OpenAI Compatible/i });
    fireEvent.click(addOpenAiBtn);

    expect(screen.getByText("Add OpenAI Compatible Gateway")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e\.g\. DeepSeek Official/i)).toBeInTheDocument();

    // Close modal via Cancel button
    const cancelBtn = screen.getByRole("button", { name: /Cancel/i });
    fireEvent.click(cancelBtn);
    expect(screen.queryByText("Add OpenAI Compatible Gateway")).not.toBeInTheDocument();

    // 2. Open Add Anthropic Claude Modal
    const addAnthropicBtn = screen.getByRole("button", { name: /Add Anthropic Claude/i });
    fireEvent.click(addAnthropicBtn);

    expect(screen.getByText("Add Anthropic Claude Gateway")).toBeInTheDocument();

    // Press Escape to close modal
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByText("Add Anthropic Claude Gateway")).not.toBeInTheDocument();

    // 3. Open Edit Modal on default card
    const editBtn = screen.getByTitle("Edit Provider Settings");
    fireEvent.click(editBtn);

    expect(screen.getByText(/Edit Gateway:/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Cancel/i }));
  });

  it("renders models under gateway profile and allows toggling workspace visibility", async () => {
    render(<AdminPage />);
    await waitFor(() => {
      expect(screen.getByText("Models & Workspace Visibility")).toBeInTheDocument();
    });

    // Check that Add Model button is present
    const addModelBtn = screen.getByRole("button", { name: /Add Model/i });
    expect(addModelBtn).toBeInTheDocument();

    // Click Add Model to open inline form
    fireEvent.click(addModelBtn);
    expect(screen.getByPlaceholderText(/e\.g\. deepseek-reasoner/i)).toBeInTheDocument();
  });

  it.each(["doppler", "infisical"] as const)("shows a read-only %s session and a local-file notice across tabs", async (provider) => {
    servePersistence({ mode: "runtime", active_provider: provider, has_local_env: true });
    render(<AdminPage />);
    await screen.findByRole("region", { name: "Configuration persistence" });
    expect(screen.getByRole("note", { name: "Local credentials notice" })).toHaveTextContent("missing values may still load from this file");
    fireEvent.click(screen.getByRole("button", { name: /Secret Vaults/i }));
    expect(screen.getByText("Active provider").nextElementSibling).toHaveTextContent(provider === "doppler" ? "Doppler" : "Infisical");
    expect(screen.getByText("This process only")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Save Secret|Purge|Local .env|Infisical CLI|Doppler CLI/i })).not.toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /Storage & S3/i }));
    expect(screen.getByRole("note", { name: "Local credentials notice" })).toBeInTheDocument();
  });

  it("does not claim zero-disk privacy when no .env is found", async () => {
    servePersistence({ mode: "runtime", active_provider: "doppler", has_local_env: false });
    render(<AdminPage />);
    await screen.findByRole("region", { name: "Configuration persistence" });
    fireEvent.click(screen.getByRole("button", { name: /Secret Vaults/i }));
    expect(screen.getByText("Not found")).toBeInTheDocument();
    expect(screen.queryByRole("note", { name: "Local credentials notice" })).not.toBeInTheDocument();
    expect(screen.queryByText(/zero.disk/i)).not.toBeInTheDocument();
  });

  it("keeps missing persistence metadata unknown", async () => {
    render(<AdminPage />);
    await screen.findByText("Persistence status unavailable");
    fireEvent.click(screen.getByRole("button", { name: /Secret Vaults/i }));
    expect(screen.getAllByText("Not reported")).toHaveLength(3);
    expect(screen.queryByText("Local configuration")).not.toBeInTheDocument();
  });

  it.each(["doppler", "infisical"] as const)("shows runtime-only storage save feedback for %s", async (provider) => {
    servePersistence({ mode: "runtime", active_provider: provider, has_local_env: true });
    render(<AdminPage />);
    await screen.findByRole("region", { name: "Configuration persistence" });
    fireEvent.click(screen.getByRole("button", { name: /Storage & S3/i }));
    fireEvent.click(screen.getByRole("button", { name: "Save Storage Settings" }));
    expect(await screen.findByRole("status")).toHaveTextContent("this process only");
    expect(screen.getByRole("status")).toHaveTextContent("after restart");
    const save = vi.mocked(fetch).mock.calls.find(([url, init]) => String(url).endsWith("/config/storage") && init?.method === "POST");
    expect(JSON.parse(String(save?.[1]?.body)).storage_type).toBe("local");
  });

  it("shows local-file storage persistence only when reported", async () => {
    servePersistence({ mode: "local_env", active_provider: "local", has_local_env: true });
    render(<AdminPage />);
    await screen.findByText("Local configuration");
    fireEvent.click(screen.getByRole("button", { name: /Storage & S3/i }));
    fireEvent.click(screen.getByRole("button", { name: "Save Storage Settings" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Configuration saved to local .env.");
  });

  it("shows process-only routing feedback", async () => {
    servePersistence({ mode: "runtime", active_provider: "doppler", has_local_env: false });
    render(<AdminPage />);
    await screen.findByRole("region", { name: "Configuration persistence" });
    fireEvent.click(screen.getByRole("button", { name: "Save Tier Routing" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Local .env was not changed");
  });

  it("reports process-only provider creation and deletion", async () => {
    servePersistence({ mode: "runtime", active_provider: "doppler", has_local_env: false });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<LLMTab config={mockConfig.llm} backendUrl="http://localhost:8000" onSaved={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Add OpenAI Compatible/i }));
    fireEvent.click(screen.getByRole("button", { name: "Save Provider" }));
    expect(await screen.findByRole("status")).toHaveTextContent("this process only");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByTitle("Delete Profile")[1]);
    await waitFor(() => expect(vi.mocked(fetch).mock.calls).toHaveLength(2));
    expect(await screen.findByRole("status")).toHaveTextContent("Local .env was not changed");
    expect(screen.queryByTitle("Delete Profile")).not.toBeInTheDocument();
  });

  it("reports process-only model creation, visibility, and removal", async () => {
    servePersistence({ mode: "runtime", active_provider: "infisical", has_local_env: false });
    render(<LLMTab config={mockConfig.llm} backendUrl="http://localhost:8000" onSaved={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Add Model" }));
    fireEvent.change(screen.getByPlaceholderText("e.g. deepseek-reasoner"), { target: { value: "fixture-model" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Model" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Update your Infisical project");
    const visibility = await screen.findByRole("checkbox", { name: "fixture-model" });
    fireEvent.click(visibility);
    await waitFor(() => expect(visibility).not.toBeChecked());
    fireEvent.click(screen.getByTitle("Delete model from profile"));
    await waitFor(() => expect(screen.queryByRole("checkbox", { name: "fixture-model" })).not.toBeInTheDocument());
    expect(vi.mocked(fetch).mock.calls).toHaveLength(3);
    expect(screen.getByRole("status")).toHaveTextContent("this process only");
  });

  it("reports both retrieval settings as process-only", async () => {
    servePersistence({ mode: "runtime", active_provider: "infisical", has_local_env: false });
    render(<AdminPage />);
    await screen.findByRole("region", { name: "Configuration persistence" });
    fireEvent.click(screen.getByRole("button", { name: /Embedding Engine/i }));
    fireEvent.click(screen.getByRole("button", { name: "Save Retrieval & Reranker Settings" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Update your Infisical project");
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2);
  });

  it.each(["http", "network"])("distinguishes a partial retrieval save from a full success after a %s failure", async (failure) => {
    servePersistence({ mode: "runtime", active_provider: "doppler", has_local_env: false }, failure === "http");
    if (failure === "network") {
      const fetchWithMetadata = global.fetch;
      global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) =>
        init?.method === "POST" && url.endsWith("/config/reranker")
          ? Promise.reject(new TypeError("Network unavailable"))
          : fetchWithMetadata(url, init),
      );
    }
    render(<AdminPage />);
    await screen.findByRole("region", { name: "Configuration persistence" });
    fireEvent.click(screen.getByRole("button", { name: /Embedding Engine/i }));
    fireEvent.click(screen.getByRole("button", { name: "Save Retrieval & Reranker Settings" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Embedding: Applied to this process only");
    expect(screen.getByRole("alert")).toHaveTextContent("Reranker update could not be confirmed");
  });
});
