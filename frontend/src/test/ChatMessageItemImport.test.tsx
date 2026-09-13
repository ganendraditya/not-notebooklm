import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { InChatMessageComponent } from "../components/chat/ChatMessageItem";
import { I18nProvider } from "../lib/i18n";
import { Document as DocType } from "../stores/documentStore";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("ChatMessageItem Add to Sources & Selection Flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockSourcesJson = JSON.stringify([
    {
      title: "Deep Residual Learning for Image Recognition",
      year: "2016",
      doi: "10.1109/CVPR.2016.90",
      venue: "CVPR",
      is_oa: true,
      authors: ["Kaiming He", "Xiangyu Zhang"]
    },
    {
      title: "Attention Is All You Need",
      year: "2017",
      doi: "10.48550/arXiv.1706.03762",
      venue: "NeurIPS",
      is_oa: true,
      authors: ["Ashish Vaswani", "Noam Shazeer"]
    }
  ]);

  const mockContent = `Here are two relevant papers for your research:
<!-- SOURCES_DATA: ${mockSourcesJson} -->`;

  it("renders Add to sources button with accurate initial candidate count", () => {
    const msg = {
      role: "assistant" as const,
      content: mockContent,
      created_at: new Date().toISOString()
    };

    renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="chat-123"
        backendUrl="http://localhost:8000"
        documents={[]}
      />
    );

    expect(screen.getByText("2/2 new selected")).toBeInTheDocument();
    const addBtn = screen.getByRole("button", { name: /add 2 to sources/i });
    expect(addBtn).toBeInTheDocument();
    expect(addBtn).not.toBeDisabled();
  });

  it("updates count when individual candidate source is unchecked", () => {
    const msg = {
      role: "assistant" as const,
      content: mockContent,
      created_at: new Date().toISOString()
    };

    renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="chat-123"
        backendUrl="http://localhost:8000"
        documents={[]}
      />
    );

    const paperHeading = screen.getByText("Deep Residual Learning for Image Recognition");
    // Click the first candidate card to toggle selection
    fireEvent.click(paperHeading);

    expect(screen.getByText("1/2 new selected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add 1 to sources/i })).toBeInTheDocument();
  });

  it("disables Add button when 0 sources are selected and toggles Select All properly", () => {
    const msg = {
      role: "assistant" as const,
      content: mockContent,
      created_at: new Date().toISOString()
    };

    renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="chat-123"
        backendUrl="http://localhost:8000"
        documents={[]}
      />
    );

    // Click "Unselect all"
    const unselectBtn = screen.getByText(/unselect all/i);
    fireEvent.click(unselectBtn);

    expect(screen.getByText("0/2 new selected")).toBeInTheDocument();
    const addBtn = screen.getByRole("button", { name: /add.*to sources/i });
    expect(addBtn).toBeDisabled();

    // Click "Select All"
    const selectAllBtn = screen.getByText(/select all/i);
    fireEvent.click(selectAllBtn);

    expect(screen.getByText("2/2 new selected")).toBeInTheDocument();
    expect(addBtn).not.toBeDisabled();
  });

  it("marks duplicate source as already in sources and ignores it from import count", () => {
    const existingDoc: DocType = {
      id: 101,
      filename: "Deep Residual Learning for Image Recognition.pdf",
      title: "Deep Residual Learning for Image Recognition",
      doi: "10.1109/CVPR.2016.90",
      created_at: new Date().toISOString()
    };

    const msg = {
      role: "assistant" as const,
      content: mockContent,
      created_at: new Date().toISOString()
    };

    renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="chat-123"
        backendUrl="http://localhost:8000"
        documents={[existingDoc]}
      />
    );

    // 1 novel remaining out of 2 total
    expect(screen.getByText("1/1 new selected")).toBeInTheDocument();
    expect(screen.getByText(/in sources/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add 1 to sources/i })).toBeInTheDocument();
  });

  it("invokes import stream on button click without auto-canceling when parent re-renders", async () => {
    const onAddPendingSources = vi.fn();
    const onResolvePendingSource = vi.fn();
    const onDocumentAdded = vi.fn();

    // Mock fetch for import_sources_stream
    const mockSSEText =
      'data: {"type": "progress", "current": 1, "total": 1, "doc": {"id": 1, "filename": "Deep Residual Learning.pdf", "title": "Deep Residual Learning", "created_at": "2026-01-01", "index": 1, "has_full_pdf": true, "is_oa": true}}\n\n' +
      'data: {"type": "done", "total": 1}\n\n';

    const mockResponse = {
      ok: true,
      status: 200,
      body: {
        getReader: () => {
          let readCount = 0;
          return {
            read: async () => {
              if (readCount === 0) {
                readCount++;
                return { done: false, value: new TextEncoder().encode(mockSSEText) };
              }
              return { done: true, value: undefined };
            },
            releaseLock: () => {}
          };
        }
      }
    };

    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    const singleSourceContent = `<!-- SOURCES_DATA: [${JSON.stringify({
      title: "Deep Residual Learning",
      year: "2016",
      doi: "10.1109/CVPR.2016.90"
    })}] -->`;

    const msg = {
      role: "assistant" as const,
      content: singleSourceContent,
      created_at: new Date().toISOString()
    };

    const { rerender } = renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="chat-123"
        backendUrl="http://localhost:8000"
        documents={[]}
        onAddPendingSources={onAddPendingSources}
        onResolvePendingSource={onResolvePendingSource}
        onDocumentAdded={onDocumentAdded}
      />
    );

    const addBtn = screen.getByRole("button", { name: /add 1 to sources/i });
    fireEvent.click(addBtn);

    // Verify pending sources registered immediately
    expect(onAddPendingSources).toHaveBeenCalled();

    // Simulate parent component re-render with fresh callback references (the exact bug that occurred)
    rerender(
      <I18nProvider>
        <InChatMessageComponent
          msg={msg}
          activeChatId="chat-123"
          backendUrl="http://localhost:8000"
          documents={[]}
          onAddPendingSources={vi.fn()}
          onResolvePendingSource={vi.fn()}
          onDocumentAdded={onDocumentAdded}
        />
      </I18nProvider>
    );

    // Verify fetch was called and document was successfully added (not aborted by the re-render!)
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/chats/chat-123/import_sources_stream",
        expect.anything()
      );
      expect(onDocumentAdded).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Deep Residual Learning" }),
        "chat-123"
      );
    });
  });
});
