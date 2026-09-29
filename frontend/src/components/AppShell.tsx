import type { ReactNode } from "react";

export function AppShell({
  sidebar,
  children,
  drawerOpen,
  onCloseDrawer,
}: {
  sidebar: ReactNode;
  children: ReactNode;
  drawerOpen: boolean;
  onCloseDrawer: () => void;
}) {
  return (
    <div className="app-shell">
      {sidebar}
      {drawerOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close conversations"
          onClick={onCloseDrawer}
        />
      )}
      <div className="main-column">{children}</div>
    </div>
  );
}
