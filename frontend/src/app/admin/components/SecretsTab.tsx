"use client";

import { KeyRound } from "lucide-react";
import type { AdminConfig, AdminPersistence } from "@/types/admin";
import { SECRET_PROVIDER_LABELS } from "@/lib/admin-persistence";

interface SecretsTabProps {
  config: AdminConfig["secrets"];
  persistence?: AdminPersistence;
}

export default function SecretsTab({ config, persistence }: SecretsTabProps) {
  return (
    <div className="space-y-6 text-sm">
      <div className="border-b border-app-border pb-4">
        <h2 className="text-base font-semibold text-app-text flex items-center gap-2">
          <KeyRound size={18} aria-hidden="true" />
          Secret Providers & Vaults
        </h2>
        <p className="text-app-text-muted mt-2">
          Inspect this backend process. This page does not connect to a vault or switch secret providers.
        </p>
      </div>

      <dl className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-x-6 gap-y-2 text-app-text">
        <dt className="text-app-text-muted">Active provider</dt>
        <dd className="font-medium">{persistence ? SECRET_PROVIDER_LABELS[persistence.active_provider] : "Not reported"}</dd>
        <dt className="text-app-text-muted">Configuration persistence</dt>
        <dd>{persistence ? (persistence.mode === "runtime" ? "This process only" : "Local .env file") : "Not reported"}</dd>
        <dt className="text-app-text-muted">Local .env file</dt>
        <dd>{persistence ? (persistence.has_local_env ? "Present" : "Not found") : "Not reported"}</dd>
      </dl>

      <section aria-labelledby="vault-launch-heading" className="space-y-2 border-t border-app-border pt-4">
        <h3 id="vault-launch-heading" className="font-semibold text-app-text">Changing the active provider</h3>
        <p className="text-app-text-muted">
          Restart the application through your vault&apos;s CLI to change the active provider. Direct Infisical launches must set <code className="break-all">INFISICAL_INJECTED=1</code>.
          To return to local configuration, restart without the vault runtime markers.
        </p>
        <p className="text-app-text-muted">Existing .env files are never deleted automatically. File removal is not available in this panel.</p>
      </section>

      <section aria-labelledby="vault-metadata-heading" className="space-y-3 border-t border-app-border pt-4">
        <h3 id="vault-metadata-heading" className="font-semibold text-app-text">Reported launch metadata</h3>
        <p className="text-app-text-muted">Project names and environment settings alone do not establish an active vault session.</p>
        <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            ["Infisical project", config.infisical_project_id],
            ["Infisical environment", config.infisical_env],
            ["Doppler project", config.doppler_project],
            ["Doppler config", config.doppler_config],
          ].map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-app-text-muted">{label}</dt>
              <dd className="mt-1 break-words text-app-text">{value || "Not set"}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
