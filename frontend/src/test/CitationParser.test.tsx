import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import React from "react";
import { parseCitationsInReactNode } from "../components/chat/CitationParser";

describe("CitationParser", () => {
  it("parses bracket citations like [1] and [2] correctly into interactive buttons", () => {
    const text = "Metode SVM memberikan hasil akurasi tinggi [1], sedangkan Random Forest lebih stabil [2].";
    const result = parseCitationsInReactNode(
      text,
      [
        { id: 1, filename: "Paper1.pdf", title: "Paper 1", created_at: "2026-01-01T00:00:00Z" }, 
        { id: 2, filename: "Paper2.pdf", title: "Paper 2", created_at: "2026-01-01T00:00:00Z" }
      ],
      undefined
    );

    const { container } = render(<div>{result}</div>);
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(2);
    expect(buttons[0].textContent).toContain("1");
    expect(buttons[1].textContent).toContain("2");
  });

  it("parses multi-digit bracket citations like [10] and [100] with dynamic width", () => {
    const text = "Penelitian lanjutan [10] dan analisis skala besar [100] memperkuat bukti.";
    const result = parseCitationsInReactNode(
      text,
      [
        { id: 10, index: 10, filename: "Paper10.pdf", title: "Paper 10", created_at: "2026-01-01T00:00:00Z" },
        { id: 100, index: 100, filename: "Paper100.pdf", title: "Paper 100", created_at: "2026-01-01T00:00:00Z" }
      ],
      undefined
    );

    const { container } = render(<div>{result}</div>);
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(2);
    expect(buttons[0].textContent).toContain("10");
    expect(buttons[1].textContent).toContain("100");
    expect(buttons[0].className).toContain("min-w-6");
  });

  it("handles text without citations gracefully", () => {
    const plainText = "Halo, selamat pagi! Apa yang bisa saya bantu hari ini?";
    const result = parseCitationsInReactNode(plainText);
    const { container } = render(<div>{result}</div>);
    expect(container.textContent).toBe(plainText);
  });

  it("ensures citation buttons in different cells/contexts have strictly unique keys and only the clicked one turns active", () => {
    const docs = [{ id: 11, index: 11, filename: "Paper11.pdf", title: "Paper 11", created_at: "2026-01-01T00:00:00Z" }];
    
    // Cell 1 has [11], Cell 2 has [11]
    let clickedKey: string | null = null;
    const onOpen = (_doc: any, ctx: any) => {
      clickedKey = ctx.citationKey;
    };

    // Render Cell 1 with prefix "td_10"
    const cell1 = parseCitationsInReactNode("[11] Mahulauw dkk.", docs, onOpen, null, undefined, undefined, "td_10");
    const { container: c1 } = render(<div>{cell1}</div>);
    const btn1 = c1.querySelector("button")!;
    btn1.click();
    expect(clickedKey).toBeTruthy();

    // Now re-render both with activeCitationKey = clickedKey
    const { container: r1 } = render(<div>{parseCitationsInReactNode("[11] Mahulauw dkk.", docs, onOpen, clickedKey, undefined, undefined, "td_10")}</div>);
    const { container: r2 } = render(<div>{parseCitationsInReactNode("[11] Evaluasi Teknik Sipil", docs, onOpen, clickedKey, undefined, undefined, "td_50")}</div>);

    const activeBtn1 = r1.querySelector("button")!;
    const activeBtn2 = r2.querySelector("button")!;

    // Button 1 (clicked) must be active (amber)
    expect(activeBtn1.className).toContain("bg-amber-400");
    // Button 2 (different cell) must NOT be active (blue)
    expect(activeBtn2.className).toContain("text-blue-300");
    expect(activeBtn2.className).not.toContain("bg-amber-400");
  });

  it("converts <br> tags into real line breaks and parses double brackets cleanly without trailing brackets", () => {
    const docs = [{ id: 1, index: 1, filename: "Paper1.pdf", title: "Paper 1", created_at: "2026-01-01T00:00:00Z" }];
    const text = "• Data: 1.000 sampel [1].<br>• Preprocessing: Cleaning [[1]]<br>(Tyas, 2024)";
    const result = parseCitationsInReactNode(text, docs);

    const { container } = render(<div>{result}</div>);
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(2);
    expect(buttons[0].textContent).toContain("1");
    expect(buttons[1].textContent).toContain("1");

    // Must render real <br> elements instead of literal "<br>" text string
    const brs = container.querySelectorAll("br");
    expect(brs.length).toBe(2);
    expect(container.innerHTML).not.toContain("&lt;br&gt;");
    expect(container.textContent).not.toContain("<br>");

    // Ensure double brackets [[1]] or [1]] don't leave trailing ']' in text
    expect(container.textContent).not.toContain("1]]");
    expect(container.textContent).not.toContain("[[1");
  });

  it("parses Dokumen [X] syntax without leaving trailing square brackets", () => {
    const docs = [
      { id: 1, index: 1, filename: "Paper1.pdf", title: "Paper 1", created_at: "2026-01-01T00:00:00Z" },
      { id: 8, index: 8, filename: "Paper8.pdf", title: "Paper 8", created_at: "2026-01-01T00:00:00Z" },
      { id: 10, index: 10, filename: "Paper10.pdf", title: "Paper 10", created_at: "2026-01-01T00:00:00Z" },
    ];
    const text = "Penerapan IndoBERT: Dokumen [8], [10], & [1]. Di bab kesimpulan, Dokumen [1] merekomendasikan.";
    const result = parseCitationsInReactNode(text, docs);

    const { container } = render(<div>{result}</div>);
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(4);

    // Text content must NOT have stray ']' after any button
    expect(container.textContent).not.toContain("8] ]");
    expect(container.textContent).not.toContain("[8] ]");
    expect(container.textContent).not.toContain("1] ]");
    expect(container.textContent).not.toContain("[1] ]");
    expect(container.textContent).toBe("Penerapan IndoBERT: [8], [10], & [1]. Di bab kesimpulan, [1] merekomendasikan.");
  });

  it("enforces fixed un-slanted typography with not-italic and eliminates native title attribute", () => {
    const docs = [{ id: 5, index: 5, filename: "Paper5.pdf", title: "Paper 5 Naive Bayes", created_at: "2026-01-01T00:00:00Z" }];
    const text = "Data preparation meliputi [5] tokenize";
    const result = parseCitationsInReactNode(text, docs);

    const { container } = render(<div>{result}</div>);
    const btn = container.querySelector("button")!;
    expect(btn).toBeTruthy();

    // Must have not-italic to prevent inheriting italic style from blockquotes/markdown
    expect(btn.className).toContain("not-italic");
    expect(btn.className).toContain("normal-case");

    // Must NOT have native title attribute (which causes ugly OS browser tooltips)
    expect(btn.getAttribute("title")).toBeNull();

    // Must have accessible aria-label
    expect(btn.getAttribute("aria-label")).toContain("Source [5]");
  });

  it("unwraps <a> tags wrapping citations so buttons are never nested inside links that open a new tab", () => {
    const docs = [{ id: 1, index: 1, filename: "Paper1.pdf", title: "Paper 1", created_at: "2026-01-01T00:00:00Z" }];
    const onOpen = vi.fn();

    // Simulate an anchor tag wrapping a citation node: <a href="#doc1" target="_blank">[1]</a>
    const linkNode = React.createElement(
      "a",
      { href: "#doc1", target: "_blank" },
      "[1]"
    );

    const result = parseCitationsInReactNode(linkNode, docs, onOpen);
    const { container } = render(<div>{result}</div>);

    // Must NOT render any <a> tag
    expect(container.querySelector("a")).toBeNull();

    // Must render the citation button directly
    const btn = container.querySelector("button")!;
    expect(btn).toBeTruthy();
    expect(btn.textContent).toContain("1");

    // Clicking the button should call onOpen, NOT open a new window/tab
    btn.click();
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("preserves regular markdown <a> hyperlinks when they do not wrap citations", () => {
    const docs = [{ id: 1, index: 1, filename: "Paper1.pdf", title: "Paper 1", created_at: "2026-01-01T00:00:00Z" }];
    const onOpen = vi.fn();

    // Legitimate markdown link: <a href="https://example.com" target="_blank">Documentation</a>
    const regularLinkNode = React.createElement(
      "a",
      { href: "https://example.com", target: "_blank", rel: "noopener noreferrer" },
      "Documentation"
    );

    const result = parseCitationsInReactNode(regularLinkNode, docs, onOpen);
    const { container } = render(<div>{result}</div>);

    const link = container.querySelector("a")!;
    expect(link).toBeTruthy();
    expect(link.getAttribute("href")).toBe("https://example.com");
    expect(link.textContent).toBe("Documentation");
    expect(container.querySelector("button")).toBeNull();
  });

  it("deduplicates repeated document citation buttons in document identity column and opens with zero highlights", () => {
    const docs = [{ id: 2, index: 2, filename: "Paper2.pdf", title: "Hyper-RAG", created_at: "2026-01-01T00:00:00Z" }];
    const onOpen = vi.fn();

    // In Document Identity column (isDocColumn = true), redundant duplicate [2] must be filtered out
    const cellText = "[2] Feng et al. (2026) Nature Communications [2]";
    const result = parseCitationsInReactNode(cellText, docs, onOpen, null, undefined, undefined, "td_0", true);
    const { container } = render(<div>{result}</div>);

    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(1);
    expect(buttons[0].textContent).toContain("2");

    // Clicking document column button must open with zero highlights (undefined context)
    buttons[0].click();
    expect(onOpen).toHaveBeenCalledWith(docs[0], undefined);
  });

  it("extracts only the specific cell context in table rows instead of the entire multi-column row", () => {
    const docs = [{ id: 2, index: 2, filename: "Paper2.pdf", title: "Hyper-RAG", created_at: "2026-01-01T00:00:00Z" }];
    let capturedCtx: any = null;
    const onOpen = (_doc: any, ctx: any) => {
      capturedCtx = ctx;
    };

    const rowMarkdown = "| [2] Feng et al. | High Stakes Domain | 35% reduction in KMR [2] | Indexing overhead [2] |";
    const cellContent = "35% reduction in KMR [2]";
    const result = parseCitationsInReactNode(cellContent, docs, onOpen, null, rowMarkdown, undefined, "td_2", false);
    const { container } = render(<div>{result}</div>);

    const btn = container.querySelector("button")!;
    btn.click();
    expect(capturedCtx).toBeTruthy();
    expect(capturedCtx.sentence).toContain("35% reduction in KMR");
    // Must NOT contain text from adjacent columns
    expect(capturedCtx.sentence).not.toContain("High Stakes Domain");
    expect(capturedCtx.sentence).not.toContain("Indexing overhead");
  });
});
