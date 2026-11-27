import { useEffect, useRef, type ReactNode } from "react";
import { t } from "../i18n";

export function AppShell({
  sidebar,
  children,
  drawerOpen,
  onCloseDrawer,
  panel,
  onClosePanel,
}: {
  sidebar: ReactNode;
  children: ReactNode;
  /** Optional detail panel beside the chat column. */
  panel?: ReactNode;
  drawerOpen: boolean;
  onCloseDrawer: () => void;
  onClosePanel?: () => void;
}) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const panelReturnFocusRef = useRef<HTMLElement | null>(null);

  function keepFocusInside(event: KeyboardEvent, container: HTMLElement | null) {
    if (event.key !== "Tab" || !container) return;
    const items = [...container.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )].filter((item) => item.offsetParent !== null);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  useEffect(() => {
    if (!drawerOpen) return;
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.setTimeout(() => drawerRef.current?.querySelector<HTMLElement>("button, a, input")?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseDrawer();
      keepFocusInside(event, drawerRef.current);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
      returnFocusRef.current?.focus();
    };
  }, [drawerOpen, onCloseDrawer]);

  useEffect(() => {
    if (!panel || !onClosePanel) return;
    panelReturnFocusRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.setTimeout(() => panelRef.current?.querySelector<HTMLElement>("button, a, input")?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClosePanel();
      keepFocusInside(event, panelRef.current);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
      panelReturnFocusRef.current?.focus();
    };
  }, [panel, onClosePanel]);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#cura-main-content">
        Skip to main content
      </a>
      <div
        ref={drawerRef}
        className="sidebar-region"
        role={drawerOpen ? "dialog" : undefined}
        aria-modal={drawerOpen || undefined}
        aria-label={drawerOpen ? "Conversations" : undefined}
      >
        {sidebar}
      </div>
      {drawerOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label={t("ui.AppShell.close_conversations", "Close conversations")}
          onClick={onCloseDrawer}
        />
      )}
      <main id="cura-main-content" className="main-column" tabIndex={-1}>{children}</main>
      {panel ? <div ref={panelRef} className="detail-panel-region" role="dialog" aria-modal="true" aria-label="Health result details">{panel}</div> : null}
    </div>
  );
}
