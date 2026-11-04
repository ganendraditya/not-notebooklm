import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchWorkspaceModels } from "@/lib/workspace-models";

const model = {
  id: "provider/exact-technical-id",
  name: "Research model",
  profile_id: "provider",
  profile_name: "Research provider",
  protocol: "openai",
  is_default: true,
};

function respond(body: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok, status: ok ? 200 : 503, json: async () => body }));
}

afterEach(() => vi.unstubAllGlobals());

describe("fetchWorkspaceModels", () => {
  it("preserves valid names, technical IDs, and supported optional fields", async () => {
    const models = [model, { ...model, id: "other", protocol: "anthropic" }];
    respond({ workspace_models: models });
    await expect(fetchWorkspaceModels("http://synthetic.invalid")).resolves.toEqual(models);
  });

  it("accepts an empty list and models without optional fields", async () => {
    respond({ workspace_models: [] });
    await expect(fetchWorkspaceModels("http://synthetic.invalid")).resolves.toEqual([]);
    const required = { id: model.id, name: "", profile_id: model.profile_id, profile_name: "" };
    respond({ workspace_models: [required] });
    await expect(fetchWorkspaceModels("http://synthetic.invalid")).resolves.toEqual([required]);
  });

  it.each([
    { ...model, id: 1 },
    { ...model, profile_id: null },
    { ...model, name: undefined },
    { ...model, name: { unexpected: "object" } },
    { ...model, profile_name: undefined },
    { ...model, profile_name: { unexpected: "object" } },
    { ...model, protocol: "unsupported" },
    { ...model, is_default: "false" },
    null,
  ])("rejects malformed entries before they reach the picker: %j", async (invalid) => {
    respond({ workspace_models: [model, invalid] });
    await expect(fetchWorkspaceModels("http://synthetic.invalid")).rejects.toThrow("Invalid model list");
  });

  it.each([null, [], {}, { workspace_models: {} }])("rejects malformed response envelopes: %j", async (body) => {
    respond(body);
    await expect(fetchWorkspaceModels("http://synthetic.invalid")).rejects.toThrow("Model list unavailable");
  });

  it("reports an unsuccessful HTTP response", async () => {
    respond({}, false);
    await expect(fetchWorkspaceModels("http://synthetic.invalid")).rejects.toThrow("HTTP 503");
  });
});
