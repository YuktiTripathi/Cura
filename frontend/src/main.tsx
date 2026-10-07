import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { useLocale } from "./components/LanguagePicker";
import { applyDocumentLang } from "./i18n";
import "./styles.css";

applyDocumentLang();

// Keying the app by locale re-renders every translated string when the language changes.
function LocalizedApp() {
  const locale = useLocale();
  return <App key={locale} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <LocalizedApp />
  </StrictMode>
);
