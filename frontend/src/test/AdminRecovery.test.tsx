import React from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import AdminPage from "@/app/admin/page";
import StorageTab from "@/app/admin/components/StorageTab";
import EmbeddingTab from "@/app/admin/components/EmbeddingTab";
import { I18nProvider } from "@/lib/i18n";
import { adminConfig, installAdminDialogs, jsonResponse, serveAdmin } from "./admin-fixtures";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); installAdminDialogs(); });
afterEach(() => vi.unstubAllGlobals());

it("keeps reconciled visibility after section navigation and a later independent save", async () => {
  const { fetcher, saved } = serveAdmin();
  const original = fetcher.getMockImplementation()!;
  let loseNextWrite = true;
  fetcher.mockImplementation(async (input, init) => {
    const result = await original(input, init);
    if (init?.method === "POST" && loseNextWrite) { loseNextWrite = false; throw new TypeError("Response lost after apply"); }
    return result;
  });
  render(<I18nProvider><AdminPage /></I18nProvider>);
  await screen.findByRole("heading", { name: "Your providers" });
  fireEvent.click(screen.getByRole("button", { name: "Fixture connection" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Show answer-model in model picker" }));
  await screen.findByRole("button", { name: "Reload saved values" });
  expect(saved.llm.profiles[0].models![0].enabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Reload saved values" }));
  await screen.findByText(/Saved values reloaded/);
  const nav = screen.getByRole("navigation", { name: "Configuration sections" });
  await waitFor(() => expect(within(nav).getByRole("button", { name: "File storage" })).toBeEnabled());
  fireEvent.click(within(nav).getByRole("button", { name: "File storage" }));
  fireEvent.click(within(nav).getByRole("button", { name: "Models & providers" }));
  fireEvent.click(screen.getByRole("button", { name: "Fixture connection" }));
  expect(screen.getByRole("checkbox", { name: "Show answer-model in model picker" })).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Add model" }));
  fireEvent.change(screen.getByLabelText("Model identifier"), { target: { value: "new-fixture-model" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Add model" }).at(-1)!);
  await waitFor(() => expect(saved.llm.profiles[0].models).toHaveLength(2));
  expect(saved.llm.profiles[0].models![0].enabled).toBe(false);
});

it.each(["llm", "storage", "embedding", "reranker"] as const)("does not discard %s write uncertainty through section navigation", async (section) => {
  const { fetcher } = serveAdmin();
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (input, init) => {
    const result = await original(input, init);
    if (init?.method === "POST") throw new TypeError("Response lost after apply");
    return result;
  });
  render(<I18nProvider><AdminPage /></I18nProvider>);
  await screen.findByRole("heading", { name: "Your providers" });
  if (section === "llm") {
    fireEvent.click(screen.getByRole("button", { name: "Fixture connection" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Show answer-model in model picker" }));
  } else {
    fireEvent.click(screen.getByRole("button", { name: section === "storage" ? "File storage" : "Document search" }));
    const label = section === "storage" ? "Bucket name" : section === "embedding" ? "Embedding model" : "Passages sent as context";
    fireEvent.change(screen.getByLabelText(label), { target: { value: section === "storage" ? "changed-bucket" : section === "embedding" ? "intfloat/multilingual-e5-large" : "15" } });
    fireEvent.click(screen.getByRole("button", { name: section === "storage" ? "Save file storage" : section === "embedding" ? "Save embeddings" : "Save reranker" }));
  }
  await screen.findByRole("button", { name: "Reload saved values" });
  await act(async () => {});
  const nav = screen.getByRole("navigation", { name: "Configuration sections" });
  expect(within(nav).getByRole("button", { name: "System status" })).toBeDisabled();
  fireEvent.click(within(nav).getByRole("button", { name: "System status" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reload saved values" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Reload saved values" }));
  await waitFor(() => expect(within(nav).getByRole("button", { name: "System status" })).toBeEnabled());
});

it.each(["storage", "embedding", "reranker"] as const)("reconciles an applied-but-unconfirmed %s change before Cancel or another write", async (section) => {
  const { fetcher, saved } = serveAdmin();
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (input, init) => {
    const result = await original(input, init);
    if (init?.method === "POST") throw new TypeError("Response lost after apply");
    return result;
  });
  render(<I18nProvider>{section === "storage"
    ? <StorageTab config={adminConfig.storage} backendUrl="http://fixture.invalid" onSaved={vi.fn()} />
    : <EmbeddingTab config={adminConfig.embedding} rerankerConfig={adminConfig.reranker} backendUrl="http://fixture.invalid" onSaved={vi.fn()} />
  }</I18nProvider>);
  const label = section === "storage" ? "Bucket name" : section === "embedding" ? "Embedding model" : "Passages sent as context";
  const save = section === "storage" ? "Save file storage" : section === "embedding" ? "Save embeddings" : "Save reranker";
  const next = section === "storage" ? "changed-bucket" : section === "embedding" ? "intfloat/multilingual-e5-large" : "15";
  fireEvent.change(screen.getByLabelText(label), { target: { value: next } });
  fireEvent.click(screen.getByRole("button", { name: save }));
  await screen.findByRole("alert");
  const form = screen.getByRole("button", { name: save }).closest("form")!;
  expect(within(form).getByRole("button", { name: "Cancel" })).toBeDisabled();
  expect(screen.getByRole("button", { name: save })).toBeDisabled();
  fireEvent.click(within(form).getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("alert")).toBeInTheDocument();
  fireEvent.click(within(form).getByRole("button", { name: "Reload saved values" }));
  await screen.findByText(/Saved values reloaded/);
  expect(screen.getByLabelText(label)).toHaveValue(section === "reranker" ? 15 : next);
  expect(section === "storage" ? saved.storage.s3_bucket : section === "embedding" ? saved.embedding.local_model : saved.reranker!.top_n).toBe(section === "reranker" ? 15 : next);
  expect(screen.getByRole("button", { name: save })).toBeDisabled();
});

it("retains independent search requests and publishes each section's authoritative snapshot", async () => {
  const pending: Array<() => void> = [];
  const fetcher = vi.fn((input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((resolve) => {
    const section = String(input).endsWith("embeddings") ? "embedding" : "reranker";
    pending.push(() => resolve(jsonResponse({ config: { ...adminConfig[section], ...JSON.parse(String(init?.body)) }, persistence: adminConfig.persistence })));
  }));
  vi.stubGlobal("fetch", fetcher);
  const embeddings = vi.fn(), reranker = vi.fn();
  render(<I18nProvider><EmbeddingTab config={adminConfig.embedding} rerankerConfig={adminConfig.reranker} backendUrl="http://fixture.invalid" onSaved={embeddings} onRerankerSaved={reranker} /></I18nProvider>);
  fireEvent.change(screen.getByLabelText("Embedding model"), { target: { value: "intfloat/multilingual-e5-large" } });
  fireEvent.change(screen.getByLabelText("Passages sent as context"), { target: { value: "15" } });
  fireEvent.click(screen.getByRole("button", { name: "Save embeddings" }));
  fireEvent.click(screen.getByRole("button", { name: "Save reranker" }));
  expect(fetcher).toHaveBeenCalledTimes(2);
  await act(async () => pending.forEach((resolve) => resolve()));
  expect(embeddings).toHaveBeenCalledWith(expect.objectContaining({ config: expect.objectContaining({ local_model: "intfloat/multilingual-e5-large" }) }));
  expect(reranker).toHaveBeenCalledWith(expect.objectContaining({ config: expect.objectContaining({ top_n: 15 }) }));
});

it.each([2, 31])("keeps other sections usable and requires repair of operator reranker value %s", async (top_n) => {
  serveAdmin({ ...adminConfig, reranker: { ...adminConfig.reranker!, top_n } });
  render(<I18nProvider><AdminPage /></I18nProvider>);
  await screen.findByRole("heading", { name: "Your providers" });
  fireEvent.click(screen.getByRole("button", { name: "Document search" }));
  expect(screen.getByLabelText("Passages sent as context")).toHaveValue(top_n);
  expect(screen.getByRole("alert")).toHaveTextContent("Enter a whole number from 3 to 30");
  expect(screen.getByRole("button", { name: "Save reranker" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Passages sent as context"), { target: { value: "12" } });
  fireEvent.click(screen.getByRole("button", { name: "Save reranker" }));
  await screen.findByText(/Passage reranking: Configuration saved/);
});
