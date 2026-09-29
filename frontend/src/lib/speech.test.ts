import { afterEach, describe, expect, it, vi } from "vitest";
import { speechLanguage, speechRecognitionCtor, transcriptFromEvent, voiceErrorMessage } from "./speech";

describe("speech helpers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps CURA languages to SpeechRecognition tags", () => {
    expect(speechLanguage("auto", "en-US")).toBe("en-IN");
    expect(speechLanguage("auto", "hi-IN")).toBe("hi-IN");
    expect(speechLanguage("hi")).toBe("hi-IN");
    expect(speechLanguage("en")).toBe("en-IN");
  });

  it("detects unsupported browsers", () => {
    vi.stubGlobal("window", {});
    expect(speechRecognitionCtor()).toBeNull();
    expect(voiceErrorMessage("unsupported")).toMatch(/isn't available in this browser/i);
  });

  it("classifies permission and recognition errors", () => {
    expect(voiceErrorMessage("permission_denied")).toMatch(/blocked/i);
    expect(voiceErrorMessage("error", "network")).toMatch(/isn't available/i);
  });

  it("extracts interim and final transcripts", () => {
    const event = {
      resultIndex: 0,
      results: [
        { isFinal: false, 0: { transcript: "What is " } },
        { isFinal: true, 0: { transcript: "What is LDL" } },
      ],
    };
    expect(transcriptFromEvent(event)).toEqual({ interim: "What is", finalText: "What is LDL" });
  });
});
