from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.data_sources.csv import CSVDataSource
from core.data_sources.sqlite import SQLiteDataSource
from text_2_sql_agentic import run_agent as run_legacy_agent
from text_2_sql_reactive_agent import run_agent as run_reactive_agent


BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY_PATH = UPLOADS_DIR / "registry.json"

app = FastAPI(title="Text2SQL Agent API", version="0.1.0")

origins = os.environ.get("FASTAPI_ALLOW_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DataSourceInfo(BaseModel):
    id: str
    type: str
    name: str


class QueryRequest(BaseModel):
    datasource_id: str
    question: str
    include_visualization: bool = True
    agent_mode: str = "reactive"


class QueryResponse(BaseModel):
    sql_query: str
    columns: List[str]
    rows: List[List[object]]
    chart_suggestion: Dict[str, object]
    summary_text: str
    status: str
    error: str | None = None


_datasources: Dict[str, object] = {}
_datasource_meta: Dict[str, DataSourceInfo] = {}
_datasource_paths: Dict[str, str] = {}


def _load_registry() -> Dict[str, Dict[str, str]]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_registry(registry: Dict[str, Dict[str, str]]) -> None:
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _rehydrate_datasource(datasource_id: str) -> object | None:
    registry = _load_registry()
    record = registry.get(datasource_id)
    if not record:
        return None

    path = record.get("path")
    ds_type = record.get("type")
    name = record.get("name", os.path.basename(path) if path else datasource_id)

    if not path or not os.path.exists(path):
        return None

    if ds_type == "sqlite":
        datasource = SQLiteDataSource(path)
    elif ds_type == "csv":
        datasource = CSVDataSource(path)
    else:
        return None

    _datasources[datasource_id] = datasource
    _datasource_meta[datasource_id] = DataSourceInfo(
        id=datasource_id, type=ds_type, name=name
    )
    _datasource_paths[datasource_id] = path
    return datasource


@app.post("/datasources/sqlite", response_model=DataSourceInfo)
def register_sqlite_source(file: UploadFile = File(...)) -> DataSourceInfo:
    if not file.filename:
        raise HTTPException(status_code=400, detail="SQLite file missing.")

    dest = UPLOADS_DIR / f"{uuid.uuid4()}_{file.filename}"
    with dest.open("wb") as f:
        f.write(file.file.read())

    datasource = SQLiteDataSource(str(dest))
    datasource_id = str(uuid.uuid4())
    info = DataSourceInfo(id=datasource_id, type="sqlite", name=file.filename)
    _datasources[datasource_id] = datasource
    _datasource_meta[datasource_id] = info
    _datasource_paths[datasource_id] = str(dest)

    registry = _load_registry()
    registry[datasource_id] = {"type": "sqlite", "path": str(dest), "name": file.filename}
    _save_registry(registry)
    return info


@app.post("/datasources/csv", response_model=DataSourceInfo)
def register_csv_source(file: UploadFile = File(...)) -> DataSourceInfo:
    if not file.filename:
        raise HTTPException(status_code=400, detail="CSV file missing.")

    dest = UPLOADS_DIR / f"{uuid.uuid4()}_{file.filename}"
    with dest.open("wb") as f:
        f.write(file.file.read())

    datasource = CSVDataSource(str(dest))
    datasource_id = str(uuid.uuid4())
    info = DataSourceInfo(id=datasource_id, type="csv", name=file.filename)
    _datasources[datasource_id] = datasource
    _datasource_meta[datasource_id] = info
    _datasource_paths[datasource_id] = str(dest)

    registry = _load_registry()
    registry[datasource_id] = {"type": "csv", "path": str(dest), "name": file.filename}
    _save_registry(registry)
    return info


@app.get("/datasources", response_model=List[DataSourceInfo])
def list_datasources() -> List[DataSourceInfo]:
    registry = _load_registry()
    for datasource_id, record in registry.items():
        if datasource_id not in _datasource_meta:
            _rehydrate_datasource(datasource_id)
    return list(_datasource_meta.values())


@app.get("/datasources/{datasource_id}/schema")
def get_schema(datasource_id: str) -> Dict[str, object]:
    datasource = _datasources.get(datasource_id)
    if datasource is None:
        datasource = _rehydrate_datasource(datasource_id)
    if datasource is None:
        raise HTTPException(status_code=404, detail="Datasource not found.")
    return datasource.get_schema()


@app.post("/query")
async def query(payload: QueryRequest) -> Any:
    datasource = _datasources.get(payload.datasource_id)
    if datasource is None:
        datasource = _rehydrate_datasource(payload.datasource_id)
    if datasource is None:
        raise HTTPException(status_code=404, detail="Datasource not found.")

    if payload.agent_mode.lower() == "legacy":
        result = run_legacy_agent(
            question=payload.question,
            datasource=datasource,
            include_visualization=payload.include_visualization,
        )
        return QueryResponse(
            sql_query=result.get("sql_query", ""),
            columns=result.get("columns", []),
            rows=result.get("rows", []),
            chart_suggestion=result.get("chart_suggestion", {}),
            summary_text=result.get("summary_text", ""),
            status="complete",
            error=result.get("error"),
        )

    async def event_stream():
        async for chunk in run_reactive_agent(
            question=payload.question,
            datasource=datasource,
            include_visualization=payload.include_visualization,
        ):
            yield json.dumps(chunk, ensure_ascii=True) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
