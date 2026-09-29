import { useCallback, useEffect, useState } from "react";
import {
  deleteConversation,
  getConversation,
  listConversations,
  type ConversationDetail,
  type ConversationSummary,
} from "../lib/api";

export function ConversationSidebar({
  refreshKey,
  activeId,
  onOpen,
  onNew,
  onDeleted,
  mobileOpen,
  onCloseMobile,
}: {
  refreshKey: number;
  activeId: string | null;
  onOpen: (detail: ConversationDetail) => void;
  onNew: () => void;
  onDeleted: (id: string) => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const next = await listConversations();
    setItems(next);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function open(id: string) {
    const detail = await getConversation(id);
    onOpen(detail);
    onCloseMobile();
  }

  async function remove(id: string) {
    await deleteConversation(id);
    setItems((current) => current.filter((row) => row.id !== id));
    onDeleted(id);
  }

  return (
    <aside
      className={`sidebar${mobileOpen ? " open" : ""}`}
      aria-label="Conversations"
    >
      <div className="sidebar-brand">
        <span className="sidebar-mark">C</span>
        <div>
          <strong>Cura</strong>
          <p>Personal health assistant</p>
        </div>
      </div>
      <button type="button" className="new-conversation" onClick={onNew}>
        + New conversation
      </button>
      <div className="sidebar-section">
        <h2>Recent conversations</h2>
        <div className="conversation-scroll">
          {!loading && items.length === 0 && (
            <div className="sidebar-empty">
              <p>No conversations yet.</p>
              <p>Start a conversation with Cura to see it here.</p>
            </div>
          )}
          {items.map((item) => {
            const active = item.id === activeId;
            return (
              <div
                key={item.id}
                className={`conversation-row${active ? " active" : ""}`}
              >
                <button
                  type="button"
                  className="conversation-title"
                  onClick={() => void open(item.id)}
                >
                  {active ? "● " : ""}
                  {item.title || "Cura conversation"}
                </button>
                <button
                  type="button"
                  className="text-button"
                  aria-label={`Delete ${item.title || "conversation"}`}
                  onClick={() => void remove(item.id)}
                >
                  Delete
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
