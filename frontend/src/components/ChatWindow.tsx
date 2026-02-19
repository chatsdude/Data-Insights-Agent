import { ChatComposer } from "@/components/ChatComposer";
import { DataSourceDropzone } from "@/components/DataSourceDropzone";
import { MessageBubble } from "@/components/MessageBubble";
import { ChatSession } from "@/lib/chat-types";

type ChatWindowProps = {
  chat: ChatSession;
  draft: string;
  visualizeResults: boolean;
  onDraftChange: (value: string) => void;
  onVisualizeResultsChange: (enabled: boolean) => void;
  onSend: () => void;
  onUploadCsv: (file: File) => void;
  onUploadSqlite: (file: File) => void;
};

export function ChatWindow({
  chat,
  draft,
  visualizeResults,
  onDraftChange,
  onVisualizeResultsChange,
  onSend,
  onUploadCsv,
  onUploadSqlite,
}: ChatWindowProps) {
  return (
    <section className="chat-main">
      <header className="chat-header">
        <div className="brand-block">
          <p className="brand-tag">LLM Agent for Data Insights</p>
          <p className="brand-subtitle">
            Connect your data source, ask a question in plain English, get
            actionable insights.
          </p>
        </div>
        {chat.datasource && (
          <div className="datasource-tag">
            <span>Connected Source</span>
            <strong>{chat.datasource.name}</strong>
          </div>
        )}
      </header>

      {chat.error && <div className="alert">{chat.error}</div>}

      <div
        className={`message-list${!chat.datasource ? " message-list-empty" : ""}`}
      >
        {!chat.datasource && (
          <DataSourceDropzone
            disabled={chat.isLoading}
            onUploadCsv={onUploadCsv}
            onUploadSqlite={onUploadSqlite}
          />
        )}
        {chat.messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
      </div>

      <ChatComposer
        draft={draft}
        visualizeResults={visualizeResults}
        inputDisabled={chat.isLoading}
        sendDisabled={chat.isLoading || !chat.datasource}
        onDraftChange={onDraftChange}
        onVisualizeResultsChange={onVisualizeResultsChange}
        onSend={onSend}
      />
    </section>
  );
}
