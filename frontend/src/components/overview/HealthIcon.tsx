const PATHS: Record<string, string> = {
  heart: "M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10zM7 12h2l1.5-2.5L13 14l1.5-2H17",
  liver: "M4 10c0-3 3-5 8-5 5 0 8 2 8 5 0 4-4 8-9 8-4 0-7-3-7-8zM9 11h4",
  drops: "M9 4s4 4.5 4 7.5a4 4 0 0 1-8 0C5 8.500 9 4 9 4zM17 12s3 3 3 5.200a3 3 0 0 1-6 0C14 15 17 12 17 12z",
  kidney: "M8 4a4 4 0 0 0-4 4c0 5 2 11 6 11a3 3 0 0 0 3-3c0-2-2-2-2-4s2-2 2-4a4 4 0 0 0-5-4z",
  blood: "M12 3s6 6.500 6 11a6 6 0 0 1-12 0c0-4.500 6-11 6-11z",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.500 1.500M17.500 17.500L19 19M5 19l1.500-1.500M17.500 6.500L19 5",
  thyroid: "M12 5c-3 0-4 2-4 4 0 3 2 6 4 6s4-3 4-6c0-2-1-4-4-4zM4 8c2 0 3 2 3 4M20 8c-2 0-3 2-3 4",
  shield: "M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z",
  hormone: "M12 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8zM12 12v8M9 17h6",
  bone: "M6 8a2 2 0 1 1 2-2l8 8a2 2 0 1 1 2 2 2 2 0 1 1-2 2L8 10a2 2 0 0 1-2-2z",
  marker: "M5 19V9M12 19V5M19 19v-7",
  moon: "M20 14.500A8 8 0 0 1 9.500 4a8 8 0 1 0 10.500 10.500z",
  check: "M5 12.500l4.500 4.500L19 7.500",
  clipboard: "M9 4h6v3H9zM7 6H6a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-1M9 13l2 2 4-4",
  calendar: "M5 6h14v14H5zM5 10h14M9 3v4M15 3v4M9 14l2 2 3-3",
  food: "M7 3v8M4 3v5a3 3 0 0 0 3 3M10 3v5a3 3 0 0 1-3 3M7 11v10M17 3c-2 2-3 5-3 8h3v10",
  walk: "M13 4a1.500 1.500 0 1 0 0 3 1.500 1.500 0 0 0 0-3zM10 21l1.500-6-2-2 1-4 3 2 2 1M8 12l2-3",
};

/** A simple line icon. Decorative: the text beside it carries the meaning. */
export function HealthIcon({ name, size = 22 }: { name: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] ?? PATHS.check} />
    </svg>
  );
}
