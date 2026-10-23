import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WelcomeExperience } from "./WelcomeExperience";

describe("WelcomeExperience", () => {
  it("uses the authenticated greeting and hides report cards when data is absent", () => {
    render(
      <WelcomeExperience
        me={{ greeting: "Hi Neha", capabilities: { has_blood_report: false, has_bio_ai_report: false, has_nutrition: false }, starters: { personal: [], general: [{ text: "What is insulin resistance?" }] } } as never}
        meLoading={false}
        onSend={() => undefined}
        inputRef={createRef()}
      />
    );
    expect(screen.getByText("Hi Neha")).toBeTruthy();
    expect(screen.queryByText("My Blood Report")).toBeNull();
    expect(screen.getByText("Ask Cura")).toBeTruthy();
    expect(screen.getByText("What is insulin resistance?")).toBeTruthy();
  });
});
