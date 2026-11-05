import { vi } from "vitest";
import type { AdminConfig, AdminSystemHealth } from "@/types/admin";

export const adminConfig: AdminConfig = {
  persistence: { mode: "local_env", active_provider: "local", has_local_env: true },
  llm: {
    base_url: "https://fixture.invalid/v1", api_key_masked: "sk-...1234", has_api_key: true,
    model: "answer-model", fast_model: "quick-model", fallback_model: null, temperature: 0.1,
    profiles: [{ id: "default", name: "Fixture connection", base_url: "https://fixture.invalid/v1", api_key_masked: "sk-...1234", has_api_key: true, protocol: "openai", models: [{ id: "answer-model", name: "Answer model", enabled: true }] }],
    primary_profile_id: "default", fast_profile_id: "default", fallback_profile_id: "default",
  },
  storage: { storage_type: "s3", s3_endpoint: "https://storage.invalid", s3_bucket: "fixture", s3_region: "auto", s3_access_key_masked: "...access", has_s3_secret: true, is_configured: true },
  secrets: { active_provider: "local", infisical_project_id: "", infisical_env: "dev", doppler_project: "", doppler_config: "dev" },
  embedding: { provider: "local", local_model: "configured-unknown-model", gemini_model: "models/gemini-embedding-001", gemini_key_masked: "...gemini", has_gemini_key: true, custom_base_url: "https://embeddings.invalid/v1", custom_model_name: "fixture-embed", has_custom_key: true, hybrid_bm25_enabled: true },
  reranker: { model: "configured-reranker", top_n: 12 },
};

export const adminHealth: AdminSystemHealth = {
  status: "ok", database: { engine: "SQLite WAL", chat_sessions: 4, documents: 12, messages: 38 },
  vector_store: { status: "healthy", collections: [{ name: "fixture-index", points_count: 140, status: "ready" }] },
  disk: { total_gb: 500, free_gb: 120, used_gb: 380 },
};

export function jsonResponse(value: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => value } as Response;
}

export function installAdminDialogs() {
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } },
    close: { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute("open"); } },
  });
}

export function serveAdmin(config: AdminConfig = structuredClone(adminConfig)) {
  const saved = structuredClone(config);
  const fetcher = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/system/health")) return jsonResponse(adminHealth);
    if (url.includes("/test/")) return jsonResponse({ success: true, message: "Fixture test response" });
    if (init?.method !== "POST") return jsonResponse(saved);
    const section = url.split("/").at(-1) === "embeddings" ? "embedding" : url.split("/").at(-1) as "llm" | "storage" | "reranker";
    const payload = JSON.parse(String(init.body));
    const next = { ...saved[section], ...payload };
    if (section === "llm") {
      next.profiles = payload.profiles.map((profile: { id: string; api_key?: string }) => {
        const { api_key, ...fields } = profile;
        const previous = saved.llm.profiles.find((item) => item.id === profile.id);
        return { ...previous, ...fields, has_api_key: !!api_key || previous?.has_api_key || false, api_key_masked: api_key ? "...new" : previous?.api_key_masked || "" };
      });
    }
    for (const key of ["api_key", "s3_access_key", "s3_secret_key", "gemini_key", "custom_key"]) delete next[key];
    Object.assign(saved, { [section]: next });
    return jsonResponse({ config: next, persistence: saved.persistence });
  });
  vi.stubGlobal("fetch", fetcher);
  return { fetcher, saved };
}
