import { ChatComposer } from "@/components/ChatComposer";
import { DataSourceDropzone } from "@/components/DataSourceDropzone";
import { MessageBubble } from "@/components/MessageBubble";
import { KnowledgeSpaceInfo } from "@/lib/api";
import { ChatSession } from "@/lib/chat-types";

type ChatWindowProps = {
  chat: ChatSession;
  knowledgeSpaces: KnowledgeSpaceInfo[];
  draft: string;
  visualizeResults: boolean;
  onDraftChange: (value: string) => void;
  onVisualizeResultsChange: (enabled: boolean) => void;
  onSend: () => void;
  onUploadCsv: (file: File) => void;
  onUploadSqlite: (file: File) => void;
  onSelectKnowledgeSpace: (spaceId: string) => void;
  onCreateKnowledgeSpace: (name: string) => void;
  onUploadKnowledgeDoc: (file: File) => void;
};

export function ChatWindow({
  chat,
  knowledgeSpaces,
  draft,
  visualizeResults,
  onDraftChange,
  onVisualizeResultsChange,
  onSend,
  onUploadCsv,
  onUploadSqlite,
  onSelectKnowledgeSpace,
  onCreateKnowledgeSpace,
  onUploadKnowledgeDoc,
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

      <section className="knowledge-setup">
        <div className="knowledge-setup-row">
          <label htmlFor="knowledge-space-select">Knowledge Space</label>
          <select
            id="knowledge-space-select"
            disabled={chat.isLoading}
            value={chat.knowledgeSpaceId ?? ""}
            onChange={(event) => onSelectKnowledgeSpace(event.target.value)}
          >
            {knowledgeSpaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => {
              const name = window.prompt("Knowledge space name:");
              if (!name) return;
              onCreateKnowledgeSpace(name.trim());
            }}
            disabled={chat.isLoading}
          >
            New Space
          </button>
        </div>
        <div className="knowledge-setup-row">
          <input
            type="file"
            accept=".pdf,.txt,.md,.doc,.docx"
            disabled={chat.isLoading || !chat.knowledgeSpaceId}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              onUploadKnowledgeDoc(file);
              event.currentTarget.value = "";
            }}
          />
          <small>
            {chat.ingestionStatus
              ? `Ingestion: ${chat.ingestionStatus}`
              : "Upload docs after selecting a space."}
          </small>
        </div>
      </section>

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
