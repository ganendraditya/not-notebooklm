import { act, waitFor } from "@testing-library/react";
import { hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider, registerLoadedLocale, setGlobalLanguage, useTranslation } from "@/lib/i18n/I18nContext";
import translations from "@/lib/i18n/locales/id.json";

let root: Root | undefined;
let container: HTMLDivElement | undefined;
function Heading() {
  const { t } = useTranslation();
  return <h1>{t("admin.title")}</h1>;
}

afterEach(async () => {
  await act(async () => root?.unmount()); root = undefined;
  container?.remove(); localStorage.clear(); setGlobalLanguage("en");
});

describe("System configuration translated hydration", () => {
  it("hydrates English server text before applying a cached Indonesian browser preference", async () => {
    localStorage.setItem("system_language", "id");
    registerLoadedLocale("id", translations);
    setGlobalLanguage("en");
    const html = renderToString(<I18nProvider><Heading /></I18nProvider>);
    expect(html).toContain("System configuration");
    setGlobalLanguage("id");
    container = document.createElement("div"); container.innerHTML = html; document.body.append(container);
    const onRecoverableError = vi.fn();
    await act(async () => { root = hydrateRoot(container!, <I18nProvider><Heading /></I18nProvider>, { onRecoverableError }); });
    await waitFor(() => expect(container).toHaveTextContent("Konfigurasi sistem"));
    expect(onRecoverableError).not.toHaveBeenCalled();
  });
});
