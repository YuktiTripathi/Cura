import type { UserProvenance } from "../../types/chat";
import { debugMode } from "./debug";
import { t } from "../../i18n";

export function ProvenanceLine({
  provenance,
  findings,
}: {
  provenance?: UserProvenance;
  findings?: Array<{ source_id?: string | null; source_label?: string | null }>;
}) {
  const sources = provenance?.sources || [];
  if (!sources.length) return null;
  const debug = debugMode();
  return (
    <details className="source-details">
      <summary className="source-line" data-testid="provenance-line">
        {t("ui.ProvenanceLine.view_sources", "View sources")}
      </summary>
      <div className="source-debug" data-testid="provenance-debug">
        {sources.map((source, index) => (
          <p key={`${source.name}-${index}`}>
            {source.url ? (
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.name}
              </a>
            ) : (
              source.name
            )}
          </p>
        ))}
        {debug
          ? sources.map((source, index) => (
              <p key={`${source.source_id || source.name}-${index}`}>
                {source.name}
                {source.source_id ? ` · ${source.source_id}` : ""}
              </p>
            ))
          : findings?.some((item) => item.source_label) ? (
              findings
                .filter((item) => item.source_label)
                .filter((item, index, all) => all.findIndex((row) => row.source_label === item.source_label) === index)
                .map((item) => <p key={item.source_label || ""}>{item.source_label}</p>)
            ) : (
              <p>{t("ui.ProvenanceLine.internal_record_identifiers_are_hidden_d", "Internal record identifiers are hidden. Dates above identify the report that was used.")}</p>
            )}
      </div>
    </details>
  );
}
