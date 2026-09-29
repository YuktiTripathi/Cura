import { useEffect, useRef, useState } from "react";
import {
  logVoiceEvent,
  speechLanguage,
  speechRecognitionCtor,
  speechRetryLanguages,
  transcriptFromEvent,
  voiceErrorMessage,
  type SpeechRecognitionLike,
  type VoiceStatus,
} from "../lib/speech";

type Options = {
  language?: string;
  onFinal?: (text: string) => void;
  onInterim?: (text: string) => void;
};

export function useSpeechInput({ language = "auto", onFinal, onInterim }: Options) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const onFinalRef = useRef(onFinal);
  const onInterimRef = useRef(onInterim);
  const wantListenRef = useRef(false);
  const langsRef = useRef<string[]>([]);
  const attemptRef = useRef(0);
  const retryingRef = useRef(false);
  onFinalRef.current = onFinal;
  onInterimRef.current = onInterim;

  useEffect(() => {
    return () => {
      wantListenRef.current = false;
      recRef.current?.abort();
      recRef.current = null;
    };
  }, []);

  function stop() {
    wantListenRef.current = false;
    retryingRef.current = false;
    recRef.current?.stop();
  }

  function begin(lang: string) {
    const Ctor = speechRecognitionCtor();
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = lang;
    rec.interimResults = true;
    rec.continuous = true;
    rec.maxAlternatives = 3;
    rec.onstart = () => {
      setStatus("listening");
      logVoiceEvent("started", { browser_support: true, language: lang });
    };
    rec.onresult = (event) => {
      attemptRef.current = langsRef.current.length;
      const { interim, finalText } = transcriptFromEvent(event);
      if (interim) onInterimRef.current?.(interim);
      if (finalText) onFinalRef.current?.(finalText);
    };
    rec.onerror = (event) => {
      const code = event.error || "error";
      if (code === "aborted") return;
      if (code === "not-allowed") {
        wantListenRef.current = false;
        setStatus("permission_denied");
        setError(voiceErrorMessage("permission_denied"));
        logVoiceEvent("error", { category: code, permission_denied: true });
        return;
      }
      const canRetry = wantListenRef.current && code === "network" && attemptRef.current < langsRef.current.length - 1;
      if (canRetry) {
        retryingRef.current = true;
        attemptRef.current += 1;
        logVoiceEvent("retry", { category: code, language: langsRef.current[attemptRef.current] });
        return;
      }
      wantListenRef.current = false;
      setStatus("error");
      setError(voiceErrorMessage("error", code));
      logVoiceEvent("error", { category: code });
    };
    rec.onend = () => {
      recRef.current = null;
      if (wantListenRef.current && retryingRef.current) {
        retryingRef.current = false;
        begin(langsRef.current[attemptRef.current] || lang);
        return;
      }
      setStatus((current) => (current === "listening" ? "idle" : current));
      logVoiceEvent("ended", { browser_support: true });
    };
    recRef.current = rec;
    try {
      rec.start();
    } catch {
      setStatus("error");
      setError(voiceErrorMessage("error"));
      logVoiceEvent("error", { category: "start_failed" });
    }
  }

  function start() {
    setError(null);
    const Ctor = speechRecognitionCtor();
    if (!Ctor) {
      setStatus("unsupported");
      setError(voiceErrorMessage("unsupported"));
      logVoiceEvent("unsupported", { browser_support: false });
      return;
    }
    wantListenRef.current = true;
    retryingRef.current = false;
    langsRef.current = speechRetryLanguages(speechLanguage(language));
    attemptRef.current = 0;
    recRef.current?.abort();
    recRef.current = null;
    begin(langsRef.current[0]);
  }

  return {
    status,
    error,
    supported: Boolean(speechRecognitionCtor()),
    start,
    stop,
    listening: status === "listening",
  };
}
