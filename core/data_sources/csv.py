from __future__ import annotations

import os
import sqlite3
import tempfile

import pandas as pd

from .base import DataSource, QueryResult, SchemaType
from .sqlite import SQLiteDataSource


class CSVDataSource(DataSource):
    """Load a CSV into a temporary SQLite database for SQL queries."""

    def __init__(self, csv_path: str, table_name: str = "data") -> None:
        self.csv_path = csv_path
        self.table_name = table_name
        self._sqlite_path = self._create_sqlite_db()
        self._sqlite = SQLiteDataSource(self._sqlite_path)

    def _create_sqlite_db(self) -> str:
        df = pd.read_csv(self.csv_path)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        df.to_sql(self.table_name, conn, if_exists="replace", index=False)
        conn.close()
        return tmp.name

    def get_schema(self) -> SchemaType:
        return self._sqlite.get_schema()

    def run_query(self, query: str) -> QueryResult:
        return self._sqlite.run_query(query)

    def cleanup(self) -> None:
        if os.path.exists(self._sqlite_path):
            os.remove(self._sqlite_path)
