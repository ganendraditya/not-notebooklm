import type { AdminConfig, AdminPersistence } from "@/types/admin";
import { SECRET_PROVIDER_LABELS } from "@/lib/admin-persistence";
import { useTranslation } from "@/lib/i18n";

export default function SecretsTab({ config, persistence }: { config: AdminConfig["secrets"]; persistence?: AdminPersistence }) {
  const { t } = useTranslation();
  const notReported = t("admin.notReported");
  return <>
    <section className="admin-info-panel">
      <div className="admin-section-heading"><div><h2>{t("admin.activeConfiguration")}</h2><p className="admin-help">{t("admin.sourceReadOnly")}</p></div></div>
      <dl className="admin-definition-list">
        <dt>{t("admin.activeProvider")}</dt><dd>{persistence ? SECRET_PROVIDER_LABELS[persistence.active_provider] : notReported}</dd>
        <dt>{t("admin.persistence")}</dt><dd>{persistence ? t(persistence.mode === "runtime" ? "admin.processOnly" : "admin.localEnvFile") : notReported}</dd>
        <dt>{t("admin.localEnvFile")}</dt><dd>{persistence ? t(persistence.has_local_env ? "admin.present" : "admin.notFound") : notReported}</dd>
      </dl>
    </section>
    <details className="admin-disclosure"><summary>{t("admin.changeSource")}</summary><div className="admin-disclosure-content admin-prose"><p>{t("admin.changeSourceHelp")}</p><p>{t("admin.noPurge")}</p></div></details>
    <details className="admin-disclosure"><summary>{t("admin.launchMetadata")}</summary><div className="admin-disclosure-content">
      <p className="admin-help">{t("admin.metadataNotSession")}</p>
      <dl className="admin-definition-list">
        <dt>{t("admin.infisicalProject")}</dt><dd>{config.infisical_project_id || t("admin.notSet")}</dd>
        <dt>{t("admin.infisicalEnvironment")}</dt><dd>{config.infisical_env || t("admin.notSet")}</dd>
        <dt>{t("admin.dopplerProject")}</dt><dd>{config.doppler_project || t("admin.notSet")}</dd>
        <dt>{t("admin.dopplerConfig")}</dt><dd>{config.doppler_config || t("admin.notSet")}</dd>
      </dl>
    </div></details>
  </>;
}
