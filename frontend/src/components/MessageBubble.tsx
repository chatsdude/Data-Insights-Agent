import { ChartRenderer } from "@/components/ChartRenderer";
import { DataTable } from "@/components/DataTable";
import { SummaryStream } from "@/components/SummaryStream";
import { ThinkingStage } from "@/components/ThinkingStage";
import { ChatMessage } from "@/lib/chat-types";

type MessageBubbleProps = {
  message: ChatMessage;
};

const streamedSummaryMessageIds = new Set<string>();

export function MessageBubble({ message }: MessageBubbleProps) {
  const bubbleClass = `message-bubble ${message.role}`;

  if (message.role === "assistant" && message.result) {
    const { result } = message;
    const chartSuggestion = result.chart_suggestion ?? null;
    const hasData = result.columns.length > 0 || result.rows.length > 0;
    const hasSql = Boolean(result.sql_query);
    const isWorking = result.status !== "complete";
    const isPartial = result.status === "partial";
    const shouldStream = !streamedSummaryMessageIds.has(message.id);

    return (
      <article className={bubbleClass}>
        {chartSuggestion && chartSuggestion.chart_type !== "table" && hasData && (
          <ChartRenderer
            columns={result.columns}
            rows={result.rows}
            suggestion={chartSuggestion}
          />
        )}
        {hasData && (
          <div className="table-section">
            <div className="table-header">
              <h3>Data table</h3>
              <span>
                {result.rows.length} rows - {result.columns.length} columns
              </span>
            </div>
            <DataTable columns={result.columns} rows={result.rows} />
          </div>
        )}
        {isWorking && (
          <ThinkingStage
            text={result.message || message.text || "Thinking..."}
            stage={result.step}
          />
        )}
        {!isWorking && (
          <SummaryStream
            text={result.summary_text || message.text}
            stream={shouldStream}
            onStreamComplete={() => {
              streamedSummaryMessageIds.add(message.id);
            }}
          />
        )}
        {(hasSql || isPartial) && (
          <details className="assistant-details" open>
            <summary>SQL</summary>
            <code className="sql">{result.sql_query || "Generating query..."}</code>
          </details>
        )}
      </article>
    );
  }

  return (
    <article className={bubbleClass}>
      <p>{message.text}</p>
    </article>
  );
}
