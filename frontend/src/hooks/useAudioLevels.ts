import { useEffect, useState } from "react";

const BARS = 24;

/**
 * Rolling microphone loudness (0–1) for a live waveform. Returns an empty array when there is no
 * stream or the browser has no Web Audio (the recorder still works without the visual).
 */
export function useAudioLevels(stream: MediaStream | null): number[] {
  const [levels, setLevels] = useState<number[]>([]);

  useEffect(() => {
    const Ctx: typeof AudioContext | undefined =
      typeof window !== "undefined" ? window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext : undefined;
    if (!stream || !Ctx) {
      setLevels([]);
      return;
    }
    let ctx: AudioContext;
    try {
      ctx = new Ctx();
    } catch {
      return;
    }
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const samples = new Uint8Array(analyser.fftSize);
    let frame = 0;
    let last = 0;
    const history: number[] = [];
    const tick = (time: number) => {
      frame = requestAnimationFrame(tick);
      if (time - last < 60) return;
      last = time;
      analyser.getByteTimeDomainData(samples);
      let sum = 0;
      for (const s of samples) sum += ((s - 128) / 128) ** 2;
      const rms = Math.sqrt(sum / samples.length);
      history.push(Math.min(1, rms * 4));
      if (history.length > BARS) history.shift();
      setLevels([...history]);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      void ctx.close().catch(() => undefined);
    };
  }, [stream]);

  return levels;
}
