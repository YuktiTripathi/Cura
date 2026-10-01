/** Answer languages the Cura API supports (backend LanguageCode). Names are shown in their own script. */
export const LANGUAGES = [
  { code: "auto", label: "Auto", htmlLang: "en" },
  { code: "en", label: "English", htmlLang: "en" },
  { code: "hi", label: "हिन्दी", htmlLang: "hi" },
  { code: "mr", label: "मराठी", htmlLang: "mr" },
  { code: "pa", label: "ਪੰਜਾਬੀ", htmlLang: "pa" },
  { code: "gu", label: "ગુજરાતી", htmlLang: "gu" },
  { code: "bn", label: "বাংলা", htmlLang: "bn" },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]["code"];

const KEY = "cura_language";

export function isLanguage(value: unknown): value is LanguageCode {
  return LANGUAGES.some((item) => item.code === value);
}

export function readLanguage(): LanguageCode {
  try {
    const value = window.localStorage.getItem(KEY);
    return isLanguage(value) ? value : "auto";
  } catch {
    return "auto";
  }
}

export function writeLanguage(code: LanguageCode): void {
  try {
    if (code === "auto") window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, code);
  } catch {
    /* storage unavailable */
  }
}

const SCRIPTS: Array<[RegExp, string]> = [
  [/[\u0900-\u097F]/, "hi"], // Devanagari (Hindi or Marathi)
  [/[\u0A00-\u0A7F]/, "pa"], // Gurmukhi
  [/[\u0A80-\u0AFF]/, "gu"], // Gujarati
  [/[\u0980-\u09FF]/, "bn"], // Bengali
];

/**
 * BCP-47 tag for text written in a supported Indic script, else undefined (the page language, English,
 * applies). Devanagari is tagged Marathi when Marathi is the chosen language, otherwise Hindi.
 * Screen readers use this to pick the right voice for that text only.
 */
export function langForText(text: string | null | undefined, chosen: LanguageCode = "auto"): string | undefined {
  if (!text) return undefined;
  for (const [pattern, tag] of SCRIPTS) {
    if (pattern.test(text)) return tag === "hi" && chosen === "mr" ? "mr" : tag;
  }
  return undefined;
}

