import { useState } from "react";

const STORAGE_KEY = "cura_done_steps";

function readDone(): string[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function writeDone(items: string[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(-200)));
  } catch {
    /* storage unavailable: ticks last for this page only */
  }
}

/** "Worth considering" as a checklist the reader can tick off; ticks are remembered on this device. */
export function NextSteps({ items }: { items: string[] }) {
  const [done, setDone] = useState<string[]>(readDone);
  if (!items.length) return null;

  function toggle(item: string) {
    const next = done.includes(item) ? done.filter((d) => d !== item) : [...done, item];
    setDone(next);
    writeDone(next);
  }

  return (
    <section className="answer-section next-steps">
      <h4>Worth considering</h4>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <label className={done.includes(item) ? "done" : undefined}>
              <input type="checkbox" checked={done.includes(item)} onChange={() => toggle(item)} />
              <span>{item}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
