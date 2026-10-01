import { useState } from "react";
import type { HealthTheme } from "../../types/chat";
import { FindingsTable } from "./FindingsTable";

export function ThemeList({ themes }: { themes: HealthTheme[] }) {
  return (
    <div className="theme-cards">
      {themes.map((theme) => (
        <ThemeCard key={theme.title} theme={theme} />
      ))}
    </div>
  );
}

export function ThemeCard({ theme }: { theme: HealthTheme }) {
  const [open, setOpen] = useState(false);
  const related = theme.related_findings || [];
  return (
    <article className={`theme-card theme-${theme.status}`} data-testid="health-theme">
      <header>
        <h4>{theme.title}</h4>
        <span className="theme-status">{theme.status.replace(/_/g, " ")}</span>
      </header>
      {theme.interpretation ? <p>{theme.interpretation}</p> : null}
      {theme.missing_information && theme.missing_information.length > 0 ? (
        <ul className="theme-missing">
          {theme.missing_information.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {related.length > 0 ? (
        <div>
          <button type="button" className="text-button" onClick={() => setOpen((value) => !value)}>
            {open ? "Hide related values" : "Related values"}
          </button>
          {open ? <FindingsTable findings={related} /> : null}
        </div>
      ) : null}
    </article>
  );
}
