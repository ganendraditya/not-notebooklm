import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "@/lib/i18n";
import { BulkDeleteModal } from "@/components/RightSidebar/BulkDeleteModal";

describe("BulkDeleteModal chat confirmation context", () => {
  it("shows the exact proposed sources and closes on Escape without deleting", async () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(
      <I18nProvider>
        <BulkDeleteModal
          isOpen
          selectedCount={2}
          sourceNames={["Paper A", "paper-b.pdf"]}
          isBulkDeleting={false}
          onClose={onClose}
          onConfirm={onConfirm}
        />
      </I18nProvider>
    );

    const dialog = await screen.findByRole("alertdialog");
    expect(screen.getByText("Paper A")).toBeInTheDocument();
    expect(screen.getByText("paper-b.pdf")).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: "Escape" });

    expect(onClose).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
