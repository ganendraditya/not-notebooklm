import { afterEach, describe, expect, it, vi } from "vitest";
import { isAdminConfig, isConfigSection } from "@/lib/admin-config";
import { llmPayload, loadAdminConfig, profilesFromConfig, saveAdminSection } from "@/lib/admin-api";
import { adminConfig, jsonResponse } from "./admin-fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("Admin configuration contracts", () => {
  it("accepts complete masked responses and preserves configured model IDs", () => {
    expect(isAdminConfig(adminConfig)).toBe(true);
    expect(isConfigSection("embedding", adminConfig.embedding)).toBe(true);
  });

  it.each([2, 31])("reads operator reranker value %s without weakening save validation", async (top_n) => {
    const config = { ...adminConfig, reranker: { ...adminConfig.reranker!, top_n } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(config)));
    await expect(loadAdminConfig("http://fixture.invalid")).resolves.toMatchObject({ reranker: { top_n } });
    expect(isConfigSection("reranker", config.reranker)).toBe(false);
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ config: config.reranker }));
    await expect(saveAdminSection("http://fixture.invalid", "reranker", config.reranker)).rejects.toThrow();
  });

  it.each([null, {}, { ...adminConfig, llm: { ...adminConfig.llm, profiles: "invalid" } }])("rejects incomplete or malformed configuration: %j", async (config) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(config)));
    await expect(loadAdminConfig("http://localhost:8000")).rejects.toThrow("Configuration response unavailable");
  });

  it("does not accept a success envelope without an authoritative saved section", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ status: "success", config: {} })));
    await expect(saveAdminSection("http://localhost:8000", "llm", {})).rejects.toThrow("Configuration response unavailable");
  });

  it("omits stored masks and blank replacement keys from combined LLM writes", () => {
    const payload = llmPayload(adminConfig.llm, adminConfig.llm.profiles, undefined, { default: "  " });
    expect(payload).not.toHaveProperty("api_key");
    expect(payload.profiles[0]).not.toHaveProperty("api_key");
    expect(payload.profiles[0]).not.toHaveProperty("api_key_masked");
    expect(payload.profiles[0]).not.toHaveProperty("has_api_key");
  });

  it("respects an explicit empty profile list even when legacy endpoint fields remain", () => {
    expect(profilesFromConfig({ ...adminConfig.llm, profiles: [] })).toEqual([]);
  });

  it("bootstraps internal routing from the first registered model without a separate answer-default form", () => {
    const saved = { ...adminConfig.llm, model: "", fast_model: "", primary_profile_id: "", fast_profile_id: "", fallback_profile_id: "", base_url: "", profiles: [] };
    const payload = llmPayload(saved, adminConfig.llm.profiles);
    expect(payload).toMatchObject({ model: "answer-model", primary_profile_id: "default", fast_profile_id: "default", fallback_profile_id: "default", base_url: "https://fixture.invalid/v1" });
    expect(payload).not.toHaveProperty("api_key");
  });

  it("does not replace an existing unregistered internal model when editing the provider list", () => {
    const saved = { ...adminConfig.llm, model: "legacy-unregistered-model" };
    expect(llmPayload(saved, saved.profiles).model).toBe("legacy-unregistered-model");
  });

  it("preserves an active legacy primary when only a custom provider's model visibility changes", () => {
    const profile = { ...adminConfig.llm.profiles[0], id: "custom-profile", base_url: "https://profile.invalid/v1" };
    const saved = { ...adminConfig.llm, base_url: "https://legacy.invalid/v1", model: "legacy-model", profiles: [profile] };
    const changed = [{ ...profile, models: profile.models!.map((model) => ({ ...model, enabled: false })) }];
    const payload = llmPayload(saved, changed);
    expect(payload).toMatchObject({ base_url: saved.base_url, model: "legacy-model", primary_profile_id: "default", fast_profile_id: "default", fallback_profile_id: "default" });
    expect(payload.profiles).toHaveLength(1);
    expect(payload.profiles[0]).toMatchObject({ id: "custom-profile", models: [{ enabled: false }] });
    expect(payload).not.toHaveProperty("api_key");
    expect(payload.profiles[0]).not.toHaveProperty("api_key");
  });
});
