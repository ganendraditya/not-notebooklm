import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import RightSidebar from "../components/RightSidebar";
import { I18nProvider } from "../lib/i18n";
import { Document } from "../stores/documentStore";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("RightSidebar Component", () => {
  const mockDocs: Document[] = [
    {
      id: 1,
      filename: "Attention_Is_All_You_Need.pdf",
      title: "Attention Is All You Need",
      doi: "10.48550/arXiv.1706.03762",
      created_at: new Date().toISOString()
    },
    {
      id: 2,
      filename: "BERT_Pretraining.txt",
      title: "BERT Pre-training of Deep Bidirectional Transformers",
      doi: "10.48550/arXiv.1810.04805",
      created_at: new Date().toISOString()
    }
  ];

  it("renders empty sources state when no documents exist", () => {
    renderWithI18n(
      <RightSidebar
        activeChatId="chat-123"
        documents={[]}
        onDocumentAdded={vi.fn()}
        backendUrl="http://localhost:8000"
        onClose={vi.fn()}
      />
    );

    // Empty state Add sources button
    expect(screen.getByRole("button", { name: /add sources/i })).toBeInTheDocument();
  });

  it("renders sources list with correct titles and index numbering", () => {
    renderWithI18n(
      <RightSidebar
        activeChatId="chat-123"
        documents={mockDocs}
        onDocumentAdded={vi.fn()}
        backendUrl="http://localhost:8000"
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    expect(screen.getByText("BERT Pre-training of Deep Bidirectional Transformers")).toBeInTheDocument();
    expect(screen.getByText("1.")).toBeInTheDocument();
    expect(screen.getByText("2.")).toBeInTheDocument();
  });

  it("switches to document reader when a document card is clicked", () => {
    const onViewingDocChange = vi.fn();

    renderWithI18n(
      <RightSidebar
        activeChatId="chat-123"
        documents={mockDocs}
        onDocumentAdded={vi.fn()}
        onViewingDocChange={onViewingDocChange}
        backendUrl="http://localhost:8000"
        onClose={vi.fn()}
      />
    );

    const docCard = screen.getByText("Attention Is All You Need");
    fireEvent.click(docCard);

    // Should switch to reader mode showing the Full Text tab and original filename
    expect(screen.getByText("Full Text")).toBeInTheDocument();
    expect(screen.getByText("Original Document")).toBeInTheDocument();
    expect(screen.getByText("Attention_Is_All_You_Need.pdf")).toBeInTheDocument();
  });

  it("handles close button click", () => {
    const onClose = vi.fn();

    renderWithI18n(
      <RightSidebar
        activeChatId="chat-123"
        documents={mockDocs}
        onDocumentAdded={vi.fn()}
        backendUrl="http://localhost:8000"
        onClose={onClose}
      />
    );

    const closeBtn = screen.getByLabelText("Close sidebar");
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });
});
