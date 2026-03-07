export type DataSourceInfo = {
  id: string;
  type: "csv" | "sqlite";
  name: string;
};

export type KnowledgeSpaceInfo = {
  id: string;
  name: string;
  created_at: string;
};

export type DocumentInfo = {
  id: string;
  space_id: string;
  filename: string;
  content_type?: string | null;
  status: "uploaded" | "processing" | "completed" | "failed";
  created_at: string;
};

export type IngestionJobInfo = {
  id: string;
  space_id: string;
  document_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  stage: string;
  progress: number;
  error?: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentUploadResponse = {
  document: DocumentInfo;
  job: IngestionJobInfo;
};

export type ChartSuggestion = {
  chart_type: "bar" | "stacked_bar" | "line" | "donut" | "table";
  x_field?: string | null;
  y_field?: string | null;
  series_field?: string | null;
  rationale?: string;
};

export type QueryResponse = {
  status?: "progress" | "partial" | "complete";
  step?: "schema" | "sql" | "query" | "postprocess";
  message?: string;
  sql_query: string;
  columns: string[];
  rows: Array<Array<unknown>>;
  chart_suggestion?: ChartSuggestion;
  summary_text?: string;
  knowledge_relations?: Array<{
    subject: string;
    relation: string;
    object: string;
  }>;
  error?: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function registerSQLite(file: File): Promise<DataSourceInfo> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/datasources/sqlite`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function registerCSV(file: File): Promise<DataSourceInfo> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/datasources/csv`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function* runQueryStream(
  datasourceId: string,
  question: string,
  includeVisualization = true,
  knowledgeSpaceId?: string | null
): AsyncGenerator<QueryResponse, void, unknown> {
  const response = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      datasource_id: datasourceId,
      question,
      include_visualization: includeVisualization,
      agent_mode: "reactive",
      knowledge_space_id: knowledgeSpaceId ?? null,
    }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!response.body || !contentType.includes("application/x-ndjson")) {
    const single = (await response.json()) as QueryResponse;
    yield single;
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;
      yield JSON.parse(line) as QueryResponse;
    }
  }

  const tail = buffer.trim();
  if (tail) {
    yield JSON.parse(tail) as QueryResponse;
  }
}

export async function runQuery(
  datasourceId: string,
  question: string,
  includeVisualization = true,
  knowledgeSpaceId?: string | null
): Promise<QueryResponse> {
  let merged: QueryResponse = {
    status: "partial",
    sql_query: "",
    columns: [],
    rows: [],
    chart_suggestion: {
      chart_type: "table",
      x_field: null,
      y_field: null,
      series_field: null,
      rationale: "",
    },
    summary_text: "",
    error: null,
  };

  for await (const chunk of runQueryStream(
    datasourceId,
    question,
    includeVisualization,
    knowledgeSpaceId
  )) {
    merged = { ...merged, ...chunk };
  }

  return merged;
}

export async function createKnowledgeSpace(
  name: string
): Promise<KnowledgeSpaceInfo> {
  const response = await fetch(`${API_BASE}/knowledge-spaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function listKnowledgeSpaces(): Promise<KnowledgeSpaceInfo[]> {
  const response = await fetch(`${API_BASE}/knowledge-spaces`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function uploadKnowledgeDocument(
  spaceId: string,
  file: File
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/knowledge-spaces/${spaceId}/documents`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function getIngestionJob(jobId: string): Promise<IngestionJobInfo> {
  const response = await fetch(`${API_BASE}/ingestion-jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}
