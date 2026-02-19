type ThinkingStageProps = {
  text: string;
  stage?: "schema" | "sql" | "query" | "postprocess";
};

const stageLabel: Record<NonNullable<ThinkingStageProps["stage"]>, string> = {
  schema: "Understanding data",
  sql: "Drafting query",
  query: "Running query",
  postprocess: "Shaping insights",
};

export function ThinkingStage({ text, stage }: ThinkingStageProps) {
  const label = stage ? stageLabel[stage] : "Thinking";
  return (
    <section className="thinking-card" aria-live="polite">
      <div className="thinking-head">
        <span className="thinking-chip">Thinking</span>
        <span className="thinking-stage">{label}</span>
      </div>
      <p className="thinking-text">{text}</p>
      <div className="thinking-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </section>
  );
}
