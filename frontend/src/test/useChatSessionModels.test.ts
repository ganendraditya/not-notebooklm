import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatSession } from "@/hooks/chat/useChatSession";
import { useChatStore, type WorkspaceModel } from "@/stores/chatStore";
import { MODEL_PREFERENCES_KEY, modelKey, recordModelSelection } from "@/lib/model-preferences";

const models: WorkspaceModel[] = [
  { id: "shared", name: "First model", profile_id: "first", profile_name: "First provider" },
  { id: "shared", name: "Second model", profile_id: "second", profile_name: "Second provider", is_default: true },
];
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

function setup(activeChatId: string | null = null) {
  const store = useChatStore.getState();
  const activeChatIdRef = { current: activeChatId };
  const fetcher = vi.mocked(fetch);
  const hook = renderHook(() => useChatSession(
    "http://fixture.invalid", store.sessions, store.setSessions, activeChatId, store.setActiveChatId,
    vi.fn(), vi.fn(), store.setMessages, vi.fn(), vi.fn(), store.setQueuedPrompts,
    store.setIsLoading, store.setActiveStatus, vi.fn(), store.updateSessionsList,
    vi.fn(), activeChatIdRef,
  ));
  return { ...hook, fetcher, activeChatIdRef };
}

describe("session model selection", () => {
  beforeEach(() => {
    localStorage.clear();
    useChatStore.setState({ sessions: [], availableModels: [], modelCatalogStatus: "loading", activeChatId: null, pendingNewChatModel: null, lastSelectedModelKey: null });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/llm/models")) return response({ workspace_models: models });
      if (init?.method === "POST") return response({ id: "created-chat", created_at: "2026-11-05", ...JSON.parse(String(init.body)) });
      return response(useChatStore.getState().sessions);
    }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it.each([
    { name: "first configured model", recent: undefined, profile_id: "first" },
    { name: "remembered provider/model pair", recent: modelKey(models[1]), profile_id: "second" },
    { name: "first model after removal", recent: modelKey({ id: "removed", profile_id: "second" }), profile_id: "first" },
  ])("persists the $name on a newly created session", async ({ recent, profile_id }) => {
    if (recent) localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify({ favorites: [], recent: [recent] }));
    const { result, fetcher } = setup();
    await act(async () => { await result.current.handleEnsureChatSession(); });
    const call = fetcher.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(JSON.parse(String(call[1]?.body))).toMatchObject({ model: "shared", profile_id });
    expect(useChatStore.getState().sessions[0]).toMatchObject({ model: "shared", profile_id });
  });

  it("uses an explicit pending selection before remembered history and clears it only after success", async () => {
    localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify({ recent: [modelKey(models[0])] }));
    useChatStore.getState().setPendingNewChatModel({ model: "shared", profile_id: "second" });
    const { result, fetcher } = setup();
    await act(async () => { await result.current.handleEnsureChatSession(); });
    expect(JSON.parse(String(fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]?.body))).toMatchObject({ model: "shared", profile_id: "second" });
    expect(useChatStore.getState().pendingNewChatModel).toBeNull();
  });

  it("keeps the last choice consistent with session creation when browser storage is blocked", async () => {
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Storage blocked"); });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Storage blocked"); });
    try {
      act(() => recordModelSelection(models[1]));
      const { result } = setup();
      await act(async () => { await result.current.handleEnsureChatSession(); });
      expect(useChatStore.getState().sessions[0]).toMatchObject({ model: "shared", profile_id: "second" });
    } finally { get.mockRestore(); set.mockRestore(); }
  });

  it("does not update a saved session when browser history points to another provider", async () => {
    const session = { id: "saved", title: "Saved", created_at: "2026-11-05", model: "legacy-model", profile_id: "legacy-provider" };
    useChatStore.setState({ sessions: [session] });
    localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify({ recent: [modelKey(models[1])] }));
    const { result, fetcher } = setup("saved");
    await expect(result.current.handleEnsureChatSession()).resolves.toBe("saved");
    expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST" || init?.method === "PATCH")).toBe(false);
    expect(useChatStore.getState().sessions[0]).toEqual(session);
  });

  it("preserves backend-default behavior for grandfathered unbound chats even at message preflight", async () => {
    useChatStore.setState({ sessions: [{ id: "legacy-unbound", title: "Legacy", created_at: "2026-11-05" }] });
    const { result, fetcher } = setup("legacy-unbound");
    await act(async () => { await expect(result.current.handleEnsureChatSession(undefined, true)).resolves.toBe("legacy-unbound"); });
    expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST" || init?.method === "PATCH")).toBe(false);
  });

  it("waits for model hydration and shares a concurrent creation request", async () => {
    let finish!: (response: Response) => void;
    const loading = new Promise<Response>((resolve) => { finish = resolve; });
    const original = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation((url, init) => String(url).endsWith("/llm/models") ? loading : original(url, init));
    const { result, fetcher } = setup();
    let first!: Promise<string>, second!: Promise<string>;
    act(() => { window.dispatchEvent(new Event("focus")); window.dispatchEvent(new Event("focus")); });
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith("/llm/models"))).toHaveLength(1);
    act(() => { first = result.current.handleEnsureChatSession(); second = result.current.handleEnsureChatSession(); });
    expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
    await act(async () => { finish(response({ workspace_models: models })); await Promise.all([first, second]); });
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    expect(useChatStore.getState().sessions[0]).toMatchObject({ model: "shared", profile_id: "first" });
  });

  it("allows a source-only session with no model without inventing or reusing an unavailable selection", async () => {
    const original = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation((url, init) => String(url).endsWith("/llm/models") ? Promise.resolve(response({ workspace_models: [] })) : original(url, init));
    useChatStore.getState().setPendingNewChatModel({ model: "removed", profile_id: "removed-provider" });
    const { result, fetcher } = setup();
    await act(async () => { await result.current.handleEnsureChatSession("Source-only notebook"); });
    const payload = JSON.parse(String(fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]?.body));
    expect(payload).toEqual({ title: "Source-only notebook" });
  });

  it("keeps the pending choice when session creation fails", async () => {
    const original = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation((url, init) => init?.method === "POST" ? Promise.resolve(response({}, 503)) : original(url, init));
    useChatStore.getState().setPendingNewChatModel({ model: "shared", profile_id: "second" });
    const { result } = setup();
    await act(async () => { await expect(result.current.handleEnsureChatSession()).rejects.toThrow("503"); });
    expect(useChatStore.getState().pendingNewChatModel).toEqual({ model: "shared", profile_id: "second" });
    expect(useChatStore.getState().sessions).toEqual([]);
  });

  it("reloads availability after returning from configuration, without changing saved chats", async () => {
    const { fetcher } = setup();
    await waitFor(() => expect(useChatStore.getState().availableModels).toEqual(models));
    fetcher.mockImplementation(async () => response({ workspace_models: [models[1]] }));
    act(() => window.dispatchEvent(new Event("focus")));
    await waitFor(() => expect(useChatStore.getState().availableModels).toEqual([models[1]]));
    expect(useChatStore.getState().modelCatalogStatus).toBe("ready");
    expect(fetcher.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
  });

  it("distinguishes a failed catalog load, preserves cached availability, and recovers on focus", async () => {
    useChatStore.setState({ availableModels: models });
    vi.mocked(fetch).mockRejectedValue(new Error("Offline"));
    const { fetcher } = setup();
    await waitFor(() => expect(useChatStore.getState().modelCatalogStatus).toBe("error"));
    expect(useChatStore.getState().availableModels).toEqual(models);
    fetcher.mockResolvedValue(response({ workspace_models: [] }));
    act(() => window.dispatchEvent(new Event("focus")));
    await waitFor(() => expect(useChatStore.getState().modelCatalogStatus).toBe("ready"));
    expect(useChatStore.getState().availableModels).toEqual([]);
  });
});
