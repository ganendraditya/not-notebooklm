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

    // Must render interactive buttons for the citations
    const buttons = container.querySelectorAll("button");
    // At least 2 citation buttons (one in col 1, one in col 2) plus the copy button
    const citationButtons = Array.from(buttons).filter(b => b.textContent?.includes("1"));
    expect(citationButtons.length).toBeGreaterThanOrEqual(2);
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
});
