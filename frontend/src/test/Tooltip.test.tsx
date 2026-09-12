import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { Tooltip } from "../components/ui/tooltip";

describe("Universal Tooltip Component", () => {
  it("renders trigger children properly without breaking child elements", () => {
    render(
      <Tooltip content="Helper info" side="top">
        <button type="button">Action Button</button>
      </Tooltip>
    );

    const btn = screen.getByRole("button", { name: "Action Button" });
    expect(btn).toBeTruthy();
  });

  it("returns children directly when content is empty or undefined", () => {
    const { container } = render(
      <Tooltip content="">
        <span data-testid="raw-child">Direct Content</span>
      </Tooltip>
    );

    const span = screen.getByTestId("raw-child");
    expect(span).toBeTruthy();
    expect(container.textContent).toBe("Direct Content");
  });

  it("returns children directly when disabled is true", () => {
    render(
      <Tooltip content="Should not show" disabled>
        <button type="button">Disabled Tooltip</button>
      </Tooltip>
    );

    const btn = screen.getByRole("button", { name: "Disabled Tooltip" });
    expect(btn).toBeTruthy();
  });
});
