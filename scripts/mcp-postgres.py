#!/usr/bin/env python3
"""Expose local PostgreSQL access over the Model Context Protocol.

The server intentionally keeps the surface area small: list tables, inspect a
table definition, and run parameterised queries. Connections default to the
`sinex` database over the systemd socket at `/run/postgresql`, but can be
overridden with the `MCP_POSTGRES_DSN` environment variable.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Mapping, Optional

import psycopg
from psycopg.rows import dict_row

from mcp.server.fastmcp import FastMCP


DEFAULT_DSN = "postgresql:///sinex?host=/run/postgresql&user=sinity"
MCP_POSTGRES_DSN = os.environ.get("MCP_POSTGRES_DSN", DEFAULT_DSN)

mcp = FastMCP(
    "Local PostgreSQL",
    description="Inspect and query the local PostgreSQL instance",
    version="0.1.0",
)


def _connect() -> psycopg.Connection:
    return psycopg.connect(MCP_POSTGRES_DSN, autocommit=True, row_factory=dict_row)


@mcp.tool(name="list-tables", description="List tables visible in the database")
def list_tables(schema: Optional[str] = None) -> List[Mapping[str, Any]]:
    query = """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
          {schema_filter}
        ORDER BY table_schema, table_name
    """
    schema_filter = "AND table_schema = %(schema)s" if schema else ""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query.format(schema_filter=schema_filter), {"schema": schema})
        return list(cur.fetchall())


@mcp.tool(
    name="describe-table",
    description="Describe columns for a given table, including type and nullability.",
)
def describe_table(table: str, schema: str = "public") -> List[Mapping[str, Any]]:
    query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = %(schema)s
          AND table_name = %(table)s
        ORDER BY ordinal_position
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query, {"schema": schema, "table": table})
        return list(cur.fetchall())


@mcp.tool(
    name="run-query",
    description="Execute a SQL query with optional parameters (uses psycopg named style).",
)
def run_query(
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = 200,
) -> Dict[str, Any]:
    params = params or {}
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        result: Dict[str, Any] = {
            "rowcount": cur.rowcount,
            "statusmessage": cur.statusmessage,
        }
        if cur.description:
            rows: Iterable[Mapping[str, Any]] = cur.fetchmany(limit) if limit else cur.fetchall()
            result["rows"] = list(rows)
            result["columns"] = [desc.name for desc in cur.description]
        return result


if __name__ == "__main__":
    mcp.run()
