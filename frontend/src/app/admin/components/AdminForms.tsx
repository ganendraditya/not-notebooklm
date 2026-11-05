"use client";

import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import type { AdminPersistence, TestResult } from "@/types/admin";
import { useTranslation } from "@/lib/i18n";
import { SECRET_PROVIDER_LABELS } from "@/lib/admin-persistence";
import { X } from "lucide-react";
import type { ConfigRecovery } from "./useConfigRecovery";

export interface DraftState { dirty: boolean; busy: boolean }
export const AdminDraftContext = createContext<(id: string, state: DraftState | null) => void>(() => {});

export function useDraftGuard(dirty: boolean, busy = false) {
  const id = useId();
  const register = useContext(AdminDraftContext);
  useEffect(() => { register(id, { dirty, busy }); }, [id, register, dirty, busy]);
  useEffect(() => () => register(id, null), [id, register]);
}

export interface Feedback { text: string; error?: boolean }

export function usePersistenceFeedback() {
  const { t } = useTranslation();
  return (persistence?: AdminPersistence) => {
    if (!persistence) return t("admin.persistenceUnconfirmed");
    return persistence.mode === "local_env"
      ? t("admin.savedLocal")
      : t("admin.savedRuntime", { provider: SECRET_PROVIDER_LABELS[persistence.active_provider] });
  };
}

export function FeedbackMessage({ feedback }: { feedback: Feedback | null }) {
  return <div className="admin-feedback-space" aria-live="polite">
    {feedback && <p className={`admin-feedback${feedback.error ? " admin-error" : ""}`} role={feedback.error ? "alert" : "status"}>{feedback.text}</p>}
  </div>;
}

export function TestFeedback({ result, pending }: { result: TestResult | null; pending?: boolean }) {
  const { t } = useTranslation();
  return <div className="admin-test-feedback" aria-live="polite">
    {pending ? <p role="status">{t("admin.testing")}</p> : result && <div role={result.success ? "status" : "alert"}>
      <strong>{t(result.success ? "admin.testSucceeded" : "admin.testNotConfirmed")}</strong>
      <p className="admin-help">{result.message}</p>
    </div>}
  </div>;
}

export function SectionRecovery({ recovery }: { recovery: ConfigRecovery }) {
  const { t } = useTranslation();
  if (!recovery.uncertain) return null;
  return <div className="admin-notice">
    <p>{t("admin.sectionReconcileHelp")}</p>
    {recovery.error && <p role="alert" className="admin-error">{t("admin.loadFailed")}</p>}
    <button className="admin-button" type="button" disabled={recovery.reloading} onClick={recovery.reload}>{t("admin.reloadSaved")}</button>
  </div>;
}

export function FormActions({ dirty, busy, pending = false, saveDisabled = false, cancelDisabled = false, onCancel, saveLabel, feedback }: { dirty: boolean; busy: boolean; pending?: boolean; saveDisabled?: boolean; cancelDisabled?: boolean; onCancel: () => void; saveLabel: string; feedback: Feedback | null }) {
  const { t } = useTranslation();
  return <>
    <div className="admin-form-actions">
      <div className="admin-form-status" aria-live="polite">{feedback ? <p className={`admin-feedback${feedback.error ? " admin-error" : ""}`} role={feedback.error ? "alert" : "status"}>{feedback.text}</p> : dirty && <span className="admin-help">{t("admin.unsaved")}</span>}</div>
      <div className="admin-actions">
        <button type="button" className="admin-button admin-quiet" disabled={!dirty || busy || pending || cancelDisabled} onClick={onCancel}>{t("admin.cancel")}</button>
        <button type="submit" className="admin-button admin-primary" disabled={!dirty || busy || pending || saveDisabled} aria-busy={busy}><span style={{ visibility: busy ? "hidden" : undefined }}>{saveLabel}</span>{busy && <span className="admin-busy-label">{t("admin.saving")}</span>}</button>
      </div>
    </div>
  </>;
}

export function SecretField({ id, label, value, onChange, configured }: { id: string; label: string; value: string; onChange: (value: string) => void; configured?: boolean }) {
  const [visible, setVisible] = useState(false);
  const { t } = useTranslation();
  return <div className="admin-field">
    <label htmlFor={id}>{label}</label>
    <div className="admin-secret">
      <input id={id} type={visible ? "text" : "password"} autoComplete="new-password" spellCheck={false} value={value} onChange={(event) => onChange(event.target.value)} aria-describedby={`${id}-help`} />
      <button className="admin-button" type="button" onClick={() => setVisible(!visible)} aria-label={t(visible ? "admin.hideEnteredKey" : "admin.showEnteredKey")} aria-pressed={visible} disabled={!value}>{t(visible ? "admin.hide" : "admin.show")}</button>
    </div>
    <small id={`${id}-help`}>{t(configured ? "admin.keepSecret" : "admin.secretNotConfigured")}</small>
  </div>;
}

export function AdminDialog({ title, description, children, onClose, busy = false, className = "", returnFocusRef }: { title: string; description?: string; children: ReactNode; onClose: () => void; busy?: boolean; className?: string; returnFocusRef?: RefObject<HTMLElement | null> }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);
  useEffect(() => {
    const node = ref.current;
    const previous = document.activeElement;
    node?.showModal();
    const restoreFocus = () => {
      const target = returnFocusRef?.current || previous;
      if (target instanceof HTMLElement && target.isConnected) target.focus({ preventScroll: true });
    };
    return () => { node?.close(); restoreFocus(); };
  }, [returnFocusRef]);
  const { t } = useTranslation();
  return <dialog ref={ref} className={`admin-control admin-dialog ${className}`} aria-labelledby={titleId} aria-describedby={description ? descriptionId : undefined} onCancel={(event) => { event.preventDefault(); if (!busy) closeRef.current(); }}>
    <div className="admin-dialog-heading">
      <div><h2 id={titleId}>{title}</h2>{description && <p id={descriptionId} className="admin-help">{description}</p>}</div>
      <button className="admin-button admin-icon-button admin-quiet" type="button" onClick={onClose} disabled={busy} aria-label={t("admin.closeDialog")}><X size={18} aria-hidden="true" /></button>
    </div>
    {children}
  </dialog>;
}

export function DiscardDialog({ onDiscard, onStay }: { onDiscard: () => void; onStay: () => void }) {
  const { t } = useTranslation();
  return <AdminDialog title={t("admin.discardTitle")} description={t("admin.discardHelp")} onClose={onStay}>
    <div className="admin-actions admin-dialog-actions">
      <button className="admin-button" type="button" onClick={onStay} autoFocus>{t("admin.stay")}</button>
      <button className="admin-button admin-danger" type="button" onClick={onDiscard}>{t("admin.discard")}</button>
    </div>
  </AdminDialog>;
}

export function useExplicitTest(backendUrl: string, kind: "llm" | "storage" | "embeddings" | "reranker") {
  const [result, setResult] = useState<TestResult | null>(null);
  const [pending, setPending] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const { t } = useTranslation();
  const invalidate = useCallback(() => {
    generation.current += 1;
    controller.current?.abort();
    setPending(false);
    setResult(null);
  }, []);
  useEffect(() => () => { generation.current += 1; controller.current?.abort(); }, []);
  const run = async (payload: object) => {
    invalidate();
    const current = generation.current;
    const abort = new AbortController();
    controller.current = abort;
    setPending(true);
    try {
      const { testAdminConnection } = await import("@/lib/admin-api");
      const data = await testAdminConnection(backendUrl, kind, payload, abort.signal);
      if (current === generation.current) setResult(data);
    } catch {
      if (current === generation.current) setResult({ success: false, message: t("admin.testRequestFailed") });
    } finally {
      if (current === generation.current) setPending(false);
    }
  };
  return { result, pending, run, invalidate };
}
