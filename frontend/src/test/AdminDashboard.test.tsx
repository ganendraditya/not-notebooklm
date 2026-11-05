import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import AdminPage from "@/app/admin/page";
import { I18nProvider } from "@/lib/i18n";
import { adminConfig, adminHealth, installAdminDialogs, jsonResponse, serveAdmin } from "./admin-fixtures";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
const renderPage = () => render(<I18nProvider><AdminPage /></I18nProvider>);

beforeEach(() => {
  vi.restoreAllMocks(); push.mockReset(); localStorage.clear();
  installAdminDialogs();
});
afterEach(() => vi.unstubAllGlobals());

describe("System configuration navigation and persistence", () => {
  it("uses five flat destinations and no non-interactive category labels", async () => {
    serveAdmin(); renderPage();
    await screen.findByRole("heading", { name: "Your providers" });
    const nav = screen.getByRole("navigation", { name: "Configuration sections" });
    expect(within(nav).getAllByRole("button")).toHaveLength(5);
    expect(nav.querySelectorAll(":scope > button")).toHaveLength(5);
    expect(within(nav).queryByText("General")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Advanced")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Configuration sections" }).querySelector("optgroup")).toBeNull();
    fireEvent.click(within(nav).getByRole("button", { name: "File storage" }));
    expect(within(nav).getByRole("button", { name: "File storage" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("button", { name: "Models & providers" })).not.toHaveAttribute("aria-current");
    expect(screen.queryByText("No unsaved changes.")).not.toBeInTheDocument();
  });

  it("keeps read-only source information separate from editable-form footers", async () => {
    serveAdmin(); renderPage();
    await screen.findByRole("heading", { name: "Your providers" });
    fireEvent.click(screen.getByRole("button", { name: "Configuration source" }));
    expect(screen.getByText("Read-only. Switching providers requires a backend restart.")).toBeInTheDocument();
    expect(screen.queryByText("Changes save to the backend's local .env file")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Save|Cancel/ })).not.toBeInTheDocument();
    const instructions = screen.getByText("Changing the configuration source").closest("details");
    expect(instructions).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Changing the configuration source"));
    expect(instructions).toHaveAttribute("open");
  });

  it("renders real forms without a static port or preview toolbar and loads status only on demand", async () => {
    const { fetcher } = serveAdmin(); renderPage();
    await screen.findByRole("heading", { name: "Your providers" });
    expect(screen.getByText("System configuration")).toBeInTheDocument();
    expect(screen.queryByLabelText("Main answer: model ID")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fixture connection" })).toBeInTheDocument();
    expect(screen.queryByText(/Port 2027|Preview state|Universal.*Vault/)).not.toBeInTheDocument();
    expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual(["http://localhost:8000/admin/config"]);
    for (const label of ["File storage", "Document search", "Configuration source"]) fireEvent.click(screen.getByRole("button", { name: label }));
    expect(fetcher.mock.calls).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "System status" }));
    await screen.findByText("SQLite WAL");
    expect(fetcher.mock.calls).toHaveLength(2);
  });

  it.each(["doppler", "infisical"] as const)("keeps %s runtime and local-file warnings visible across sections", async (provider) => {
    const config = structuredClone(adminConfig);
    config.persistence = { mode: "runtime", active_provider: provider, has_local_env: true };
    const { fetcher } = serveAdmin(config); renderPage();
    await screen.findByRole("region", { name: "Configuration persistence" });
    for (const label of ["File storage", "Document search", "Configuration source"]) {
      fireEvent.click(screen.getByRole("button", { name: label }));
      expect(screen.getByRole("note", { name: "Local credentials notice" })).toHaveTextContent("missing values may still load from this file");
    }
    expect(screen.getByText("Active provider").nextElementSibling).toHaveTextContent(provider === "doppler" ? "Doppler" : "Infisical");
    expect(screen.getByText("This process only")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Save|Connect|Purge/ })).not.toBeInTheDocument();
    expect(fetcher.mock.calls).toHaveLength(1);
  });

  it("keeps missing persistence unknown and makes no zero-disk privacy claim", async () => {
    const config = structuredClone(adminConfig); delete config.persistence;
    serveAdmin(config); renderPage(); await screen.findByText("Persistence status unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Configuration source" }));
    expect(screen.getAllByText("Not reported")).toHaveLength(3);
    expect(screen.queryByText("Local configuration")).not.toBeInTheDocument();
    expect(screen.queryByText(/zero.disk/i)).not.toBeInTheDocument();
  });

  it("offers Stay or Discard for section navigation and protects browser unload", async () => {
    serveAdmin(); renderPage(); await screen.findByRole("heading", { name: "Your providers" });
    fireEvent.click(screen.getByText("Quick tasks, backup & sampling"));
    fireEvent.click(screen.getAllByText("Enter a model ID manually")[0]);
    fireEvent.change(screen.getByLabelText("Quick tasks: model ID"), { target: { value: "draft-model" } });
    const unload = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "File storage" }));
    fireEvent.click(screen.getByRole("button", { name: "Stay here" }));
    expect(screen.getByLabelText("Quick tasks: model ID")).toHaveValue("draft-model");
    fireEvent.change(screen.getByRole("combobox", { name: "Configuration sections" }), { target: { value: "storage" } });
    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(screen.getByRole("heading", { name: "Storage location" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Models & providers" }));
    expect(screen.getByLabelText("Quick tasks: model ID")).toHaveValue("quick-model");
  });

  it("protects Back to app and Cancel only discards its routing draft", async () => {
    const { fetcher } = serveAdmin(); renderPage(); await screen.findByRole("heading", { name: "Your providers" });
    fireEvent.click(screen.getByText("Quick tasks, backup & sampling"));
    fireEvent.click(screen.getAllByText("Enter a model ID manually")[0]);
    fireEvent.change(screen.getByLabelText("Quick tasks: model ID"), { target: { value: "draft-model" } });
    fireEvent.click(screen.getByRole("link", { name: "Back to app" }));
    expect(push).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Stay here" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByLabelText("Quick tasks: model ID")).toHaveValue("quick-model");
    expect(fetcher.mock.calls).toHaveLength(1);
  });

  it("loads status despite config failure and retains last-known data on a failed refresh", async () => {
    const { fetcher } = serveAdmin();
    fetcher.mockResolvedValueOnce(jsonResponse({}, 503));
    renderPage(); await screen.findByText(/Configuration could not be loaded/);
    fireEvent.click(screen.getByRole("button", { name: "System status" }));
    await screen.findByText("SQLite WAL");
    fetcher.mockRejectedValueOnce(new TypeError("Offline"));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await screen.findByText(/Refresh failed. These are last-known/);
    expect(screen.getByText("SQLite WAL")).toBeInTheDocument();
    fetcher.mockResolvedValueOnce(jsonResponse({ ...adminHealth, vector_store: { status: "error", error: "Unavailable", collections: [] } }));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await screen.findByText(/The document index reported an error/);
    expect(screen.queryByText(/Refresh failed/)).not.toBeInTheDocument();
  });

  it("retries a failed configuration load", async () => {
    const { fetcher } = serveAdmin(); fetcher.mockRejectedValueOnce(new TypeError("Offline"));
    renderPage(); await screen.findByText(/Configuration could not be loaded/);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByRole("heading", { name: "Your providers" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows unavailable and partial status without green health claims", async () => {
    const { fetcher } = serveAdmin(); renderPage(); await screen.findByRole("heading", { name: "Your providers" });
    fetcher.mockRejectedValueOnce(new TypeError("Offline"));
    fireEvent.click(screen.getByRole("button", { name: "System status" }));
    await screen.findByText(/System status could not be loaded/);
    fetcher.mockResolvedValueOnce(jsonResponse({ status: "ok", database: {}, vector_store: {}, disk: {} }));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await screen.findByText("Metadata database");
    expect(screen.getAllByText(/Not reported/).length).toBeGreaterThan(3);
    expect(screen.queryByText("healthy")).not.toBeInTheDocument();
  });
});
