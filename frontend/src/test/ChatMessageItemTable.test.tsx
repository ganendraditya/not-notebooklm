import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import React from "react";
import { InChatMessageComponent } from "../components/chat/ChatMessageItem";
import { I18nProvider } from "../lib/i18n";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("ChatMessageItem Table & Cleanliness", () => {
  it("strips spurious HTML anchor tags like <a id='doc1'></a> from content", () => {
    const rawContent = `| Kolom 1 | Kolom 2 |
|:---|---:|
| <a id="doc1"></a>[1] (JEPIN 2018) | 85.5% |
| <a id="doc2"></a>[2] (TEKNOINFO 2020) | 91.2% |`;

    const msg = {
      role: "assistant" as const,
      content: rawContent,
      created_at: new Date().toISOString(),
    };

    const { container } = renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
      />
    );

    // The text content should NOT contain raw "<a id=" strings
    expect(container.innerHTML).not.toContain('&lt;a id="doc1"&gt;');
    expect(container.innerHTML).not.toContain('<a id="doc1">');
    expect(container.textContent).toContain("[1] (JEPIN 2018)");
    expect(container.textContent).toContain("[2] (TEKNOINFO 2020)");
  });

  it("renders table with dynamic alignment classes and Copy Table button", () => {
    const tableMarkdown = `| Model | Parameters | Accuracy |
|:---|:---:|---:|
| BERT | 110M | 88.5% |
| RoBERTa | 355M | 92.1% |`;

    const msg = {
      role: "assistant" as const,
      content: tableMarkdown,
      created_at: new Date().toISOString(),
    };

    const { container } = renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
      />
    );

    // Should render table and copy button
    const copyBtn = screen.getByLabelText("Copy table");
    expect(copyBtn).toBeTruthy();

    const thElements = container.querySelectorAll("th");
    expect(thElements.length).toBe(3);
    // 1st column is left-aligned (:---)
    expect(thElements[0].className).toContain("text-left");
    // 2nd column is center-aligned (:---:)
    expect(thElements[1].className).toContain("text-center");
    // 3rd column is right-aligned (---:)
    expect(thElements[2].className).toContain("text-right");

    const tdElements = container.querySelectorAll("td");
    // Row 1
    expect(tdElements[0].className).toContain("text-left");
    expect(tdElements[1].className).toContain("text-center");
    expect(tdElements[2].className).toContain("text-right");
  });

  it("copies table content when Copy Table button is clicked", async () => {
    const tableMarkdown = `| Item | Price |
|:---|---:|
| Book | $20 |`;

    const msg = {
      role: "assistant" as const,
      content: tableMarkdown,
      created_at: new Date().toISOString(),
    };

    // Mock navigator.clipboard
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
      />
    );

    const copyBtn = screen.getByLabelText("Copy table");
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(writeTextMock).toHaveBeenCalledTimes(1);
    const copiedText = writeTextMock.mock.calls[0][0];
    expect(copiedText).toContain("| Item | Price |");
    expect(copiedText).toContain("| Book | $20 |");
  });

  it("strips <blockquote> and <mark> HTML tags from table cells and rendered text", async () => {
    const rawContent = `| Metrik | Bukti Teks |
|:---|:---|
| Akurasi | 💬 Bukti Teks: <blockquote><mark>"Sistem analisis sentimen dibagi 5 tahap."</mark></blockquote> |
| Limitasi | 💬 Bukti Teks: <blockquote><mark>"Data diperoleh dari twitter."</mark></blockquote> |`;

    const msg = {
      role: "assistant" as const,
      content: rawContent,
      created_at: new Date().toISOString(),
    };

    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    const { container } = renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
      />
    );

    // Rendered text content must NOT contain raw "<blockquote>" or "</mark>" strings
    expect(container.innerHTML).not.toContain("&lt;mark&gt;");
    expect(container.innerHTML).not.toContain("&lt;blockquote&gt;");
    expect(container.innerHTML).not.toContain("&lt;/mark&gt;");
    expect(container.innerHTML).not.toContain("&lt;/blockquote&gt;");
    expect(container.textContent).toContain('"Sistem analisis sentimen dibagi 5 tahap."');
    expect(container.textContent).not.toContain("</mark></blockquote>");

    // Copied table must NOT contain HTML tags either
    const copyBtn = screen.getByLabelText("Copy table");
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(writeTextMock).toHaveBeenCalled();
    const copiedText = writeTextMock.mock.calls[0][0];
    expect(copiedText).not.toContain("</mark>");
    expect(copiedText).not.toContain("</blockquote>");
    expect(copiedText).toContain('"Sistem analisis sentimen dibagi 5 tahap."');
  });

  it("converts markdown citation links like [[1]](#doc1) into interactive buttons instead of new-tab links", () => {
    const rawContent = `| Dokumen | Metode |
|:---|:---|
| [[1]](#doc1) | Pipeline 5 tahap [1] |`;

    const msg = {
      role: "assistant" as const,
      content: rawContent,
      created_at: new Date().toISOString(),
    };

    const documents = [
      { id: 1, index: 1, filename: "Paper1.pdf", title: "Paper 1", created_at: "2026-01-01T00:00:00Z" }
    ];

    const { container } = renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
        documents={documents}
      />
    );

    // Must NOT contain any <a target="_blank"> linking to #doc1
    const anchorLinks = container.querySelectorAll("a");
    expect(anchorLinks.length).toBe(0);

    // Must render interactive buttons for the content column citations (while identity column is clean text)
    const buttons = container.querySelectorAll("button");
    const citationButtons = Array.from(buttons).filter(b => b.textContent?.includes("1"));
    expect(citationButtons.length).toBe(1);
    expect(container.textContent).toContain("Pipeline 5 tahap [1]");
  });

  it("preserves horizontal scroll position when activeCitationKey updates upon clicking a citation", () => {
    const rawContent = `| Col 1 | Col 2 | Col 3 | Col 4 |
|:---|:---|:---|:---|
| [1] Paper 1 | Data 1 | Data 2 | Metric 88% [1] |`;

    const msg = {
      role: "assistant" as const,
      content: rawContent,
      created_at: new Date().toISOString(),
    };

    const documents = [
      { id: 1, index: 1, filename: "Paper1.pdf", title: "Paper 1", created_at: "2026-01-01T00:00:00Z" }
    ];

    const { container, rerender } = renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
        documents={documents}
        activeCitationKey={null}
      />
    );

    const scrollContainer = container.querySelector(".overflow-x-auto") as HTMLDivElement;
    expect(scrollContainer).toBeTruthy();

    // User scrolls horizontally to the right
    fireEvent.scroll(scrollContainer, { target: { scrollLeft: 450 } });

    // Re-render when active citation key changes (as happens when user clicks citation button)
    rerender(
      <I18nProvider>
        <InChatMessageComponent
          msg={msg}
          activeChatId="test-chat"
          backendUrl="http://localhost:8000"
          documents={documents}
          activeCitationKey="cite-td_10-88-1-0"
        />
      </I18nProvider>
    );

    // scrollLeft must remain preserved at 450 instead of resetting to 0
    expect(scrollContainer.scrollLeft).toBe(450);
  });

  it("stops propagation on wheel and scroll events for tables and report sources to protect main canvas", () => {
    const rawContent = `Berikut laporannya:
<!-- SOURCES_DATA: [{"title":"Paper A","authors":"Auth A","year":2022,"venue":"Conf"}] -->
| Col A | Col B |
|:---|:---|
| Val 1 | Val 2 |`;

    const msg = {
      role: "assistant" as const,
      content: rawContent,
      created_at: new Date().toISOString(),
    };

    const onParentWheel = vi.fn();
    const onParentScroll = vi.fn();

    const { container } = renderWithI18n(
      <div onWheel={onParentWheel} onScroll={onParentScroll}>
        <InChatMessageComponent
          msg={msg}
          activeChatId="test-chat"
          backendUrl="http://localhost:8000"
        />
      </div>
    );

    // 1. Table scroll container
    const tableScrollContainer = container.querySelector(".overflow-x-auto") as HTMLDivElement;
    expect(tableScrollContainer).toBeTruthy();

    fireEvent.wheel(tableScrollContainer, { deltaY: -50 });
    expect(onParentWheel).not.toHaveBeenCalled();

    fireEvent.scroll(tableScrollContainer, { target: { scrollLeft: 100 } });
    expect(onParentScroll).not.toHaveBeenCalled();

    // 2. Sources list container
    const sourcesScrollContainer = container.querySelector(".overflow-y-auto") as HTMLDivElement;
    expect(sourcesScrollContainer).toBeTruthy();

    fireEvent.wheel(sourcesScrollContainer, { deltaY: -50 });
    expect(onParentWheel).not.toHaveBeenCalled();

    fireEvent.scroll(sourcesScrollContainer, { target: { scrollTop: 50 } });
    expect(onParentScroll).not.toHaveBeenCalled();
  });

  it("suppresses non-highlighting buttons on No, Author, and Title columns while keeping buttons on empirical columns", () => {
    const rawContent = `| No & Dokumen | Penulis & Tahun | Judul & Fokus Utama | Metode / Pendekatan Teknis | Temuan Utama (Hasil & Performa) | Limitasi / Kendala | Rekomendasi Future Work |
| --- | --- | --- | --- | --- | --- | --- |
| [1] | Tahir et al. (2023) [1] | Real-Time Event-Driven Road Traffic Monitoring System Using CCTV Video Analytics [1] | Sequential DCNN (data sintetis BeamNG Drive) [1]. | Akurasi klasifikasi insiden rata-rata 82.3% [1]. | Akurasi malam hari sangat rendah (56.7%) [1]. | Penambahan data sintetis malam hari [1]. |`;

    const documents = [
      {
        id: 1,
        index: 1,
        filename: "Tahir2023.pdf",
        title: "Real-Time Event-Driven Road Traffic Monitoring System Using CCTV Video Analytics",
        created_at: "2026-01-01T00:00:00Z"
      }
    ];

    const onOpenDocument = vi.fn();

    const msg = {
      role: "assistant" as const,
      content: rawContent,
      created_at: new Date().toISOString(),
    };

    const { container } = renderWithI18n(
      <InChatMessageComponent
        msg={msg}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
        documents={documents}
        onOpenDocument={onOpenDocument}
      />
    );

    const tdElements = container.querySelectorAll("td");
    expect(tdElements.length).toBe(7);

    // Col 0: No & Dokumen -> plain text, NO button
    expect(tdElements[0].querySelectorAll("button").length).toBe(0);
    expect(tdElements[0].textContent).toContain("[1]");

    // Col 1: Penulis & Tahun -> plain text, NO button
    expect(tdElements[1].querySelectorAll("button").length).toBe(0);
    expect(tdElements[1].textContent).toContain("Tahir et al. (2023)");

    // Col 2: Judul & Fokus Utama -> plain text, NO button
    expect(tdElements[2].querySelectorAll("button").length).toBe(0);
    expect(tdElements[2].textContent).toContain("Real-Time Event-Driven Road Traffic Monitoring System");

    // Col 3: Metode -> HAS citation button
    const col3Btns = tdElements[3].querySelectorAll("button");
    expect(col3Btns.length).toBe(1);

    // Col 4: Temuan -> HAS citation button
    const col4Btns = tdElements[4].querySelectorAll("button");
    expect(col4Btns.length).toBe(1);

    // Col 5: Limitasi -> HAS citation button
    const col5Btns = tdElements[5].querySelectorAll("button");
    expect(col5Btns.length).toBe(1);

    // Col 6: Rekomendasi -> HAS citation button
    const col6Btns = tdElements[6].querySelectorAll("button");
    expect(col6Btns.length).toBe(1);

    // Clicking empirical button triggers onOpenDocument with context
    col4Btns[0].click();
    expect(onOpenDocument).toHaveBeenCalledTimes(1);
    expect(onOpenDocument).toHaveBeenCalledWith(
      documents[0],
      expect.objectContaining({
        sentence: expect.stringContaining("82.3%"),
        num: 1
      })
    );
  });

  it("renders buttons in column-mapped table cells (where columns are Dokumen [1], Dokumen [2])", () => {
    const rawContent = `| No | Parameter Analisis | Dokumen [1] (Batubara dkk., 2024) | Dokumen [2] (Pradana dkk., 2024) |
| :---: | :--- | :--- | :--- |
| **1** | **Judul Paper** | Perancangan Sistem Deteksi Pelanggaran Penggunaan Helm... Menggunakan YOLOv5 Ultralytics [1] | Deteksi Rambu Lalu Lintas Real-Time di Indonesia dengan Penerapan YOLOv11 [2]. |
| **8** | **Kinerja & Evaluasi Utama** | • mAP@0.5 rata-rata: **0,938** [1].<br>• Evaluasi sistem real-time (1.200 motor): **Akurasi 98,5%**, Presisi 98,97%, Recall 96,48%, F1-score 97,71% [1]. | • mAP@0.5: **0,995** [2]. |

<!-- CITATION_MAP: {"1": ["Perancangan sistem deteksi", "Akurasi 98,5%"], "2": ["Deteksi rambu", "mAP 0,995"]} -->`;

    const documents = [
      { id: 1, index: 1, filename: "Batubara2024.pdf", title: "Paper 1", created_at: "2026-01-01T00:00:00Z" },
      { id: 2, index: 2, filename: "Pradana2024.pdf", title: "Paper 2", created_at: "2026-01-01T00:00:00Z" }
    ];

    const { container } = renderWithI18n(
      <InChatMessageComponent
        msg={{ role: "assistant", content: rawContent, created_at: new Date().toISOString() }}
        activeChatId="test-chat"
        backendUrl="http://localhost:8000"
        documents={documents}
      />
    );

    const ths = container.querySelectorAll("th");
    // Headers must not have buttons
    ths.forEach(th => expect(th.querySelectorAll("button").length).toBe(0));

    const tds = container.querySelectorAll("td");
    // Row 1 (Parameter: Judul Paper):
    // Col 0: **1** -> 0 buttons
    expect(tds[0].querySelectorAll("button").length).toBe(0);
    // Col 1: **Judul Paper** -> 0 buttons
    expect(tds[1].querySelectorAll("button").length).toBe(0);
    // Col 2: Perancangan ... [1] -> 1 button
    expect(tds[2].querySelectorAll("button").length).toBe(1);
    // Col 3: Deteksi ... [2] -> 1 button
    expect(tds[3].querySelectorAll("button").length).toBe(1);

    // Row 2 (Parameter: Kinerja & Evaluasi Utama):
    // Col 0: **8** -> 0 buttons
    expect(tds[4].querySelectorAll("button").length).toBe(0);
    // Col 1: **Kinerja & Evaluasi Utama** -> 0 buttons
    expect(tds[5].querySelectorAll("button").length).toBe(0);
    // Col 2: • mAP@0.5 rata-rata: 0,938 [1] ... Akurasi 98,5% [1] -> has buttons
    expect(tds[6].querySelectorAll("button").length).toBeGreaterThanOrEqual(1);
    // Col 3: • mAP@0.5: 0,995 [2] -> 1 button
    expect(tds[7].querySelectorAll("button").length).toBe(1);
  });
});
