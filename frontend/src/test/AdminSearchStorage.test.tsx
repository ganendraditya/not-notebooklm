import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import EmbeddingTab from "@/app/admin/components/EmbeddingTab";
import StorageTab from "@/app/admin/components/StorageTab";
import { I18nProvider } from "@/lib/i18n";
import { adminConfig, jsonResponse, serveAdmin } from "./admin-fixtures";

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());
const renderSearch = () => render(<I18nProvider><EmbeddingTab config={adminConfig.embedding} rerankerConfig={adminConfig.reranker} backendUrl="http://localhost:8000" onSaved={vi.fn()} /></I18nProvider>);
const renderStorage = () => render(<I18nProvider><StorageTab config={adminConfig.storage} backendUrl="http://localhost:8000" onSaved={vi.fn()} /></I18nProvider>);

describe("Independent search save boundaries", () => {
  it("names independent save forms and discloses testing without making requests", () => {
    const { fetcher } = serveAdmin(); renderSearch();
    expect(screen.getByRole("form", { name: "Document embeddings" })).toContainElement(screen.getByRole("button", { name: "Save embeddings" }));
    expect(screen.getByRole("form", { name: "Passage reranking" })).toContainElement(screen.getByRole("button", { name: "Save reranker" }));
    const disclosure = screen.getByText("Test reranker (optional)").closest("details");
    expect(disclosure).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Test reranker (optional)"));
    expect(disclosure).toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Test reranker" })).toBeEnabled();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("preserves unknown model IDs and never tests/downloads on mount or selection", () => {
    const { fetcher } = serveAdmin(); renderSearch();
    expect(screen.getByLabelText("Embedding model")).toHaveValue("configured-unknown-model");
    expect(screen.getByLabelText("Reranker model")).toHaveValue("configured-reranker");
    fireEvent.change(screen.getByLabelText("Embedding provider"), { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("Reranker model"), { target: { value: "ms-marco-TinyBERT-L-2-v2" } });
    expect(fetcher).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Save embeddings" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Save reranker" })).toBeEnabled();
  });

  it.each(["http", "network"])("keeps an embedding success visible after a separate reranker %s failure", async (failure) => {
    const config = structuredClone(adminConfig); config.persistence = { mode: "runtime", active_provider: "infisical", has_local_env: false };
    const { fetcher } = serveAdmin(config); renderSearch();
    fireEvent.change(screen.getByLabelText("Embedding model"), { target: { value: "intfloat/multilingual-e5-large" } });
    fireEvent.change(screen.getByLabelText("Passages sent as context"), { target: { value: "15" } });
    fireEvent.click(screen.getByRole("button", { name: "Save embeddings" }));
    await screen.findByText(/Document embeddings: Applied to this process only/);
    expect(fetcher.mock.calls).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Save reranker" })).toBeEnabled();
    if (failure === "http") fetcher.mockResolvedValueOnce(jsonResponse({}, 500));
    else fetcher.mockRejectedValueOnce(new TypeError("Offline"));
    fireEvent.click(screen.getByRole("button", { name: "Save reranker" }));
    await screen.findByText(/Passage reranking: The save could not be confirmed/);
    expect(screen.getByRole("status")).toHaveTextContent("Update your Infisical project");
    expect(screen.getByLabelText("Passages sent as context")).toHaveValue(15);
    expect(screen.getByRole("button", { name: "Save embeddings" })).toBeDisabled();
    expect(fetcher.mock.calls.map(([url]) => String(url).split("/").at(-1))).toEqual(["embeddings", "reranker"]);
  });

  it("requires explicit embedding credentials for a changed endpoint and keeps blank credentials omitted", async () => {
    const { fetcher } = serveAdmin(); renderSearch();
    fireEvent.change(screen.getByLabelText("Embedding provider"), { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "https://changed.invalid/v1" } });
    fireEvent.click(screen.getByText("Test endpoint & dimensions (optional)"));
    expect(screen.getByRole("button", { name: "Test endpoint & dimensions" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "fixture-key" } });
    fireEvent.click(screen.getByRole("button", { name: "Test endpoint & dimensions" }));
    await screen.findByText("The test request succeeded.");
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "" } });
    expect(screen.queryByText("The test request succeeded.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save embeddings" }));
    await screen.findByText(/Document embeddings: Configuration saved/);
    const body = JSON.parse(String(fetcher.mock.calls[1][1]?.body));
    expect(body).not.toHaveProperty("custom_key");
    expect(body).not.toHaveProperty("gemini_key");
  });
});

describe("File storage drafts", () => {
  it("preserves blank credentials on save and only tests explicitly", async () => {
    const { fetcher } = serveAdmin(); renderStorage();
    expect(screen.getByLabelText("Access key ID")).toHaveValue("");
    expect(screen.getByLabelText("Secret access key")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Bucket name"), { target: { value: "changed-bucket" } });
    fireEvent.click(screen.getByText("Test bucket access (optional)"));
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Test bucket access" }));
    await screen.findByText("The test request succeeded.");
    fireEvent.change(screen.getByLabelText("Region"), { target: { value: "region-fixture" } });
    expect(screen.queryByText("The test request succeeded.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save file storage" }));
    await screen.findByText("Configuration saved to local .env.");
    const body = JSON.parse(String(fetcher.mock.calls[1][1]?.body));
    expect(body).not.toHaveProperty("s3_access_key"); expect(body).not.toHaveProperty("s3_secret_key");
    expect(body).toMatchObject({ s3_bucket: "changed-bucket", s3_region: "region-fixture" });
  });

  it("retains failed drafts until an uncertain write is reconciled", async () => {
    const { fetcher } = serveAdmin(); renderStorage();
    fireEvent.change(screen.getByLabelText("Bucket name"), { target: { value: "draft-bucket" } });
    fetcher.mockRejectedValueOnce(new TypeError("Offline"));
    fireEvent.click(screen.getByRole("button", { name: "Save file storage" }));
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Bucket name")).toHaveValue("draft-bucket");
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save file storage" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Reload saved values" }));
    await screen.findByText(/Saved values reloaded/);
    expect(screen.getByLabelText("Bucket name")).toHaveValue("fixture");
    expect(screen.getByRole("button", { name: "Save file storage" })).toBeDisabled();
  });
});
