import type { AdminSystemHealth } from "@/types/admin";
import { useTranslation } from "@/lib/i18n";

export default function SystemHealthTab({ health, onRefresh, isLoading, error, updatedAt }: { health: AdminSystemHealth | null; onRefresh: () => void; isLoading: boolean; error: boolean; updatedAt: string | null }) {
  const { t } = useTranslation();
  const metric = (value?: number, suffix = "") => typeof value === "number" && Number.isFinite(value) ? `${value.toLocaleString()}${suffix}` : t("admin.notReported");
  return <>
    <div className="admin-status-toolbar"><div className="admin-help" aria-live="polite">{isLoading ? <p role="status">{t(health ? "admin.refreshingStatus" : "admin.loadingStatus")}</p> : updatedAt && <p>{t("admin.lastUpdated", { time: updatedAt })}</p>}</div><button className="admin-button" type="button" onClick={onRefresh} disabled={isLoading} aria-busy={isLoading}>{t("admin.refresh")}</button></div>
    {error && <p role="alert" className="admin-notice admin-error">{t(health ? "admin.staleStatus" : "admin.statusUnavailable")}</p>}
    {health && <>
      <section className="admin-status-section"><h2>{t("admin.database")}</h2><dl className="admin-definition-list">
        <dt>{t("admin.engine")}</dt><dd>{health.database?.engine || t("admin.notReported")}</dd>
        <dt>{t("admin.conversations")}</dt><dd>{metric(health.database?.chat_sessions)}</dd>
        <dt>{t("admin.documents")}</dt><dd>{metric(health.database?.documents)}</dd>
        <dt>{t("admin.messages")}</dt><dd>{metric(health.database?.messages)}</dd>
      </dl></section>
      <section className="admin-status-section"><h2>{t("admin.documentIndex")}</h2><div><dl className="admin-definition-list"><dt>{t("admin.reportedState")}</dt><dd>{health.vector_store?.status || t("admin.notReported")}</dd></dl>
        {health.vector_store?.error && <p role="alert" className="admin-error">{t("admin.indexUnavailable")}</p>}
        <details className="admin-disclosure"><summary>{t("admin.collections")}</summary><div className="admin-disclosure-content">
          {!Array.isArray(health.vector_store?.collections) ? <p className="admin-help">{t("admin.notReported")}</p> : !health.vector_store.collections.length ? <p className="admin-help">{t("admin.noCollections")}</p> : health.vector_store.collections.map((collection) => <div className="admin-collection" key={collection.name}>
            <code>{collection.name}</code><span>{metric(collection.points_count)} {t("admin.indexedPoints")}</span><span className="admin-help">{collection.status || t("admin.notReported")}</span>
          </div>)}
        </div></details>
      </div></section>
      <section className="admin-status-section"><h2>{t("admin.backendDisk")}</h2><dl className="admin-definition-list"><dt>{t("admin.freeSpace")}</dt><dd>{metric(health.disk?.free_gb, " GB")}</dd><dt>{t("admin.usedSpace")}</dt><dd>{metric(health.disk?.used_gb, " GB")}</dd><dt>{t("admin.totalSpace")}</dt><dd>{metric(health.disk?.total_gb, " GB")}</dd></dl></section>
      <p className="admin-help admin-policy-note">{t("admin.statusHelp")}</p>
    </>}
  </>;
}
