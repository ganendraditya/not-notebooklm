import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import SettingsModal from "../components/SettingsModal";
import { I18nProvider } from "../lib/i18n";
import { ChatSession } from "../stores/chatStore";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("SettingsModal Component", () => {
  const mockSessions: ChatSession[] = [
    {
      id: "chat-1",
      title: "Test Chat",
      created_at: new Date().toISOString()
    }
  ];

  it("renders modal when isOpen is true and switches tabs", async () => {
    // Mock fetch for storage summary
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        uploads_count: 5,
        total_size: 1048576,
        quota_bytes: 10737418240,
        usage_percentage: 0.01,
        categories: { images: 0, documents: 1048576, others: 0 },
        storage_type: "local"
      })
    });

    const onClose = vi.fn();

    renderWithI18n(
      <SettingsModal
        isOpen={true}
        onClose={onClose}
        backendUrl="http://localhost:8000"
        sessions={mockSessions}
        onChatsDeleted={vi.fn()}
        onAllDataReset={vi.fn()}
      />
    );

    // Initial General tab button should be active
    expect(screen.getByRole("button", { name: /^general/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^storage/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^notifications/i })).toBeInTheDocument();

    // Click Storage tab
    const storageTabBtn = screen.getByRole("button", { name: /^storage/i });
    fireEvent.click(storageTabBtn);

    // Storage summary should be requested
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/storage/summary")
      );
    });

    // Click Notifications tab
    const notifTabBtn = screen.getByRole("button", { name: /^notifications/i });
    fireEvent.click(notifTabBtn);

    // Close modal via close button
    const closeBtn = screen.getByRole("button", { name: /close/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it("does not render when isOpen is false", () => {
    const { container } = renderWithI18n(
      <SettingsModal
        isOpen={false}
        onClose={vi.fn()}
        backendUrl="http://localhost:8000"
        sessions={mockSessions}
        onChatsDeleted={vi.fn()}
        onAllDataReset={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });
});
