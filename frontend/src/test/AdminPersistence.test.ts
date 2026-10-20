import { describe, expect, it } from "vitest";
import { parseAdminPersistence, readConfigUpdateMessage } from "@/lib/admin-persistence";

describe("admin persistence metadata", () => {
  it.each([
    { mode: "local_env", active_provider: "local", has_local_env: false },
    { mode: "runtime", active_provider: "doppler", has_local_env: true },
    { mode: "runtime", active_provider: "infisical", has_local_env: false },
  ])("accepts coherent metadata: $active_provider", (metadata) => {
    expect(parseAdminPersistence(metadata)).toEqual(metadata);
  });

  it.each([
    undefined, null, {}, "runtime",
    { mode: "runtime", active_provider: "local", has_local_env: true },
    { mode: "local_env", active_provider: "doppler", has_local_env: true },
    { mode: "runtime", active_provider: "unknown", has_local_env: true },
    { mode: "runtime", active_provider: "infisical", has_local_env: "false" },
    { mode: "runtime", active_provider: "doppler" },
  ])("rejects missing or inconsistent metadata: %j", (metadata) => {
    expect(parseAdminPersistence(metadata)).toBeUndefined();
  });

  it.each(["doppler", "infisical"])("explains runtime-only updates for %s", async (provider) => {
    const message = await readConfigUpdateMessage({ json: async () => ({
      message: "Saved successfully!",
      persistence: { mode: "runtime", active_provider: provider, has_local_env: true },
    }) });
    expect(message).toContain("this process only");
    expect(message).toContain("Local .env was not changed");
    expect(message).toContain("after restart");
    expect(message).not.toContain("Saved successfully");
  });

  it("only claims local persistence when the response reports it", async () => {
    expect(await readConfigUpdateMessage({ json: async () => ({
      persistence: { mode: "local_env", active_provider: "local", has_local_env: true },
    }) })).toBe("Configuration saved to local .env.");
  });

  it.each([undefined, null, {}, { message: "Saved!" }])("does not assume persistence for a legacy response: %j", async (data) => {
    expect(await readConfigUpdateMessage({ json: async () => data })).toContain("persistence status was not reported");
  });

  it("does not assume persistence when JSON cannot be read", async () => {
    expect(await readConfigUpdateMessage({ json: async () => { throw new SyntaxError(); } })).toContain("persistence status was not reported");
  });
});
