export function CuraHeader({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  return (
    <header className="cura-header">
      <div className="title-row">
        <button type="button" className="menu-button" aria-label="Open conversations" onClick={onOpenSidebar}>
          ☰
        </button>
        <h1>Cura ✨</h1>
        <span className="header-spacer" aria-hidden="true" />
      </div>
    </header>
  );
}
