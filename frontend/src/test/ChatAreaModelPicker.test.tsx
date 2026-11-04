import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import ChatArea from "@/components/ChatArea";
import { I18nProvider } from "@/lib/i18n";
import { type ChatMessage, useChatStore } from "@/stores/chatStore";

describe("ChatArea model picker placement", () => {
  beforeEach(() => {
    localStorage.clear();
    useChatStore.setState({
      availableModels: [{ id: "answer-model", name: "Answer model", profile_id: "fixture", profile_name: "Fixture provider", is_default: true }],
      sessions: [], pendingNewChatModel: null,
    });
  });

  it.each([
    { state: "empty chat", messages: [] as ChatMessage[] },
    { state: "existing conversation", messages: [{ role: "user", content: "Research question", created_at: "2026-11-04" }] as ChatMessage[] },
  ])("keeps exactly one picker inside the composer, not the header, for $state", async ({ messages }) => {
    render(<I18nProvider><ChatArea activeChatId={null} messages={messages} documents={[]} onSendMessage={vi.fn()} backendUrl="http://localhost:8000" /></I18nProvider>);
    const composer = screen.getByRole("textbox").parentElement!;
    const picker = within(composer).getByRole("button", { name: "Select model: Answer model" });
    const filter = within(composer).getByRole("button", { name: "Filter" });
    const sources = within(composer).getByRole("button", { name: "0 sources" });
    for (const control of [picker, filter, sources]) expect(control).toHaveClass("rounded-full");
    expect(picker).toHaveClass("w-max", "max-w-full", "min-w-11", "sm:min-w-0", "px-1.5", "sm:px-3");
    expect(picker.parentElement).toHaveClass("max-w-[16rem]");
    const send = within(composer).getByRole("button", { name: "Send message" });
    const attachment = within(composer).getByRole("button", { name: "Add attachment (images, files)" });
    const rightActions = sources.parentElement!;
    expect(rightActions).toHaveClass("ml-auto", "min-w-0");
    expect(within(rightActions).getAllByRole("button")).toEqual([picker, filter, sources, send]);
    expect(rightActions).not.toContainElement(attachment);
    expect(screen.getAllByRole("button", { name: /Select model/i })).toHaveLength(1);
    expect(screen.getByText("Chat", { selector: "span" }).parentElement).not.toContainElement(picker);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Unsubmitted draft" } });
    fireEvent.click(picker);
    const dialog = await screen.findByRole("dialog");
    const manage = within(dialog).getByRole("link", { name: "Open System configuration in a new tab" });
    expect(manage).toHaveAttribute("href", "/admin");
    expect(manage).toHaveAttribute("target", "_blank");
    expect(manage).toHaveAttribute("rel", "noopener noreferrer");
    expect(within(dialog).getAllByRole("link")).toEqual([manage]);
    expect(within(dialog).getByRole("button", { name: "Refresh model list" })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox")).toHaveValue("Unsubmitted draft");
  });
});
