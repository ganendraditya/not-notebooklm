import React from "react";
import { act, render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ModelSwitcher } from "@/components/chat/ModelSwitcher";
import { useChatStore } from "@/stores/chatStore";
import { I18nProvider } from "../lib/i18n";
import { MODEL_PREFERENCES_KEY, modelKey } from "@/hooks/chat/useModelPreferences";

const renderWithI18n = (ui: React.ReactElement) => render(<I18nProvider>{ui}</I18nProvider>);

describe("ModelSwitcher Component", () => {
  const backendUrl = "http://localhost:8000";

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    useChatStore.setState({
      sessions: [
        {
          id: "session-1",
          title: "Session 1",
          created_at: new Date().toISOString(),
          model: "deepseek-reasoner",
          profile_id: "deepseek",
        },
        {
          id: "session-2",
          title: "Session 2",
          created_at: new Date().toISOString(),
          model: null,
          profile_id: null,
        },
      ],
      activeChatId: "session-1",
      availableModels: [
        {
          id: "gpt-4o",
          name: "GPT-4o",
          profile_id: "default",
          profile_name: "Default Gateway",
          is_default: true,
        },
        {
          id: "deepseek-reasoner",
          name: "DeepSeek R1",
          profile_id: "deepseek",
          profile_name: "DeepSeek API",
          is_default: false,
        },
        {
          id: "claude-3-7-sonnet",
          name: "Claude 3.7 Sonnet",
          profile_id: "anthropic",
          profile_name: "Anthropic Claude",
          is_default: false,
        },
      ],
      pendingNewChatModel: null,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows only the model in the trigger, with provider details in its title", () => {
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);

    const trigger = screen.getByRole("button", { name: "Select model: DeepSeek R1" });
    expect(trigger).toHaveAttribute("title", "DeepSeek API: DeepSeek R1");
    expect(within(trigger).queryByText("DeepSeek API")).not.toBeInTheDocument();
    expect(trigger.querySelector(".lucide-sparkles")).not.toBeInTheDocument();
  });

  it("retains full legacy labels and technical IDs while applying visual width limits", async () => {
    const longName = "Legacy model name ".repeat(8);
    const longId = `provider/${"technical-id-".repeat(10)}`;
    useChatStore.setState({
      sessions: [{ id: "session-1", title: "Session", created_at: "2026-11-04", model: longId, profile_id: "fixture" }],
      availableModels: [{ id: longId, name: longName, profile_id: "fixture", profile_name: "Fixture connection" }],
    });
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    const trigger = screen.getByRole("button", { name: new RegExp(longName.trim()) });
    expect(trigger).toHaveAttribute("title", `Fixture connection: ${longName}`);
    expect(trigger).toHaveClass("w-max", "max-w-full");
    expect(trigger.parentElement).toHaveClass("max-w-[16rem]");
    expect(trigger.querySelector("span")).toHaveClass("truncate");
    fireEvent.click(trigger);
    const option = await screen.findByRole("button", { name: new RegExp(`^Use ${longName.trim()}`) });
    expect(option).toHaveTextContent(longId);
    expect(option.querySelector(".truncate")).toBeNull();
  });

  it("falls back to default model when session model is unset", () => {
    useChatStore.setState({ activeChatId: "session-2" });
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-2" />);

    expect(screen.queryByText("Default Gateway")).not.toBeInTheDocument();
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
  });

  it("opens grouped dropdown and allows selecting another model", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ id: "session-1", model: "claude-3-7-sonnet", profile_id: "anthropic" }),
    } as Response);

    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);

    const triggerBtn = screen.getByRole("button", { name: /DeepSeek R1/i });
    fireEvent.click(triggerBtn);

    const claudeOption = await screen.findByRole("button", { name: /Use Claude 3.7 Sonnet/i });
    expect(screen.getByText("Anthropic Claude")).toBeInTheDocument();
    expect(claudeOption).toBeInTheDocument();

    fireEvent.click(claudeOption);

    const session = useChatStore.getState().sessions.find((s) => s.id === "session-1");
    expect(session?.model).toBe("claude-3-7-sonnet");
    expect(session?.profile_id).toBe("anthropic");

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        `${backendUrl}/chats/session-1`,
        expect.objectContaining({
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: "claude-3-7-sonnet",
            profile_id: "anthropic",
          }),
        })
      );
    });
  });

  it("updates pendingNewChatModel when switching model on a new unsaved chat", async () => {
    useChatStore.setState({ activeChatId: null });
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);

    const triggerBtn = screen.getByRole("button", { name: /GPT-4o/i });
    fireEvent.click(triggerBtn);

    const deepseekOption = await screen.findByRole("button", { name: /Use DeepSeek R1/i });
    fireEvent.click(deepseekOption);

    expect(useChatStore.getState().pendingNewChatModel).toEqual({
      model: "deepseek-reasoner",
      profile_id: "deepseek",
    });
  });

  it.each([
    { language: "en", label: "System configuration", accessibleName: "Open System configuration in a new tab" },
    { language: "id", label: "Konfigurasi sistem", accessibleName: "Buka Konfigurasi sistem di tab baru" },
  ])("opens only System configuration separately in $language", async ({ language, label, accessibleName }) => {
    localStorage.setItem("system_language", language);
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    fireEvent.click(screen.getByRole("button", { name: /DeepSeek R1/i }));
    const dialog = await screen.findByRole("dialog");
    const link = await within(dialog).findByRole("link", { name: accessibleName });
    expect(link).toHaveTextContent(label);
    expect(link).toHaveAttribute("href", "/admin");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(within(dialog).getAllByRole("link")).toEqual([link]);
    expect(within(dialog).queryByRole("button", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("refreshes only availability, retaining the active override and unsaved new-chat selection", async () => {
    const originalSessions = useChatStore.getState().sessions;
    const pending = { model: "pending-model", profile_id: "pending-provider" };
    useChatStore.setState({ pendingNewChatModel: pending });
    const models = [{ id: "fresh-model", profile_id: "fresh-provider", name: "Fresh model", is_default: true }];
    const fetcher = vi.spyOn(global, "fetch").mockResolvedValue({ ok: true, json: async () => ({ workspace_models: models }) } as Response);
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    fireEvent.click(screen.getByRole("button", { name: /DeepSeek R1/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Refresh model list" }));
    await screen.findByText("Model list refreshed. Your conversation selection is unchanged.");
    expect(fetcher).toHaveBeenCalledWith(`${backendUrl}/llm/models`);
    expect(useChatStore.getState().sessions).toEqual(originalSessions);
    expect(useChatStore.getState().pendingNewChatModel).toEqual(pending);
    expect(useChatStore.getState().availableModels).toEqual(models);
  });

  it("keeps the last list and current selection after refresh failure", async () => {
    const models = useChatStore.getState().availableModels;
    vi.spyOn(global, "fetch").mockRejectedValue(new TypeError("Offline"));
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    fireEvent.click(screen.getByRole("button", { name: /DeepSeek R1/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Refresh model list" }));
    await screen.findByText("The model list could not be refreshed. Your current selection is unchanged.");
    expect(useChatStore.getState().availableModels).toEqual(models);
    expect(useChatStore.getState().sessions[0].model).toBe("deepseek-reasoner");
  });

  it.each(["mouse", "touch", "pen"])("does not autofocus search when opened by %s", async (pointerType) => {
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    const trigger = screen.getByRole("button", { name: /Select model: DeepSeek R1/i });
    trigger.focus();
    fireEvent(trigger, Object.assign(new MouseEvent("pointerdown", { bubbles: true }), { pointerType }));
    fireEvent.click(trigger, { detail: 1 });
    const search = await screen.findByRole("searchbox");
    await act(async () => {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    });
    expect(search).not.toHaveFocus();
    expect(trigger).toHaveFocus();
    act(() => search.focus());
    fireEvent.change(search, { target: { value: "sonnet" } });
    expect(screen.getAllByRole("button", { name: /^Use / })).toHaveLength(1);
    expect(screen.getByRole("button", { name: /Use Claude 3.7 Sonnet/i })).toBeInTheDocument();
  });

  it.each(["ArrowDown", "ArrowUp"])("opens with %s, navigates options, and restores focus on Escape", async (key) => {
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    const trigger = screen.getByRole("button", { name: /Select model: DeepSeek R1/i });
    trigger.focus();
    fireEvent.keyDown(trigger, { key });
    const search = await screen.findByRole("searchbox");
    await waitFor(() => expect(search).toHaveFocus());
    expect(search).toHaveClass("outline-none", "caret-app-text");
    fireEvent.keyDown(search, { key: "ArrowDown" });
    const first = screen.getByRole("button", { name: /Use GPT-4o/i });
    expect(first).toHaveFocus();
    expect(first).toHaveClass("focus-visible:outline-2");
    fireEvent.keyDown(first, { key: "ArrowDown" });
    const selected = screen.getByRole("button", { name: /Use DeepSeek R1/i });
    expect(selected).toHaveFocus();
    expect(selected).toHaveAttribute("aria-pressed", "true");
    fireEvent.keyDown(selected, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("dismisses on an outside click without adding a redundant close button", async () => {
    renderWithI18n(<><button type="button">Outside picker</button><ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" /></>);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    const outside = screen.getByRole("button", { name: "Outside picker" });
    fireEvent.mouseDown(outside); fireEvent.mouseUp(outside); fireEvent.click(outside);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("rolls back a failed save and does not record it as recent", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(global, "fetch").mockResolvedValue({ ok: false, statusText: "Unavailable" } as Response);
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Use Claude 3.7 Sonnet/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your previous model is still selected");
    expect(screen.queryByRole("region", { name: "Recent" })).not.toBeInTheDocument();
    expect(useChatStore.getState().sessions[0]).toMatchObject({ model: "deepseek-reasoner", profile_id: "deepseek" });
  });

  it("shows an empty menu without inventing model options", async () => {
    useChatStore.setState({ availableModels: [] });
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Select model" }));
    expect(await screen.findByText("No models configured. Add one in System configuration.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Use / })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open System configuration in a new tab" })).toHaveAttribute("href", "/admin");
  });

  it("searches labels, IDs and providers even when the matching group was collapsed", async () => {
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    const provider = await screen.findByRole("button", { name: "Anthropic Claude" });
    fireEvent.click(provider);
    expect(provider).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: /Use Claude/i })).not.toBeInTheDocument();
    const search = screen.getByRole("searchbox");
    for (const query of ["  SONNET  ", "claude-3-7", "Anthropic"]) {
      fireEvent.change(search, { target: { value: query } });
      expect(screen.getAllByRole("button", { name: /^Use / })).toHaveLength(1);
      expect(screen.getByRole("button", { name: /Use Claude 3.7 Sonnet/i })).toBeInTheDocument();
    }
    fireEvent.change(search, { target: { value: "no-match" } });
    expect(screen.getByRole("status")).toHaveTextContent("No matching models");
    fireEvent.change(search, { target: { value: "" } });
    expect(screen.getByRole("button", { name: "Anthropic Claude" })).toHaveAttribute("aria-expanded", "false");
  });

  it("persists favorites without selecting a model and can remove them after remount", async () => {
    const fetcher = vi.spyOn(global, "fetch");
    const view = renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Favorite GPT-4o/i }));
    expect(useChatStore.getState().sessions[0].model).toBe("deepseek-reasoner");
    expect(fetcher).not.toHaveBeenCalled();
    await waitFor(() => expect(JSON.parse(localStorage.getItem(MODEL_PREFERENCES_KEY)!).favorites).toEqual([modelKey(useChatStore.getState().availableModels[0])]));
    view.unmount();
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    fireEvent.click(within(await screen.findByRole("region", { name: "Favorites" })).getByRole("button", { name: /Favorite GPT-4o/i }));
    expect(screen.queryByRole("region", { name: "Favorites" })).not.toBeInTheDocument();
  });

  it("records and restores unique recent choices in order", async () => {
    const view = renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    await screen.findByRole("dialog");
    for (const name of ["DeepSeek R1", "Claude 3.7 Sonnet", "DeepSeek R1"]) {
      fireEvent.click(screen.getAllByRole("button", { name: new RegExp(`^Use ${name}`) })[0]);
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
      await screen.findByRole("dialog");
    }
    const recent = screen.getByRole("region", { name: "Recent" });
    expect(within(recent).getAllByRole("button", { name: /^Use / }).map((button) => button.getAttribute("aria-label"))).toEqual([
      "Use DeepSeek R1 (DeepSeek API)", "Use Claude 3.7 Sonnet (Anthropic Claude)",
    ]);
    view.unmount();
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    expect(within(await screen.findByRole("region", { name: "Recent" })).getAllByRole("button", { name: /^Use / })).toHaveLength(2);
  });

  it("keeps identical model IDs and provider names separate by provider ID", async () => {
    useChatStore.setState({ availableModels: [
      { id: "same", name: "Model A", profile_id: "a", profile_name: "Gateway", is_default: true },
      { id: "same", name: "Model B", profile_id: "b", profile_name: "Gateway" },
    ] });
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    expect(await screen.findAllByRole("region", { name: "Gateway" })).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Favorite Model B (Gateway)" }));
    expect(within(screen.getByRole("region", { name: "Favorites" })).getByRole("button", { name: "Use Model B (Gateway)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Favorite Model A (Gateway)" })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: "Use Model A (Gateway)" }));
    expect(useChatStore.getState().pendingNewChatModel).toEqual({ model: "same", profile_id: "a" });
  });

  it("ignores malformed stored entries", async () => {
    localStorage.setItem(MODEL_PREFERENCES_KEY, JSON.stringify({ favorites: [null, 2, "missing"], recent: "bad" }));
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    expect(await screen.findAllByRole("button", { name: /^Use / })).toHaveLength(3);
    expect(screen.queryByRole("region", { name: "Favorites" })).not.toBeInTheDocument();
  });

  it("remains usable when browser storage is blocked", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Blocked"); });
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);
    fireEvent.click(screen.getByRole("button", { name: /Select model/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Favorite GPT-4o/i }));
    expect(screen.getByRole("region", { name: "Favorites" })).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /^Use DeepSeek R1/ })[0]);
    expect(useChatStore.getState().pendingNewChatModel?.model).toBe("deepseek-reasoner");
  });
});
