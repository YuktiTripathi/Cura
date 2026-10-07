import { useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, listDocuments, type UploadedDocument } from "../lib/api";
import { queryKeys } from "../lib/queryClient";
import { useRefetchOnChange } from "../hooks/useRefetchOnChange";
import { t } from "../i18n";

const POLL_MS = 2000;

type Props = {
  refreshKey: number;
  selected: string[];
  onSelectedChange: (ids: string[]) => void;
  /** Opens the extracted-values review for a ready document. */
  onReview?: (documentId: string) => void;
};

function statusLabel(doc: UploadedDocument): string {
  if (doc.extraction_status === "failed") return "Could not read";
  if (doc.structured_facts_ready && doc.pageindex_status === "BUILDING") return "Measurements ready";
  if (doc.extraction_status === "completed" || doc.structured_facts_ready) return "Ready";
  if (doc.extraction_status === "processing" || doc.extraction_status === "not_started") return "Processing…";
  return "Uploaded";
}

export function isStillProcessing(doc: UploadedDocument): boolean {
  return (
    doc.extraction_status === "processing" ||
    doc.extraction_status === "not_started" ||
    (Boolean(doc.structured_facts_ready) && doc.pageindex_status === "BUILDING")
  );
}

export function DocumentPanel({ refreshKey, selected, onSelectedChange, onReview }: Props) {
  const client = useQueryClient();
  const { data: docs = [] } = useQuery({
    queryKey: queryKeys.documents,
    queryFn: () => listDocuments().catch(() => [] as UploadedDocument[]),
    // Poll only while a document is still being processed.
    refetchInterval: (query) => ((query.state.data || []).some(isStillProcessing) ? POLL_MS : false),
  });
  useRefetchOnChange(queryKeys.documents, refreshKey);

  if (!docs.length) return null;

  return (
    <section className="doc-panel">
      <h2>{t("ui.DocumentPanel.uploaded_documents", "Uploaded Documents")}</h2>
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
              {onReview && (d.structured_facts_ready || d.extraction_status === "completed") ? (
                <>
                  <button type="button" className="text-button" onClick={() => onReview(d.document_id)}>
                    Review values
                  </button>
                  {" · "}
                </>
              ) : null}
              <button
                type="button"
                className="text-button"
                onClick={async () => {
                  await deleteDocument(d.document_id);
                  onSelectedChange(selected.filter((id) => id !== d.document_id));
                  client.setQueryData<UploadedDocument[]>(queryKeys.documents, (current = []) =>
                    current.filter((row) => row.document_id !== d.document_id)
                  );
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
