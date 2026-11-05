import type { AdminConfig } from "@/types/admin";

export type ConfigSection = "llm" | "storage" | "embedding" | "reranker";
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const strings = (value: Record<string, unknown>, keys: string[]) => keys.every((key) => typeof value[key] === "string");
const booleans = (value: Record<string, unknown>, keys: string[]) => keys.every((key) => typeof value[key] === "boolean");
const isRerankerConfig = (value: unknown) => record(value) && typeof value.model === "string"
  && typeof value.top_n === "number" && Number.isInteger(value.top_n);

export function isConfigSection<K extends ConfigSection>(section: K, value: unknown): value is NonNullable<AdminConfig[K]> {
  if (!record(value)) return false;
  switch (section) {
    case "llm":
      return strings(value, ["base_url", "api_key_masked", "model", "fast_model", "primary_profile_id", "fast_profile_id", "fallback_profile_id"])
        && typeof value.has_api_key === "boolean" && typeof value.temperature === "number" && Number.isFinite(value.temperature)
        && (value.fallback_model === null || typeof value.fallback_model === "string")
        && Array.isArray(value.profiles) && value.profiles.every((profile) => record(profile)
          && strings(profile, ["id", "name", "base_url", "api_key_masked"]) && typeof profile.has_api_key === "boolean"
          && (profile.protocol === undefined || profile.protocol === "openai" || profile.protocol === "anthropic")
          && (profile.models === undefined || Array.isArray(profile.models) && profile.models.every((model) => record(model)
            && typeof model.id === "string" && typeof model.enabled === "boolean" && (model.name === undefined || typeof model.name === "string"))));
    case "storage":
      return (value.storage_type === "local" || value.storage_type === "s3")
        && strings(value, ["s3_endpoint", "s3_bucket", "s3_region", "s3_access_key_masked"])
        && booleans(value, ["has_s3_secret", "is_configured"]);
    case "embedding":
      return ["local", "gemini", "openai", "custom"].includes(String(value.provider))
        && strings(value, ["local_model", "gemini_model", "gemini_key_masked"])
        && booleans(value, ["has_gemini_key", "hybrid_bm25_enabled"])
        && ["custom_base_url", "custom_model_name", "custom_local_path", "custom_key_masked"].every((key) => value[key] === undefined || typeof value[key] === "string")
        && (value.has_custom_key === undefined || typeof value.has_custom_key === "boolean");
    case "reranker":
      return isRerankerConfig(value) && typeof value.top_n === "number" && value.top_n >= 3 && value.top_n <= 30;
  }
}

export function isAdminConfig(value: unknown): value is AdminConfig {
  return record(value) && isConfigSection("llm", value.llm) && isConfigSection("storage", value.storage)
    && isConfigSection("embedding", value.embedding) && (value.reranker === undefined || isRerankerConfig(value.reranker))
    && record(value.secrets) && strings(value.secrets, ["active_provider", "infisical_project_id", "infisical_env", "doppler_project", "doppler_config"]);
}
