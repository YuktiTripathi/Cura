import { act, cleanup, fireEvent, render as plainRender, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery as render } from "../../test/render";
import { useDocumentUpload } from "../../hooks/useDocumentUpload";
import { PageDropZone } from "./PageDropZone";
import { ReviewValues } from "./ReviewValues";

const uploadDocument = vi.fn();
const getDocumentFacts = vi.fn();
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    uploadDocument: (...args: unknown[]) => uploadDocument(...args),
    getDocumentFacts: (...args: unknown[]) => getDocumentFacts(...args),
  };
});

const pdf = () => new File(["%PDF-1.4"], "labs.pdf", { type: "application/pdf" });

function dragEvent(type: string, file?: File) {
  const event = new Event(type, { bubbles: true, cancelable: true }) as DragEvent;
  Object.defineProperty(event, "dataTransfer", {
    value: { types: ["Files"], files: file ? [file] : [], dropEffect: "none" },
  });
  return event;
}

describe("upload flow", () => {
  afterEach(() => {
    cleanup();
    uploadDocument.mockReset();
    getDocumentFacts.mockReset();
  });

  it("shows a drop target while dragging files and hands over the dropped file", () => {
    const onFile = vi.fn();
    plainRender(<PageDropZone onFile={onFile} />);
    act(() => {
      window.dispatchEvent(dragEvent("dragenter"));
    });
    expect(screen.getByTestId("drop-overlay").textContent).toContain("Drop your PDF report");
    const file = pdf();
    act(() => {
      window.dispatchEvent(dragEvent("drop", file));
    });
    expect(onFile).toHaveBeenCalledWith(file);
    expect(screen.queryByTestId("drop-overlay")).toBeNull();
  });

  it("rejects non-PDF files without uploading", async () => {
    const { result } = renderHook(() => useDocumentUpload(null));
    await act(async () => {
      await result.current.upload(new File(["x"], "photo.png", { type: "image/png" }));
    });
    expect(uploadDocument).not.toHaveBeenCalled();
    expect(result.current.chip).toMatchObject({ status: "failed", error: "Only PDF reports can be added." });
  });

  it("uploads a PDF and reports it ready", async () => {
    uploadDocument.mockResolvedValue({ document_id: "d1", filename: "labs.pdf", extraction_status: "completed", structured_facts_ready: true });
    const onUploaded = vi.fn();
    const { result } = renderHook(() => useDocumentUpload("c1", onUploaded));
    await act(async () => {
      await result.current.upload(pdf());
    });
    expect(uploadDocument).toHaveBeenCalledWith(expect.any(File), "c1");
    expect(result.current.chip?.status).toBe("uploaded");
    expect(onUploaded).toHaveBeenCalled();
  });

  it("reviews extracted values with their source line, then compares or asks", async () => {
    getDocumentFacts.mockResolvedValue({
      document_id: "d1",
      filename: "labs.pdf",
      ready: true,
      facts: [
        { key: "ldl", label: "LDL cholesterol", value: 142, unit: "mg/dL", reference_high: 100, reference_text: "< 100", status: "high", page: 1, line: 2, excerpt: "LDL Cholesterol 142 mg/dL (ref < 100)" },
        { key: "tsh", label: "TSH", value: 2.1, unit: "µIU/mL", page: 1, line: 3, excerpt: "TSH 2.1 µIU/mL" },
      ],
    });
    const onCompare = vi.fn();
    const onAsk = vi.fn();
    render(<ReviewValues documentId="d1" onOpenChange={vi.fn()} onCompare={onCompare} onAsk={onAsk} />);
    await waitFor(() => expect(screen.getAllByTestId("review-row")).toHaveLength(2));
    expect(screen.getByRole("heading", { name: "Values read from labs.pdf" })).toBeTruthy();
    const [ldl, tsh] = screen.getAllByTestId("review-row");
    expect(ldl.textContent).toContain("Above range");
    expect(ldl.textContent).toContain("page 1 · line 2");
    expect(ldl.textContent).toContain("LDL Cholesterol 142 mg/dL (ref < 100)");
    expect(tsh.textContent).toContain("No reference range on this line");
    fireEvent.click(screen.getByRole("button", { name: "Compare with my SuperShyft results" }));
    expect(onCompare).toHaveBeenCalledWith("d1");
    fireEvent.click(screen.getByRole("button", { name: "Ask about this report" }));
    expect(onAsk).toHaveBeenCalledWith("d1");
  });
});
