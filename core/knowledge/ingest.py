from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI
from pypdf import PdfReader

from core.knowledge.neo4j_client import upsert_triples
from core.knowledge.store import (
    load_documents,
    load_jobs,
    save_documents,
    save_jobs,
)

KG_EXTRACT_MODEL = os.environ.get("KG_EXTRACT_MODEL", "gpt-4o-mini")
KG_MAX_TRIPLES = int(os.environ.get("KG_MAX_TRIPLES", "80"))
KG_INPUT_CHAR_LIMIT = int(os.environ.get("KG_INPUT_CHAR_LIMIT", "30000"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_openai_client() -> OpenAI:
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def _fallback_extract_triples(text: str) -> List[Tuple[str, str, str]]:
    triples: List[Tuple[str, str, str]] = []

    for raw in text.splitlines():
        line = raw.strip()
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        subject = left.strip()
        obj = right.strip()
        if subject and obj:
            triples.append((subject, "describes", obj))
            if len(triples) >= KG_MAX_TRIPLES:
                break
    return triples


def extract_triples(text: str) -> List[Tuple[str, str, str]]:
    prompt = (
        "Extract only the most important factual relationships from the text.\n"
        f"Return at most {KG_MAX_TRIPLES} triples.\n"
        "Output strict JSON with this shape: "
        '{"triples":[{"subject":"...","relation":"...","object":"..."}]}.\n'
        "Keep entities short and specific. Avoid generic relations."
    )
    content = text[:KG_INPUT_CHAR_LIMIT]

    try:
        completion = _get_openai_client().chat.completions.create(
            model=KG_EXTRACT_MODEL,
            messages=[
                {"role": "developer", "content": prompt},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            timeout=35,
        )
        parsed = json.loads(completion.choices[0].message.content or "{}")
        raw_triples = parsed.get("triples") or []
        triples: List[Tuple[str, str, str]] = []
        seen = set()
        for item in raw_triples:
            if not isinstance(item, dict):
                continue
            subject = str(item.get("subject", "")).strip()
            relation = str(item.get("relation", "")).strip().lower()
            obj = str(item.get("object", "")).strip()
            if not subject or not relation or not obj:
                continue
            triple = (subject, relation, obj)
            if triple in seen:
                continue
            seen.add(triple)
            triples.append(triple)
            if len(triples) >= KG_MAX_TRIPLES:
                break
        if triples:
            return triples
    except Exception:
        pass

    return _fallback_extract_triples(content)


def _update_job(job_id: str, *, status: str, stage: str, progress: int, error: str | None = None) -> None:
    jobs = load_jobs()
    record = jobs.get(job_id)
    if not record:
        return
    record["status"] = status
    record["stage"] = stage
    record["progress"] = progress
    record["error"] = error
    record["updated_at"] = _now_iso()
    save_jobs(jobs)


def _update_document(document_id: str, *, status: str) -> None:
    docs = load_documents()
    record = docs.get(document_id)
    if not record:
        return
    record["status"] = status
    save_documents(docs)


def run_ingestion_job(job_id: str) -> None:
    jobs = load_jobs()
    job = jobs.get(job_id)
    if not job:
        return

    document_id = job["document_id"]
    space_id = job["space_id"]
    docs = load_documents()
    doc = docs.get(document_id)
    if not doc:
        _update_job(
            job_id,
            status="failed",
            stage="load_document",
            progress=100,
            error="Document not found.",
        )
        return

    try:
        _update_job(job_id, status="processing", stage="extract_text", progress=20)
        _update_document(document_id, status="processing")

        text = extract_text(doc["path"])
        _update_job(job_id, status="processing", stage="extract_triples_llm", progress=60)

        triples = extract_triples(text)
        _update_job(job_id, status="processing", stage="upsert_neo4j", progress=85)

        upsert_triples(space_id=space_id, triples=triples, source_doc_id=document_id)

        _update_document(document_id, status="completed")
        _update_job(job_id, status="completed", stage="done", progress=100)
    except Exception as exc:
        _update_document(document_id, status="failed")
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            progress=100,
            error=str(exc),
        )
