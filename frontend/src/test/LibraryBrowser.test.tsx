import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import LibraryBrowser from "../components/library/LibraryBrowser";
import { I18nProvider } from "../lib/i18n";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("LibraryBrowser Component", () => {
  const mockStorageFiles = [
    {
      id: "doc-1",
      filename: "Quantum_Algorithms.pdf",
      raw_filename: "chat-1_Quantum_Algorithms.pdf",
      category: "documents",
      size_bytes: 1048576,
      modified: new Date().toISOString(),
      chat_id: "chat-1",
      chat_title: "Quantum Physics"
    },
    {
      id: "img-1",
      filename: "Circuit_Diagram.png",
      raw_filename: "chat-2_Circuit_Diagram.png",
      category: "images",
      size_bytes: 524288,
      modified: new Date().toISOString(),
      chat_id: "chat-2",
      chat_title: "Hardware Arch"
    }
  ];

  beforeEach(() => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/storage/summary")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            uploads_count: 2,
            total_size: 1572864,
            quota_bytes: 10737418240,
            usage_percentage: 0.015,
            categories: { images: 524288, documents: 1048576, others: 0 }
          })
        });
      }
      if (url.includes("/storage/files")) {
        return Promise.resolve({
          ok: true,
          json: async () => mockStorageFiles
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({})
      });
    });
  });

  it("renders list of files and filters by search input", async () => {
    renderWithI18n(
      <LibraryBrowser
        backendUrl="http://localhost:8000"
      />
    );

    // Wait for files to load
    await waitFor(() => {
      expect(screen.getByText("Quantum_Algorithms.pdf")).toBeInTheDocument();
      expect(screen.getByText("Circuit_Diagram.png")).toBeInTheDocument();
    });

    // Type in search box
    const searchInput = screen.getByPlaceholderText(/search files/i);
    fireEvent.change(searchInput, { target: { value: "Circuit" } });

    await waitFor(() => {
      expect(screen.queryByText("Quantum_Algorithms.pdf")).not.toBeInTheDocument();
      expect(screen.getByText("Circuit_Diagram.png")).toBeInTheDocument();
    });
  });

  it("filters by category tabs (Documents vs Images)", async () => {
    renderWithI18n(
      <LibraryBrowser
        backendUrl="http://localhost:8000"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Quantum_Algorithms.pdf")).toBeInTheDocument();
    });

    const imagesTab = screen.getByRole("button", { name: /^images/i });
    fireEvent.click(imagesTab);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("category=images")
      );
    });
  });
});
