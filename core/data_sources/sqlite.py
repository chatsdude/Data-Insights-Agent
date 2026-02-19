from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Tuple

from .base import DataSource, QueryResult, SchemaType


class SQLiteDataSource(DataSource):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def get_schema(self) -> SchemaType:
        schema: SchemaType = {}
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            tables = [row[0] for row in cursor.fetchall()]
            for table_name in tables:
                cursor.execute(f"PRAGMA table_info('{table_name}')")
                columns = [row[1] for row in cursor.fetchall()]
                cursor.execute(f"SELECT * FROM '{table_name}' LIMIT 3")
                sample_rows = cursor.fetchall()
                schema[table_name] = {
                    "columns": columns,
                    "sample_rows": [list(row) for row in sample_rows],
                }
        return schema

    def run_query(self, query: str) -> QueryResult:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [column[0] for column in cursor.description] if cursor.description else []
        return columns, rows
