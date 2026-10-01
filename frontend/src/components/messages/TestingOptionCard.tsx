import { useState } from "react";
import { openSuperShyftPackage } from "../../lib/packageActions";
import type { PackageAction, TestingOption } from "../../types/chat";

export function TestingOptionCard({ option }: { option: TestingOption }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const name = option.package?.name || option.display_name;
  const reason = option.reason || option.medical_rationale || "";
  const headline = option.headline || "A test that may help clarify this";
  const primary = option.primary_action || {
    type: "OPEN_PACKAGE" as const,
    label: `View ${name}`,
    package_id: option.package?.id || option.catalog_id,
    catalog_kind: option.package?.kind || option.kind,
  };
  const comparison = option.comparison;
  const relevance = option.relevance || "OPTIONAL";
  const alreadyHave =
    comparison?.already_have?.length
      ? comparison.already_have
      : (option.already_recent || []).map((label) => ({ key: label, label, measured_on: null }));

  function runAction(action: PackageAction) {
    if (action.type === "COMPARE_WITH_EXISTING_RESULTS") {
      setDetailsOpen(true);
      return;
    }
    const packageId = action.package_id || option.package?.id || option.catalog_id;
    if (action.type === "OPEN_PACKAGE" && packageId) {
      openSuperShyftPackage(action.catalog_kind || option.kind, packageId);
    }
  }

  return (
    <section
      className={`testing-option testing-option-${relevance.toLowerCase()}`}
      data-testid="testing-option"
      data-relevance={relevance}
    >
      <p className="testing-option-headline">{headline}</p>
      <p className="testing-option-name">
        <strong>{name}</strong>
      </p>
      {reason ? <p className="testing-option-reason">{reason}</p> : null}
      <div className="testing-option-actions">
        <button
          type="button"
          className="testing-option-primary"
          data-testid="package-primary-cta"
          onClick={() => runAction(primary)}
        >
          {primary.label}
        </button>
        {option.secondary_action ? (
          <button
            type="button"
            className="text-button"
            data-testid="package-secondary-cta"
            onClick={() => runAction(option.secondary_action!)}
          >
            {option.secondary_action.label}
          </button>
        ) : null}
        <button
          type="button"
          className="text-button"
          data-testid="package-details-toggle"
          onClick={() => setDetailsOpen((value) => !value)}
        >
          {detailsOpen ? "Hide details" : "Details"}
        </button>
      </div>
      {detailsOpen ? (
        <div className="testing-option-details" data-testid="package-details">
          {option.helps_answer ? (
            <p>
              <strong>Helps answer: </strong>
              {option.helps_answer}
            </p>
          ) : null}
          {(option.relevant_tests || []).length > 0 ? (
            <div>
              <h4>Relevant tests</h4>
              <ul>
                {(option.relevant_tests || []).map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {alreadyHave.length > 0 ? (
            <div>
              <h4>Already in your reports</h4>
              <ul>
                {alreadyHave.map((item) => (
                  <li key={item.key}>
                    {item.label}
                    {item.measured_on ? ` · ${item.measured_on}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {(comparison?.adds_information || []).length > 0 ? (
            <div>
              <h4>Would add new information</h4>
              <ul>
                {comparison!.adds_information.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {comparison?.timing_note ? <p className="muted">{comparison.timing_note}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
