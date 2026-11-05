import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import LLMTab from "@/app/admin/components/LLMTab";
import { I18nProvider } from "@/lib/i18n";
import { adminConfig, installAdminDialogs, serveAdmin } from "./admin-fixtures";

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); installAdminDialogs(); });
afterEach(() => vi.unstubAllGlobals());

function renderModels(config = structuredClone(adminConfig)) {
  const api = serveAdmin(config);
  render(<I18nProvider><LLMTab config={config.llm} backendUrl="http://localhost:8000" onSaved={vi.fn()} /></I18nProvider>);
  return api;
}

describe("Provider-first configuration", () => {
  it("leads with providers, removes the answer-default control, and keeps supporting settings secondary", () => {
    const { fetcher } = renderModels();
    expect(screen.getByRole("heading", { name: "Your providers" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fixture connection" })).toHaveAccessibleDescription(/OpenAI-compatible.*https:\/\/fixture.invalid/);
    expect(screen.queryByRole("heading", { name: "Main answer model" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add model" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit connection" })).not.toBeInTheDocument();
    expect(screen.queryByText("Model defaults")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Main answer: model ID")).not.toBeInTheDocument();
    const defaults = screen.getByText("Quick tasks, backup & sampling").closest("details");
    expect(defaults).not.toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Save routing" }).closest("details")).toBe(defaults);
    expect(screen.getByRole("button", { name: "Fixture connection" }).compareDocumentPosition(defaults!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("opens only the selected provider and adds a model to that exact connection without changing routing", async () => {
    const config = structuredClone(adminConfig);
    config.llm.profiles.push({ ...config.llm.profiles[0], id: "other", name: "Other provider", base_url: "https://other.invalid/v1", models: [{ id: "answer-model", name: "Other answer", enabled: false }] });
    const { fetcher } = renderModels(config);
    fireEvent.click(screen.getByRole("button", { name: "Other provider" }));
    expect(screen.getByRole("heading", { name: "Other provider" })).toBeInTheDocument();
    expect(screen.getByText("Models sent through Other provider. List changes save immediately.")).toBeInTheDocument();
    expect(screen.queryByText("Answer model", { selector: "span" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add provider" })).not.toBeInTheDocument();
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Add model" }));
    expect(screen.getByRole("heading", { name: "Add model to Other provider" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Model identifier"), { target: { value: "other-only-model" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add model" }).at(-1)!);
    await screen.findByRole("checkbox", { name: "Show other-only-model in model picker" });
    const payload = JSON.parse(String(fetcher.mock.calls[0][1]?.body));
    expect(payload).toMatchObject({ primary_profile_id: "default", fast_profile_id: "default", fallback_profile_id: "default", model: "answer-model", fast_model: "quick-model" });
    expect(payload.profiles[0].models).toEqual(config.llm.profiles[0].models);
    expect(payload.profiles[1].models).toContainEqual({ id: "other-only-model", name: "other-only-model", enabled: true });
    expect(payload.profiles[1].base_url).toBe("https://other.invalid/v1");
    expect(String(fetcher.mock.calls[0][1]?.body)).not.toContain("api_key");
    await waitFor(() => expect(screen.getByRole("button", { name: "All providers" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "All providers" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Other provider" })).toHaveFocus());
    fireEvent.click(screen.getByRole("button", { name: "Fixture connection" }));
    expect(screen.queryByRole("checkbox", { name: "Show other-only-model in model picker" })).not.toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("guards an unsaved model when returning to the list and preserves it when staying", async () => {
    const { fetcher } = renderModels();
    fireEvent.click(screen.getByRole("button", { name: "Fixture connection" }));
    fireEvent.click(screen.getByRole("button", { name: "Add model" }));
    fireEvent.change(screen.getByLabelText("Model identifier"), { target: { value: "unsaved-model" } });
    fireEvent.click(screen.getByRole("button", { name: "All providers" }));
    expect(screen.getByRole("dialog", { name: "Discard unsaved changes?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stay here" }));
    expect(screen.getByLabelText("Model identifier")).toHaveValue("unsaved-model");
    fireEvent.click(screen.getByRole("button", { name: "All providers" }));
    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Fixture connection" })).toHaveFocus());
    fireEvent.click(screen.getByRole("button", { name: "Fixture connection" }));
    fireEvent.click(screen.getByRole("button", { name: "Add model" }));
    expect(screen.getByLabelText("Model identifier")).toHaveValue("");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("keeps an existing personal provider name and opens a separate blank provider form", () => {
    const config = structuredClone(adminConfig);
    config.llm.profiles[0].name = "9Router Local";
    const { fetcher } = renderModels(config);
    fireEvent.click(screen.getByRole("button", { name: "9Router Local" }));
    expect(screen.getByRole("heading", { name: "9Router Local" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "All providers" }));
    fireEvent.click(screen.getByRole("button", { name: "Add provider" }));
    expect(screen.getByLabelText("Provider name")).toHaveValue("");
    expect(screen.getByLabelText("Base URL")).toHaveValue("");
    expect(screen.getByLabelText("API key")).toHaveValue("");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("searches labels, IDs, and connections and stages the exact model/connection pair until Save", async () => {
    const config = structuredClone(adminConfig);
    config.llm.profiles.push({ ...config.llm.profiles[0], id: "other", name: "Other provider", models: [{ id: "answer-model", name: "Other answer", enabled: false }] });
    const { fetcher } = renderModels(config);
    fireEvent.click(screen.getByText("Quick tasks, backup & sampling"));
    fireEvent.click(screen.getByRole("button", { name: "Choose Quick tasks model: quick-model" }));
    const picker = await screen.findByRole("dialog");
    const search = within(picker).getByRole("searchbox", { name: "Search models or connections" });
    for (const query of ["OTHER ANSWER", "answer-model", "Other provider"]) {
      fireEvent.change(search, { target: { value: query } });
      expect(within(picker).getByRole("button", { name: "Other answer answer-model" })).toBeInTheDocument();
    }
    fireEvent.click(within(picker).getByRole("button", { name: "Other answer answer-model" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Quick tasks: connection")).toHaveValue("other");
    expect(screen.getByLabelText("Quick tasks: model ID")).toHaveValue("answer-model");
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Save routing" }));
    await screen.findByText("Configuration saved to local .env.");
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toMatchObject({ primary_profile_id: "default", model: "answer-model", fast_profile_id: "other", fast_model: "answer-model" });
  });

  it("offers manual entry on an empty search without replacing an unknown saved ID", async () => {
    const config = structuredClone(adminConfig);
    const unknownId = `custom/${"unregistered-model-".repeat(10)}`;
    config.llm.fast_model = unknownId;
    const { fetcher } = renderModels(config);
    fireEvent.click(screen.getByText("Quick tasks, backup & sampling"));
    fireEvent.click(screen.getByRole("button", { name: `Choose Quick tasks model: ${unknownId}` }));
    const picker = await screen.findByRole("dialog");
    fireEvent.change(within(picker).getByRole("searchbox"), { target: { value: "no-such-model" } });
    expect(within(picker).getByRole("status")).toHaveTextContent("No registered models match");
    fireEvent.click(within(picker).getByRole("button", { name: "Enter a model ID manually" }));
    await waitFor(() => expect(screen.getByLabelText("Quick tasks: model ID")).toHaveFocus());
    expect(screen.getByLabelText("Quick tasks: model ID")).toHaveValue(unknownId);
    expect(screen.getByLabelText("Quick tasks: model ID").closest("details")).toHaveAttribute("open");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("starts an unconfigured frontend with Add provider instead of a disabled routing form", () => {
    const config = structuredClone(adminConfig);
    config.llm.base_url = ""; config.llm.profiles = [];
    renderModels(config);
    expect(screen.getByText("No providers configured")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add provider" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Save routing" })).not.toBeInTheDocument();
  });

  it("opens provider-neutral and applies optional presets without overwriting a personal connection name", () => {
    const { fetcher } = renderModels();
    fireEvent.click(screen.getByRole("button", { name: "Add provider" }));
    const preset = screen.getByLabelText("Provider preset (optional)");
    expect(preset).toHaveValue("");
    expect(within(preset).queryByRole("option", { name: "9Router" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Provider name")).toHaveValue("");
    expect(screen.getByLabelText("Base URL")).toHaveValue("");
    fireEvent.change(preset, { target: { value: "OpenAI" } });
    expect(screen.getByLabelText("Base URL")).toHaveValue("https://api.openai.com/v1");
    expect(screen.getByLabelText("Provider name")).toHaveValue("OpenAI");
    fireEvent.change(preset, { target: { value: "Anthropic" } });
    expect(screen.getByLabelText("Provider name")).toHaveValue("Anthropic");
    expect(screen.getByLabelText("Protocol")).toHaveValue("anthropic");
    fireEvent.change(screen.getByLabelText("Provider name"), { target: { value: "My research provider" } });
    fireEvent.change(preset, { target: { value: "Ollama" } });
    expect(screen.getByLabelText("Provider name")).toHaveValue("My research provider");
    expect(screen.getByLabelText("Base URL")).toHaveValue("http://localhost:11434/v1");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("saves without running an optional model test or changing existing routing", async () => {
    const { fetcher } = renderModels();
    fireEvent.click(screen.getByRole("button", { name: "Add provider" }));
    const testDisclosure = screen.getByText("Test connection (optional)").closest("details");
    expect(testDisclosure).not.toHaveAttribute("open");
    fireEvent.change(screen.getByLabelText("Provider name"), { target: { value: "Custom connection" } });
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "https://custom.invalid/v1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save connection" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(String(fetcher.mock.calls[0][0])).toMatch(/config\/llm$/);
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toMatchObject({ model: "answer-model", primary_profile_id: "default" });
  });

  it("returns focus to the stable action trigger after dismissing model removal", async () => {
    renderModels();
    fireEvent.click(screen.getByRole("button", { name: "Fixture connection" }));
    const trigger = screen.getByRole("button", { name: "Actions for answer-model" });
    fireEvent.click(trigger);
    fireEvent.click(await screen.findByRole("menuitem", { name: "Remove model answer-model" }));
    const dialog = screen.getByRole("dialog", { name: "Remove registered model?" });
    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
