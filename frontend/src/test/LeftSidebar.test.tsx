import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import React from "react";
import LeftSidebar from "../components/LeftSidebar";
import { I18nProvider } from "../lib/i18n";
import { ChatSession, useChatStore } from "../stores/chatStore";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("LeftSidebar Component", () => {
  const mockSessions: ChatSession[] = [
    {
      id: "chat-1",
      title: "Deep Learning Research",
      created_at: new Date().toISOString(),
      is_pinned: false
    },
    {
      id: "chat-2",
      title: "Quantum Computing Review",
      created_at: new Date().toISOString(),
      is_pinned: true
    }
  ];

  it("renders chat sessions list and highlights the active chat", () => {
    const onSelectChat = vi.fn();
    const onCreateChat = vi.fn();
    const onDeleteChat = vi.fn();
    const onRenameChat = vi.fn();

    renderWithI18n(
      <LeftSidebar
        sessions={mockSessions}
        activeChatId="chat-1"
        onSelectChat={onSelectChat}
        onCreateChat={onCreateChat}
        onDeleteChat={onDeleteChat}
        onRenameChat={onRenameChat}
      />
    );

    expect(screen.getByText("Deep Learning Research")).toBeInTheDocument();
    expect(screen.getByText("Quantum Computing Review")).toBeInTheDocument();

    // Click inactive chat
    const chat2 = screen.getByText("Quantum Computing Review");
    fireEvent.click(chat2);
    expect(onSelectChat).toHaveBeenCalledWith("chat-2");
  });

  it("calls onCreateChat when New Chat button is clicked", () => {
    const onCreateChat = vi.fn();

    renderWithI18n(
      <LeftSidebar
        sessions={mockSessions}
        activeChatId="chat-1"
        onSelectChat={vi.fn()}
        onCreateChat={onCreateChat}
        onDeleteChat={vi.fn()}
        onRenameChat={vi.fn()}
      />
    );

    const newChatBtns = screen.getAllByRole("button");
    const newChatBtn = newChatBtns.find(b => b.textContent?.includes("New chat") || b.getAttribute("aria-label")?.includes("New chat"));
    expect(newChatBtn).toBeDefined();
    fireEvent.click(newChatBtn!);
    expect(onCreateChat).toHaveBeenCalled();
  });

  it("triggers search, library, and settings navigation callbacks", () => {
    const onOpenSearch = vi.fn();
    const onOpenLibrary = vi.fn();
    const onOpenSettings = vi.fn();

    renderWithI18n(
      <LeftSidebar
        sessions={mockSessions}
        activeChatId="chat-1"
        onSelectChat={vi.fn()}
        onCreateChat={vi.fn()}
        onDeleteChat={vi.fn()}
        onRenameChat={vi.fn()}
        onOpenSearch={onOpenSearch}
        onOpenLibrary={onOpenLibrary}
        onOpenSettings={onOpenSettings}
      />
    );

    const searchBtn = screen.getByRole("button", { name: /search/i });
    fireEvent.click(searchBtn);
    expect(onOpenSearch).toHaveBeenCalled();

    const libraryBtn = screen.getByRole("button", { name: /library/i });
    fireEvent.click(libraryBtn);
    expect(onOpenLibrary).toHaveBeenCalled();

    const settingsBtn = screen.getByRole("button", { name: /settings/i });
    fireEvent.click(settingsBtn);
    expect(onOpenSettings).toHaveBeenCalled();
  });

  it("renders the current app version in the footer", () => {
    renderWithI18n(
      <LeftSidebar
        sessions={mockSessions}
        activeChatId="chat-1"
        onSelectChat={vi.fn()}
        onCreateChat={vi.fn()}
        onDeleteChat={vi.fn()}
        onRenameChat={vi.fn()}
      />
    );

    expect(screen.getByText("v1.10.0")).toBeInTheDocument();
  });

  it("renders live running execution indicator and completed duration badge properly", () => {
    act(() => {
      useChatStore.getState().setSessionExecution("chat-1", {
        status: "running",
        startedAt: Date.now() - 5000,
      });
      useChatStore.getState().setSessionExecution("chat-2", {
        status: "completed",
        startedAt: Date.now() - 65000,
        durationFormatted: "1m 5s",
      });
    });

    renderWithI18n(
      <LeftSidebar
        sessions={mockSessions}
        activeChatId="chat-1"
        onSelectChat={vi.fn()}
        onCreateChat={vi.fn()}
        onDeleteChat={vi.fn()}
        onRenameChat={vi.fn()}
      />
    );

    // chat-2 should display completed duration "1m 5s"
    expect(screen.getByText("1m 5s")).toBeInTheDocument();

    // chat-1 should display a ticking timer (e.g. "5s" or similar)
    expect(screen.getByText(/^\d+s$/)).toBeInTheDocument();
  });
});
