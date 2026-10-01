import type { ReactNode } from "react";

export function AppShell({
  sidebar,
  children,
  drawerOpen,
  onCloseDrawer,
  panel,
}: {
  sidebar: ReactNode;
  children: ReactNode;
  /** Optional detail panel beside the chat column. */
  panel?: ReactNode;
  drawerOpen: boolean;
  onCloseDrawer: () => void;
}) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#cura-message-input">
        Skip to message box
      </a>
      {sidebar}
      {drawerOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close conversations"
          onClick={onCloseDrawer}
        />
      )}
      <main className="main-column">{children}</main>
      {panel}
    </div>
  );
}
