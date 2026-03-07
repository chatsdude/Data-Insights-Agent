from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import spacy

from core.knowledge.neo4j_client import query_context
from core.knowledge.runtime import DEFAULT_SPACE_ID

_NLP = None


def _get_nlp():
    global _NLP
    if _NLP is not None:
        return _NLP
    try:
        _NLP = spacy.load("en_core_web_sm")
    except Exception:
        _NLP = spacy.blank("en")
        if "sentencizer" not in _NLP.pipe_names:
            _NLP.add_pipe("sentencizer")
    return _NLP


def extract_query_terms(question: str) -> list[str]:
    doc = _get_nlp()(question)
    terms: list[str] = []

    if doc.has_annotation("ENT_IOB"):
        for ent in doc.ents:
            value = ent.text.strip().lower()
            if len(value) > 1:
                terms.append(value)

    if doc.has_annotation("DEP"):
        for chunk in doc.noun_chunks:
            value = chunk.text.strip().lower()
            if len(value) > 2:
                terms.append(value)

    for token in doc:
        if token.is_stop or token.is_punct:
            continue
        value = (token.lemma_ or token.text).strip().lower()
        if len(value) > 2:
            terms.append(value)

    seen = set()
    deduped: list[str] = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        deduped.append(term)
        if len(deduped) >= 20:
            break
    return deduped


def extract_keyword_terms(text: str) -> list[str]:
    # Keep alphanumeric codes (e.g. E101, 305) plus normal words.
    tokens = re.findall(r"[A-Za-z]+\d+|\d+|[A-Za-z]{3,}", text)
    seen = set()
    result: list[str] = []
    for token in tokens:
        value = token.strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= 20:
            break
    return result


def _compact_result_text(columns: list[str], rows: list[list[Any]]) -> str:
    compact_rows = rows[:3]
    safe_rows = [[str(cell)[:40] for cell in row[:8]] for row in compact_rows]
    return json.dumps({"columns": columns[:8], "rows": safe_rows}, ensure_ascii=False)


def get_context_from_neo4j(
    question: str,
    columns: list[str],
    rows: list[list[Any]],
    knowledge_space_id: Optional[str],
) -> Dict[str, Any]:
    effective_space_id = knowledge_space_id or DEFAULT_SPACE_ID
    if not effective_space_id:
        return {"entities": [], "relations": [], "source": "none"}

    try:
        question_terms = extract_query_terms(question)
        result_text = _compact_result_text(columns, rows)
        result_terms = extract_query_terms(result_text)
        keyword_terms = extract_keyword_terms(
            f"{question}\n{result_text}"
        )
        terms = list(question_terms + result_terms + keyword_terms)
        # Preserve order and avoid very long token lists.
        seen = set()
        deduped_terms: list[str] = []
        for term in terms:
            if term in seen:
                continue
            seen.add(term)
            deduped_terms.append(term)
            if len(deduped_terms) >= 20:
                break
        return query_context(
            space_id=effective_space_id,
            question=question,
            terms=deduped_terms,
            limit=20,
        )
    except Exception:
        return {"entities": [], "relations": [], "source": "neo4j_error"}
