import { LANGUAGES, isLanguage, type LanguageCode } from "../lib/language";

/** Which language Cura answers in. "Auto" follows the language of each message. */
export function LanguagePicker({ value, onChange }: { value: LanguageCode; onChange: (code: LanguageCode) => void }) {
  return (
    <label className="language-picker">
      <span className="visually-hidden">Answer language</span>
      <select
        value={value}
        onChange={(event) => {
          if (isLanguage(event.target.value)) onChange(event.target.value);
        }}
        title="Answer language"
      >
        {LANGUAGES.map((item) => (
          <option key={item.code} value={item.code} lang={item.htmlLang}>
            {item.code === "auto" ? "🌐 Auto" : item.label}
          </option>
        ))}
      </select>
    </label>
  );
}
