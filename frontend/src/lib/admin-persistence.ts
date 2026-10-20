import type { AdminPersistence } from "@/types/admin";

export const SECRET_PROVIDER_LABELS = {
  local: "Local .env",
  infisical: "Infisical",
  doppler: "Doppler",
} as const;

export function parseAdminPersistence(value: unknown): AdminPersistence | undefined {
  if (typeof value !== "object" || value === null) return;
  if (!("mode" in value) || !("active_provider" in value) || !("has_local_env" in value)) return;
  if (typeof value.has_local_env !== "boolean") return;
  const { mode, active_provider, has_local_env } = value;
  if (
    (mode === "local_env" && active_provider === "local") ||
    (mode === "runtime" && (active_provider === "doppler" || active_provider === "infisical"))
  ) {
    return { mode, active_provider, has_local_env };
  }
}

export async function readConfigUpdateMessage(response: Pick<Response, "json">): Promise<string> {
  const data: unknown = await response.json().catch(() => null);
  const persistence = parseAdminPersistence(
    typeof data === "object" && data !== null && "persistence" in data ? data.persistence : undefined,
  );
  if (!persistence) {
    return "Configuration accepted, but persistence status was not reported. Refresh the dashboard to check.";
  }
  if (persistence.mode === "runtime") {
    return `Applied to this process only. Local .env was not changed. Update your ${SECRET_PROVIDER_LABELS[persistence.active_provider]} project to keep changes after restart.`;
  }
  return "Configuration saved to local .env.";
}
