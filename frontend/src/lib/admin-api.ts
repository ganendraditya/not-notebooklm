import type { AdminConfig, AdminPersistence, GatewayProfile, TestResult } from "@/types/admin";
import { parseAdminPersistence } from "./admin-persistence";
import { isAdminConfig, isConfigSection, type ConfigSection } from "./admin-config";

export interface ConfigUpdate<T> {
  config: T;
  persistence?: AdminPersistence;
}

export async function adminRequest<T>(baseUrl: string, path: string, body?: object, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${baseUrl}/admin/${path}`, {
    method: body === undefined ? "GET" : "POST",
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    signal,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export async function loadAdminConfig(baseUrl: string): Promise<AdminConfig> {
  const config = await adminRequest<unknown>(baseUrl, "config");
  if (!isAdminConfig(config)) throw new Error("Configuration response unavailable");
  return config;
}

export async function saveAdminSection<K extends ConfigSection>(
  baseUrl: string,
  section: K,
  body: object,
): Promise<ConfigUpdate<NonNullable<AdminConfig[K]>>> {
  const path = section === "embedding" ? "embeddings" : section;
  const result = await adminRequest<ConfigUpdate<NonNullable<AdminConfig[K]>>>(baseUrl, `config/${path}`, body);
  if (!result || !isConfigSection(section, result.config)) throw new Error("Configuration response unavailable");
  return { config: result.config, persistence: parseAdminPersistence(result.persistence) };
}

export async function testAdminConnection(baseUrl: string, kind: "llm" | "storage" | "embeddings" | "reranker", body: object, signal?: AbortSignal): Promise<TestResult> {
  const result = await adminRequest<TestResult>(baseUrl, `test/${kind}`, body, signal);
  if (!result || typeof result.success !== "boolean" || typeof result.message !== "string") throw new Error("Test response unavailable");
  return result;
}

export type LlmRouting = Pick<AdminConfig["llm"], "model" | "fast_model" | "fallback_model" | "temperature" | "primary_profile_id" | "fast_profile_id" | "fallback_profile_id">;

export function routingFromConfig(config: AdminConfig["llm"]): LlmRouting {
  return {
    model: config.model,
    fast_model: config.fast_model,
    fallback_model: config.fallback_model,
    temperature: config.temperature,
    primary_profile_id: config.primary_profile_id,
    fast_profile_id: config.fast_profile_id,
    fallback_profile_id: config.fallback_profile_id,
  };
}

export function profilesFromConfig(config: AdminConfig["llm"]): GatewayProfile[] {
  return config.profiles;
}

export function llmPayload(saved: AdminConfig["llm"], profiles: GatewayProfile[], routing = routingFromConfig(saved), credentials: Record<string, string> = {}) {
  const firstModel = profiles.flatMap((profile) => (profile.models || []).filter((model) => model.enabled).map((model) => ({ profile, model })))[0];
  const existingPrimary = profiles.find((profile) => profile.id === routing.primary_profile_id);
  const primaryId = routing.model ? routing.primary_profile_id : firstModel?.profile.id || existingPrimary?.id || profiles[0]?.id || "";
  const primary = profiles.find((profile) => profile.id === primaryId);
  return {
    ...routing,
    model: routing.model || firstModel?.model.id || "",
    primary_profile_id: primaryId,
    fast_profile_id: routing.fast_profile_id || primaryId,
    fallback_profile_id: routing.fallback_profile_id || primaryId,
    fallback_model: routing.fallback_model || null,
    base_url: primary?.base_url ?? saved.base_url,
    ...(primary && credentials[primary.id]?.trim() ? { api_key: credentials[primary.id].trim() } : {}),
    profiles: profiles.map((profile) => ({
      id: profile.id,
      name: profile.name,
      base_url: profile.base_url,
      protocol: profile.protocol || "openai",
      models: profile.models,
      ...(credentials[profile.id]?.trim() ? { api_key: credentials[profile.id].trim() } : {}),
    })),
  };
}
