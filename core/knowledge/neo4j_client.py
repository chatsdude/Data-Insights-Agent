from __future__ import annotations

import os
from typing import Any, Dict, List, Sequence, Tuple

from neo4j import GraphDatabase

from core.knowledge.runtime import APP_SCOPE, CURRENT_SESSION_ID


def _get_driver():
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")
    if not uri or not user or not password:
        return None
    return GraphDatabase.driver(uri, auth=(user, password))


def upsert_triples(
    *,
    space_id: str,
    triples: List[Tuple[str, str, str]],
    source_doc_id: str,
) -> None:
    driver = _get_driver()
    if driver is None:
        raise RuntimeError("Neo4j is not configured.")

    cypher = """
    MERGE (a:Entity {
      name: $subject,
      space_id: $space_id,
      app_scope: $app_scope,
      session_id: $session_id
    })
    MERGE (b:Entity {
      name: $object,
      space_id: $space_id,
      app_scope: $app_scope,
      session_id: $session_id
    })
    MERGE (a)-[r:RELATED {relation: $relation, source_doc_id: $source_doc_id}]->(b)
    """

    with driver.session() as session:
        for subject, relation, obj in triples:
            if not subject or not relation or not obj:
                continue
            session.run(
                cypher,
                subject=subject.strip(),
                relation=relation.strip(),
                object=obj.strip(),
                source_doc_id=source_doc_id,
                space_id=space_id,
                app_scope=APP_SCOPE,
                session_id=CURRENT_SESSION_ID,
            )

    driver.close()


def query_context(
    *,
    space_id: str,
    question: str,
    terms: Sequence[str] | None = None,
    limit: int = 20,
) -> Dict[str, Any]:
    driver = _get_driver()
    if driver is None:
        return {"entities": [], "relations": [], "source": "neo4j_unconfigured"}

    tokens = [token.strip().lower() for token in (terms or []) if token.strip()]
    if not tokens:
        tokens = [token.strip().lower() for token in question.split() if token.strip()]
    if not tokens:
        tokens = [""]

    cypher = """
    MATCH (a:Entity {
      space_id: $space_id,
      app_scope: $app_scope,
      session_id: $session_id
    })-[r:RELATED]->(b:Entity {
      space_id: $space_id,
      app_scope: $app_scope,
      session_id: $session_id
    })
    WITH a, r, b, [token IN $tokens WHERE
      toLower(a.name) CONTAINS token OR
      toLower(b.name) CONTAINS token OR
      toLower(r.relation) CONTAINS token
    ] AS matched_tokens
    WITH a, r, b, size(matched_tokens) AS score
    WHERE score >= $min_score
    RETURN a.name AS subject, r.relation AS relation, b.name AS object, score
    ORDER BY score DESC
    LIMIT $limit
    """

    records: List[Tuple[str, str, str]] = []
    source = "neo4j"
    with driver.session() as session:
        result = session.run(
            cypher,
            space_id=space_id,
            app_scope=APP_SCOPE,
            session_id=CURRENT_SESSION_ID,
            tokens=tokens,
            min_score=2,
            limit=limit,
        )
        records = [
            (
                row.get("subject", ""),
                row.get("relation", ""),
                row.get("object", ""),
                row.get("score", 0),
            )
            for row in result
        ]
        if not records:
            print(
                f"[kg-retrieval] fallback used space_id={space_id} session_id={CURRENT_SESSION_ID}",
                flush=True,
            )
            # Fallback: return a small sample of current-session relations for the space.
            fallback_cypher = """
            MATCH (a:Entity {
              space_id: $space_id,
              app_scope: $app_scope,
              session_id: $session_id
            })-[r:RELATED]->(b:Entity {
              space_id: $space_id,
              app_scope: $app_scope,
              session_id: $session_id
            })
            RETURN a.name AS subject, r.relation AS relation, b.name AS object
            LIMIT $limit
            """
            fallback_result = session.run(
                fallback_cypher,
                space_id=space_id,
                app_scope=APP_SCOPE,
                session_id=CURRENT_SESSION_ID,
                limit=min(limit, 12),
            )
            records = [
                (
                    row.get("subject", ""),
                    row.get("relation", ""),
                    row.get("object", ""),
                    0,
                )
                for row in fallback_result
            ]
            source = "neo4j_fallback"
        else:
            print(
                f"[kg-retrieval] matched relations={len(records)} space_id={space_id} session_id={CURRENT_SESSION_ID}",
                flush=True,
            )

    driver.close()

    entities = sorted(list({value for rec in records for value in (rec[0], rec[2]) if value}))
    relations = [
        {"subject": subject, "relation": relation, "object": obj, "score": score}
        for subject, relation, obj, score in records
    ]
    return {"entities": entities, "relations": relations, "source": source}


def clear_previous_sessions() -> None:
    driver = _get_driver()
    if driver is None:
        return

    cypher = """
    MATCH (n:Entity {app_scope: $app_scope})
    WHERE n.session_id <> $session_id
    DETACH DELETE n
    """
    with driver.session() as session:
        session.run(
            cypher,
            app_scope=APP_SCOPE,
            session_id=CURRENT_SESSION_ID,
        )
    driver.close()
