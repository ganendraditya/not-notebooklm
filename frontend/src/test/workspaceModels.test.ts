import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { fetchWorkspaceModels, resolveNewChatModel } from "@/lib/workspace-models";
import { modelKey } from "@/lib/model-preferences";
import type { WorkspaceModel } from "@/stores/chatStore";

const first: WorkspaceModel = { id: "same", name: "First", profile_id: "a", profile_name: "Provider A" };
const second: WorkspaceModel = { id: "same", name: "Second", profile_id: "b", profile_name: "Provider B", is_default: true };

describe("new-chat model resolution", () => {
  it("uses the first active configured model when there is no remembered selection, not a separate answer default", () => {
    expect(resolveNewChatModel([first, second])).toBe(first);
  });

  it("remembers the exact provider/model pair", () => {
    expect(resolveNewChatModel([first, second], modelKey(second))).toBe(second);
  });

  it("gives a pending explicit selection priority over browser history", () => {
    expect(resolveNewChatModel([first, second], modelKey(second), { model: first.id, profile_id: first.profile_id })).toBe(first);
  });

  it("uses the first active model when the remembered or pending choice is removed or disabled", () => {
    expect(resolveNewChatModel([first], modelKey(second), { model: second.id, profile_id: second.profile_id })).toBe(first);
  });

  it("does not invent a model when the configured catalog is empty", () => {
    expect(resolveNewChatModel([], modelKey(second), { model: second.id, profile_id: second.profile_id })).toBeUndefined();
  });
});

describe("workspace model loading", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => vi.unstubAllGlobals());

  it("accepts an authoritative empty model catalog", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ workspace_models: [] })));
    expect(await fetchWorkspaceModels("http://fixture.invalid")).toEqual([]);
  });

  it.each([{ workspace_models: null }, { workspace_models: [{ id: "incomplete" }] }, {}])("rejects malformed catalogs: %j", async (payload) => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(payload)));
    await expect(fetchWorkspaceModels("http://fixture.invalid")).rejects.toThrow();
  });

  it("does not treat a failed load as an authoritative empty catalog", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("unavailable", { status: 503 }));
    await expect(fetchWorkspaceModels("http://fixture.invalid")).rejects.toThrow("HTTP 503");
  });

  it.each([
    { ...first, name: {} }, { ...first, profile_name: null }, { ...first, protocol: "unsupported" }, { ...first, is_default: "yes" },
  ])("rejects invalid display or optional fields without publishing a partial catalog: %j", async (model) => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ workspace_models: [first, model] })));
    await expect(fetchWorkspaceModels("http://fixture.invalid")).rejects.toThrow("Invalid model list");
  });
});
