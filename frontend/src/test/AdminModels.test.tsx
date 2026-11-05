import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import LLMTab from "@/app/admin/components/LLMTab";
import { I18nProvider } from "@/lib/i18n";
import { adminConfig, installAdminDialogs, jsonResponse, serveAdmin } from "./admin-fixtures";

beforeEach(() => {
  vi.restoreAllMocks(); localStorage.clear();
  installAdminDialogs();
});
afterEach(() => vi.unstubAllGlobals());
const renderModels = (config = adminConfig.llm) => render(<I18nProvider><LLMTab config={config} backendUrl="http://localhost:8000" onSaved={vi.fn()} /></I18nProvider>);
const openProvider = () => fireEvent.click(screen.getByRole("button", { name: "Fixture connection" }));
const openDefaults = () => {
  fireEvent.click(screen.getByText("Quick tasks, backup & sampling"));
  fireEvent.click(screen.getAllByText("Enter a model ID manually")[0]);
};

describe("Models drafts, BYOK and isolated configuration writes", () => {
  it("limits a newly entered display name to 64 characters without limiting the model identifier", async () => {
    const { fetcher } = serveAdmin(); renderModels(); openProvider();
    fireEvent.click(screen.getByRole("button", { name: "Add model" }));
    const name = screen.getByLabelText("Display name (optional)");
    const identifier = screen.getByLabelText("Model identifier");
    expect(name).toHaveAttribute("maxlength", "64");
    expect(identifier).not.toHaveAttribute("maxlength");
    const longId = `provider/${"technical-model-id-".repeat(8)}`;
    fireEvent.change(identifier, { target: { value: longId } });
    fireEvent.change(name, { target: { value: "A".repeat(64) } });
    expect(name).toHaveAccessibleDescription(/64\/64/);
    fireEvent.click(screen.getAllByRole("button", { name: "Add model" }).at(-1)!);
    await screen.findByRole("checkbox", { name: `Show ${longId} in model picker` });
    const saved = JSON.parse(String(fetcher.mock.calls[0][1]?.body)).profiles[0].models.at(-1);
    expect(saved).toMatchObject({ id: longId, name: "A".repeat(64) });
  });

  it("blocks an overlong label even if a programmatic input change bypasses native maxlength", () => {
    const { fetcher } = serveAdmin(); renderModels(); openProvider();
    fireEvent.click(screen.getByRole("button", { name: "Add model" }));
    fireEvent.change(screen.getByLabelText("Model identifier"), { target: { value: "new-model" } });
    fireEvent.change(screen.getByLabelText("Display name (optional)"), { target: { value: "A".repeat(65) } });
    expect(screen.getByRole("alert")).toHaveTextContent("64 characters or fewer");
    expect(screen.getAllByRole("button", { name: "Add model" }).at(-1)).toBeDisabled();
    fireEvent.submit(screen.getByLabelText("Display name (optional)").closest("form")!);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("preserves legacy long labels on visibility saves and never silently shortens an edit", async () => {
    const config = structuredClone(adminConfig);
    const legacyName = "Legacy label ".repeat(8);
    config.llm.profiles[0].models![0].name = legacyName;
    const { fetcher } = serveAdmin(config); renderModels(config.llm); openProvider();
    fireEvent.click(screen.getByRole("checkbox", { name: "Show answer-model in model picker" }));
    await waitFor(() => expect(screen.getByRole("checkbox")).not.toBeChecked());
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body)).profiles[0].models[0].name).toBe(legacyName);
    fireEvent.click(screen.getByRole("button", { name: "Actions for answer-model" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Edit label for answer-model" }));
    expect(screen.getByLabelText("Display name (optional)")).toHaveValue(legacyName);
    expect(screen.getByRole("button", { name: "Save label" })).toBeDisabled();
    expect(fetcher).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Display name (optional)"), { target: { value: "Shorter label" } });
    fireEvent.click(screen.getByRole("button", { name: "Save label" }));
    await screen.findByText("Shorter label", { selector: "span" });
    expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body)).profiles[0].models[0].name).toBe("Shorter label");
  });

  it("uses the full technical identifier when the optional display name is left empty", async () => {
    const { fetcher } = serveAdmin(); renderModels(); openProvider();
    const identifier = `provider/${"model-id-".repeat(12)}`;
    fireEvent.click(screen.getByRole("button", { name: "Add model" }));
    fireEvent.change(screen.getByLabelText("Model identifier"), { target: { value: identifier } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add model" }).at(-1)!);
    await screen.findByRole("checkbox", { name: `Show ${identifier} in model picker` });
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body)).profiles[0].models.at(-1)).toMatchObject({ id: identifier, name: identifier });
  });

  it("opens a neutral connection form and only tests explicitly, before saving", async () => {
    const { fetcher } = serveAdmin(); renderModels();
    fireEvent.click(screen.getByRole("button", { name: "Add provider" }));
    const dialog = screen.getByRole("dialog", { name: "Add provider" });
    expect(within(dialog).getByLabelText("Provider name")).toHaveValue("");
    expect(within(dialog).getByLabelText("Base URL")).toHaveValue("");
    fireEvent.change(within(dialog).getByLabelText("Provider name"), { target: { value: "New connection" } });
    fireEvent.change(within(dialog).getByLabelText("Base URL"), { target: { value: "https://new.invalid/v1" } });
    fireEvent.change(within(dialog).getByLabelText("API key"), { target: { value: "fixture-key" } });
    fireEvent.click(within(dialog).getByText("Test connection (optional)"));
    fireEvent.change(within(dialog).getByLabelText("Model ID to test"), { target: { value: "test-model" } });
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Test connection" }));
    await screen.findByText("The test request succeeded.");
    expect(fetcher.mock.calls).toHaveLength(1);
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toEqual({ base_url: "https://new.invalid/v1", api_key: "fixture-key", protocol: "openai", model: "test-model" });
    fireEvent.change(within(dialog).getByLabelText("Model ID to test"), { target: { value: "other-model" } });
    expect(screen.queryByText("The test request succeeded.")).not.toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Save connection" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const payload = JSON.parse(String(fetcher.mock.calls[1][1]?.body));
    expect(payload.profiles[1]).toMatchObject({ name: "New connection", api_key: "fixture-key", models: [] });
    expect(payload.model).toBe("answer-model");
    expect(payload).not.toHaveProperty("api_key");
  });

  it("does not reveal or send a stored mask and requires an entered key for a changed destination", async () => {
    const { fetcher } = serveAdmin(); renderModels(); openProvider();
    fireEvent.click(screen.getByRole("button", { name: "Edit connection" }));
    expect(screen.getByLabelText("API key")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Show the newly entered key" })).toBeDisabled();
    fireEvent.click(screen.getByText("Test connection (optional)"));
    fireEvent.change(screen.getByLabelText("Model ID to test"), { target: { value: "answer-model" } });
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await screen.findByText("The test request succeeded.");
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toMatchObject({ profile_id: "default", model: "answer-model" });
    expect(String(fetcher.mock.calls[0][1]?.body)).not.toContain("1234");
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "https://changed.invalid/v1" } });
    expect(screen.getByRole("button", { name: "Test connection" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "new-key" } });
    fireEvent.click(screen.getByRole("button", { name: "Show the newly entered key" }));
    expect(screen.getByLabelText("API key")).toHaveAttribute("type", "text");
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await screen.findByText("The test request succeeded.");
    expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).not.toHaveProperty("profile_id");
  });

  it("ignores a late test response after the tested inputs have changed", async () => {
    const { fetcher } = serveAdmin(); let resolve!: (response: Response) => void;
    fetcher.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    renderModels(); openProvider(); fireEvent.click(screen.getByRole("button", { name: "Edit connection" }));
    fireEvent.click(screen.getByText("Test connection (optional)"));
    fireEvent.change(screen.getByLabelText("Model ID to test"), { target: { value: "answer-model" } });
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText("Model ID to test"), { target: { value: "changed" } });
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true);
    await act(async () => resolve(jsonResponse({ success: true, message: "Old result" })));
    expect(screen.queryByText("Old result")).not.toBeInTheDocument();
  });

  it("guards connection close including Escape cancellation and clears credentials on discard", () => {
    serveAdmin(); renderModels(); fireEvent.click(screen.getByRole("button", { name: "Add provider" }));
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "transient-key" } });
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));
    expect(screen.getByRole("dialog", { name: "Discard unsaved changes?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stay here" }));
    expect(screen.getByLabelText("API key")).toHaveValue("transient-key");
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    fireEvent.click(screen.getByRole("button", { name: "Add provider" }));
    expect(screen.getByLabelText("API key")).toHaveValue("");
  });

  it("does not test unsupported native aliases while allowing them to be saved", () => {
    serveAdmin(); renderModels(); openProvider(); fireEvent.click(screen.getByRole("button", { name: "Edit connection" }));
    fireEvent.change(screen.getByLabelText("Protocol"), { target: { value: "anthropic" } });
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "fixture-key" } });
    fireEvent.click(screen.getByText("Test connection (optional)"));
    fireEvent.change(screen.getByLabelText("Model ID to test"), { target: { value: "custom-alias" } });
    expect(screen.getByRole("button", { name: "Test connection" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save connection" })).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Model ID to test"), { target: { value: "claude-fixture" } });
    expect(screen.getByRole("button", { name: "Test connection" })).toBeEnabled();
  });

  it("isolates model visibility, label, and registration writes from unrelated routing drafts", async () => {
    const { fetcher } = serveAdmin(); renderModels();
    openDefaults();
    fireEvent.change(screen.getByLabelText("Quick tasks: model ID"), { target: { value: "unsaved-routing" } });
    openProvider();
    fireEvent.click(screen.getByRole("checkbox", { name: "Show answer-model in model picker" }));
    await waitFor(() => expect(screen.getByRole("checkbox")).not.toBeChecked());
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body)).model).toBe("answer-model");
    expect(screen.getByLabelText("Quick tasks: model ID")).toHaveValue("unsaved-routing");
    expect(String(fetcher.mock.calls[0][1]?.body)).not.toContain("api_key");
    fireEvent.click(screen.getByRole("button", { name: "Actions for answer-model" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Edit label for answer-model" }));
    fireEvent.change(screen.getByLabelText("Display name (optional)"), { target: { value: "Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save label" }));
    await screen.findByText("Renamed", { selector: "span" });
    fireEvent.click(screen.getByRole("button", { name: "Add model" }));
    fireEvent.change(screen.getByLabelText("Model identifier"), { target: { value: "another-model" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add model" }).at(-1)!);
    await screen.findByRole("checkbox", { name: "Show another-model in model picker" });
    expect(fetcher.mock.calls.every(([, init]) => JSON.parse(String(init?.body)).model === "answer-model" && JSON.parse(String(init?.body)).fast_model === "quick-model")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "All providers" }));
    fireEvent.click(screen.getByRole("button", { name: "Save routing" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Save routing" })).toBeDisabled());
    expect(JSON.parse(String(fetcher.mock.calls.at(-1)?.[1]?.body)).profiles[0].models).toHaveLength(2);
  });

  it("retains committed visibility and routing drafts after failure and reconciles before retry", async () => {
    const { fetcher } = serveAdmin(); fetcher.mockRejectedValueOnce(new TypeError("Offline")); renderModels();
    openDefaults();
    fireEvent.change(screen.getByLabelText("Quick tasks: model ID"), { target: { value: "unsaved-routing" } });
    openProvider();
    fireEvent.click(screen.getByRole("checkbox"));
    await screen.findByRole("alert");
    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByLabelText("Quick tasks: model ID")).toHaveValue("unsaved-routing");
    fireEvent.click(screen.getByRole("button", { name: "All providers" }));
    expect(screen.getByRole("button", { name: "Save routing" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Reload saved values" }));
    await screen.findByText(/Saved values reloaded/);
    expect(screen.getByRole("button", { name: "Save routing" })).toBeEnabled();
    expect(screen.getByLabelText("Quick tasks: model ID")).toHaveValue("unsaved-routing");
  });

  it("reports runtime persistence and removes a connection only after explicit confirmation", async () => {
    const config = structuredClone(adminConfig); config.persistence = { mode: "runtime", active_provider: "doppler", has_local_env: false };
    config.llm.profiles.push({ ...config.llm.profiles[0], id: "second", name: "Second connection" });
    const { fetcher } = serveAdmin(config); renderModels(config.llm);
    openProvider();
    fireEvent.click(screen.getByRole("button", { name: "Remove provider" }));
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove" }));
    await screen.findByText(/Update your Doppler project/);
    expect(screen.queryByRole("button", { name: "Fixture connection" })).not.toBeInTheDocument();
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toMatchObject({ primary_profile_id: "second", fast_profile_id: "second", fallback_profile_id: "second", model: "answer-model" });
  });

  it("reuses the same new-connection identity after a write applied but its response was lost", async () => {
    const { fetcher } = serveAdmin();
    const saveThenLoseResponse = fetcher.getMockImplementation()!;
    fetcher.mockImplementationOnce(async (...args) => { await saveThenLoseResponse(...args); throw new TypeError("Response lost"); });
    renderModels(); fireEvent.click(screen.getByRole("button", { name: "Add provider" }));
    fireEvent.change(screen.getByLabelText("Provider name"), { target: { value: "Recoverable connection" } });
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "https://recover.invalid/v1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save connection" }));
    await within(screen.getByRole("dialog")).findByRole("alert");
    expect(screen.getByLabelText("Provider name")).toHaveValue("Recoverable connection");
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Reload saved values" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Save connection" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Save connection" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const first = JSON.parse(String(fetcher.mock.calls[0][1]?.body));
    const last = JSON.parse(String(fetcher.mock.calls.at(-1)?.[1]?.body));
    expect(last.profiles).toHaveLength(2);
    expect(last.profiles[1].id).toBe(first.profiles[1].id);
  });

  it("allows closing a failed model-removal dialog to reconcile instead of trapping the user", async () => {
    const { fetcher } = serveAdmin(); renderModels(); openProvider();
    fireEvent.click(screen.getByRole("button", { name: "Actions for answer-model" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Remove model answer-model" }));
    fetcher.mockRejectedValueOnce(new TypeError("Offline"));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove" }));
    await screen.findByText(/This operation could not be confirmed/);
    const cancel = within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" });
    expect(cancel).toBeEnabled(); fireEvent.click(cancel);
    fireEvent.click(screen.getByRole("button", { name: "Reload saved values" }));
    await screen.findByText(/Saved values reloaded/);
    expect(screen.getByRole("checkbox")).toBeChecked();
  });
});
