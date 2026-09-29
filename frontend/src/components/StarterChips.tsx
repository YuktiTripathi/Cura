type Item = { id: string; label: string; prompt?: string };
type Props = { items: Item[]; onPick: (prompt: string) => void; onAsk: () => void };

export function StarterChips({ items, onPick, onAsk }: Props) {
  return (
    <div className="chips">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => (item.prompt ? onPick(item.prompt) : onAsk())}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
