from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SPACES_PATH = ROOT / "api" / "uploads" / "knowledge" / "spaces.json"
ENV_PATH = ROOT / ".env"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_spaces() -> dict:
    if not SPACES_PATH.exists():
        return {}
    try:
        return json.loads(SPACES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_spaces_with_single_default(space_id: str, space_name: str) -> None:
    SPACES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        space_id: {
            "id": space_id,
            "name": space_name,
            "created_at": _now_iso(),
        }
    }
    SPACES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _upsert_env_var(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(prefix):
            out.append(f"{prefix}{value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{prefix}{value}")
    return out


def _update_env_defaults(space_id: str, session_id: str) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    lines = _upsert_env_var(lines, "KNOWLEDGE_DEFAULT_SPACE_ID", space_id)
    lines = _upsert_env_var(lines, "KNOWLEDGE_SESSION_ID", session_id)
    lines = _upsert_env_var(lines, "KNOWLEDGE_FLUSH_ON_START", "false")
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _resolve_files(paths: Iterable[str]) -> list[Path]:
    resolved: list[Path] = []
    for item in paths:
        p = Path(item)
        if not p.is_absolute():
            p = ROOT / p
        p = p.resolve()
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Document not found: {item}")
        resolved.append(p)
    if not resolved:
        raise ValueError("Provide at least one file path.")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-shot ingest docs into Neo4j and set them as default knowledge context."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Document files to ingest (pdf/txt/etc).",
    )
    parser.add_argument(
        "--space-name",
        default="test_new",
        help="Knowledge space name to persist in spaces.json (default: test_new).",
    )
    parser.add_argument(
        "--space-id",
        default=None,
        help="Optional fixed space id. If omitted, a new UUID is generated.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional fixed session id. If omitted, a new UUID is generated.",
    )
    args = parser.parse_args()

    load_dotenv(ENV_PATH)

    space_id = args.space_id or str(uuid.uuid4())
    session_id = args.session_id or str(uuid.uuid4())
    files = _resolve_files(args.files)

    # Must be set before importing modules that read runtime constants.
    os.environ["KNOWLEDGE_SESSION_ID"] = session_id
    os.environ["KNOWLEDGE_DEFAULT_SPACE_ID"] = space_id
    os.environ["KNOWLEDGE_FLUSH_ON_START"] = "false"

    from core.knowledge.ingest import extract_text, extract_triples
    from core.knowledge.neo4j_client import upsert_triples

    total_triples = 0
    for file_path in files:
        text = extract_text(str(file_path))
        triples = extract_triples(text)
        upsert_triples(
            space_id=space_id,
            triples=triples,
            source_doc_id=f"seed-{file_path.stem}",
        )
        total_triples += len(triples)
        print(f"Ingested {len(triples)} triples from {file_path.name}")

    _write_spaces_with_single_default(space_id, args.space_name)
    _update_env_defaults(space_id, session_id)

    print("Done.")
    print(f"Default space_id: {space_id}")
    print(f"Default session_id: {session_id}")
    print(f"Total triples ingested: {total_triples}")
    print(f"Updated: {SPACES_PATH}")
    print(f"Updated: {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

