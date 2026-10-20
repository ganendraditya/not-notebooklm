import type { AdminPersistence } from "@/types/admin";
import { SECRET_PROVIDER_LABELS } from "@/lib/admin-persistence";

interface PersistenceNoticeProps {
  persistence?: AdminPersistence;
}

export default function PersistenceNotice({ persistence }: PersistenceNoticeProps) {
  return (
    <section aria-label="Configuration persistence" className="mb-6 rounded-lg border border-app-border bg-app-input-surface p-4 text-sm text-app-text">
      {!persistence ? (
        <>
          <h2 className="font-semibold">Persistence status unavailable</h2>
          <p className="mt-1 text-app-text-muted">
            The backend did not report valid persistence metadata. Refresh or update the backend before assuming changes will survive a restart.
          </p>
        </>
      ) : persistence.mode === "runtime" ? (
        <>
          <h2 className="font-semibold">{SECRET_PROVIDER_LABELS[persistence.active_provider]} runtime session</h2>
          <p className="mt-1 text-app-text-muted">
            Configuration changes apply only to this backend process and are lost after restart. Update your vault separately to keep them.
          </p>
          {persistence.has_local_env && (
            <div role="note" aria-label="Local credentials notice" className="mt-3 border-t border-app-border pt-3">
              <h3 className="font-semibold">Local .env file still present</h3>
              <p className="mt-1 text-app-text-muted">
                Credentials may still exist in plaintext on disk. Injected values take precedence, but missing values may still load from this file. Nothing has been deleted.
              </p>
            </div>
          )}
        </>
      ) : (
        <>
          <h2 className="font-semibold">Local configuration</h2>
          <p className="mt-1 text-app-text-muted">
            Configuration changes are written to local .env. No injected vault session was detected.
          </p>
        </>
      )}
    </section>
  );
}
