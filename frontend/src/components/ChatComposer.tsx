type ChatComposerProps = {
  draft: string;
  visualizeResults: boolean;
  inputDisabled: boolean;
  sendDisabled: boolean;
  onDraftChange: (value: string) => void;
  onVisualizeResultsChange: (enabled: boolean) => void;
  onSend: () => void;
};

export function ChatComposer({
  draft,
  visualizeResults,
  inputDisabled,
  sendDisabled,
  onDraftChange,
  onVisualizeResultsChange,
  onSend,
}: ChatComposerProps) {
  return (
    <div className="chat-composer">
      <div className="composer-input-group">
        <textarea
          rows={3}
          placeholder="Ask a question about this chat's data source..."
          value={draft}
          disabled={inputDisabled}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (!sendDisabled) onSend();
            }
          }}
        />
        <label className="composer-toggle">
          <input
            type="checkbox"
            checked={visualizeResults}
            disabled={inputDisabled}
            onChange={(event) => onVisualizeResultsChange(event.target.checked)}
          />
          <span>I want to visualize the results</span>
        </label>
      </div>
      <button className="primary" onClick={onSend} disabled={sendDisabled}>
        {inputDisabled ? "Running..." : "Send"}
      </button>
    </div>
  );
}
