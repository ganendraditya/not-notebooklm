import { afterEach, describe, it, expect, vi } from "vitest";
import { act, render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import React from "react";
import { ChatInputBox } from "../components/chat/ChatInput";
import { I18nProvider } from "../lib/i18n";

const renderWithI18n = (ui: React.ReactElement) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("ChatInput Component", () => {
  afterEach(() => vi.unstubAllGlobals());

  const setComposerWidth = (width: number) => {
    vi.stubGlobal("ResizeObserver", class {
      constructor(private callback: ResizeObserverCallback) {}
      observe() { this.callback([{ contentRect: { width } } as ResizeObserverEntry], this as unknown as ResizeObserver); }
      disconnect() {}
    });
  };

  it("moves secondary actions into a labeled menu without hiding Model or Send", async () => {
    setComposerWidth(320);
    const onToggleRightSidebar = vi.fn();
    renderWithI18n(<ChatInputBox onSubmit={vi.fn()} backendUrl="http://localhost:8000" documentsCount={3} onToggleRightSidebar={onToggleRightSidebar} />);
    expect(screen.queryByRole("button", { name: "Filter" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "3 sources" })).not.toBeInTheDocument();
    const more = screen.getByRole("button", { name: "More prompt actions" });
    expect(more.parentElement).toHaveClass("ml-auto");
    expect(more.parentElement).toContainElement(screen.getByRole("button", { name: /Select model/i }));
    expect(more.parentElement).toContainElement(screen.getByRole("button", { name: "Send message" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Unsubmitted draft" } });
    fireEvent.click(more);
    const menu = await screen.findByRole("menu");
    expect(within(menu).getAllByRole("menuitem")).toHaveLength(2);
    fireEvent.click(within(menu).getByRole("menuitem", { name: "3 sources" }));
    expect(onToggleRightSidebar).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
    fireEvent.click(more);
    fireEvent.click(await screen.findByRole("menuitem", { name: "Filter" }));
    const dialog = await screen.findByRole("dialog", { name: "Search & Paper Filters" });
    await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
    fireEvent.click(within(dialog).getByRole("button", { name: "Past 3 years" }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Apply Filters/i }));
    await waitFor(() => expect(more).toHaveFocus());
    expect(more).toHaveAccessibleName("More prompt actions, Filter (1)");
    expect(screen.getByRole("textbox")).toHaveValue("Unsubmitted draft");
    fireEvent.click(more);
    fireEvent.click(await screen.findByRole("menuitem", { name: "Filter (1)" }));
    const reopened = await screen.findByRole("dialog", { name: "Search & Paper Filters" });
    fireEvent.keyDown(reopened, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(more).toHaveFocus());
  });

  it.each([479, 480, 760])("chooses actions by composer width (%ipx), not the screen width", (width) => {
    setComposerWidth(width);
    renderWithI18n(<ChatInputBox onSubmit={vi.fn()} backendUrl="http://localhost:8000" />);
    expect(Boolean(screen.queryByRole("button", { name: /More prompt actions/ }))).toBe(width < 480);
    expect(Boolean(screen.queryByRole("button", { name: "Filter" }))).toBe(width >= 480);
  });

  it("preserves an open filter draft when the composer changes width", async () => {
    let resize: ResizeObserverCallback;
    vi.stubGlobal("ResizeObserver", class {
      constructor(private callback: ResizeObserverCallback) {}
      observe(target: Element) { if (target.id === "chat-input-textarea") resize = this.callback; }
      disconnect() {}
    });
    renderWithI18n(<ChatInputBox onSubmit={vi.fn()} backendUrl="http://localhost:8000" />);
    fireEvent.click(screen.getByRole("button", { name: "Filter" }));
    const dialog = await screen.findByRole("dialog");
    const year = within(dialog).getByPlaceholderText("From");
    fireEvent.change(year, { target: { value: "2020" } });
    act(() => resize!([{ contentRect: { width: 320 } } as ResizeObserverEntry], {} as ResizeObserver));
    expect(year).toHaveValue(2020);
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.getByRole("button", { name: "More prompt actions" })).toHaveFocus());
  });

  it("keeps Stop directly reachable with overflow actions", () => {
    setComposerWidth(320);
    const stop = vi.fn();
    renderWithI18n(<ChatInputBox onSubmit={vi.fn()} backendUrl="http://localhost:8000" isLoading onStopGeneration={stop} />);
    expect(screen.getByRole("button", { name: "More prompt actions" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stop generation" }));
    expect(stop).toHaveBeenCalledOnce();
  });

  it("disables the Sources menu item if its panel action is unavailable", async () => {
    setComposerWidth(320);
    renderWithI18n(<ChatInputBox onSubmit={vi.fn()} backendUrl="http://localhost:8000" />);
    fireEvent.click(screen.getByRole("button", { name: "More prompt actions" }));
    expect(await screen.findByRole("menuitem", { name: "0 sources" })).toHaveAttribute("aria-disabled", "true");
  });

  it("renders input box and triggers onSubmit with trimmed text", () => {
    const onSubmit = vi.fn();

    renderWithI18n(
      <ChatInputBox
        onSubmit={onSubmit}
        isLoading={false}
        backendUrl="http://localhost:8000"
      />
    );

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "Tell me about quantum computing" } });

    const sendBtn = screen.getByRole("button", { name: /send/i });
    fireEvent.click(sendBtn);

    expect(onSubmit).toHaveBeenCalledWith("Tell me about quantum computing", undefined);
  });

  it("disables send button when input is empty and no attachments", () => {
    const onSubmit = vi.fn();

    renderWithI18n(
      <ChatInputBox
        onSubmit={onSubmit}
        isLoading={false}
        backendUrl="http://localhost:8000"
      />
    );

    const sendBtn = screen.getByRole("button", { name: /send/i });
    expect(sendBtn).toBeDisabled();
  });

  it("displays targeted source badge and allows clearing it", () => {
    const onClearTargetedSource = vi.fn();
    const targetedSource = {
      id: 1,
      filename: "Attention.pdf",
      title: "Attention Is All You Need",
      created_at: new Date().toISOString()
    };

    renderWithI18n(
      <ChatInputBox
        onSubmit={vi.fn()}
        isLoading={false}
        backendUrl="http://localhost:8000"
        targetedSource={targetedSource}
        onClearTargetedSource={onClearTargetedSource}
      />
    );

    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();

    const clearBtn = screen.getByRole("button", { name: /clear focused document/i });
    fireEvent.click(clearBtn);
    expect(onClearTargetedSource).toHaveBeenCalled();
  });

  it("shows stop generation button when isLoading is true", () => {
    const onStopGeneration = vi.fn();

    renderWithI18n(
      <ChatInputBox
        onSubmit={vi.fn()}
        isLoading={true}
        onStopGeneration={onStopGeneration}
        backendUrl="http://localhost:8000"
      />
    );

    const stopBtn = screen.getByRole("button", { name: /stop generation/i });
    expect(stopBtn).toBeInTheDocument();
    fireEvent.click(stopBtn);
    expect(onStopGeneration).toHaveBeenCalled();
  });
});
