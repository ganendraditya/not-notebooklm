import React, { useRef } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ChatInputBox } from "@/components/chat/ChatInput";
import { ModelSwitcher } from "@/components/chat/ModelSwitcher";
import { useChatSession } from "@/hooks/chat/useChatSession";
import { useChatStore } from "@/stores/chatStore";
import { I18nProvider } from "@/lib/i18n";
import { MODEL_PREFERENCES_KEY, modelKey, recordModelSelection, syncRememberedModelSelection } from "@/lib/model-preferences";
import { chatRequiresModel, MODEL_REQUIRED_CHATS_KEY, setChatRequiresModel } from "@/lib/new-chat-models";
import { jsonResponse } from "./admin-fixtures";

const models = [
  { id: "a", name: "Model A", profile_id: "first", profile_name: "First provider" },
  { id: "b", name: "Model B", profile_id: "second", profile_name: "Second provider" },
  { id: "c", name: "Model C", profile_id: "third", profile_name: "Third provider" },
];
beforeEach(() => {
  localStorage.clear();
  useChatStore.setState({ sessions: [], availableModels: [], modelCatalogStatus: "loading", activeChatId: null, pendingNewChatModel: null, lastSelectedModelKey: null, modelRequiredChatIds: [], modelUpdatingChatIds: [] });
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function Harness({ accepted }: { accepted: (message: string) => void }) {
  const store = useChatStore();
  const active = useRef<string | null>(store.activeChatId);
  const session = useChatSession("http://fixture.invalid", store.sessions, store.setSessions, store.activeChatId, store.setActiveChatId,
    vi.fn(), vi.fn(), store.setMessages, vi.fn(), vi.fn(), store.setQueuedPrompts, store.setIsLoading, store.setActiveStatus,
    vi.fn(), store.updateSessionsList, vi.fn(), active);
  return <I18nProvider><ModelSwitcher backendUrl="http://fixture.invalid" activeChatId={store.activeChatId} />
    <ChatInputBox chatId={store.activeChatId} backendUrl="http://fixture.invalid" onEnsureChatSession={session.handleEnsureChatSession} onSubmit={accepted} />
  </I18nProvider>;
}

function transport(catalog: () => Promise<Response>) {
  const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/llm/models")) return catalog();
    if (url.endsWith("/upload_chat_media")) return jsonResponse({ attachment: { type: "file", filename: "dummy.txt", url: "/dummy.txt", size: 5 } });
    if (init?.method === "POST") return jsonResponse({ id: "dummy-chat", created_at: "2026-11-05", ...JSON.parse(String(init.body)) });
    if (init?.method === "PATCH") return jsonResponse({ id: "dummy-chat", ...JSON.parse(String(init.body)) });
    return jsonResponse(useChatStore.getState().sessions);
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

it("uses the displayed external-tab choice even when focus refresh fails", async () => {
  localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify({ recent: [modelKey(models[0])] }));
  let offline = false;
  const fetcher = transport(async () => { if (offline) throw new Error("Mock offline"); return jsonResponse({ workspace_models: models }); });
  const accepted = vi.fn();
  render(<Harness accepted={accepted} />);
  await screen.findByRole("button", { name: /Model A/ });
  await waitFor(() => expect(useChatStore.getState().modelCatalogStatus).toBe("ready"));
  act(() => {
    localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify({ recent: [modelKey(models[1])] }));
    window.dispatchEvent(new StorageEvent("storage", { key: MODEL_PREFERENCES_KEY }));
    offline = true; window.dispatchEvent(new Event("focus"));
  });
  await waitFor(() => expect(useChatStore.getState().modelCatalogStatus).toBe("error"));
  expect(screen.getByRole("button", { name: /Model B/ })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Use the displayed model" } });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(accepted).toHaveBeenCalled());
  const post = fetcher.mock.calls.find(([, init]) => init?.method === "POST")!;
  expect(JSON.parse(String(post[1]?.body))).toMatchObject({ model: "b", profile_id: "second" });
});

it("preserves the draft and sends nothing when the pending refresh removes every model", async () => {
  let finish!: (response: Response) => void;
  let calls = 0;
  const refresh = new Promise<Response>((resolve) => { finish = resolve; });
  const fetcher = transport(async () => ++calls === 1 ? jsonResponse({ workspace_models: models }) : refresh);
  const accepted = vi.fn();
  render(<Harness accepted={accepted} />);
  await waitFor(() => expect(useChatStore.getState().modelCatalogStatus).toBe("ready"));
  act(() => window.dispatchEvent(new Event("focus")));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Keep this draft" } });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(screen.getByRole("textbox")).toHaveValue("Keep this draft");
  await act(async () => { finish(jsonResponse({ workspace_models: [] })); });
  await screen.findByRole("alert");
  expect(accepted).not.toHaveBeenCalled();
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  expect(screen.getByRole("textbox")).toHaveValue("Keep this draft");
});

it("blocks a new source-only first message, then binds it when a model becomes available", async () => {
  let available = false;
  const fetcher = transport(async () => jsonResponse({ workspace_models: available ? models : [] }));
  const accepted = vi.fn();
  const { container } = render(<Harness accepted={accepted} />);
  await waitFor(() => expect(useChatStore.getState().modelCatalogStatus).toBe("ready"));
  fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(["dummy"], "dummy.txt", { type: "text/plain" })] } });
  await waitFor(() => expect(useChatStore.getState().activeChatId).toBe("dummy-chat"));
  await waitFor(() => expect(screen.getByRole("button", { name: /send/i })).not.toBeDisabled());
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Ask after choosing a model" } });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(accepted).not.toHaveBeenCalled();
  expect(chatRequiresModel("dummy-chat")).toBe(true);
  act(() => useChatStore.setState({ modelRequiredChatIds: [] }));
  expect(JSON.parse(localStorage.getItem(MODEL_REQUIRED_CHATS_KEY)!)).toContain("dummy-chat");
  expect(chatRequiresModel("dummy-chat")).toBe(true);
  act(() => { available = true; window.dispatchEvent(new Event("focus")); });
  await waitFor(() => expect(useChatStore.getState().availableModels).toHaveLength(models.length));
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(accepted).toHaveBeenCalled());
  expect(fetcher.mock.calls.find(([, init]) => init?.method === "PATCH")?.[1]?.body).toBe(JSON.stringify({ model: "a", profile_id: "first" }));
  expect(chatRequiresModel("dummy-chat")).toBe(false);
});

it("serializes saved-model selection so an older response cannot overwrite a later preference", async () => {
  useChatStore.setState({ sessions: [{ id: "saved", title: "Saved", created_at: "2026-11-05", model: "a", profile_id: "first" }], availableModels: models, modelCatalogStatus: "ready" });
  let finish!: (response: Response) => void;
  const fetcher = vi.fn(() => new Promise<Response>((resolve) => { finish = resolve; }));
  vi.stubGlobal("fetch", fetcher);
  render(<I18nProvider><ModelSwitcher backendUrl="http://fixture.invalid" activeChatId="saved" /></I18nProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Model A/ }));
  fireEvent.click(screen.getByRole("menuitem", { name: /Model B/ }));
  expect(screen.getByRole("button", { name: /Model B/ })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /Model B/ }));
  expect(screen.queryByRole("menuitem", { name: /Model C/ })).not.toBeInTheDocument();
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  await act(async () => finish(jsonResponse({})));
  fireEvent.click(screen.getByRole("button", { name: /Model B/ }));
  fireEvent.click(screen.getByRole("menuitem", { name: /Model C/ }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  await act(async () => finish(jsonResponse({})));
  expect(useChatStore.getState().lastSelectedModelKey).toBe(modelKey(models[2]));
  expect(screen.getByRole("button", { name: /Model C/ })).toBeEnabled();
});

it("keeps an unpersisted memory choice when storage writes fail but reads still work", () => {
  localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify({ recent: [modelKey(models[0])] }));
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Quota"); });
  recordModelSelection(models[1]);
  expect(syncRememberedModelSelection()).toBe(modelKey(models[1]));
  expect(useChatStore.getState().lastSelectedModelKey).toBe(modelKey(models[1]));
});

it("preserves a prepared draft instead of sending it to a different active chat", async () => {
  useChatStore.setState({ activeChatId: "source-only", availableModels: models });
  setChatRequiresModel("source-only", true);
  let finish!: (id: string) => void;
  const ensure = vi.fn(() => new Promise<string>((resolve) => { finish = resolve; }));
  const accepted = vi.fn();
  const composer = (chatId: string) => <I18nProvider><ChatInputBox chatId={chatId} backendUrl="http://fixture.invalid" onEnsureChatSession={ensure} onSubmit={accepted} /></I18nProvider>;
  const { rerender } = render(composer("source-only"));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Draft intended for source-only" } });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
  act(() => useChatStore.getState().setActiveChatId("other-chat"));
  rerender(composer("other-chat"));
  await act(async () => finish("source-only"));
  expect(accepted).not.toHaveBeenCalled();
  expect(screen.getByRole("textbox")).toHaveValue("Draft intended for source-only");
});

it("displays the remembered pair for a new source-only chat without changing legacy-unbound display", () => {
  useChatStore.setState({ sessions: [{ id: "source-only", title: "Sources", created_at: "2026-11-05" }], availableModels: models });
  setChatRequiresModel("source-only", true);
  recordModelSelection(models[1]);
  render(<I18nProvider><ModelSwitcher backendUrl="http://fixture.invalid" activeChatId="source-only" /></I18nProvider>);
  expect(screen.getByRole("button", { name: /Model B/ })).toBeInTheDocument();
});

it.each([200, 503])("waits for picker binding before accepting a new source-only message (HTTP %s)", async (status) => {
  useChatStore.setState({ activeChatId: "source-only", sessions: [{ id: "source-only", title: "Sources", created_at: "2026-11-05" }], availableModels: models });
  setChatRequiresModel("source-only", true);
  let finish!: (response: Response) => void;
  const fetcher = transport(async () => jsonResponse({ workspace_models: models }));
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation((input, init) => init?.method === "PATCH" ? new Promise<Response>((resolve) => { finish = resolve; }) : original(input, init));
  const accepted = vi.fn();
  render(<Harness accepted={accepted} />);
  await waitFor(() => expect(useChatStore.getState().modelCatalogStatus).toBe("ready"));
  fireEvent.click(screen.getByRole("button", { name: /Model A/ }));
  fireEvent.click(screen.getByRole("menuitem", { name: /Model B/ }));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Keep until binding succeeds" } });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1));
  expect(accepted).not.toHaveBeenCalled();
  expect(screen.getByRole("textbox")).toHaveValue("Keep until binding succeeds");
  await act(async () => finish(jsonResponse({}, status)));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
  if (status === 200) {
    expect(accepted).toHaveBeenCalled();
    expect(chatRequiresModel("source-only")).toBe(false);
    expect(useChatStore.getState().sessions[0]).toMatchObject({ model: "b", profile_id: "second" });
  } else {
    expect(accepted).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox")).toHaveValue("Keep until binding succeeds");
    expect(chatRequiresModel("source-only")).toBe(true);
  }
});
