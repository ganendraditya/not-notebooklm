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
});
