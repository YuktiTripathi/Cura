export type VoiceStatus = "idle" | "listening" | "unsupported" | "permission_denied" | "error";

export const SPEECH_LANGUAGES: Record<string, string> = {
  en: "en-IN",
  hi: "hi-IN",
  mr: "mr-IN",
  pa: "pa-IN",
  gu: "gu-IN",
  bn: "bn-IN",
  ta: "ta-IN",
  te: "te-IN",
  kn: "kn-IN",
  ml: "ml-IN",
  ur: "ur-IN",
};

export const SPEECH_RETRY_LANGS = ["hi-IN", "en-IN", "mr-IN", "gu-IN", "pa-IN", "bn-IN"] as const;

export function speechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function preferredSpeechLanguage(navLang?: string): string {
  const raw = (
    navLang ||
    (typeof navigator !== "undefined" ? navigator.language || navigator.languages?.[0] : "") ||
    "en-IN"
  ).toLowerCase();
  const prefix = raw.slice(0, 2);
  if (SPEECH_LANGUAGES[prefix]) return SPEECH_LANGUAGES[prefix];
  if (raw.includes("-in")) return raw;
  return "en-IN";
}

export function speechLanguage(code?: string, navLang?: string): string {
  if (code && code !== "auto" && SPEECH_LANGUAGES[code]) return SPEECH_LANGUAGES[code];
  return preferredSpeechLanguage(navLang);
}

export function speechRetryLanguages(preferred: string): string[] {
  return [preferred, ...SPEECH_RETRY_LANGS.filter((item) => item !== preferred)].slice(0, 3);
}

export type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onstart: ((this: SpeechRecognitionLike, ev: Event) => void) | null;
  onresult: ((this: SpeechRecognitionLike, ev: SpeechRecognitionResultEventLike) => void) | null;
  onerror: ((this: SpeechRecognitionLike, ev: { error: string }) => void) | null;
  onend: ((this: SpeechRecognitionLike, ev: Event) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

export type SpeechRecognitionResultEventLike = {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
};

export function transcriptFromEvent(event: SpeechRecognitionResultEventLike): { interim: string; finalText: string } {
  let interim = "";
  let finalText = "";
  for (let i = event.resultIndex; i < event.results.length; i += 1) {
    const piece = event.results[i][0]?.transcript || "";
    if (event.results[i].isFinal) finalText += piece;
    else interim += piece;
  }
  return { interim: interim.trim(), finalText: finalText.trim() };
}

export function voiceErrorMessage(status: VoiceStatus, detail?: string): string {
  if (status === "unsupported") {
    return "Voice input isn't available in this browser. You can continue by typing your message.";
  }
  if (status === "permission_denied") {
    return "Microphone access is blocked. Allow microphone access in your browser settings or continue typing.";
  }
  if (detail === "no-speech") {
    return "I couldn't hear a question. Please try again or type your message.";
  }
  if (detail === "network") {
    return "The browser speech service isn't available. Use the mic to record, then stop so Cura can transcribe it, or type your question.";
  }
  return "Voice input failed. You can continue by typing your message.";
}

export function logVoiceEvent(event: string, extra?: Record<string, string | boolean | number | undefined>): void {
  if (typeof console === "undefined" || typeof console.debug !== "function") return;
  console.debug("cura.voice", { event, ...extra });
}
