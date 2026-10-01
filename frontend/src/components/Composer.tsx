import { FormEvent, useEffect, useRef, useState, type ChangeEvent, type RefObject } from "react";
import { transcribeVoice } from "../lib/api";
import { useDocumentUpload, type DocumentUploader, type UploadChip } from "../hooks/useDocumentUpload";
import { useAudioLevels } from "../hooks/useAudioLevels";

type Props = {
  disabled: boolean;
  onSend: (value: string, documentIds?: string[]) => void;
  inputRef?: RefObject<HTMLInputElement>;
  language?: string;
  conversationId?: string | null;
  onUploaded?: () => void;
  /** Shared uploader (e.g. with a page-wide drop zone). The composer uses its own when absent. */
  uploader?: DocumentUploader;
  /** Opens the extracted-values review for an uploaded document. */
  onReview?: (documentId: string) => void;
  /** False when the server has no speech-to-text configured: the microphone is not offered. */
  voiceEnabled?: boolean;
};

export function Composer({
  disabled,
  onSend,
  inputRef,
  language = "auto",
  conversationId = null,
  onUploaded,
  uploader: sharedUploader,
  onReview,
  voiceEnabled = true,
}: Props) {
  const ownUploader = useDocumentUpload(conversationId, onUploaded);
  const uploader = sharedUploader ?? ownUploader;
  const chip = uploader.chip;
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [liveStream, setLiveStream] = useState<MediaStream | null>(null);
  const levels = useAudioLevels(liveStream);
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

  function chipSub(chip: UploadChip): string {
    const ex = chip.document?.extraction_status;
    if (chip.status === "uploading") return "Uploading…";
    if (chip.status === "failed") return chip.error ? `${chip.error} ` : "Upload failed — ";
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
    void uploader.upload(file);
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
        setLiveStream(null);
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
      setLiveStream(stream);
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
        id="cura-message-input"
        aria-label="Message Cura"
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={
          transcribing ? "Turning your voice into text…" : recording ? "Listening…" : "Ask Cura about your health"
        }
        disabled={disabled || transcribing}
      />
      {recording && levels.length > 0 ? (
        <span className="waveform" aria-hidden="true" data-testid="waveform">
          {levels.map((level, index) => (
            <span key={index} style={{ height: `${Math.max(12, level * 100)}%` }} />
          ))}
        </span>
      ) : null}
      {recording ? (
        <span className="visually-hidden" role="status">
          Recording. Press Stop when you're done.
        </span>
      ) : null}
      {voiceEnabled || recording ? (
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
      ) : null}
      <button type="submit" disabled={disabled || transcribing}>
        Send
      </button>
      {chip && (
        <div className="attach-chip">
          <span>📄 {chip.localName}</span>
          <span className="muted">
            {chipSub(chip)}
          </span>
          {chip.status === "failed" && !chip.error && (
            <button type="button" onClick={uploader.retry}>
              Retry
            </button>
          )}
          {onReview && chip.document && (chip.document.structured_facts_ready || chip.document.extraction_status === "completed") ? (
            <button type="button" onClick={() => onReview(chip.document!.document_id)}>
              Review values
            </button>
          ) : null}
          <button type="button" onClick={uploader.clear} aria-label="Remove attachment">
            ×
          </button>
        </div>
      )}
      {voiceError && <p className="error voice-error">{voiceError}</p>}
    </form>
  );
}
