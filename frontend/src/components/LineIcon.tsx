const ICON_PATHS: Record<string, string> = {
  meal: "M7 3v8M4 3v5a3 3 0 0 0 3 3M10 3v5a3 3 0 0 1-3 3M7 11v10M17 3c-2 2-3 5-3 8h3v10",
  move: "M8 4c-1.5 0-2.5 1.5-2.5 3.5S6.5 11 8 11s2.5-1 2.5-3.5S9.5 4 8 4zM6.5 14h3l.5 3a1.5 1.5 0 0 1-3 0zM16 8c-1.5 0-2.5 1.5-2.5 3.5S14.5 15 16 15s2.5-1 2.5-3.5S17.5 8 16 8zM14.5 18h3l.5 2a1.5 1.5 0 0 1-3 0z",
  sleep: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  stress: "M12 21c-4-3-7-6-7-10a4 4 0 0 1 7-2 4 4 0 0 1 7 2c0 4-3 7-7 10z",
  water: "M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z",
  test: "M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3M8 15h8",
  doctor: "M6 3v6a4 4 0 0 0 8 0V3M10 13v3a4 4 0 0 0 8 0v-2M18 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
  weight: "M5 8h14l1 12H4zM9 8a3 3 0 0 1 6 0M12 12v3",
  smoke: "M4 16h13v3H4zM19 16v3M17 8c0-2 2-2 2-4M13 8c0-2 2-2 2-4",
  heart: "M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z",
  liver: "M4 10c0-3 3-5 8-5 5 0 8 2 8 5 0 4-4 8-9 8-4 0-7-3-7-8zM14 9c0 2 1 3 3 3",
  drops: "M9 4s4 4.5 4 8a4 4 0 0 1-8 0c0-3.5 4-8 4-8zM17 12s3 3 3 5.5a3 3 0 0 1-6 0c0-2.5 3-5.5 3-5.5z",
  kidney: "M9 4C5 4 3 8 3 12s2 8 6 8c2 0 3-1.5 3-3.5 0-1.5-1-2-1-3.5S12 11 12 9.5C12 6 11 4 9 4zM15 7c3 0 6 2 6 5s-3 6-6 6",
  blood: "M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11zM9.5 14a2.5 2.5 0 0 0 2.5 2.5",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4 12H2M22 12h-2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4",
  thyroid: "M12 6c-1 0-2 1-2 2.5V11c-2 0-5 1-5 4s2 4 4 4c2 0 3-1.5 3-3 0 1.5 1 3 3 3 2 0 4-1 4-4s-3-4-5-4V8.5C14 7 13 6 12 6z",
  shield: "M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z",
  hormone: "M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 12v9M9 18h6",
  bone: "M7 8a2.5 2.5 0 1 1 3-3l7 7a2.5 2.5 0 1 1 3 3 2.5 2.5 0 1 1-3 3l-7-7a2.5 2.5 0 0 1-3-3z",
  marker: "M12 21s-6-5.5-6-10a6 6 0 0 1 12 0c0 4.5-6 10-6 10zM12 8.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  habit: "M5 12l4 4 10-10",
};


/** A simple line icon. Decorative: the title next to it carries the meaning. */
export function LineIcon({ name, size = 22 }: { name: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICON_PATHS[name] ?? ICON_PATHS.habit} />
    </svg>
  );
}
