export function UserQuestionEditor({
  draft,
  onDraftChange,
  onSave,
  onCancel,
}: {
  draft: string;
  onDraftChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="edit-question">
      <textarea
        value={draft}
        onChange={(e) => onDraftChange(e.target.value)}
        aria-label="Edit question"
      />
      <div className="edit-question-actions">
        <button type="button" onClick={onSave} disabled={!draft.trim()}>
          Save
        </button>
        <button type="button" className="text-button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export function UserQuestionActions({ disabled, onEdit }: { disabled: boolean; onEdit: () => void }) {
  return (
    <div className="user-actions">
      <button type="button" className="text-button" disabled={disabled} onClick={onEdit}>
        Edit
      </button>
    </div>
  );
}
