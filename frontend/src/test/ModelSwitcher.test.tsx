import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ModelSwitcher } from "@/components/chat/ModelSwitcher";
import { useChatStore } from "@/stores/chatStore";
import { I18nProvider } from "../lib/i18n";

const renderWithI18n = (ui: React.ReactElement) => render(<I18nProvider>{ui}</I18nProvider>);

describe("ModelSwitcher Component", () => {
  const backendUrl = "http://localhost:8000";

  beforeEach(() => {
    vi.restoreAllMocks();
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

  it("renders trigger button displaying the active session's model and provider", () => {
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);

    expect(screen.getByText("DeepSeek API")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek R1")).toBeInTheDocument();
  });

  it("falls back to default model when session model is unset", () => {
    useChatStore.setState({ activeChatId: "session-2" });
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-2" />);

    expect(screen.getByText("Default Gateway")).toBeInTheDocument();
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
  });

  it("opens grouped dropdown and allows selecting another model", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ id: "session-1", model: "claude-3-7-sonnet", profile_id: "anthropic" }),
    } as Response);

    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId="session-1" />);

    // Click trigger to open dropdown
    const triggerBtn = screen.getByRole("button", { name: /DeepSeek R1/i });
    fireEvent.click(triggerBtn);

    // Verify grouped headers and models are displayed
    expect(screen.getByText("Anthropic Claude")).toBeInTheDocument();
    const claudeOption = screen.getByRole("menuitem", { name: /Claude 3.7 Sonnet/i });
    expect(claudeOption).toBeInTheDocument();

    // Select Claude 3.7 Sonnet
    fireEvent.click(claudeOption);

    // Verify store was optimistically updated
    const session = useChatStore.getState().sessions.find((s) => s.id === "session-1");
    expect(session?.model).toBe("claude-3-7-sonnet");
    expect(session?.profile_id).toBe("anthropic");

    // Verify PATCH request fired to backend
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

  it("updates pendingNewChatModel when switching model on a new unsaved chat", () => {
    useChatStore.setState({ activeChatId: null });
    renderWithI18n(<ModelSwitcher backendUrl={backendUrl} activeChatId={null} />);

    const triggerBtn = screen.getByRole("button", { name: /GPT-4o/i });
    fireEvent.click(triggerBtn);

    const deepseekOption = screen.getByRole("menuitem", { name: /DeepSeek R1/i });
    fireEvent.click(deepseekOption);

    expect(useChatStore.getState().pendingNewChatModel).toEqual({
      model: "deepseek-reasoner",
      profile_id: "deepseek",
    });
  });
});
