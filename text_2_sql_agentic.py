from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from openai import OpenAI
from typing_extensions import TypedDict

from dotenv import load_dotenv

from core.data_sources.base import DataSource

load_dotenv()


def _get_openai_client() -> OpenAI:
    """Create a fresh OpenAI client with current env vars."""
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


MANUFACTURING_KNOWLEDGE_GRAPH: Dict[str, Dict[str, List[str]]] = {
    "Manufacturing Plant": {
        "has_document": ["Error Code Reference Guide"],
        "contains_system": ["Automated Multi-Station Assembly & Inspection Line"],
        "tracks_data_in": ["Production Loss Database"],
    },
    "Error Code 0": {
        "means": ["Normal Operation"],
        "related_to": [
            "Informational Event",
            "Startup Sequence",
            "Batch Completion",
            "Planned Restart",
        ],
    },
    "Error Code 1": {
        "means": ["Minor Transient Fault"],
        "caused_by": ["Sensor", "PLC", "Voltage"],
    },
    "Error Code 197": {
        "means": ["Conveyor Jam"],
        "caused_by": ["Debris", "Conveyor Belt"],
        "related_to": ["Transport System"],
    },
    "Error Code 305": {
        "means": ["Motor Overcurrent"],
        "caused_by": ["Bearing"],
        "related_to": ["Drive Motor"],
    },
    "Error Code 412": {
        "means": ["Gearbox Vibration"],
        "caused_by": ["Vibration Sensor"],
    },
    "Error Code 293": {
        "means": ["Robotic Arm"],
        "caused_by": ["Encoder", "Joint"],
    },
    "Error Code 321": {
        "means": ["Servo Drive"],
        "caused_by": ["Ethernet"],
        "related_to": ["PLC", "Servo Controller"],
    },
    "Error Code 334": {
        "means": ["Axis Synchronization"],
        "caused_by": ["Encoder"],
    },
    "Error Code 290": {
        "means": ["Pneumatic Pressure"],
        "caused_by": ["Air Compressor"],
        "related_to": ["Pressure Regulator"],
    },
    "Error Code 288": {
        "means": ["Temperature Threshold"],
        "caused_by": ["Cooling Fan"],
    },
    "Error Code 355": {
        "means": ["Humidity Control"],
        "caused_by": ["HVAC", "Humidity Sensor"],
    },
    "Error Code 460": {
        "means": ["Vision System"],
        "related_to": ["Inspection System", "CPU", "Camera", "Lighting System"],
    },
    "Error Code 478": {
        "means": ["Quality Reject Threshold"],
        "related_to": ["Statistical Control Limit", "Quality Investigation"],
    },
    "Error Code 1241": {
        "means": ["Database"],
        "related_to": ["Central Logging Database", "Authentication Token"],
    },
    "Error Code 1502": {
        "means": ["MES"],
        "related_to": ["Manufacturing Execution System", "API", "Firewall"],
    },
    "Error Code 188": {
        "means": ["Power Supply"],
        "caused_by": ["Voltage"],
        "related_to": ["UPS", "Electrical Panel"],
    },
    "Error Code 378": {
        "means": ["Safety Interlock"],
        "related_to": [
            "Safety Circuit",
            "Emergency Stop",
            "Guard Door",
            "Safety Sensor",
        ],
    },
    "Error Code 390": {
        "means": ["Light Curtain"],
        "related_to": ["Safety Zone"],
    },
    "Analysis Tools": {
        "includes": ["Pareto Analysis", "Maintenance Logs", "Predictive Analytics"],
    },
}

class InputState(TypedDict):
    question: str
    datasource: DataSource
    schema: Dict[str, Any]
    sql_query: str
    columns: List[str]
    rows: List[List[Any]]
    retry_count: int
    no_data: bool
    error: Optional[str]
    sql_checked: bool
    visualize_enabled: bool
    chart_suggestion: Dict[str, Any]
    summary_text: str

class OutputState(TypedDict):
    sql_query: str
    columns: List[str]
    rows: List[List[Any]]
    chart_suggestion: Dict[str, Any]
    summary_text: str

def get_schema(state) -> dict:
    """Retrieves the schema using the configured DataSource."""
    datasource = state["datasource"]
    schema = datasource.get_schema()
    return {"schema": schema}

def generate_sql_query(state) -> dict:
    """Generates a SQL query from a natural language question."""
    question = state["question"]
    schema = state["schema"]
    
    llm = ChatOpenAI(model="gpt-5-nano")
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
        You are an SQL expert. Generate a SQLite-compatible SQL query based on the database schema and question.
        Always generate syntactically correct SQLite queries. Avoid including unncessary columns in the query. Only use the columns that are relevant to the question. If the user asks to exclude something from the results, follow the instructions completely.
        Ensure the output query is executable. Do not put ```sql in the beginning of the query. Just provide raw executable query as a string. Use appropriate column names for the results.
        """),
        ("human", "===Database Schema:\n{schema}\n\n===User Question:\n{question}\n\nSQLite Query:")
    ])
    
    generate_query_chain = prompt | llm | StrOutputParser()
    response = generate_query_chain.invoke({"question": question, "schema": schema})

    print(f"Original SQL query: {response}")
    
    return {"sql_query": response}

def sql_query_checker(state) -> dict:
    """Basic SQL query checker."""

    query = state["sql_query"]
    question = state["question"]

    query_check_system_prefix = """You are an SQL expert with a strong attention to detail.
    You will be provided a SQLite query and a question. Double check the SQL query for common mistakes and verify if it answers the question properly.
    If there are any mistakes, rewrite the query. If there are no mistakes, just reproduce the original query. Always produce the query as raw string which the user can execute directly.
    Do not output anything else other then the query itself. No explanations. Just provide the relevant query."""

    template = f"""
    Check if the SQL query answers the user question properly. Specifically, review if the query satisfies all the information asked by the user and is syntactically correct.

    Question: {question}
    SQLite Query: {query}
    """

    client = _get_openai_client()
    completion = client.chat.completions.create(
    model="gpt-5-mini",
    messages=[
        {"role": "developer", "content": query_check_system_prefix},
        {
            "role": "user",
            "content": template,
        },
    ])
    print(f"SQL query checker response: {completion.choices[0].message.content}")
    return {
        "sql_query": completion.choices[0].message.content,
        "sql_checked": True,
    }

def run_sql_query(state) -> dict:
    """Executes a SQL query using the DataSource and returns columns/rows."""
    query = state["sql_query"]
    datasource = state["datasource"]

    try:
        columns, rows = datasource.run_query(query)
        return {
            "columns": columns,
            "rows": [list(row) for row in rows],
            "no_data": len(rows) == 0,
            "error": None,
        }
    except Exception as exc:
        return {
            "columns": [],
            "rows": [],
            "no_data": True,
            "error": f"Error executing query: {exc}",
        }


def generate_chart_suggestion(state) -> dict:
    """Select a chart type and config for frontend rendering."""
    question = state["question"]
    columns = state.get("columns", [])
    rows = state.get("rows", [])
    schema = state.get("schema", {})

    if not rows or not columns:
        return {
            "chart_suggestion": {
                "chart_type": "table",
                "x_field": None,
                "y_field": None,
                "series_field": None,
                "rationale": "No data returned; defaulting to table.",
            }
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

    client = _get_openai_client()
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "developer", "content": system_prefix},
            {"role": "user", "content": template},
        ],
    )

    try:
        suggestion = json.loads(completion.choices[0].message.content)
    except json.JSONDecodeError:
        suggestion = {}

    chart_type = suggestion.get("chart_type")
    allowed_types = {"bar", "stacked_bar", "line", "donut", "table"}
    if chart_type not in allowed_types:
        suggestion = {
            "chart_type": "table",
            "x_field": None,
            "y_field": None,
            "series_field": None,
            "rationale": "Fallback to table due to invalid chart type.",
        }

    return {"chart_suggestion": suggestion}


def generate_simpler_query(state) -> dict:
    """Regenerate a simpler SQL query when no data is returned."""
    question = state["question"]
    schema = state["schema"]
    previous_query = state["sql_query"]
    retry_count = state.get("retry_count", 0)

    system_prefix = (
        "You are an SQL expert. The previous SQL query returned zero rows. "
        "Generate a simpler SQLite query that is more likely to return data. "
        "Avoid overly restrictive filters and prefer broader aggregation. "
        "Return only the SQL query as plain text."
    )

    template = f"""
    Question: {question}
    Schema: {schema}
    Previous Query: {previous_query}
    Reason: The query executed successfully but returned no rows.

    Simpler SQLite Query:
    """

    client = _get_openai_client()
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "developer", "content": system_prefix},
            {"role": "user", "content": template},
        ],
    )

    return {
        "sql_query": completion.choices[0].message.content,
        "retry_count": retry_count + 1,
    }


def summarize_result(state) -> dict:
    """Generate domain-grounded, user-friendly reliability insights."""
    question = state["question"]
    sql_query = state.get("sql_query", "")
    columns = state.get("columns", [])
    rows = state.get("rows", [])
    chart_suggestion = state.get("chart_suggestion", {})

    if not rows or not columns:
        return {
            "summary_text": (
                "I ran the query, but it returned no rows. "
                "Try broadening filters, checking date ranges, or asking for top-level aggregates."
            )
        }

    sample_rows = rows[:10]
    chart_type = chart_suggestion.get("chart_type", "table")

    system_prefix = (
    "You are a senior reliability engineer reviewing plant alarm data. "
    "Write sharp, concise operational insights. "
    "Do not restate definitions or explain what codes mean unless necessary. "
    "Focus only on what is unusual, risky, or worth acting on. "
    "Avoid generic commentary. Avoid mentioning the knowledge graph. "
    "Keep it tight and decision-oriented."
    )

    template = f"""
    Knowledge Graph (JSON):
    {json.dumps(MANUFACTURING_KNOWLEDGE_GRAPH, indent=2)}

    User question: {question}

    SQL used: {sql_query}
    Columns: {columns}
    Row count: {len(rows)}
    Sample rows: {sample_rows}

    Write 3–5 concise insights (max 2 sentences each).
    Only include findings that would matter in an operations meeting.
    Skip obvious restatements.
    Do not mention the knowledge graph.
    """

    client = _get_openai_client()
    completion = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "developer", "content": system_prefix},
            {"role": "user", "content": template},
        ],
    )

    summary = (completion.choices[0].message.content or "").strip()
    if not summary:
        summary = "Results are available in the table and chart. Ask a follow-up for deeper analysis."

    return {"summary_text": summary}


def route_after_run_sql(state) -> str:
    has_error = bool(state.get("error"))
    has_data = bool(state.get("rows"))
    visualize_enabled = state.get("visualize_enabled", True)

    if not has_error and has_data:
        return "select_chart" if visualize_enabled else "summarize_result"

    if not state.get("sql_checked", False):
        return "check_sql_query"

    if state.get("retry_count", 0) < 1:
        return "retry_query"

    return "select_chart" if visualize_enabled else "summarize_result"


def build_workflow() -> StateGraph:
    workflow = StateGraph(InputState, output=OutputState)
    workflow.add_node("get_schema", get_schema)
    workflow.add_node("generate_sql", generate_sql_query)
    workflow.add_node("check_sql_query", sql_query_checker)
    workflow.add_node("run_sql", run_sql_query)
    workflow.add_node("retry_query", generate_simpler_query)
    workflow.add_node("select_chart", generate_chart_suggestion)
    workflow.add_node("summarize_result", summarize_result)

    workflow.add_edge("get_schema", "generate_sql")
    workflow.add_edge("generate_sql", "run_sql")
    workflow.add_edge("check_sql_query", "run_sql")
    workflow.add_conditional_edges(
        "run_sql",
        route_after_run_sql,
        {
            "check_sql_query": "check_sql_query",
            "retry_query": "retry_query",
            "select_chart": "select_chart",
            "summarize_result": "summarize_result",
        },
    )
    workflow.add_edge("retry_query", "run_sql")
    workflow.add_edge("select_chart", "summarize_result")
    workflow.add_edge("summarize_result", END)
    workflow.set_entry_point("get_schema")

    return workflow


_compiled_workflow = None


def run_agent(
    question: str,
    datasource: DataSource,
    include_visualization: bool = True,
) -> OutputState:
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_workflow().compile()

    state = {
        "question": question,
        "datasource": datasource,
        "retry_count": 0,
        "sql_checked": False,
        "visualize_enabled": include_visualization,
        "chart_suggestion": {
            "chart_type": "table",
            "x_field": None,
            "y_field": None,
            "series_field": None,
            "rationale": (
                "Visualization disabled by user preference."
                if not include_visualization
                else "No chart selected yet."
            ),
        },
    }

    result = _compiled_workflow.invoke(state)
    return result


if __name__ == "__main__":
    from core.data_sources.sqlite import SQLiteDataSource

    db_path = "loss-data.db"
    datasource = SQLiteDataSource(db_path)
    output = run_agent(
        question="Show the top 10 error codes by frequency.",
        datasource=datasource,
    )
    print(output)
