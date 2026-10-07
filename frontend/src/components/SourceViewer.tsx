import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { getDocumentPage } from "../lib/api";
import { highlightedLines, type SourceGroup } from "../lib/sources";
import { t } from "../i18n";

/** Where an answer's values came from: each record's values, or the uploaded page with quoted rows marked. */
export function SourceViewer({
  groups,
  open,
  onOpenChange,
}: {
  groups: SourceGroup[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content source-viewer" aria-describedby="source-viewer-desc">
          <header className="dialog-header">
            <Dialog.Title>{t("ui.SourceViewer.sources_for_this_answer", "Sources for this answer")}</Dialog.Title>
            <Dialog.Close className="dialog-close" aria-label={t("ui.SourceViewer.close_sources", "Close sources")}>
              ×
            </Dialog.Close>
          </header>
          <p id="source-viewer-desc" className="muted">
            The values Cura used, exactly as recorded.
          </p>
          {groups.map((group) => (
            <section key={group.key} className="source-group" data-testid="source-group">
              <h3>{group.title}</h3>
              {group.items.some((item) => item.value != null || item.referenceRange) ? (
                <table className="findings-table">
                  <thead>
                    <tr>
                      <th>{t("ui.SourceViewer.measurement", "Measurement")}</th>
                      <th>{t("ui.SourceViewer.value", "Value")}</th>
                      <th>{t("ui.SourceViewer.reference", "Reference")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.items.map((item, index) => (
                      <tr key={`${item.label}-${index}`}>
                        <td>{item.label}</td>
                        <td>{item.value != null ? `${item.value}${item.unit ? ` ${item.unit}` : ""}` : "—"}</td>
                        <td>{item.referenceRange || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <ul className="source-items">
                  {group.items.map((item, index) => (
                    <li key={`${item.label}-${index}`}>{item.label}</li>
                  ))}
                </ul>
              )}
              {group.kind === "document" && group.documentId && group.page ? (
                <DocumentPageView
                  documentId={group.documentId}
                  page={group.page}
                  excerpts={group.items.map((item) => item.excerpt || "").filter(Boolean)}
                />
              ) : null}
            </section>
          ))}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function DocumentPageView({ documentId, page, excerpts }: { documentId: string; page: number; excerpts: string[] }) {
  const query = useQuery({
    queryKey: ["document-page", documentId, page],
    queryFn: () => getDocumentPage(documentId, page),
    staleTime: Infinity,
  });
  if (query.isPending) return <p className="muted">Loading page {page}…</p>;
  if (query.isError || !query.data) return <p className="muted">{t("ui.SourceViewer.this_page_isn_t_available_any_more", "This page isn't available any more.")}</p>;
  const lines = query.data.text.split("\n");
  const marked = highlightedLines(query.data.text, excerpts);
  return (
    <figure className="page-view">
      <figcaption className="muted">
        {query.data.filename} · page {query.data.page} of {query.data.page_count}
        {query.data.approximate ? " · text recognised from a scan, may differ slightly" : ""}
      </figcaption>
      <div className="page-text" data-testid="page-text">
        {lines.map((line, index) =>
          marked.has(index) ? (
            <mark key={index} className="page-line">
              {line}
            </mark>
          ) : (
            <span key={index} className="page-line">
              {line || " "}
            </span>
          )
        )}
      </div>
    </figure>
  );
}
