from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.data_sources.csv import CSVDataSource
from core.data_sources.sqlite import SQLiteDataSource
from core.knowledge.ingest import run_ingestion_job
from core.knowledge.models import (
    DocumentInfo,
    IngestionJobInfo,
    KnowledgeSpaceCreate,
    KnowledgeSpaceInfo,
)
from core.knowledge.neo4j_client import clear_previous_sessions
from core.knowledge.runtime import CURRENT_SESSION_ID
from core.knowledge.store import (
    KNOWLEDGE_DIR,
    load_documents,
    load_jobs,
    load_spaces,
    save_documents,
    save_jobs,
    save_spaces,
)
from text_2_sql_agentic import run_agent as run_legacy_agent
from text_2_sql_reactive_agent import run_agent as run_reactive_agent


BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY_PATH = UPLOADS_DIR / "registry.json"
KNOWLEDGE_DOCS_DIR = KNOWLEDGE_DIR / "docs"
KNOWLEDGE_DOCS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SPACES_PATH = BASE_DIR / "default_data" / "spaces.json"
DEFAULT_DATASOURCE_ID = "default-sqlite"
DEFAULT_DATASOURCE_NAME = os.environ.get(
    "DEFAULT_DATASOURCE_NAME", "loss-data.db (default)"
)
DEFAULT_SQLITE_PATH = Path(
    os.environ.get(
        "DEFAULT_SQLITE_PATH", str(BASE_DIR / "default_data" / "loss-data.db")
    )
)

app = FastAPI(title="Text2SQL Agent API", version="0.1.0")

origins = os.environ.get("FASTAPI_ALLOW_ORIGINS", "https://data-insights-agent-fz6i.vercel.app/").split(",")
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
    knowledge_space_id: str | None = None


class QueryResponse(BaseModel):
    sql_query: str
    columns: List[str]
    rows: List[List[object]]
    chart_suggestion: Dict[str, object]
    summary_text: str
    knowledge_relations: List[Dict[str, object]] = []
    status: str
    follow_up_questions: List[str] = []
    error: str | None = None


class DocumentUploadResponse(BaseModel):
    document: DocumentInfo
    job: IngestionJobInfo


_datasources: Dict[str, object] = {}
_datasource_meta: Dict[str, DataSourceInfo] = {}
_datasource_paths: Dict[str, str] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.on_event("startup")
def on_startup() -> None:
    _ensure_default_sqlite_datasource()
    _ensure_default_knowledge_spaces()
    should_flush = os.environ.get("KNOWLEDGE_FLUSH_ON_START", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    if not should_flush:
        return
    try:
        clear_previous_sessions()
        print(f"Knowledge graph session active: {CURRENT_SESSION_ID}")
    except Exception as exc:
        print(f"Knowledge graph cleanup skipped: {exc}")


def _load_registry() -> Dict[str, Dict[str, str]]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_registry(registry: Dict[str, Dict[str, str]]) -> None:
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _ensure_default_sqlite_datasource() -> None:
    if not DEFAULT_SQLITE_PATH.exists():
        print(f"Default datasource file not found: {DEFAULT_SQLITE_PATH}")
        return

    registry = _load_registry()
    registry[DEFAULT_DATASOURCE_ID] = {
        "type": "sqlite",
        "path": str(DEFAULT_SQLITE_PATH),
        "name": DEFAULT_DATASOURCE_NAME,
    }
    _save_registry(registry)
    _rehydrate_datasource(DEFAULT_DATASOURCE_ID)


def _ensure_default_knowledge_spaces() -> None:
    if load_spaces():
        return
    if not DEFAULT_SPACES_PATH.exists():
        print(f"Default knowledge spaces file not found: {DEFAULT_SPACES_PATH}")
        return
    try:
        payload = json.loads(DEFAULT_SPACES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Default knowledge spaces file is invalid JSON: {DEFAULT_SPACES_PATH}")
        return
    if not isinstance(payload, dict):
        print(f"Default knowledge spaces payload must be an object: {DEFAULT_SPACES_PATH}")
        return
    save_spaces(payload)


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
    _ensure_default_sqlite_datasource()
    registry = _load_registry()
    for datasource_id in registry:
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


@app.post("/knowledge-spaces", response_model=KnowledgeSpaceInfo)
def create_knowledge_space(payload: KnowledgeSpaceCreate) -> KnowledgeSpaceInfo:
    space_id = str(uuid.uuid4())
    record = {
        "id": space_id,
        "name": payload.name.strip() or "Untitled Space",
        "created_at": _now_iso(),
    }
    spaces = load_spaces()
    spaces[space_id] = record
    save_spaces(spaces)
    return KnowledgeSpaceInfo(**record)


@app.get("/knowledge-spaces", response_model=List[KnowledgeSpaceInfo])
def list_knowledge_spaces() -> List[KnowledgeSpaceInfo]:
    _ensure_default_knowledge_spaces()
    return [KnowledgeSpaceInfo(**item) for item in load_spaces().values()]


@app.post("/knowledge-spaces/{space_id}/documents", response_model=DocumentUploadResponse)
def upload_knowledge_document(
    space_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Document file missing.")
    spaces = load_spaces()
    if space_id not in spaces:
        raise HTTPException(status_code=404, detail="Knowledge space not found.")

    created_at = _now_iso()
    document_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    dest = KNOWLEDGE_DOCS_DIR / f"{document_id}_{file.filename}"
    with dest.open("wb") as f:
        f.write(file.file.read())

    documents = load_documents()
    document_record = {
        "id": document_id,
        "space_id": space_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "status": "uploaded",
        "path": str(dest),
        "created_at": created_at,
    }
    documents[document_id] = document_record
    save_documents(documents)

    jobs = load_jobs()
    job_record = {
        "id": job_id,
        "space_id": space_id,
        "document_id": document_id,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "error": None,
        "created_at": created_at,
        "updated_at": created_at,
    }
    jobs[job_id] = job_record
    save_jobs(jobs)

    background_tasks.add_task(run_ingestion_job, job_id)
    return DocumentUploadResponse(
        document=DocumentInfo(**{k: v for k, v in document_record.items() if k != "path"}),
        job=IngestionJobInfo(**job_record),
    )


@app.get("/ingestion-jobs/{job_id}", response_model=IngestionJobInfo)
def get_ingestion_job(job_id: str) -> IngestionJobInfo:
    jobs = load_jobs()
    record = jobs.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")
    return IngestionJobInfo(**record)


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
            knowledge_space_id=payload.knowledge_space_id,
        )
        return QueryResponse(
            sql_query=result.get("sql_query", ""),
            columns=result.get("columns", []),
            rows=result.get("rows", []),
            chart_suggestion=result.get("chart_suggestion", {}),
            summary_text=result.get("summary_text", ""),
            knowledge_relations=result.get("knowledge_relations", []),
            status="complete",
            error=result.get("error"),
        )

    async def event_stream():
        async for chunk in run_reactive_agent(
            question=payload.question,
            datasource=datasource,
            include_visualization=payload.include_visualization,
            knowledge_space_id=payload.knowledge_space_id,
        ):
            yield json.dumps(chunk, ensure_ascii=True) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
