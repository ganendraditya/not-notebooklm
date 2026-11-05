import { beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { ChatInputBox } from "../components/chat/ChatInput";
import { I18nProvider } from "../lib/i18n";
import { useChatStore } from "@/stores/chatStore";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("ChatInput Component", () => {
  beforeEach(() => {
    useChatStore.setState({ availableModels: [{ id: "fixture", name: "Fixture", profile_id: "provider", profile_name: "Provider" }], modelCatalogStatus: "ready" });
  });

  it.each(["loading", "error", "ready"] as const)("preserves a new prompt without models when the catalog is %s", (status) => {
    useChatStore.setState({ availableModels: [], modelCatalogStatus: status });
    const onSubmit = vi.fn();
    renderWithI18n(<ChatInputBox onSubmit={onSubmit} backendUrl="http://fixture.invalid" />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Keep this research draft" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("Keep this research draft");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "System configuration" })).toHaveAttribute("target", "_blank");
  });

  it("preserves legacy unbound saved-chat behavior with an empty catalog", () => {
    useChatStore.setState({ availableModels: [], modelCatalogStatus: "ready" });
    const onSubmit = vi.fn();
    renderWithI18n(<ChatInputBox chatId="legacy-saved-chat" onSubmit={onSubmit} backendUrl="http://fixture.invalid" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Continue saved chat" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSubmit).toHaveBeenCalledWith("Continue saved chat", undefined);
  });

  it("renders input box and triggers onSubmit with trimmed text", () => {
    const onSubmit = vi.fn();

    renderWithI18n(
      <ChatInputBox
        onSubmit={onSubmit}
        isLoading={false}
        backendUrl="http://localhost:8000"
      />
    );

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Tell me about quantum computing" } });

    const sendBtn = screen.getByRole("button", { name: /send/i });
    fireEvent.click(sendBtn);

    expect(onSubmit).toHaveBeenCalledWith("Tell me about quantum computing", undefined);
  });

  it("disables send button when input is empty and no attachments", () => {
    const onSubmit = vi.fn();

    renderWithI18n(
      <ChatInputBox
        onSubmit={onSubmit}
        isLoading={false}
        backendUrl="http://localhost:8000"
      />
    );

    const sendBtn = screen.getByRole("button", { name: /send/i });
    expect(sendBtn).toBeDisabled();
  });

  it("displays targeted source badge and allows clearing it", () => {
    const onClearTargetedSource = vi.fn();
    const targetedSource = {
      id: 1,
      filename: "Attention.pdf",
      title: "Attention Is All You Need",
      created_at: new Date().toISOString()
    };

    renderWithI18n(
      <ChatInputBox
        onSubmit={vi.fn()}
        isLoading={false}
        backendUrl="http://localhost:8000"
        targetedSource={targetedSource}
        onClearTargetedSource={onClearTargetedSource}
      />
    );

    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();

    const clearBtn = screen.getByRole("button", { name: /clear focused document/i });
    fireEvent.click(clearBtn);
    expect(onClearTargetedSource).toHaveBeenCalled();
  });

  it("shows stop generation button when isLoading is true", () => {
    const onStopGeneration = vi.fn();

    renderWithI18n(
      <ChatInputBox
        onSubmit={vi.fn()}
        isLoading={true}
        onStopGeneration={onStopGeneration}
        backendUrl="http://localhost:8000"
      />
    );

    const stopBtn = screen.getByRole("button", { name: /stop generation/i });
    expect(stopBtn).toBeInTheDocument();
    fireEvent.click(stopBtn);
    expect(onStopGeneration).toHaveBeenCalled();
  });
});
