import { FormEvent, useEffect, useRef, useState, type ChangeEvent, type RefObject } from "react";
import { transcribeVoice, getDocument, uploadDocument, type UploadedDocument } from "../lib/api";

type Props = {
  disabled: boolean;
  onSend: (value: string, documentIds?: string[]) => void;
  inputRef?: RefObject<HTMLInputElement>;
  language?: string;
  conversationId?: string | null;
  onUploaded?: () => void;
};

type Chip = {
  localName: string;
  status: "uploading" | "uploaded" | "failed";
  document?: UploadedDocument;
};

export function Composer({
  disabled,
  onSend,
  inputRef,
  language = "auto",
  conversationId = null,
  onUploaded,
}: Props) {
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [chip, setChip] = useState<Chip | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      mediaRef.current?.stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = value.trim();
    if (!text) return;
    const ids = chip?.status === "uploaded" && chip.document ? [chip.document.document_id] : [];
    onSend(text, ids);
    setValue("");
  }

  async function runUpload(file: File) {
    setChip({ localName: file.name, status: "uploading" });
    setPendingFile(file);
    try {
      const doc = await uploadDocument(file, conversationId);
      setChip({ localName: file.name, status: "uploaded", document: doc });
      setPendingFile(null);
      onUploaded?.();
      if (doc.extraction_status === "processing" || doc.extraction_status === "not_started") {
        void pollExtraction(doc.document_id, file.name);
      }
    } catch {
      setChip({ localName: file.name, status: "failed" });
    }
  }

  async function pollExtraction(documentId: string, name: string) {
    for (let i = 0; i < 30; i += 1) {
      await new Promise((r) => setTimeout(r, 1000));
      try {
        const doc = await getDocument(documentId);
        if (doc.extraction_status === "failed") {
          setChip({ localName: name, status: "uploaded", document: doc });
          onUploaded?.();
          return;
        }
        if (doc.structured_facts_ready || doc.extraction_status === "completed") {
          setChip({ localName: name, status: "uploaded", document: doc });
          onUploaded?.();
          const idx = doc.pageindex_status;
          if (!idx || (idx !== "BUILDING" && idx !== "NOT_STARTED")) return;
        }
      } catch {
        return;
      }
    }
  }

  function chipSub(chip: Chip): string {
    const ex = chip.document?.extraction_status;
    if (chip.status === "uploading") return "Uploading…";
    if (chip.status === "failed") return "Upload failed — ";
    if (ex === "processing" || ex === "not_started") return "Processing…";
    if (chip.document?.structured_facts_ready && chip.document.pageindex_status === "BUILDING") {
      return "Measurements ready";
    }
    if (ex === "completed") return "Ready";
    if (ex === "failed") return "Could not read";
    return "Uploaded";
  }

  function onPickFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    void runUpload(file);
  }

  function pickMimeType(): string {
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
    for (const type of candidates) {
      try {
        if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type)) return type;
      } catch {
        /* ignore */
      }
    }
    return "";
  }

  async function startRecording() {
    setVoiceError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setVoiceError("Voice input isn't available in this browser. You can continue by typing your message.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data.size) chunksRef.current.push(ev.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType || "audio/webm" });
        if (!blob.size) {
          setVoiceError("I couldn't clearly transcribe that. Please try again or type your message.");
          return;
        }
        setTranscribing(true);
        try {
          const result = await transcribeVoice(blob, language);
          const text = (result.transcript || result.text || "").trim();
          if (!text) {
            setVoiceError("I couldn't clearly transcribe that. Please try again or type your message.");
            return;
          }
          setValue(text);
        } catch (err) {
          setVoiceError(
            err instanceof Error && /microphone|permission/i.test(err.message)
              ? err.message
              : "I couldn't clearly transcribe that. Please try again or type your message."
          );
        } finally {
          setTranscribing(false);
        }
      };
      mediaRef.current = recorder;
      recorder.start(250);
      setRecording(true);
      setElapsed(0);
      timerRef.current = window.setInterval(() => {
        setElapsed((s) => {
          if (s + 1 >= 60) {
            window.setTimeout(() => mediaRef.current?.stop(), 0);
            return 60;
          }
          return s + 1;
        });
      }, 1000);
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setVoiceError("I couldn't access your microphone. Check your browser permission and try again.");
      } else {
        setVoiceError("Voice input isn't available in this browser. You can continue by typing your message.");
      }
    }
  }

  function stopRecording() {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setRecording(false);
    mediaRef.current?.stop();
  }

  return (
    <form className="composer" onSubmit={submit}>
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf,.pdf"
        hidden
        onChange={onPickFile}
      />
      <button
        type="button"
        className="attach"
        disabled={disabled || transcribing}
        onClick={() => fileRef.current?.click()}
        aria-label="Attach PDF"
      >
        📎
      </button>
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={
          transcribing ? "Turning your voice into text…" : recording ? "Listening…" : "Ask Cura about your health"
        }
        disabled={disabled || transcribing}
      />
      <button
        type="button"
        className={recording ? "mic recording" : "mic"}
        disabled={disabled || transcribing}
        onClick={recording ? stopRecording : startRecording}
        aria-label={recording ? "Stop recording" : "Start voice input"}
        data-voice-engine="record-transcribe"
      >
        {recording ? `Stop ${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}` : transcribing ? "…" : "🎙"}
      </button>
      <button type="submit" disabled={disabled || transcribing}>
        Send
      </button>
      {chip && (
        <div className="attach-chip">
          <span>📄 {chip.localName}</span>
          <span className="muted">
            {chipSub(chip)}
          </span>
          {chip.status === "failed" && pendingFile && (
            <button type="button" onClick={() => pendingFile && void runUpload(pendingFile)}>
              Retry
            </button>
          )}
          <button type="button" onClick={() => { setChip(null); setPendingFile(null); }} aria-label="Remove attachment">
            ×
          </button>
        </div>
      )}
      {voiceError && <p className="error voice-error">{voiceError}</p>}
    </form>
  );
}
