import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery as render } from "../test/render";
import { MessageList } from "./MessageList";

const getDocumentPage = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, getDocumentPage: (...args: unknown[]) => getDocumentPage(...args) };
});

describe("View sources", () => {
  afterEach(() => {
    cleanup();
    getDocumentPage.mockReset();
  });

  it("lists the values used from a report without internal ids", async () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Your LDL is 138 mg/dL.",
            evidence: [
              {
                evidence_id: "ev-1",
                report_id: "blood-002",
                report_type: "blood_report",
                report_date: "2026-08-18",
                marker: "LDL",
                source: "ihr",
                value: 138,
                unit: "mg/dL",
                reference_range: "0–100 mg/dL",
              },
            ],
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "View sources (1)" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("LDL");
    expect(dialog.textContent).toContain("138 mg/dL");
    expect(dialog.textContent).toContain("0–100 mg/dL");
    expect(dialog.textContent).not.toContain("blood-002");
    expect(getDocumentPage).not.toHaveBeenCalled();
  });

  it("opens the uploaded page with the quoted row highlighted", async () => {
    getDocumentPage.mockResolvedValue({
      document_id: "doc-1",
      filename: "labs.pdf",
      page: 2,
      page_count: 2,
      text: "Lab Report\nHbA1c 5.6 % (ref 4.0-5.6)\nVitamin D 18 ng/mL (ref 30-100)",
      approximate: false,
    });
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Your HbA1c is 5.6 %.",
            evidence: [
              {
                evidence_id: "c1",
                report_id: "doc-1",
                report_type: "user_uploaded",
                report_date: "2026-10-01",
                source: "user_uploaded",
                document_id: "doc-1",
                filename: "labs.pdf",
                page_start: 2,
                marker: "HbA1c",
                value: 5.6,
                unit: "%",
                excerpt: "HbA1c 5.6 % (ref 4.0-5.6)",
              },
            ],
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "View sources (1)" }));
    await waitFor(() => expect(screen.getByTestId("page-text")).toBeTruthy());
    expect(getDocumentPage).toHaveBeenCalledWith("doc-1", 2);
    const marked = screen.getByTestId("page-text").querySelectorAll("mark");
    expect(Array.from(marked).map((m) => m.textContent)).toEqual(["HbA1c 5.6 % (ref 4.0-5.6)"]);
    expect(screen.getByText("labs.pdf · page 2")).toBeTruthy();
  });
});
