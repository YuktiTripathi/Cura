from __future__ import annotations


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_text_pdf(pages: list[str] | list[list[str]]) -> bytes:
    """Each page is a single string (one text run) or a list of lines (one PDF line each)."""
    n = len(pages)
    font_id = 3
    page_ids = list(range(4, 4 + n))
    content_ids = list(range(4 + n, 4 + 2 * n))
    kids = " ".join(f"{i} 0 R" for i in page_ids)
    pieces: list[bytes] = [b"%PDF-1.4\n"]
    xref_entries = ["0000000000 65535 f "]
    cursor = len(pieces[0])

    def emit(blob: bytes) -> None:
        nonlocal cursor
        xref_entries.append(f"{cursor:010d} 00000 n ")
        pieces.append(blob)
        cursor += len(blob)

    def obj_bytes(obj_id: int, body: str) -> bytes:
        return f"{obj_id} 0 obj\n{body}\nendobj\n".encode("latin-1")

    emit(obj_bytes(1, "<< /Type /Catalog /Pages 2 0 R >>"))
    emit(obj_bytes(2, f"<< /Type /Pages /Kids [{kids}] /Count {n} >>"))
    emit(obj_bytes(font_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
    for i, text in enumerate(pages):
        pid = page_ids[i]
        cid = content_ids[i]
        if isinstance(text, (list, tuple)):
            # One PDF text line per entry, like a real lab table row.
            shown = " ".join(f"({escape_pdf_text(line)}) Tj T*" for line in text)
            stream = f"BT /F1 10 Tf 50 750 Td 14 TL {shown} ET\n"
        else:
            stream = f"BT /F1 12 Tf 50 720 Td ({escape_pdf_text(text)}) Tj ET\n"
        raw = stream.encode("latin-1")
        emit(
            obj_bytes(
                pid,
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>",
            )
        )
        emit(
            f"{cid} 0 obj\n<< /Length {len(raw)} >>\nstream\n".encode("latin-1")
            + raw
            + b"endstream\nendobj\n"
        )
    startxref = cursor
    xref = f"xref\n0 {len(xref_entries)}\n" + "\n".join(xref_entries) + "\n"
    trailer = f"trailer\n<< /Size {len(xref_entries)} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n"
    return b"".join(pieces) + xref.encode("latin-1") + trailer.encode("latin-1")


def make_blank_pdf(page_count: int = 1) -> bytes:
    from io import BytesIO

    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()
