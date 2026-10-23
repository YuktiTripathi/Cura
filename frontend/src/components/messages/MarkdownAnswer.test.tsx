import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownAnswer, parseMarkdown } from "./MarkdownAnswer";

describe("MarkdownAnswer", () => {
  it("renders short prose as a paragraph with bold", () => {
    const { container } = render(<MarkdownAnswer content={"Your HbA1c is **9.1%**, above your report's range."} />);
    expect(container.querySelector("p")?.textContent).toContain("Your HbA1c is 9.1%");
    expect(container.querySelector("strong")?.textContent).toBe("9.1%");
    expect(container.querySelector("ul, ol, table, h3")).toBeNull();
  });

  it("renders a numbered ranking with indented detail lines", () => {
    const md = "The three areas I'd focus on:\n\n1. **Blood sugar**\n   HbA1c and glucose are both high.\n2. **Triglycerides**\n3. **Iron pattern**";
    const { container } = render(<MarkdownAnswer content={md} />);
    const items = container.querySelectorAll("ol > li");
    expect(items.length).toBe(3);
    expect(items[0].textContent).toContain("HbA1c and glucose are both high.");
  });

  it("renders bullets, headings and a small comparison table", () => {
    const md = "### Change since May\n\n| Marker | May | Aug |\n|---|---|---|\n| HbA1c | 9.6% | 9.1% |\n\n- improving\n- still above range";
    const { container } = render(<MarkdownAnswer content={md} />);
    expect(container.querySelector("h3, h4")?.textContent).toBe("Change since May");
    expect(container.querySelectorAll("tbody tr").length).toBe(1);
    expect(container.querySelectorAll("ul > li").length).toBe(2);
  });

  it("never injects HTML", () => {
    const { container } = render(<MarkdownAnswer content={"<img src=x onerror=alert(1)> hello"} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img");
  });

  it("keeps a closing question outside the bullet list", () => {
    const md = "- Iron is low.\n\nWould you like a summary of the lipid results?";
    const blocks = parseMarkdown(md);
    expect(blocks.map((block) => block.kind)).toEqual(["ul", "p"]);
    expect(blocks[1]).toMatchObject({ kind: "p" });
  });

  it("splits bullets that were written on the same line", () => {
    const { container } = render(
      <MarkdownAnswer content={"These conditions include: * A large waistline. * High blood pressure."} />,
    );
    expect(container.querySelectorAll("ul > li").length).toBe(2);
  });

  it("parses different shapes as different blocks", () => {
    expect(parseMarkdown("One line answer.").map((b) => b.kind)).toEqual(["p"]);
    expect(parseMarkdown("Intro\n\n- a\n- b").map((b) => b.kind)).toEqual(["p", "ul"]);
  });
});
