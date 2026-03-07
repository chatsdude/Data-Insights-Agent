from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = BASE_DIR / "api" / "uploads" / "knowledge"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

SPACES_PATH = KNOWLEDGE_DIR / "spaces.json"
DOCUMENTS_PATH = KNOWLEDGE_DIR / "documents.json"
JOBS_PATH = KNOWLEDGE_DIR / "jobs.json"


def _load_json(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_json(path: Path, payload: Dict[str, Dict[str, Any]]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_spaces() -> Dict[str, Dict[str, Any]]:
    return _load_json(SPACES_PATH)


def save_spaces(payload: Dict[str, Dict[str, Any]]) -> None:
    _save_json(SPACES_PATH, payload)


def load_documents() -> Dict[str, Dict[str, Any]]:
    return _load_json(DOCUMENTS_PATH)


def save_documents(payload: Dict[str, Dict[str, Any]]) -> None:
    _save_json(DOCUMENTS_PATH, payload)


def load_jobs() -> Dict[str, Dict[str, Any]]:
    return _load_json(JOBS_PATH)


def save_jobs(payload: Dict[str, Dict[str, Any]]) -> None:
    _save_json(JOBS_PATH, payload)

