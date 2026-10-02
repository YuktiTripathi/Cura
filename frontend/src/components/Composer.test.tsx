import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";

const transcribeVoice = vi.fn();

vi.mock("../lib/api", () => ({
  transcribeVoice: (...args: unknown[]) => transcribeVoice(...args),
  getDocument: vi.fn(),
  uploadDocument: vi.fn(),
}));

function installRecorder() {
  const tracks = [{ stop: vi.fn() }];
  const stream = { getTracks: () => tracks };
  class FakeRecorder {
    mimeType = "audio/webm";
    ondataavailable: ((ev: { data: Blob }) => void) | null = null;
    onstop: (() => void) | null = null;
    start = vi.fn();
    stream = stream;
    stop = vi.fn(() => {
      this.ondataavailable?.({ data: new Blob(["abc"], { type: "audio/webm" }) });
      void this.onstop?.();
    });
  }
  (FakeRecorder as unknown as { isTypeSupported: (type: string) => boolean }).isTypeSupported = () => true;
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue(stream) },
  });
  return { FakeRecorder };
}

describe("Composer voice input", () => {
  beforeEach(() => {
    transcribeVoice.mockReset();
    installRecorder();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders the microphone button", () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);
    expect(screen.getByLabelText("Start voice input")).toBeTruthy();
  });

  it("records locally and inserts the Whisper transcript", async () => {
    transcribeVoice.mockResolvedValue({ transcript: "मेरा कोलेस्ट्रॉल कितना है?", detected_language: "hi", confidence: 0.9 });
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);
    fireEvent.click(screen.getByLabelText("Start voice input"));
    await waitFor(() => expect(screen.getByLabelText("Stop recording")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("Stop recording"));
    await waitFor(() =>
      expect((screen.getByPlaceholderText("Ask Cura about your health") as HTMLInputElement).value).toBe(
        "मेरा कोलेस्ट्रॉल कितना है?"
      )
    );
    expect(transcribeVoice).toHaveBeenCalled();
    fireEvent.submit(screen.getByPlaceholderText("Ask Cura about your health").closest("form") as HTMLFormElement);
    expect(onSend).toHaveBeenCalledWith("मेरा कोलेस्ट्रॉल कितना है?", []);
  });

  it("explains permission denial", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockRejectedValue(Object.assign(new DOMException("denied", "NotAllowedError"))),
      },
    });
    render(<Composer disabled={false} onSend={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Start voice input"));
    await waitFor(() => expect(screen.getByText(/I couldn't access your microphone/i)).toBeTruthy());
  });

  it("explains an unsupported browser", () => {
    vi.stubGlobal("MediaRecorder", undefined);
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
    render(<Composer disabled={false} onSend={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Start voice input"));
    expect(screen.getByText(/isn't available in this browser/i)).toBeTruthy();
  });

  it("does not use Chrome SpeechRecognition network errors", async () => {
    function SpeechRecognition() {
      return { start: vi.fn(), stop: vi.fn() };
    }
    vi.stubGlobal("SpeechRecognition", SpeechRecognition);
    transcribeVoice.mockResolvedValue({ transcript: "HDL vs LDL", detected_language: "en", confidence: 0.8 });
    render(<Composer disabled={false} onSend={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Start voice input"));
    await waitFor(() => expect(screen.getByLabelText("Stop recording")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("Stop recording"));
    await waitFor(() => expect(transcribeVoice).toHaveBeenCalled());
    expect(screen.queryByText(/lost its connection/i)).toBeNull();
  });
});

describe("Composer voice availability", () => {
  afterEach(() => cleanup());

  it("does not offer the microphone when the server has no speech-to-text", () => {
    render(<Composer disabled={false} onSend={vi.fn()} voiceEnabled={false} />);
    expect(screen.queryByLabelText("Start voice input")).toBeNull();
    expect(screen.getByLabelText("Attach PDF")).toBeTruthy();
  });
});
