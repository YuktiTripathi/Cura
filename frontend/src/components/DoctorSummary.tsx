import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { handoffAsText, type DoctorHandoff } from "../lib/companion";

const SECTIONS: Array<[keyof DoctorHandoff, string]> = [
  ["key_findings", "Key findings"],
  ["longitudinal_changes", "Changes over time"],
  ["relevant_context", "Relevant context"],
  ["missing_information", "Not yet available"],
  ["questions_for_clinician", "Questions to ask"],
];

/** A one-page summary to bring to a clinician: print it or copy it into a message. */
export function DoctorSummary({
  handoff,
  open,
  onOpenChange,
}: {
  handoff: DoctorHandoff | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [copied, setCopied] = useState(false);
  if (!handoff) return null;
  const preparedOn = new Date();

  async function copy() {
    try {
      await navigator.clipboard.writeText(handoffAsText(handoff!, preparedOn));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked */
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content doctor-summary" aria-describedby="doctor-summary-desc">
          <header className="dialog-header">
            <Dialog.Title>Summary for my doctor</Dialog.Title>
            <Dialog.Close className="dialog-close no-print" aria-label="Close summary">
              ×
            </Dialog.Close>
          </header>
          <p id="doctor-summary-desc" className="muted">
            Prepared with Cura on {preparedOn.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })} from
            your own records. Educational, not a diagnosis.
          </p>
          {SECTIONS.map(([key, title]) =>
            handoff[key].length ? (
              <section key={key} className="doctor-summary-section">
                <h3>{title}</h3>
                <ul>
                  {handoff[key].map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            ) : null
          )}
          <div className="doctor-summary-actions no-print">
            <button type="button" className="testing-option-primary" onClick={() => window.print()}>
              Print
            </button>
            <button type="button" className="text-button" onClick={() => void copy()}>
              {copied ? "Copied" : "Copy as text"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
