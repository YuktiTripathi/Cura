import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { getDocumentFacts, type DocumentFact } from "../../lib/api";
import { fmt } from "../../lib/range";
import { RangeBar } from "../messages/RangeBar";
import { t } from "../../i18n";

/**
 * What Cura read from an uploaded report, row by row, so the user can check it before relying on it,
 * then compare it with their SuperShyft results or ask about it.
 */
export function ReviewValues({
  documentId,
  onOpenChange,
  onCompare,
  onAsk,
}: {
  documentId: string | null;
  onOpenChange: (open: boolean) => void;
  onCompare: (documentId: string) => void;
  onAsk: (documentId: string) => void;
}) {
  const query = useQuery({
    queryKey: ["document-facts", documentId],
    queryFn: () => getDocumentFacts(documentId!),
    enabled: Boolean(documentId),
  });
  const data = query.data;
  return (
    <Dialog.Root open={Boolean(documentId)} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content review-values" aria-describedby="review-values-desc">
          <header className="dialog-header">
            <Dialog.Title>{data ? `Values read from ${data.filename}` : "Values read from your report"}</Dialog.Title>
            <Dialog.Close className="dialog-close" aria-label={t("ui.ReviewValues.close_review", "Close review")}>
              ×
            </Dialog.Close>
          </header>
          <p id="review-values-desc" className="muted">
            Check these against your report. Each value shows the line it came from.
          </p>
          {query.isPending ? <p className="muted">Loading values…</p> : null}
          {query.isError ? <p className="error">{t("ui.ReviewValues.these_values_aren_t_available_right_now", "These values aren't available right now.")}</p> : null}
          {data && !data.facts.length ? (
            <p>{t("ui.ReviewValues.no_measurements_were_found_in_this_repor", "No measurements were found in this report. You can still ask questions about its text.")}</p>
          ) : null}
          {data && data.facts.length ? (
            <ul className="review-list">
              {data.facts.map((fact, index) => (
                <ReviewRow key={`${fact.key}-${index}`} fact={fact} />
              ))}
            </ul>
          ) : null}
          {documentId ? (
            <div className="review-actions">
              <button
                type="button"
                className="testing-option-primary"
                disabled={!data?.facts.length}
                onClick={() => onCompare(documentId)}
              >
                Compare with my SuperShyft results
              </button>
              <button type="button" className="text-button" onClick={() => onAsk(documentId)}>
                Ask about this report
              </button>
            </div>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function ReviewRow({ fact }: { fact: DocumentFact }) {
  const where = [fact.page ? `page ${fact.page}` : null, fact.line ? `line ${fact.line}` : null].filter(Boolean).join(" · ");
  const hasRange = fact.reference_low != null || fact.reference_high != null;
  return (
    <li className="review-row" data-testid="review-row">
      <div className="review-row-head">
        <strong>{fact.label}</strong>
        <span className="review-row-value">
          {fact.value != null ? fmt(fact.value) : "—"}
          {fact.unit ? ` ${fact.unit}` : ""}
        </span>
      </div>
      {hasRange && fact.value != null ? (
        <RangeBar label={fact.label} value={fact.value} unit={fact.unit} low={fact.reference_low} high={fact.reference_high} />
      ) : (
        <span className="muted review-row-norange">{t("ui.ReviewValues.no_reference_range_on_this_line", "No reference range on this line")}</span>
      )}
      {fact.excerpt ? (
        <p className="review-row-quote">
          <span className="muted">{where ? `${where}: ` : ""}</span>“{fact.excerpt}”
        </p>
      ) : null}
    </li>
  );
}
