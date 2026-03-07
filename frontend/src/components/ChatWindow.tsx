import { useRef, useState } from "react";

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
  onRunStarter: (question: string) => void;
};

function getKnowledgeSpaceDisplayName(name: string): string {
  if (name === "test_new") {
    return "Manufacturing Alarms";
  }
  return name;
}

const DEFAULT_STARTER_QUESTIONS = [
  "Show me the first 5 rows in the dataset.",
  "Show me top 10 error codes in the dataset.",
  "Show me top 10 error code categories. Visualize the result as a pie chart.",
];

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
  onRunStarter,
}: ChatWindowProps) {
  const datasourceFileRef = useRef<HTMLInputElement>(null);
  const knowledgeFileRef = useRef<HTMLInputElement>(null);
  const [isCreatingSpace, setIsCreatingSpace] = useState(false);
  const [newSpaceName, setNewSpaceName] = useState("");
  const latestAssistantWithFollowUps = [...chat.messages]
    .reverse()
    .find(
      (message) =>
        message.role === "assistant" &&
        message.result?.status === "complete" &&
        (message.result.follow_up_questions?.length ?? 0) > 0
    );
  const suggestedQuestions =
    latestAssistantWithFollowUps?.result?.follow_up_questions?.slice(0, 3) ??
    DEFAULT_STARTER_QUESTIONS;
  const showInitialSuggestions = chat.datasource && chat.messages.length === 0;
  const showFollowUpSuggestions =
    chat.datasource && chat.messages.length > 0 && !chat.isLoading;
  const showSuggestionCards = showInitialSuggestions || showFollowUpSuggestions;

  const handleDatasourcePick = (file: File) => {
    const name = file.name.toLowerCase();
    if (name.endsWith(".csv")) {
      onUploadCsv(file);
      return;
    }
    if (
      name.endsWith(".db") ||
      name.endsWith(".sqlite") ||
      name.endsWith(".sqlite3")
    ) {
      onUploadSqlite(file);
    }
  };

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
            <div className="datasource-tag-row">
              <span>Connected Source</span>
              <button
                type="button"
                className="datasource-plus"
                onClick={() => datasourceFileRef.current?.click()}
                disabled={chat.isLoading}
                aria-label="Upload another data source"
                title="Upload another data source"
              >
                +
              </button>
            </div>
            <strong>{chat.datasource.name}</strong>
            <input
              ref={datasourceFileRef}
              type="file"
              accept=".csv,.db,.sqlite,.sqlite3"
              hidden
              disabled={chat.isLoading}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                handleDatasourcePick(file);
                event.currentTarget.value = "";
              }}
            />
          </div>
        )}
      </header>

      <section className="knowledge-setup">
        <details className="knowledge-help">
          <summary>What is this about?</summary>
          <p>
            Knowledge spaces let you upload custom files so the agent can use
            domain-specific context and return better insights.
          </p>
        </details>
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
                {getKnowledgeSpaceDisplayName(space.name)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setIsCreatingSpace((prev) => !prev)}
            disabled={chat.isLoading}
          >
            + New Space
          </button>
        </div>
        {isCreatingSpace && (
          <div className="knowledge-space-create">
            <input
              type="text"
              placeholder="Enter knowledge space name"
              value={newSpaceName}
              disabled={chat.isLoading}
              onChange={(event) => setNewSpaceName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return;
                const name = newSpaceName.trim();
                if (!name) return;
                onCreateKnowledgeSpace(name);
                setNewSpaceName("");
                setIsCreatingSpace(false);
              }}
            />
            <button
              type="button"
              disabled={chat.isLoading || !newSpaceName.trim()}
              onClick={() => {
                const name = newSpaceName.trim();
                if (!name) return;
                onCreateKnowledgeSpace(name);
                setNewSpaceName("");
                setIsCreatingSpace(false);
              }}
            >
              Create
            </button>
            <button
              type="button"
              disabled={chat.isLoading}
              onClick={() => {
                setNewSpaceName("");
                setIsCreatingSpace(false);
              }}
            >
              Cancel
            </button>
          </div>
        )}
        <div className="knowledge-setup-row">
          <button
            type="button"
            className="knowledge-upload-btn"
            disabled={chat.isLoading || !chat.knowledgeSpaceId}
            onClick={() => knowledgeFileRef.current?.click()}
          >
            <span aria-hidden="true">+</span>
            Add files
          </button>
          <input
            ref={knowledgeFileRef}
            type="file"
            accept=".pdf,.txt,.md,.doc,.docx"
            hidden
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
        {showSuggestionCards && (
          <section className="starter-prompts">
            <p>
              {showInitialSuggestions
                ? "Quick start with a suggested question"
                : "Suggested follow-up questions"}
            </p>
            <div className="starter-prompts-grid">
              {suggestedQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  disabled={chat.isLoading}
                  onClick={() => onRunStarter(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </section>
        )}
        {chat.error && <div className="alert">{chat.error}</div>}
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
