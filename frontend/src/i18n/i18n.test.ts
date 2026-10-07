import { afterEach, describe, expect, it } from "vitest";
import hi from "./messages/hi.json";
import hinglish from "./messages/hinglish.json";
import { __setLocaleForTests, t } from "./index";
import { processingCopy } from "../lib/processingMessages";

afterEach(() => __setLocaleForTests("en"));

describe("i18n", () => {
  it("falls back to the inline English text", () => {
    expect(t("missing.key", "Hello {name}", { name: "Asha" })).toBe("Hello Asha");
  });

  it("translates when the locale has the key", () => {
    __setLocaleForTests("hi");
    expect(t("composer.placeholder", "Ask Cura about your health")).toBe(hi["composer.placeholder"]);
  });

  it("localizes progress messages by message_key", () => {
    __setLocaleForTests("hinglish");
    expect(processingCopy({ stage: "PLANNING", message_key: "planning" })).toBe(hinglish["progress.planning"]);
  });

  it("keeps the same keys and placeholders in every language", () => {
    const keys = (d: Record<string, string>) => Object.keys(d).sort();
    expect(keys(hi)).toEqual(keys(hinglish));
    for (const key of Object.keys(hi)) {
      const holes = (s: string) => (s.match(/\{\w+\}/g) || []).sort().join();
      expect(holes((hi as Record<string, string>)[key])).toBe(holes((hinglish as Record<string, string>)[key]));
    }
  });
});
