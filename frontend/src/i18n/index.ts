// Web translation layer (readiness plan 3.6). English text stays inline at the call site
// as the default, so a missing translation can never blank the UI. Other languages live
// in ./messages/<lang>.json (DRAFT until reviewed by native speaking clinicians).
import hi from "./messages/hi.json";
import hinglish from "./messages/hinglish.json";

export type Locale = "en" | "hi" | "hinglish";
export const LOCALES: Locale[] = ["en", "hi", "hinglish"];

const DICTIONARIES: Record<Locale, Record<string, string>> = { en: {}, hi, hinglish };
const STORAGE_KEY = "cura_locale";
const HTML_LANG: Record<Locale, string> = { en: "en", hi: "hi", hinglish: "hi-Latn" };

let current: Locale = detectLocale();
const listeners = new Set<(locale: Locale) => void>();

function detectLocale(): Locale {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY) as Locale | null;
    if (saved && LOCALES.includes(saved)) return saved;
  } catch {
    // Storage can be unavailable (private mode); fall through to the browser language.
  }
  const nav = typeof navigator !== "undefined" ? (navigator.language || "").toLowerCase() : "";
  return nav.startsWith("hi") ? "hi" : "en";
}

/** The locale the member picked themselves, or null if Cura is following the browser. */
export function explicitLocale(): Locale | null {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY) as Locale | null;
    return saved && LOCALES.includes(saved) ? saved : null;
  } catch {
    return null;
  }
}

export function getLocale(): Locale {
  return current;
}

export function setLocale(locale: Locale): void {
  if (!LOCALES.includes(locale)) return;
  current = locale;
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // Ignore: the choice still applies for this page view.
  }
  applyDocumentLang();
  listeners.forEach((listener) => listener(locale));
}

export function onLocaleChange(listener: (locale: Locale) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function applyDocumentLang(): void {
  if (typeof document !== "undefined") document.documentElement.lang = HTML_LANG[current];
}

/** Translate `key`, using `english` when the current locale has no entry. */
export function t(key: string, english: string, values: Record<string, string | number> = {}): string {
  const template = DICTIONARIES[current][key] || english;
  return template.replace(/\{(\w+)\}/g, (match, name) => (name in values ? String(values[name]) : match));
}

/** Testing hook: set the locale without touching storage. */
export function __setLocaleForTests(locale: Locale): void {
  current = locale;
}
