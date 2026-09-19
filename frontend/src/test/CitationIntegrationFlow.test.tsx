import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { InChatMessageComponent } from "../components/chat/ChatMessageItem";
import { useDocumentStore, Document as DocType } from "../stores/documentStore";
import { I18nProvider } from "../lib/i18n";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("End-to-End Citation & Document Ordering Integration Test", () => {
  beforeEach(() => {
    useDocumentStore.setState({
      documents: [],
      pendingSources: [],
      targetedSource: null,
      viewingDoc: null,
      groundingHighlight: null,
    });
  });

  it("guarantees clicking [2] resolves to Document 2 (TXT) even if documents arrive out-of-order", () => {
    // Simulate real-world asynchronous arrivals where doc 112 (PDF) finishes before doc 110 (TXT)
    const doc109: DocType = { id: 109, filename: "Paper1_PlatNomor.pdf", title: "Deteksi Plat Nomor (PDF)", created_at: "2026-01-01T00:00:00Z" };
    const doc110: DocType = { id: 110, filename: "Paper2_PlatNomor.txt", title: "Deteksi Objek Plat Nomor (TXT)", created_at: "2026-01-01T00:00:00Z" };
    const doc112: DocType = { id: 112, filename: "Paper4_RambuLaluLintas.pdf", title: "Deteksi Rambu Lalu Lintas (PDF)", created_at: "2026-01-01T00:00:00Z" };

    // Arrived in random order: 112 first, then 109, then 110
    useDocumentStore.getState().addDocument(doc112);
    useDocumentStore.getState().addDocument(doc109);
    useDocumentStore.getState().addDocument(doc110);

    const storeDocs = useDocumentStore.getState().documents;

    // Verify canonical ID sorting and index assignment:
    expect(storeDocs[0].id).toBe(109);
    expect(storeDocs[0].index).toBe(1);

    expect(storeDocs[1].id).toBe(110);
    expect(storeDocs[1].index).toBe(2);
    expect(storeDocs[1].filename).toContain(".txt");

    expect(storeDocs[2].id).toBe(112);
    expect(storeDocs[2].index).toBe(3);

    const onOpenDocument = vi.fn();
    const markdownWithCitation = `Segmentasi Masalah: Paper [1], [2], dan [3] berfokus pada analisis objek.`;

    const msg = {
      role: "assistant" as const,
      content: markdownWithCitation,
      created_at: new Date().toISOString(),
    };

    renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
        documents={storeDocs}
        onOpenDocument={onOpenDocument}
      />
    );

    // Locate the citation button with number 2
    const btn2 = screen.getByRole("button", { name: /Source \[2\]/i });
    expect(btn2).toBeDefined();

    // Clicking [2] MUST open Document 2 (id: 110, TXT), NOT Document 4/3 (id: 112, PDF)!
    btn2.click();
    expect(onOpenDocument).toHaveBeenCalledTimes(1);
    expect(onOpenDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 110,
        filename: "Paper2_PlatNomor.txt",
        title: "Deteksi Objek Plat Nomor (TXT)",
      }),
      expect.objectContaining({
        num: 2,
      })
    );
  });

  it("automatically attaches citations and correctly routes clicks in row-based tables with bold No (**1**, **2**)", () => {
    const documents: DocType[] = [
      { id: 109, index: 1, filename: "Paper1.pdf", title: "Deteksi Plat Nomor (Yanuangga 2023)", created_at: "2026-01-01T00:00:00Z" },
      { id: 110, index: 2, filename: "Paper2.txt", title: "Deteksi Objek Plat Nomor (Susilo 2024)", created_at: "2026-01-01T00:00:00Z" },
    ];

    const rawTable = `| No | Judul & Tahun | Metode & Dataset | Temuan Utama & Metrik Performa |
| :---: | :--- | :--- | :--- |
| **1** | **Deteksi Plat Nomor...** *(Yanuangga et al., 2023)* | • Metode: CNN + OCR.<br>• Dataset: 100 citra. | • Akurasi 98%, Presisi 98%.<br>• Pembacaan OCR: Akurasi 88%. |
| **2** | **Deteksi Objek Plat...** *(Susilo, 2024)* | • Metode: YOLOv5n + TRBA.<br>• Dataset: 3.200 citra. | • mAP 0,893 dan F1-score 0,887.<br>• Akurasi karakter 83,08%. |`;

    const onOpenDocument = vi.fn();
    const msg = {
      role: "assistant" as const,
      content: rawTable,
      created_at: new Date().toISOString(),
    };

    renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
        documents={documents}
        onOpenDocument={onOpenDocument}
      />
    );

    // Table rows must contain buttons for [1] and [2]
    const row1Buttons = screen.getAllByRole("button", { name: /Source \[1\]/i });
    const row2Buttons = screen.getAllByRole("button", { name: /Source \[2\]/i });

    expect(row1Buttons.length).toBeGreaterThan(0);
    expect(row2Buttons.length).toBeGreaterThan(0);

    // Clicking a button in row 2 opens doc 2
    row2Buttons[0].click();
    expect(onOpenDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 110,
        title: "Deteksi Objek Plat Nomor (Susilo 2024)",
      }),
      expect.objectContaining({
        num: 2,
      })
    );
  });
});
