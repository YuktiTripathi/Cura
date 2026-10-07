import { LanguagePicker } from "./LanguagePicker";
import { ThemeToggle } from "./ThemeToggle";
import { t } from "../i18n";

export function CuraHeader({
  onOpenSidebar,
}: {
  onOpenSidebar: () => void;
}) {
  return (
    <header className="cura-header">
      <div className="title-row">
        <button type="button" className="menu-button" aria-label={t("ui.CuraHeader.open_conversations", "Open conversations")} onClick={onOpenSidebar}>
          ☰
        </button>
        <h1>Cura ✨</h1>
        <span className="header-controls">
          <LanguagePicker />
          <ThemeToggle />
        </span>
      </div>
    </header>
  );
}
