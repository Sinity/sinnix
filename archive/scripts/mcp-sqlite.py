#!/usr/bin/env python3
"""Expose local SQLite databases over the Model Context Protocol (read-only).

Default database: `~/.local/share/atuin/history.db` or `MCP_SQLITE_DB`.

Tools:
  - list-tables: list tables in the database.
  - describe-table: inspect columns and types for a table.
  - run-query: execute a SELECT-style query with optional named params.

All connections are opened in read-only mode (`mode=ro`). Provide `db_path`
when you need a database other than the default.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from mcp.server.fastmcp import FastMCP


DEFAULT_DB = Path(
    os.environ.get("MCP_SQLITE_DB", Path.home() / ".local/share/atuin/history.db")
)

mcp = FastMCP(
    name="Local SQLite",
    instructions=(
        "Run read-only SQLite queries. Defaults to the Atuin history database; "
        "pass db_path to target another database file."
    ),
)


def _resolve_db(db_path: Optional[str]) -> Path:
    path = Path(db_path) if db_path else DEFAULT_DB
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"database not found: {resolved}")
    return resolved


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    target = _resolve_db(db_path)
    return sqlite3.connect(f"file:{target}?mode=ro", uri=True, check_same_thread=False)


@mcp.tool(name="list-tables", description="List tables in the SQLite database")
def list_tables(db_path: Optional[str] = None) -> List[Mapping[str, Any]]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
            "ORDER BY type, name"
        )
        return [dict(row) for row in cur.fetchall()]


@mcp.tool(
    name="describe-table",
    description="Describe columns for a given table (name, type, notnull, default).",
)
def describe_table(table: str, db_path: Optional[str] = None) -> List[Mapping[str, Any]]:
    if not table:
        raise ValueError("table must be provided")
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        # pragma_table_info is a table-valued function, so it accepts parameters safely.
        cur = conn.execute("SELECT * FROM pragma_table_info(?)", (table,))
        rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            raise ValueError(f"table not found: {table}")
        return rows


@mcp.tool(
    name="run-query",
    description="Execute a SQL query with optional parameters (named style).",
)
def run_query(
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = 200,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    if not sql:
        raise ValueError("sql must be provided")
    params = params or {}
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params)
        result: Dict[str, Any] = {
            "rowcount": cur.rowcount,
        }
        if cur.description:
            rows = cur.fetchmany(limit) if limit else cur.fetchall()
            result["columns"] = [col[0] for col in cur.description]
            result["rows"] = [dict(row) for row in rows]
        return result


if __name__ == "__main__":
    mcp.run()
