import { useEffect, useState } from "react";
import { deleteDocument, listDocuments, type UploadedDocument } from "../lib/api";

type Props = {
  refreshKey: number;
  selected: string[];
  onSelectedChange: (ids: string[]) => void;
};

function statusLabel(doc: UploadedDocument): string {
  if (doc.extraction_status === "failed") return "Could not read";
  if (doc.structured_facts_ready && doc.pageindex_status === "BUILDING") return "Measurements ready";
  if (doc.extraction_status === "completed" || doc.structured_facts_ready) return "Ready";
  if (doc.extraction_status === "processing" || doc.extraction_status === "not_started") return "Processing…";
  return "Uploaded";
}

export function DocumentPanel({ refreshKey, selected, onSelectedChange }: Props) {
  const [docs, setDocs] = useState<UploadedDocument[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const next = await listDocuments().catch(() => []);
      if (!cancelled) setDocs(next);
    }
    load();
    const id = window.setInterval(() => {
      load();
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [refreshKey]);

  if (!docs.length) return null;

  return (
    <section className="doc-panel">
      <h2>Uploaded Documents</h2>
      <ul>
        {docs.map((d) => (
          <li key={d.document_id}>
            <label>
              <input
                type="checkbox"
                checked={selected.includes(d.document_id)}
                disabled={d.extraction_status !== "completed" && !d.structured_facts_ready}
                onChange={(event) =>
                  onSelectedChange(
                    event.target.checked
                      ? [...selected, d.document_id]
                      : selected.filter((id) => id !== d.document_id)
                  )
                }
              />
              📄 {d.filename}
            </label>
            <span className="muted">
              {statusLabel(d)}
              {" · "}
              {new Date(d.created_at).toLocaleDateString(undefined, {
                day: "2-digit",
                month: "short",
                year: "numeric",
              })}
              {" · "}
              <button
                type="button"
                className="text-button"
                onClick={async () => {
                  await deleteDocument(d.document_id);
                  onSelectedChange(selected.filter((id) => id !== d.document_id));
                  setDocs((current) => current.filter((row) => row.document_id !== d.document_id));
                }}
              >
                Delete
              </button>
            </span>
            {d.extraction_error && <small className="error">{d.extraction_error}</small>}
          </li>
        ))}
      </ul>
    </section>
  );
}
