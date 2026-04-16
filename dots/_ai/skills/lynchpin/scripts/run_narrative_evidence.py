#!/usr/bin/env python3
"""Execute Lynchpin narrative evidence queries and persist raw outputs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

QUERY_LIBRARY = {
    "daily_shape": """
SELECT date,
       round(active_seconds / 3600.0, 1) AS active_h,
       round(recovery_seconds / 3600.0, 1) AS recovery_h,
       dominant_mode,
       dominant_project,
       commit_count
FROM trajectory_day
WHERE date BETWEEN DATE '{start}' AND DATE '{end}'
ORDER BY date;
""",
    "delivery_telemetry": """
SELECT date,
       total_commits,
       active_hours,
       commit_density_per_active_hour
FROM processed_delivery_telemetry
WHERE date BETWEEN DATE '{start}' AND DATE '{end}'
ORDER BY date;
""",
    "git_daily": """
SELECT date,
       project,
       commit_count,
       ai_ratio,
       dominant_prefix,
       commit_burst_count
FROM processed_git_daily
WHERE date BETWEEN DATE '{start}' AND DATE '{end}'
ORDER BY date, commit_count DESC
LIMIT 50;
""",
    "project_attention": """
SELECT date, entropy, gini, top_project, top_project_share, project_count, rotation_speed
FROM processed_project_attention
WHERE date BETWEEN DATE '{start}' AND DATE '{end}'
ORDER BY entropy DESC
LIMIT 50;
""",
    "chat_effort": """
SELECT date, provider, total_messages, total_wall_minutes, engaged_minutes,
       round(total_wall_minutes - engaged_minutes, 2) AS wall_minus_engaged
FROM processed_chat_activity
WHERE date BETWEEN DATE '{start}' AND DATE '{end}'
  AND provider IN ({providers})
ORDER BY date, provider;
""",
    "focus_spans": """
SELECT date,
       start,
       end_time,
       round(duration_seconds / 60.0, 1) AS duration_minutes,
       app,
       title,
       keylog_state
FROM processed_focus_spans
WHERE date BETWEEN DATE '{start}' AND DATE '{end}'
  AND duration_seconds >= 30 * 60
ORDER BY duration_seconds DESC
LIMIT 50;
""",
}


def _run_polylogue_command(cmd: list[str]) -> dict | list[dict]:
    """Run a polylogue CLI command and parse JSON output."""
    completed = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        return {
            "error": completed.stderr.strip() or completed.stdout.strip(),
            "command": cmd,
        }
    if not completed.stdout.strip():
        return []
    try:
        payload = json.loads(completed.stdout)
        if isinstance(payload, list):
            return payload
        return [payload]
    except json.JSONDecodeError as exc:
        return {
            "error": f"polylogue output was not JSON: {exc}",
            "raw": completed.stdout[:2000],
            "command": cmd,
        }


def _duckdb_records(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    """Return duckdb query result rows as plain JSON objects."""
    rel = con.execute(sql)
    columns = [c[0] for c in rel.description]
    records = []
    for row in rel.fetchall():
        row_map = {}
        for key, value in zip(columns, row, strict=True):
            if hasattr(value, "to_eng_string"):
                value = value.to_eng_string()
            elif hasattr(value, "isoformat"):
                value = value.isoformat()
            row_map[key] = value
        records.append(row_map)
    return records


def run_evidence(args: argparse.Namespace) -> dict:
    start = args.start
    end = args.end
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    providers_sql = ", ".join(f"'{provider}'" for provider in args.providers)
    result: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "params": {
            "repo_root": str(args.repo),
            "start": start,
            "end": end,
            "providers": args.providers,
        },
        "queries": {},
        "errors": [],
    }

    # Polylogue query family (CLI-backed for portability)
    for provider in args.providers:
        conv_cmd = [
            "polylogue",
            "--provider",
            provider,
            "--since",
            start,
            "--until",
            end,
            "--format",
            "json",
            "--list",
            "--fields",
            "id,title,provider,created_at,updated_at,messages",
            "--limit",
            str(args.limit),
        ]
        if args.has_tool_use:
            conv_cmd.append("--has-tool-use")
        if args.action_text:
            conv_cmd += ["--action-text", args.action_text]

        payload = _run_polylogue_command(conv_cmd)
        result["queries"][f"polylogue:{provider}"] = {
            "query": " ".join(conv_cmd),
            "results": payload,
        }

    # Optional deep search query, useful for targeted architecture prompts.
    if args.search:
        search_provider = args.providers[0] if args.providers else "claude-code"
        search_cmd = [
            "polylogue",
            args.search,
            "--provider",
            search_provider,
            "--format",
            "json",
            "--list",
            "--fields",
            "id,title,provider,created_at,updated_at,messages",
            "--limit",
            str(args.limit),
        ]
        payload = _run_polylogue_command(search_cmd)
        result["queries"]["polylogue_search"] = {
            "query": " ".join(search_cmd),
            "results": payload,
        }

    # DuckDB evidence queries.
    db_path = os.path.join(args.repo, "artefacts", "lynchpin", "warehouse.duckdb")
    if not os.path.exists(db_path):
        result["errors"].append(f"Missing DuckDB file: {db_path}")
        return result

    con = duckdb.connect(db_path)
    try:
        for name, template in QUERY_LIBRARY.items():
            sql = template.format(start=start, end=end, providers=providers_sql)
            result["queries"][name] = {
                "query": sql.strip(),
                "results": _duckdb_records(con, sql),
            }
    finally:
        con.close()

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect evidence artifacts for Lynchpin narratives"
    )
    parser.add_argument(
        "--repo",
        default="/realm/project/sinity-lynchpin",
        help="Repository root containing artefacts/lynchpin/warehouse.duckdb",
    )
    parser.add_argument(
        "--start",
        default=(datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat(),
        help="Inclusive start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Inclusive end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["claude-code", "codex"],
        help="Polylogue providers to include",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max Polylogue conversations per provider",
    )
    parser.add_argument(
        "--outdir",
        default="/realm/project/sinity-lynchpin/.agent/scratch/narratives",
        help="Output directory for raw evidence JSON",
    )
    parser.add_argument(
        "--has-tool-use",
        dest="has_tool_use",
        action="store_true",
        help="Filter polylogue list by has_tool_use",
    )
    parser.add_argument(
        "--action-text",
        help="Filter Polylogue action text by substring",
    )
    parser.add_argument(
        "--search",
        help="Optional search keyword for additional polylogue search artifact",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON filename (defaults to auto-named file)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence = run_evidence(args)
    output_path = args.output or (
        f"{args.outdir}/narrative-evidence-{args.start}-to-{args.end}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, default=str)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
