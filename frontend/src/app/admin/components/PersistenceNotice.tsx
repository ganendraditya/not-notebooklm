import type { AdminPersistence } from "@/types/admin";
import { SECRET_PROVIDER_LABELS } from "@/lib/admin-persistence";
import { useTranslation } from "@/lib/i18n";

export default function PersistenceNotice({ persistence }: { persistence?: AdminPersistence }) {
  const { t } = useTranslation();
  const runtime = persistence?.mode === "runtime";
  if (persistence?.mode === "local_env") return <details className="admin-persistence-local" aria-label={t("admin.persistence")}>
    <summary>{t("admin.localPersistenceSummary")}</summary><p className="admin-help">{t("admin.localPersistenceHelp")}</p>
  </details>;
  return <section aria-label={t("admin.persistence")} className={`admin-persistence${!persistence || runtime ? " admin-persistence-warning" : ""}`}>
    <h2>{!persistence ? t("admin.persistenceUnavailable") : runtime ? t("admin.runtimeSession", { provider: SECRET_PROVIDER_LABELS[persistence.active_provider] }) : t("admin.localConfiguration")}</h2>
    <p>{t(!persistence ? "admin.persistenceUnavailableHelp" : runtime ? "admin.runtimeHelp" : "admin.localPersistenceHelp")}</p>
    {runtime && persistence.has_local_env && <div role="note" aria-label={t("admin.localCredentialsNotice")}>
      <h3>{t("admin.localFilePresent")}</h3><p>{t("admin.localFileWarning")}</p>
    </div>}
  </section>;
}
