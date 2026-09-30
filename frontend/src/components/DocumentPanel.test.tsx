import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentPanel } from "./DocumentPanel";

const listDocuments = vi.fn();
const deleteDocument = vi.fn();

vi.mock("../lib/api", () => ({
  listDocuments: (...args: unknown[]) => listDocuments(...args),
  deleteDocument: (...args: unknown[]) => deleteDocument(...args),
}));

describe("DocumentPanel status", () => {
  beforeEach(() => {
    listDocuments.mockReset();
    deleteDocument.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("lets the user select a report once measurements are ready", async () => {
    listDocuments.mockResolvedValue([
      {
        document_id: "doc-1",
        filename: "labs.pdf",
        content_type: "application/pdf",
        file_size: 12,
        source: "user_uploaded",
        upload_status: "uploaded",
        extraction_status: "completed",
        created_at: "2026-09-30T00:00:00Z",
        structured_facts_ready: true,
        pageindex_status: "BUILDING",
      },
    ]);
    render(<DocumentPanel refreshKey={1} selected={[]} onSelectedChange={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Measurements ready", { exact: false })).toBeTruthy());
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.disabled).toBe(false);
  });
});
