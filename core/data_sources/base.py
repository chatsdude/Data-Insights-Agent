from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Tuple


SchemaType = Dict[str, Dict[str, List[Any]]]
QueryResult = Tuple[List[str], List[Tuple[Any, ...]]]


class DataSource(ABC):
    """Abstract data source interface used by the agent."""

    @abstractmethod
    def get_schema(self) -> SchemaType:
        """Return schema with sample rows for each table."""

    @abstractmethod
    def run_query(self, query: str) -> QueryResult:
        """Execute query and return (columns, rows)."""
