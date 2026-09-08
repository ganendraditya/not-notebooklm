import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
