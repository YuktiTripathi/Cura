import { describe, expect, it } from "vitest";
import { langForText } from "./language";

describe("langForText", () => {
  it("tags Indic-script text and leaves English untagged", () => {
    expect(langForText("नमस्ते, Alex 👋")).toBe("hi");
    expect(langForText("नमस्कार, Alex", "mr")).toBe("mr");
    expect(langForText("ਸਤ ਸ੍ਰੀ ਅਕਾਲ")).toBe("pa");
    expect(langForText("નમસ્તે")).toBe("gu");
    expect(langForText("নমস্কার")).toBe("bn");
    expect(langForText("Your LDL is 138 mg/dL.")).toBeUndefined();
    expect(langForText(null)).toBeUndefined();
  });
});
