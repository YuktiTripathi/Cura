import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PresentedAnswer } from "./PresentedAnswer";

describe("PresentedAnswer", () => {
  it("renders educational markdown as headings and bullets, not raw asterisks", () => {
    const { container } = render(
      <PresentedAnswer
        presentation={{
          mode: "INTERPRETATION",
          summary:
            "Heart health means how well the heart moves blood.\n\n**Key factors**\n\n- Blood pressure stays steady.\n- Vessels stay flexible.",
          findings: [],
          uncertainties: [],
          next_steps: [],
        }}
        fallback=""
      />
    );
    expect(container.querySelector("strong")?.textContent).toBe("Key factors");
    expect(container.querySelectorAll("ul > li").length).toBe(2);
    expect(container.textContent).not.toContain("**");
    expect(container.textContent).not.toContain("* Blood");
  });

  it("keeps a safety answer visible and does not invent a biomarker card", () => {
    const { container } = render(
      <PresentedAnswer
        presentation={{ mode: "SAFETY", summary: "Please seek urgent care.", findings: [], uncertainties: [], next_steps: [] }}
        fallback=""
      />
    );
    expect(container.querySelector(".safety-notice")).toBeTruthy();
    expect(container.textContent).toContain("Please seek urgent care.");
    expect(container.querySelector(".value-cards")).toBeNull();
  });
});
