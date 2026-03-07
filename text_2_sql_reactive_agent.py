from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from core.data_sources.base import DataSource
from core.knowledge.context import get_context_from_neo4j

try:
    from langchain_community.agent_toolkits.sql.base import create_sql_agent
except ImportError:
    from langchain_community.agent_toolkits import create_sql_agent

load_dotenv()
_executor_cache: Dict[Tuple[str, str], Any] = {}
SQL_GEN_TIMEOUT_SECONDS = float(os.environ.get("SQL_GEN_TIMEOUT_SECONDS", "45"))
SQL_RUN_TIMEOUT_SECONDS = float(os.environ.get("SQL_RUN_TIMEOUT_SECONDS", "20"))
POSTPROCESS_TIMEOUT_SECONDS = float(os.environ.get("POSTPROCESS_TIMEOUT_SECONDS", "60"))
SUMMARY_MODEL = os.environ.get("SUMMARY_MODEL", "gpt-4o-mini")


def _get_openai_client() -> OpenAI:
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def _log(message: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[reactive-agent] {ts} {message}", flush=True)


def _chat_completion_with_retry(
    *,
    model: str,
    messages: List[Dict[str, str]],
    response_format: Optional[Dict[str, str]] = None,
    retries: int = 3,
    backoff_seconds: float = 0.8,
    timeout_seconds: float = 20.0,
):
    client = _get_openai_client()
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            start = time.perf_counter()
            kwargs: Dict[str, Any] = {"model": model, "messages": messages}
            if response_format is not None:
                kwargs["response_format"] = response_format
            kwargs["timeout"] = timeout_seconds
            response = client.chat.completions.create(**kwargs)
            elapsed = time.perf_counter() - start
            _log(f"OpenAI call success model={model} attempt={attempt + 1} elapsed={elapsed:.2f}s")
            return response
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_error = exc
            _log(
                f"OpenAI call retry model={model} attempt={attempt + 1}/{retries} error={type(exc).__name__}: {exc}"
            )
            if attempt == retries - 1:
                break
            time.sleep(backoff_seconds * (2**attempt))
    raise last_error if last_error is not None else RuntimeError("OpenAI call failed.")


def _clean_sql_text(query: str) -> str:
    cleaned = query.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```sql", "").replace("```", "").strip()
    return cleaned.strip().rstrip(";")


def _sqlite_db_path_from_datasource(datasource: DataSource) -> str:
    # SQLiteDataSource(db_path=...) and CSVDataSource(_sqlite_path=...) are both supported.
    db_path = getattr(datasource, "db_path", None) or getattr(
        datasource, "_sqlite_path", None
    )
    if not db_path:
        raise ValueError(
            "Reactive SQL agent requires a datasource backed by a SQLite file path."
        )
    return str(db_path)


def _extract_last_sql_from_steps(intermediate_steps: List[Any]) -> Optional[str]:
    last_sql: Optional[str] = None
    for step in intermediate_steps:
        if not isinstance(step, (tuple, list)) or len(step) < 1:
            continue
        action = step[0]
        tool_name = getattr(action, "tool", "")
        if tool_name != "sql_db_query":
            continue
        tool_input = getattr(action, "tool_input", None)
        if isinstance(tool_input, dict):
            candidate = tool_input.get("query") or tool_input.get("input")
        else:
            candidate = str(tool_input) if tool_input is not None else None
        if candidate:
            last_sql = _clean_sql_text(str(candidate))
    return last_sql


def _build_reactive_executor(db_path: str):
    model_name = os.environ.get("SQL_AGENT_MODEL", "gpt-5-mini")
    cache_key = (db_path, model_name)
    if cache_key in _executor_cache:
        return _executor_cache[cache_key]
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    llm = ChatOpenAI(model=model_name)
    executor = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="tool-calling",
        verbose=False,
        agent_executor_kwargs={"return_intermediate_steps": True},
    )
    _executor_cache[cache_key] = executor
    return executor


def _build_reactive_sql(question: str, datasource: DataSource) -> str:
    # Fast path first: one-shot SQL generation avoids tool-agent loops.
    try:
        schema = datasource.get_schema()
        prompt = (
            "Generate exactly one SQLite query for the user question.\n"
            "Use only tables/columns from the schema.\n"
            "Return raw SQL only. No markdown, no explanation."
        )
        completion = _chat_completion_with_retry(
            model=os.environ.get("SQL_AGENT_MODEL", "gpt-5-mini"),
            messages=[
                {"role": "developer", "content": prompt},
                {
                    "role": "user",
                    "content": f"Schema: {json.dumps(schema)}\nQuestion: {question}",
                },
            ],
            timeout_seconds=18,
        )
        fast_sql = _clean_sql_text(completion.choices[0].message.content or "")
        if fast_sql:
            return fast_sql
    except Exception:
        pass

    sql_query: Optional[str] = None
    try:
        executor = _build_reactive_executor(_sqlite_db_path_from_datasource(datasource))
        result = executor.invoke({"input": question})
        sql_query = _extract_last_sql_from_steps(result.get("intermediate_steps", []))
    except Exception:
        sql_query = None

    if sql_query:
        return sql_query

    # Fallback when intermediate SQL is unavailable.
    fallback_prompt = (
        "Return exactly one SQLite query for the user request. "
        "No markdown, no explanation."
    )
    completion = _chat_completion_with_retry(
        model=os.environ.get("SQL_AGENT_MODEL", "gpt-5-mini"),
        messages=[
            {"role": "developer", "content": fallback_prompt},
            {"role": "user", "content": f"Question: {question}"},
        ],
    )
    return _clean_sql_text(completion.choices[0].message.content or "SELECT 1")


def _run_sql_with_retry(
    question: str,
    datasource: DataSource,
    sql_query: str,
    allow_retry: bool = False,
) -> Dict[str, Any]:
    error_message: Optional[str] = None
    try:
        columns, rows = datasource.run_query(sql_query)
        rows_as_lists = [list(row) for row in rows]
        return {
            "sql_query": sql_query,
            "columns": columns,
            "rows": rows_as_lists,
            "error": None,
        }
    except Exception as exc:
        error_message = f"Query execution failed: {exc}"
        if not allow_retry:
            return {
                "sql_query": sql_query,
                "columns": [],
                "rows": [],
                "error": error_message,
            }

    if not allow_retry:
        return {
            "sql_query": sql_query,
            "columns": [],
            "rows": [],
            "error": error_message
            or "The query returned no rows. Try broadening filters.",
        }

    broadened_question = (
        f"{question}\n\nThe previous query failed or returned no data. "
        "Retry with broader conditions and fewer filters."
    )
    retry_sql = _build_reactive_sql(broadened_question, datasource)
    columns, rows = datasource.run_query(retry_sql)
    return {
        "sql_query": retry_sql,
        "columns": columns,
        "rows": [list(row) for row in rows],
        "error": None,
    }


def _generate_chart_suggestion(
    question: str,
    schema: Dict[str, Any],
    columns: List[str],
    rows: List[List[Any]],
) -> Dict[str, Any]:
    chart_start = time.perf_counter()
    if not rows or not columns:
        _log("Chart suggestion skipped: no rows or columns.")
        return {
            "chart_type": "table",
            "x_field": None,
            "y_field": None,
            "series_field": None,
            "rationale": "No data returned; defaulting to table.",
        }

    system_prefix = (
        "You are a data visualization assistant. "
        "Choose the best chart for the given question and data. "
        "Allowed chart_type values: bar, stacked_bar, line, donut, table. "
        "Only choose non-table when you are confident it is appropriate. "
        "Use column names exactly as provided."
    )

    template = f"""
    Question: {question}
    Columns: {columns}
    SampleRows: {rows[:5]}
    Schema: {schema}

    Return a JSON object with keys:
    chart_type, x_field, y_field, series_field, rationale.
    If unsure, set chart_type to table and other fields to null.
    """

    try:
        completion = _chat_completion_with_retry(
            model="gpt-5-mini",
            messages=[
                {"role": "developer", "content": system_prefix},
                {"role": "user", "content": template},
            ],
            response_format={"type": "json_object"},
        )
    except Exception:
        elapsed = time.perf_counter() - chart_start
        _log(f"Chart suggestion fallback due to connectivity/issues after {elapsed:.2f}s")
        return {
            "chart_type": "table",
            "x_field": None,
            "y_field": None,
            "series_field": None,
            "rationale": "Fallback to table due to chart generation connectivity issues.",
        }

    try:
        suggestion = json.loads(completion.choices[0].message.content)
    except json.JSONDecodeError:
        suggestion = {}

    allowed_types = {"bar", "stacked_bar", "line", "donut", "table"}
    if suggestion.get("chart_type") not in allowed_types:
        elapsed = time.perf_counter() - chart_start
        _log(f"Chart suggestion invalid output; fallback to table after {elapsed:.2f}s")
        return {
            "chart_type": "table",
            "x_field": None,
            "y_field": None,
            "series_field": None,
            "rationale": "Fallback to table due to invalid chart type.",
        }

    elapsed = time.perf_counter() - chart_start
    _log(f"Chart suggestion ready chart_type={suggestion.get('chart_type')} elapsed={elapsed:.2f}s")
    return suggestion


def _summarize_result(
    question: str,
    sql_query: str,
    columns: List[str],
    rows: List[List[Any]],
    knowledge_space_id: str | None = None,
    kg_context: Dict[str, Any] | None = None,
) -> str:
    summary_start = time.perf_counter()
    if not rows or not columns:
        _log("Summary skipped: no rows or columns.")
        return (
            "I ran the query, but it returned no rows. "
            "Try broadening filters, checking date ranges, or asking for top-level aggregates."
        )

    if kg_context is None:
        kg_context = get_context_from_neo4j(question, columns, rows, knowledge_space_id)
    relations = (kg_context.get("relations") or [])[:24]
    # Chunk KG relations so prompt size stays bounded on larger graphs.
    relation_chunks = [relations[i : i + 6] for i in range(0, len(relations), 6)]
    selected_chunks = relation_chunks[:2]
    compact_kg_lines: List[str] = []
    for chunk_index, chunk in enumerate(selected_chunks, start=1):
        compact_kg_lines.append(f"Chunk {chunk_index}:")
        for item in chunk:
            compact_kg_lines.append(
                f"- {item.get('subject', '')} -> {item.get('relation', '')} -> {item.get('object', '')}"
            )
    compact_kg_text = "\n".join(compact_kg_lines) if compact_kg_lines else "No KG relations."

    system_prefix = (
        "You are a senior reliability engineer reviewing plant alarm data. "
        "Write sharp, concise operational insights. "
        "Do not restate definitions or explain what codes mean unless necessary. "
        "Focus only on what is unusual, risky, or worth acting on. "
        "Avoid generic commentary. Avoid mentioning the knowledge graph. "
        "Keep it tight and decision-oriented."
    )

    compact_columns = columns[:8]
    sample_rows = rows[:3]
    template = (
        f"Question: {question}\n"
        f"Columns: {compact_columns}\n"
        f"Row count: {len(rows)}\n"
        f"Sample rows: {sample_rows}\n"
        f"KG relations:\n{compact_kg_text}\n\n"
        "Write 3 concise, action-oriented insights. "
        "Ground insights in returned rows first, then KG if relevant. "
        "Do not mention the knowledge graph."
    )

    try:
        completion = _chat_completion_with_retry(
            model=SUMMARY_MODEL,
            messages=[
                {"role": "developer", "content": system_prefix},
                {"role": "user", "content": template},
            ],
            retries=1,
            timeout_seconds=18,
        )
        summary = (completion.choices[0].message.content or "").strip()
        elapsed = time.perf_counter() - summary_start
        _log(f"Summary generation completed elapsed={elapsed:.2f}s")
        return (
            summary
            or "Results are available in the table and chart. Ask a follow-up for deeper analysis."
        )
    except Exception:
        elapsed = time.perf_counter() - summary_start
        _log(f"Summary generation failed after {elapsed:.2f}s")
        return "Results are available in the table. Summary generation temporarily failed due to network issues."


async def run_agent(
    question: str,
    datasource: DataSource,
    include_visualization: bool = True,
    knowledge_space_id: str | None = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    request_start = time.perf_counter()
    _log("run_agent start")
    yield {
        "status": "progress",
        "step": "schema",
        "message": "Reading schema",
    }
    schema = await asyncio.to_thread(datasource.get_schema)
    _log(f"Schema loaded elapsed={time.perf_counter() - request_start:.2f}s")
    yield {
        "status": "progress",
        "step": "sql",
        "message": "Generating SQL query",
    }
    try:
        sql_query = await asyncio.wait_for(
            asyncio.to_thread(_build_reactive_sql, question, datasource),
            timeout=SQL_GEN_TIMEOUT_SECONDS,
        )
        _log(f"SQL generated elapsed={time.perf_counter() - request_start:.2f}s")
    except asyncio.TimeoutError:
        _log("SQL generation timeout")
        yield {
            "status": "partial",
            "sql_query": "",
            "columns": [],
            "rows": [],
            "error": (
                "Timed out while generating SQL. "
                "Try a simpler question or narrower date range."
            ),
        }
        yield {
            "status": "complete",
            "sql_query": "",
            "columns": [],
            "rows": [],
            "chart_suggestion": {
                "chart_type": "table",
                "x_field": None,
                "y_field": None,
                "series_field": None,
                "rationale": "No query generated due to timeout.",
            },
            "summary_text": "Query generation timed out. Try rephrasing or narrowing scope.",
            "error": "sql_generation_timeout",
        }
        return

    yield {
        "status": "progress",
        "step": "query",
        "message": "Running query",
    }
    try:
        sql_result = await asyncio.wait_for(
            asyncio.to_thread(_run_sql_with_retry, question, datasource, sql_query, False),
            timeout=SQL_RUN_TIMEOUT_SECONDS,
        )
        _log(f"SQL execution completed elapsed={time.perf_counter() - request_start:.2f}s")
    except asyncio.TimeoutError:
        _log("SQL execution timeout")
        sql_result = {
            "sql_query": sql_query,
            "columns": [],
            "rows": [],
            "error": "Query execution timed out.",
        }

    columns = sql_result.get("columns", [])
    rows = sql_result.get("rows", [])
    final_sql = sql_result.get("sql_query", sql_query)
    error = sql_result.get("error")

    yield {
        "status": "partial",
        "sql_query": final_sql,
        "columns": columns,
        "rows": rows,
        "error": error,
    }

    yield {
        "status": "progress",
        "step": "postprocess",
        "message": "Generating chart and insights",
    }

    postprocess_start = time.perf_counter()
    _log("Postprocess started: fetching KG context")
    kg_context = await asyncio.to_thread(
        get_context_from_neo4j, question, columns, rows, knowledge_space_id
    )
    _log(
        "KG context fetched "
        f"relations={len(kg_context.get('relations', []))} "
        f"elapsed={time.perf_counter() - postprocess_start:.2f}s"
    )
    knowledge_relations = (kg_context.get("relations") or [])[:12]

    _log("Postprocess started: launching summary/chart tasks")
    summary_task = asyncio.to_thread(
        _summarize_result,
        question,
        final_sql,
        columns,
        rows,
        knowledge_space_id,
        kg_context,
    )

    if include_visualization:
        chart_task = asyncio.to_thread(
            _generate_chart_suggestion, question, schema, columns, rows
        )
    else:
        chart_task = asyncio.sleep(
            0,
            result={
                "chart_type": "table",
                "x_field": None,
                "y_field": None,
                "series_field": None,
                "rationale": "Visualization disabled",
            },
        )

    try:
        summary_text, chart_suggestion = await asyncio.wait_for(
            asyncio.gather(summary_task, chart_task),
            timeout=POSTPROCESS_TIMEOUT_SECONDS,
        )
        _log(f"Postprocess finished elapsed={time.perf_counter() - postprocess_start:.2f}s")
    except asyncio.TimeoutError:
        _log(
            "Postprocess timeout "
            f"limit={POSTPROCESS_TIMEOUT_SECONDS}s elapsed={time.perf_counter() - postprocess_start:.2f}s"
        )
        summary_text = (
            "Base query results are ready. Extra insight generation timed out."
        )
        chart_suggestion = {
            "chart_type": "table",
            "x_field": None,
            "y_field": None,
            "series_field": None,
            "rationale": "Fallback to table because post-processing timed out.",
        }

    yield {
        "status": "complete",
        "sql_query": final_sql,
        "columns": columns,
        "rows": rows,
        "chart_suggestion": chart_suggestion,
        "summary_text": summary_text,
        "knowledge_relations": knowledge_relations,
        "error": error,
    }
    _log(f"run_agent complete total_elapsed={time.perf_counter() - request_start:.2f}s")


async def get_results(chunks: AsyncGenerator[Dict[str, Any], None]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    async for chunk in chunks:
        result.update(chunk)
    return result


def run_reactive_agent(
    question: str,
    datasource: DataSource,
    include_visualization: bool = True,
    knowledge_space_id: str | None = None,
) -> Dict[str, Any]:
    return asyncio.run(
        get_results(
            run_agent(
                question,
                datasource,
                include_visualization=include_visualization,
                knowledge_space_id=knowledge_space_id,
            )
        )
    )
