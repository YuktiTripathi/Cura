import { ThemeToggle } from "./ThemeToggle";
import { LanguagePicker } from "./LanguagePicker";
import type { LanguageCode } from "../lib/language";

export function CuraHeader({
  onOpenSidebar,
  language,
  onLanguageChange,
}: {
  onOpenSidebar: () => void;
  language?: LanguageCode;
  onLanguageChange?: (code: LanguageCode) => void;
}) {
  return (
    <header className="cura-header">
      <div className="title-row">
        <button type="button" className="menu-button" aria-label="Open conversations" onClick={onOpenSidebar}>
          ☰
        </button>
        <h1>Cura ✨</h1>
        <span className="header-controls">
          {language && onLanguageChange ? <LanguagePicker value={language} onChange={onLanguageChange} /> : null}
          <ThemeToggle />
        </span>
      </div>
    </header>
  );
}
