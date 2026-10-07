import { useEffect, useState } from "react";
import { getLocale, LOCALES, onLocaleChange, setLocale, type Locale } from "../i18n";

const LABELS: Record<Locale, string> = { en: "English", hi: "हिन्दी", hinglish: "Hinglish" };

/** Re-renders whenever the locale changes. */
export function useLocale(): Locale {
  const [locale, setState] = useState<Locale>(getLocale());
  useEffect(() => onLocaleChange(setState), []);
  return locale;
}

export function LanguagePicker() {
  const locale = useLocale();
  return (
    <select
      className="language-picker"
      aria-label="Language"
      value={locale}
      onChange={(event) => setLocale(event.target.value as Locale)}
    >
      {LOCALES.map((code) => (
        <option key={code} value={code} lang={code === "hi" ? "hi" : "en"}>
          {LABELS[code]}
        </option>
      ))}
    </select>
  );
}
