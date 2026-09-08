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
});
