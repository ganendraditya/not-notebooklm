"use client";

import { useState } from "react";
import type { AdminConfig } from "@/types/admin";
import { saveAdminSection } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n";
import { FormActions, SecretField, TestFeedback, useDraftGuard, useExplicitTest, usePersistenceFeedback, type Feedback } from "./AdminForms";

const storageDraft = (config: AdminConfig["storage"]) => ({
  storage_type: config.storage_type,
  s3_endpoint: config.s3_endpoint,
  s3_bucket: config.s3_bucket,
  s3_region: config.s3_region,
  s3_access_key: "",
  s3_secret_key: "",
});

export default function StorageTab({ config, backendUrl, onSaved }: { config: AdminConfig["storage"]; backendUrl: string; onSaved: () => void }) {
  const { t } = useTranslation();
  const describePersistence = usePersistenceFeedback();
  const [saved, setSaved] = useState(config);
  const [draft, setDraft] = useState(() => storageDraft(config));
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const test = useExplicitTest(backendUrl, "storage");
  const dirty = JSON.stringify(draft) !== JSON.stringify(storageDraft(saved));
  useDraftGuard(dirty, busy || test.pending);
  const update = <K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) => { test.invalidate(); setFeedback(null); setDraft({ ...draft, [key]: value }); };
  const body = () => ({ ...draft, s3_access_key: draft.s3_access_key.trim() || undefined, s3_secret_key: draft.s3_secret_key.trim() || undefined });
  return <form className="admin-form-panel" aria-label={t("admin.storageLocation")} onSubmit={async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setFeedback(null);
    try {
      const result = await saveAdminSection(backendUrl, "storage", body());
      setSaved(result.config); setDraft(storageDraft(result.config)); test.invalidate();
      setFeedback({ text: describePersistence(result.persistence) }); onSaved();
    } catch { setFeedback({ text: t("admin.saveUnconfirmed"), error: true }); }
    finally { setBusy(false); }
  }}>
    <div className="admin-section-heading"><div><h2>{t("admin.storageLocation")}</h2><p className="admin-help">{t("admin.storageLocationHelp")}</p></div></div>
      <fieldset disabled={busy}>
        <div className="admin-field admin-service-choice">
          <label htmlFor="storage-type">{t("admin.storageType")}</label>
          <select id="storage-type" value={draft.storage_type} onChange={(event) => update("storage_type", event.target.value as "local" | "s3")}>
            <option value="local">{t("admin.localStorage")}</option><option value="s3">{t("admin.s3Storage")}</option>
          </select>
        </div>
        {draft.storage_type === "s3" ? <>
          <div className="admin-grid admin-field-group">
            <div className="admin-field admin-wide"><label htmlFor="storage-endpoint">{t("admin.storageEndpoint")}</label><input id="storage-endpoint" type="url" required value={draft.s3_endpoint} onChange={(event) => update("s3_endpoint", event.target.value)} /></div>
            <div className="admin-field"><label htmlFor="storage-bucket">{t("admin.bucket")}</label><input id="storage-bucket" required value={draft.s3_bucket} onChange={(event) => update("s3_bucket", event.target.value)} /></div>
            <div className="admin-field"><label htmlFor="storage-region">{t("admin.region")}</label><input id="storage-region" value={draft.s3_region} onChange={(event) => update("s3_region", event.target.value)} /></div>
          </div>
          <div className="admin-grid admin-field-group">
            <SecretField id="storage-access-key" label={t("admin.accessKey")} value={draft.s3_access_key} onChange={(value) => update("s3_access_key", value)} configured={!!saved.s3_access_key_masked} />
            <SecretField id="storage-secret-key" label={t("admin.secretKey")} value={draft.s3_secret_key} onChange={(value) => update("s3_secret_key", value)} configured={saved.has_s3_secret} />
          </div>
          <details className="admin-disclosure admin-test-disclosure"><summary>{t("admin.optionalBucketTest")}</summary><div className="admin-disclosure-content">
            <p className="admin-help">{t("admin.bucketTestHelp")}</p>
            <div className="admin-actions"><button className="admin-button" type="button" disabled={test.pending || !draft.s3_endpoint || !draft.s3_bucket} onClick={() => test.run(body())}>{t("admin.testBucket")}</button></div>
            <TestFeedback result={test.result} pending={test.pending} />
          </div></details>
        </> : <p className="admin-help admin-field-note">{t("admin.backendLocalStorage")}</p>}
        <p className="admin-notice admin-warning">{t("admin.storageNoMigration")}</p>
      </fieldset>
      <FormActions dirty={dirty} busy={busy} pending={test.pending} onCancel={() => { setDraft(storageDraft(saved)); test.invalidate(); setFeedback(null); }} saveLabel={t("admin.saveStorage")} feedback={feedback} />
  </form>;
}
