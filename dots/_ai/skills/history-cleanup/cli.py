#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shlex
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from structural import register_structural_subcommands

COMMIT_HEADER_RE = re.compile(r"^commit ([0-9a-f]{40})$")
DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
SURFACE_TOKEN_RE = re.compile(
    r"`[^`]+`|[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+|[A-Za-z_][A-Za-z0-9_]+\.[A-Za-z0-9_]+"
)
EFFECT_SIGNAL_RE = re.compile(
    r"\b(add|remove|split|extract|rename|migrate|deduplicate|normalize|validate|record|generate|"
    r"rebuild|index|persist|render|route|wire|isolate|retire|separate|introduce|restrict|repair|"
    r"stabilize|unify|decompose|harden|merge|replace|archive|publish)\b"
)
WHY_SIGNAL_RE = re.compile(
    r"\b(because|so that|to avoid|to keep|to allow|to support|to make|to ensure|which lets|this keeps|"
    r"this avoids|this allows|to preserve)\b"
)
VAGUE_SUBJECT_RE = re.compile(
    r"\b(wip|misc|stuff|various|updates?|cleanup|clean up|finish|finalize|complete|execute|progress|"
    r"followups?|remaining work|polish)\b"
)
FILLER_PHRASE_RE = re.compile(
    r"\b(this commit|this change|behaviorally|the practical effect is|this update|the update|"
    r"the ux shifts|after the refactor|this collapses|unifying that path also|the sync path now)\b",
    re.IGNORECASE,
)
TRAILER_LINE_RE = re.compile(
    r"^(?:Co-authored-by|Signed-off-by|Reviewed-by|Acked-by|Tested-by|Reported-by|Suggested-by|"
    r"Pair-programmed-with|Fixes|Refs|Relates-to):\s+.+$",
    re.IGNORECASE,
)
WINDOW_PROFILES: dict[str, dict[str, Any]] = {
    "spark-128k": {
        "description": "Current narrow-window packet geometry for 128k-class workers.",
        "full_diff_budget_tokens": 56000,
        "jumbo_threshold_tokens": 96000,
        "jumbo_chunk_budget_tokens": 56000,
        "edge_context_commits": 2,
        "max_commits_per_normal_packet": None,
    },
    "wide-1m-750k": {
        "description": "Wide-window geometry that spends budget on larger feature arcs plus richer edge context.",
        "full_diff_budget_tokens": 350000,
        "jumbo_threshold_tokens": 500000,
        "jumbo_chunk_budget_tokens": 250000,
        "edge_context_commits": 12,
        "max_commits_per_normal_packet": 24,
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    temp_path.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_row_list(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("rows", "proposals", "items", "commits"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError(f"unsupported row container in {path}")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "unknown"


def resolve_window_profile(name: str | None) -> dict[str, Any]:
    profile_name = (name or "spark-128k").strip()
    profile = WINDOW_PROFILES.get(profile_name)
    if profile is None:
        choices = ", ".join(sorted(WINDOW_PROFILES))
        raise SystemExit(
            f"unsupported window profile {profile_name!r}; expected one of: {choices}"
        )
    return {"name": profile_name, **profile}


def parse_boolish(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "strict", "full", "complete"}:
            return True
        if lowered in {"false", "no", "n", "0", "none", "missing", "partial"}:
            return False
    return None


def normalize_surrounding_context(value: Any) -> tuple[bool, str]:
    boolish = parse_boolish(value)
    if boolish is True:
        return True, "adjacent_context_reviewed"
    if boolish is False:
        return False, "not_recorded"
    if value is None:
        return False, "not_recorded"
    if isinstance(value, list):
        labels = [slugify(str(item)) for item in value if str(item).strip()]
        if not labels:
            return False, "not_recorded"
        return True, "+".join(labels)
    if isinstance(value, str):
        normalized = slugify(value)
        if normalized in {"none", "not_recorded", "not_used", "false"}:
            return False, "not_recorded"
        return True, normalized
    return True, slugify(str(value))


def normalize_why_basis(value: Any) -> str:
    if value is None:
        return "not_recorded"
    if isinstance(value, list):
        joined = " ".join(str(item) for item in value)
    else:
        joined = str(value)
    lowered = joined.lower()
    if not lowered.strip():
        return "not_recorded"
    if (
        "patch" in lowered
        and "context" in lowered
        and ("behavior" in lowered or "reason" in lowered)
    ):
        return "patch_plus_adjacent_context_behavior_and_reason"
    if "patch" in lowered and "context" in lowered:
        return "patch_plus_adjacent_context"
    if "patch" in lowered:
        return "patch_only"
    if "docs" in lowered or "plan" in lowered:
        return "docs_or_plans"
    if "followup" in lowered or "follow_up" in lowered or "revert" in lowered:
        return "followup_or_revert"
    return slugify(joined)


def compose_message(message: str, trailer: str | None) -> str:
    body = message.rstrip()
    if trailer and trailer.strip() and trailer.strip() not in body:
        return f"{body}\n\n{trailer.strip()}\n"
    return body + "\n"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def git_optional(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=False,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def run_git_to_file(repo: Path, output_path: Path, *args: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            stdout=handle,
            stderr=subprocess.DEVNULL,
        )


def estimate_tokens_from_bytes(byte_count: int) -> int:
    return max(0, math.ceil(byte_count / 4))


def current_message_from_subject_body(subject: str, body_lines: list[str]) -> str:
    body = "\n".join(body_lines).strip()
    if body:
        return f"{subject.strip()}\n\n{body}"
    return subject.strip()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_now_iso_precise() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def strip_known_git_trailers(body: str) -> str:
    lines = body.rstrip().splitlines()
    if not lines:
        return ""
    index = len(lines)
    while index > 0 and not lines[index - 1].strip():
        index -= 1
    trailer_end = index
    while index > 0 and TRAILER_LINE_RE.match(lines[index - 1].strip()):
        index -= 1
    if index == trailer_end:
        return body.strip()
    while index > 0 and not lines[index - 1].strip():
        index -= 1
    return "\n".join(lines[:index]).strip()


def normalized_subject_line(value: Any) -> str:
    if value is None:
        return ""
    normalized = str(value).replace("\\r\\n", "\n").replace("\\n", "\n")
    return re.split(r"\r?\n", normalized, maxsplit=1)[0].strip()


def parse_numstat_history_log(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_body = False
    in_numstat = False

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        current["files_touched"] = len(current["paths"])
        current["lines_changed"] = current["additions"] + current["deletions"]
        current["path_roots"] = sorted(
            {top_level_area_for_path(path) for path in current["paths"]}
        )
        current["current_body"] = "\n".join(current["body_lines"]).strip()
        current["current_message"] = current_message_from_subject_body(
            current["subject"], current["body_lines"]
        )
        rows.append(current)
        current = None

    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            match = COMMIT_HEADER_RE.match(line)
            if match:
                flush()
                current = {
                    "sha": match.group(1),
                    "parents": [],
                    "author": "",
                    "date": "",
                    "subject": "",
                    "body_lines": [],
                    "additions": 0,
                    "deletions": 0,
                    "paths": [],
                }
                in_body = False
                in_numstat = False
                continue
            if current is None:
                continue
            if line == "==END-COMMIT==":
                in_body = False
                in_numstat = True
                continue
            if line.startswith("parents ") and not in_numstat:
                current["parents"] = [
                    part for part in line[len("parents ") :].split() if part
                ]
                continue
            if line.startswith("author ") and not in_numstat:
                current["author"] = line[len("author ") :].strip()
                continue
            if line.startswith("date ") and not in_numstat:
                current["date"] = line[len("date ") :].strip()
                continue
            if line.startswith("subject ") and not in_numstat:
                current["subject"] = line[len("subject ") :].strip()
                continue
            if line == "body" and not in_numstat:
                in_body = True
                continue
            if in_numstat and "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 3:
                    current["additions"] += int(parts[0]) if parts[0].isdigit() else 0
                    current["deletions"] += int(parts[1]) if parts[1].isdigit() else 0
                    current["paths"].append(parts[2])
                    continue
            if in_body:
                current["body_lines"].append(line)
    flush()

    rows.sort(key=lambda row: (row.get("date") or "", row["sha"]))
    for index, row in enumerate(rows, 1):
        row["history_sequence"] = index
    return rows


def enrich_rows_with_patch_metrics(
    rows: list[dict[str, Any]], diff_log_path: Path
) -> None:
    by_sha = {row["sha"]: row for row in rows}
    current_sha: str | None = None
    in_diff = False
    with diff_log_path.open(encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            match = COMMIT_HEADER_RE.match(line)
            if match:
                current_sha = match.group(1)
                row = by_sha.get(current_sha)
                if row is not None:
                    row["patch_line_count"] = 0
                    row["patch_byte_count"] = 0
                    row["diff_file_sections"] = 0
                    row["hunk_count"] = 0
                in_diff = False
                continue
            if current_sha is None:
                continue
            row = by_sha.get(current_sha)
            if row is None:
                continue
            if line.startswith("diff --git "):
                in_diff = True
                row["diff_file_sections"] += 1
            if in_diff:
                row["patch_line_count"] += 1
                row["patch_byte_count"] += len(raw.encode("utf-8", errors="replace"))
                if line.startswith("@@"):
                    row["hunk_count"] += 1

    for row in rows:
        row.setdefault("patch_line_count", 0)
        row.setdefault("patch_byte_count", 0)
        row.setdefault("diff_file_sections", 0)
        row.setdefault("hunk_count", 0)
        row["merge_commit"] = len(row.get("parents") or []) > 1
        row["body_word_count"] = body_word_count(row.get("current_body"))
        row["approx_patch_tokens"] = estimate_tokens_from_bytes(row["patch_byte_count"])
        row["approx_transport_tokens"] = estimate_tokens_from_bytes(
            row["patch_byte_count"]
            + len((row.get("subject") or "").encode("utf-8"))
            + len((row.get("current_body") or "").encode("utf-8"))
        )


def quantile_map(
    values: list[int], *, points: tuple[float, ...] = (0.5, 0.75, 0.9, 0.95, 0.99)
) -> dict[str, int]:
    if not values:
        return {}
    ordered = sorted(values)
    result: dict[str, int] = {}
    for point in points:
        index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * point) - 1))
        result[str(point)] = ordered[index]
    return result


def packet_simulation_summary(
    rows: list[dict[str, Any]], budget_tokens: int, *, per_commit_overhead_tokens: int
) -> dict[str, Any]:
    non_merge = [row for row in rows if not row.get("merge_commit")]
    packets = 0
    current_count = 0
    current_used = 0
    max_used = 0
    counts: list[int] = []
    oversize_single_commit_count = 0
    for row in sorted(
        non_merge, key=lambda item: (item.get("date") or "", item["sha"])
    ):
        cost = max(
            120, (row.get("approx_patch_tokens") or 0) + per_commit_overhead_tokens
        )
        if cost > budget_tokens:
            oversize_single_commit_count += 1
            if current_count:
                packets += 1
                counts.append(current_count)
                max_used = max(max_used, current_used)
                current_count = 0
                current_used = 0
            packets += 1
            counts.append(1)
            max_used = max(max_used, cost)
            continue
        if current_count and current_used + cost > budget_tokens:
            packets += 1
            counts.append(current_count)
            max_used = max(max_used, current_used)
            current_count = 0
            current_used = 0
        current_count += 1
        current_used += cost
    if current_count:
        packets += 1
        counts.append(current_count)
        max_used = max(max_used, current_used)
    return {
        "packet_count": packets,
        "avg_commits_per_packet": round(sum(counts) / max(1, len(counts)), 2)
        if counts
        else 0.0,
        "min_commits_per_packet": min(counts) if counts else 0,
        "max_commits_per_packet": max(counts) if counts else 0,
        "max_used_tokens": max_used,
        "oversize_single_commit_count": oversize_single_commit_count,
    }


def summarize_history_surface(
    rows: list[dict[str, Any]],
    *,
    repo: Path,
    branch: str,
    after: str | None,
    before: str | None,
    per_commit_overhead_tokens: int,
) -> dict[str, Any]:
    non_merge = [row for row in rows if not row.get("merge_commit")]
    merges = [row for row in rows if row.get("merge_commit")]

    month_buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "commit_count": 0,
            "merge_commit_count": 0,
            "lines_changed": 0,
            "patch_lines": 0,
            "approx_patch_tokens": 0,
        }
    )
    primary_path_roots: Counter[str] = Counter()
    for row in rows:
        month = (row.get("date") or "")[:7] or "unknown"
        bucket = month_buckets[month]
        bucket["commit_count"] += 1
        bucket["merge_commit_count"] += 1 if row.get("merge_commit") else 0
        bucket["lines_changed"] += row.get("lines_changed") or 0
        bucket["patch_lines"] += row.get("patch_line_count") or 0
        bucket["approx_patch_tokens"] += row.get("approx_patch_tokens") or 0
        roots = row.get("path_roots") or []
        primary_path_roots[roots[0] if roots else "unknown"] += 1

    summary = {
        "repo": str(repo),
        "branch": branch,
        "after": after,
        "before": before,
        "commit_count": len(rows),
        "non_merge_commit_count": len(non_merge),
        "merge_commit_count": len(merges),
        "totals": {
            "additions": sum(row.get("additions") or 0 for row in rows),
            "deletions": sum(row.get("deletions") or 0 for row in rows),
            "lines_changed": sum(row.get("lines_changed") or 0 for row in rows),
            "patch_lines": sum(row.get("patch_line_count") or 0 for row in rows),
            "patch_bytes": sum(row.get("patch_byte_count") or 0 for row in rows),
            "approx_patch_tokens": sum(
                row.get("approx_patch_tokens") or 0 for row in rows
            ),
        },
        "distributions": {
            "files_touched": quantile_map(
                [row.get("files_touched") or 0 for row in rows]
            ),
            "lines_changed": quantile_map(
                [row.get("lines_changed") or 0 for row in rows]
            ),
            "patch_line_count": quantile_map(
                [row.get("patch_line_count") or 0 for row in rows]
            ),
            "approx_patch_tokens": quantile_map(
                [row.get("approx_patch_tokens") or 0 for row in rows]
            ),
            "body_word_count": quantile_map(
                [row.get("body_word_count") or 0 for row in rows]
            ),
        },
        "packet_simulation": {
            str(budget): packet_simulation_summary(
                rows, budget, per_commit_overhead_tokens=per_commit_overhead_tokens
            )
            for budget in (
                24000,
                32000,
                40000,
                48000,
                56000,
                64000,
                80000,
                96000,
                112000,
            )
        },
        "primary_path_root_top10": [
            {"root": root, "commit_count": count}
            for root, count in primary_path_roots.most_common(10)
        ],
        "months": [
            dict(month=month, **month_buckets[month])
            for month in sorted(month_buckets.keys())
        ],
        "top_patch_commits": [
            {
                "sha": row["sha"],
                "date": row.get("date"),
                "subject": row.get("subject"),
                "patch_line_count": row.get("patch_line_count"),
                "files_touched": row.get("files_touched"),
                "approx_patch_tokens": row.get("approx_patch_tokens"),
                "merge_commit": row.get("merge_commit"),
            }
            for row in sorted(
                rows,
                key=lambda item: (
                    -(item.get("patch_line_count") or 0),
                    item.get("date") or "",
                    item["sha"],
                ),
            )[:25]
        ],
        "top_token_commits": [
            {
                "sha": row["sha"],
                "date": row.get("date"),
                "subject": row.get("subject"),
                "approx_patch_tokens": row.get("approx_patch_tokens"),
                "patch_line_count": row.get("patch_line_count"),
                "files_touched": row.get("files_touched"),
                "merge_commit": row.get("merge_commit"),
            }
            for row in sorted(
                rows,
                key=lambda item: (
                    -(item.get("approx_patch_tokens") or 0),
                    item.get("date") or "",
                    item["sha"],
                ),
            )[:25]
        ],
    }
    return summary


NORMALIZED_CORE_KEYS = {
    "range_id",
    "history_index_from_head",
    "selection_index",
    "sha",
    "author_date_iso",
    "author_name",
    "author_email",
    "committer_name",
    "committer_email",
    "current_subject",
    "current_message",
    "proposed_message",
    "proposed_trailer",
    "attribution_bucket",
    "attribution_confidence",
    "full_patch_confirmed",
    "strict_process_attested",
    "surrounding_context_used",
    "normalized_surrounding_context_label",
    "why_basis_recorded",
    "notes",
    "review_status",
    "remaining_review_required",
}


RAW_META_DROP_KEYS = {
    "effective_full_patch_confirmed",
    "effective_strict_process_attested",
    "normalized_why_basis",
    "normalized_surrounding_context_label",
    "main_agent_notes",
    "after_sha",
    "after_message",
    "global_index",
    "wave2_index",
    "wave3_index",
}


EXTRA_WORKER_METADATA_KEYS = [
    "atomicity_assessment",
    "atomicity_confidence",
    "split_likely",
    "split_reason",
    "suggested_split_units",
    "merge_with_prev_likely",
    "merge_with_prev_sha",
    "merge_with_prev_reason",
    "merge_with_next_likely",
    "merge_with_next_sha",
    "merge_with_next_reason",
    "merge_cluster_hint",
    "reorder_likely",
    "reorder_reason",
    "reorder_with_prev_likely",
    "reorder_with_next_likely",
    "reorder_partner_sha",
    "sqlx_noise_assessment",
    "semantic_change_summary",
    "adjacent_context_window",
    "context_window_shas",
    "edge_context_note",
]


INPUT_SURFACE_KEYS = [
    "scope",
    "files_changed_count",
    "insertions",
    "deletions",
    "churn",
    "semantic_files_changed_count",
    "semantic_insertions",
    "semantic_deletions",
    "semantic_churn",
    "sqlx_files_changed_count",
    "sqlx_insertions",
    "sqlx_deletions",
    "sqlx_churn",
    "top_level_areas",
    "top_level_area_count",
    "semantic_top_level_areas",
    "semantic_top_level_area_count",
    "binary_or_non_numstat_paths",
    "file_stats",
]


def iter_git_commits(repo: Path, start_index: int, count: int) -> list[dict[str, Any]]:
    if start_index < 1:
        raise ValueError("start-index must be >= 1")
    if count < 1:
        raise ValueError("count must be >= 1")
    skip = start_index - 1
    fmt = "%H%x00%aI%x00%an%x00%ae%x00%cN%x00%cE%x00%s%x00%B%x00%x1e"
    raw = git(repo, "log", f"--skip={skip}", f"-n{count}", f"--format={fmt}")
    rows: list[dict[str, Any]] = []
    for selection_index, chunk in enumerate(raw.split("\x1e"), 1):
        if not chunk.strip():
            continue
        chunk = chunk.lstrip("\n")
        parts = chunk.split("\x00")
        if len(parts) < 8:
            raise ValueError(
                f"unexpected git log record at selection index {selection_index}"
            )
        (
            sha,
            author_date_iso,
            author_name,
            author_email,
            committer_name,
            committer_email,
            current_subject,
            current_message,
        ) = parts[:8]
        rows.append(
            {
                "history_index_from_head": start_index + selection_index - 1,
                "selection_index": selection_index,
                "sha": sha.strip(),
                "author_date_iso": author_date_iso.strip(),
                "author_name": author_name.strip(),
                "author_email": author_email.strip(),
                "committer_name": committer_name.strip(),
                "committer_email": committer_email.strip(),
                "current_subject": current_subject.strip(),
                "current_message": current_message.rstrip("\n"),
            }
        )
    return rows


def preserve_extra_worker_metadata(row: dict[str, Any]) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    for key in EXTRA_WORKER_METADATA_KEYS:
        value = row.get(key)
        if value is not None:
            extras[key] = value
    passthrough: dict[str, Any] = {}
    for key, value in row.items():
        if key in NORMALIZED_CORE_KEYS or key in RAW_META_DROP_KEYS or key in extras:
            continue
        if value is None:
            continue
        passthrough[key] = value
    if extras:
        extras["worker_passthrough"] = passthrough
        return extras
    if passthrough:
        return {"worker_passthrough": passthrough}
    return {}


def preserve_base_surface_metadata(base: dict[str, Any]) -> dict[str, Any]:
    preserved: dict[str, Any] = {}
    for key in INPUT_SURFACE_KEYS:
        value = base.get(key)
        if value is not None:
            preserved[key] = value
    return preserved


def top_level_area_for_path(path: str) -> str:
    if " => " in path:
        path = path.split(" => ", 1)[1]
    path = path.strip()
    if not path:
        return "(root)"
    parts = Path(path).parts
    return parts[0] if parts else "(root)"


def path_prefix(path: str, depth: int = 2) -> str:
    if " => " in path:
        path = path.split(" => ", 1)[1]
    parts = list(Path(path.strip()).parts)
    if not parts:
        return "(root)"
    return "/".join(parts[:depth])


def parse_subject_scope(subject: str) -> str | None:
    match = re.match(r"^[a-zA-Z0-9_-]+(?:\(([^)]+)\))?:", subject)
    if not match:
        return None
    scope = match.group(1)
    if not scope:
        return None
    normalized = scope.replace("`", "").replace("/", ",").replace("+", ",")
    tokens = [
        slugify(token) for token in re.split(r"[, ]+", normalized) if token.strip()
    ]
    if not tokens:
        return None
    return ",".join(tokens)


def collect_commit_surface(repo: Path, sha: str) -> dict[str, Any]:
    raw = git(repo, "show", "--numstat", "--format=%H%x00%s", "--no-ext-diff", sha)
    lines = raw.splitlines()
    if not lines:
        raise ValueError(f"git show returned no lines for {sha}")
    header = lines[0]
    if "\x00" not in header:
        raise ValueError(f"unexpected git show header for {sha}")
    actual_sha, subject = header.split("\x00", 1)
    if actual_sha != sha:
        sha = actual_sha
    insertions = 0
    deletions = 0
    files_changed_count = 0
    semantic_files_changed_count = 0
    binary_paths: list[str] = []
    paths: list[str] = []
    top_level_areas: list[str] = []
    areas_seen: set[str] = set()
    semantic_top_level_areas: list[str] = []
    semantic_areas_seen: set[str] = set()
    sqlx_files_changed_count = 0
    sqlx_insertions = 0
    sqlx_deletions = 0
    semantic_insertions = 0
    semantic_deletions = 0
    file_stats: list[dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        ins_raw, del_raw, path = parts
        files_changed_count += 1
        paths.append(path)
        area = top_level_area_for_path(path)
        prefix = path_prefix(path)
        if area not in areas_seen:
            areas_seen.add(area)
            top_level_areas.append(area)
        is_sqlx = area == ".sqlx"
        if is_sqlx:
            sqlx_files_changed_count += 1
        else:
            semantic_files_changed_count += 1
            if area not in semantic_areas_seen:
                semantic_areas_seen.add(area)
                semantic_top_level_areas.append(area)
        if ins_raw == "-" or del_raw == "-":
            binary_paths.append(path)
            file_stats.append(
                {
                    "path": path,
                    "area": area,
                    "prefix": prefix,
                    "is_sqlx": is_sqlx,
                    "is_binary_or_non_numstat": True,
                    "insertions": None,
                    "deletions": None,
                    "churn": None,
                }
            )
            continue
        try:
            ins = int(ins_raw)
            dele = int(del_raw)
            insertions += ins
            deletions += dele
            file_stats.append(
                {
                    "path": path,
                    "area": area,
                    "prefix": prefix,
                    "is_sqlx": is_sqlx,
                    "is_binary_or_non_numstat": False,
                    "insertions": ins,
                    "deletions": dele,
                    "churn": ins + dele,
                }
            )
            if is_sqlx:
                sqlx_insertions += ins
                sqlx_deletions += dele
            else:
                semantic_insertions += ins
                semantic_deletions += dele
        except ValueError:
            binary_paths.append(path)
    return {
        "sha": sha,
        "subject": subject,
        "scope": parse_subject_scope(subject),
        "files_changed_count": files_changed_count,
        "insertions": insertions,
        "deletions": deletions,
        "churn": insertions + deletions,
        "semantic_files_changed_count": semantic_files_changed_count,
        "semantic_insertions": semantic_insertions,
        "semantic_deletions": semantic_deletions,
        "semantic_churn": semantic_insertions + semantic_deletions,
        "sqlx_files_changed_count": sqlx_files_changed_count,
        "sqlx_insertions": sqlx_insertions,
        "sqlx_deletions": sqlx_deletions,
        "sqlx_churn": sqlx_insertions + sqlx_deletions,
        "paths": paths,
        "top_level_areas": top_level_areas,
        "top_level_area_count": len(top_level_areas),
        "semantic_top_level_areas": semantic_top_level_areas,
        "semantic_top_level_area_count": len(semantic_top_level_areas),
        "binary_or_non_numstat_paths": binary_paths,
        "file_stats": file_stats,
    }


def commit_rows_with_surface(
    repo: Path, start_index: int, count: int
) -> list[dict[str, Any]]:
    rows = iter_git_commits(repo, start_index=start_index, count=count)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        surface = collect_commit_surface(repo, row["sha"])
        enriched.append({**row, **surface})
    return enriched


def split_candidate_reasons(
    row: dict[str, Any],
    files_threshold: int,
    areas_threshold: int,
    churn_threshold: int,
) -> list[str]:
    reasons: list[str] = []
    if (row.get("semantic_files_changed_count") or 0) >= files_threshold:
        reasons.append(f"semantic_files>={files_threshold}")
    if (row.get("semantic_top_level_area_count") or 0) >= areas_threshold:
        reasons.append(f"semantic_areas>={areas_threshold}")
    if (row.get("semantic_churn") or 0) >= churn_threshold:
        reasons.append(f"semantic_churn>={churn_threshold}")
    sqlx_files = row.get("sqlx_files_changed_count") or 0
    semantic_files = row.get("semantic_files_changed_count") or 0
    if sqlx_files and semantic_files:
        reasons.append("mixed_sqlx_and_semantic_changes")
    return reasons


def shared_area_count(left: dict[str, Any], right: dict[str, Any]) -> int:
    return len(
        set(left.get("semantic_top_level_areas") or [])
        & set(right.get("semantic_top_level_areas") or [])
    )


def scopes_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_scope = set((left.get("scope") or "").split(",")) - {""}
    right_scope = set((right.get("scope") or "").split(",")) - {""}
    return bool(left_scope & right_scope)


def merge_strength(left: dict[str, Any], right: dict[str, Any]) -> int:
    score = 0
    if scopes_overlap(left, right):
        score += 2
    if shared_area_count(left, right) >= 1:
        score += 1
    if any(
        token in (right.get("subject") or "").lower()
        for token in (
            "fix",
            "follow-up",
            "followup",
            "leftover",
            "remaining",
            "docs",
            "test",
        )
    ):
        score += 1
    return score


def reorder_reason(left: dict[str, Any], right: dict[str, Any]) -> str | None:
    left_subject = (left.get("subject") or "").lower()
    right_subject = (right.get("subject") or "").lower()
    if any(token in left_subject for token in ("remove", "drop")) and any(
        token in right_subject for token in ("restore", "reintroduce", "bring back")
    ):
        return "remove_then_restore"
    if any(
        token in right_subject
        for token in ("leftover", "remaining", "follow-up", "followup")
    ) and (scopes_overlap(left, right) or shared_area_count(left, right) >= 1):
        return "followup_leftovers_after_primary_change"
    if any(token in right_subject for token in ("docs", "test")) and (
        scopes_overlap(left, right) or shared_area_count(left, right) >= 1
    ):
        return "docs_or_tests_interleaved_with_same_scope_change"
    return None


def cmd_analyze_series(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    rows = commit_rows_with_surface(
        repo, start_index=args.start_index, count=args.count
    )
    split_candidates: list[dict[str, Any]] = []
    merge_clusters: list[dict[str, Any]] = []
    reorder_candidates: list[dict[str, Any]] = []
    for row in rows:
        reasons = split_candidate_reasons(
            row,
            args.split_files_threshold,
            args.split_areas_threshold,
            args.split_churn_threshold,
        )
        if reasons:
            split_candidates.append(
                {
                    "selection_index": row["selection_index"],
                    "history_index_from_head": row["history_index_from_head"],
                    "sha": row["sha"],
                    "subject": row["subject"],
                    "scope": row["scope"],
                    "files_changed_count": row["files_changed_count"],
                    "semantic_files_changed_count": row["semantic_files_changed_count"],
                    "top_level_area_count": row["top_level_area_count"],
                    "semantic_top_level_area_count": row[
                        "semantic_top_level_area_count"
                    ],
                    "churn": row["churn"],
                    "semantic_churn": row["semantic_churn"],
                    "top_level_areas": row["top_level_areas"],
                    "semantic_top_level_areas": row["semantic_top_level_areas"],
                    "sqlx_files_changed_count": row["sqlx_files_changed_count"],
                    "sqlx_churn": row["sqlx_churn"],
                    "reasons": reasons,
                }
            )
    active_cluster: list[dict[str, Any]] = []
    for row in rows:
        if not active_cluster:
            active_cluster = [row]
            continue
        previous = active_cluster[-1]
        if merge_strength(previous, row) >= args.merge_min_score:
            active_cluster.append(row)
            continue
        if len(active_cluster) >= 2:
            merge_clusters.append(
                {
                    "start_selection_index": active_cluster[0]["selection_index"],
                    "end_selection_index": active_cluster[-1]["selection_index"],
                    "count": len(active_cluster),
                    "areas_union": sorted(
                        {
                            area
                            for item in active_cluster
                            for area in item.get("semantic_top_level_areas") or []
                        }
                    ),
                    "subjects": [item["subject"] for item in active_cluster],
                    "shas": [item["sha"] for item in active_cluster],
                }
            )
        active_cluster = [row]
    if len(active_cluster) >= 2:
        merge_clusters.append(
            {
                "start_selection_index": active_cluster[0]["selection_index"],
                "end_selection_index": active_cluster[-1]["selection_index"],
                "count": len(active_cluster),
                "areas_union": sorted(
                    {
                        area
                        for item in active_cluster
                        for area in item.get("semantic_top_level_areas") or []
                    }
                ),
                "subjects": [item["subject"] for item in active_cluster],
                "shas": [item["sha"] for item in active_cluster],
            }
        )
    for left, right in zip(rows, rows[1:], strict=True):
        reason = reorder_reason(left, right)
        if reason:
            reorder_candidates.append(
                {
                    "left_selection_index": left["selection_index"],
                    "right_selection_index": right["selection_index"],
                    "left_sha": left["sha"],
                    "right_sha": right["sha"],
                    "left_subject": left["subject"],
                    "right_subject": right["subject"],
                    "reason": reason,
                }
            )
    payload = {
        "repo": str(repo),
        "start_index": args.start_index,
        "count": args.count,
        "split_thresholds": {
            "files_changed_count": args.split_files_threshold,
            "top_level_area_count": args.split_areas_threshold,
            "churn": args.split_churn_threshold,
        },
        "merge_min_score": args.merge_min_score,
        "rows": rows,
        "split_candidates": split_candidates,
        "merge_clusters": merge_clusters,
        "reorder_candidates": reorder_candidates,
    }
    if args.output_json:
        write_json(Path(args.output_json).resolve(), payload)
    summary = {
        "rows": len(rows),
        "split_candidates": len(split_candidates),
        "merge_clusters": len(merge_clusters),
        "reorder_candidates": len(reorder_candidates),
    }
    if args.summary_json:
        write_json(Path(args.summary_json).resolve(), summary)
    print(json.dumps(summary, indent=2))
    return 0


def subject_for_optional_sha(repo: Path, sha: str | None) -> str | None:
    if not sha:
        return None
    output = git_optional(repo, "show", "-s", "--format=%s", sha).strip()
    return output or None


def cmd_scaffold_split(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    surface = collect_commit_surface(repo, args.sha)
    parent_sha = git_optional(repo, "rev-parse", f"{args.sha}^").strip() or None
    child_line = git_optional(
        repo, "rev-list", "--children", "-n", "1", args.sha
    ).strip()
    child_sha = None
    if child_line:
        parts = child_line.split()
        if len(parts) > 1:
            child_sha = parts[1]
    by_area: dict[str, dict[str, Any]] = {}
    by_prefix: dict[str, dict[str, Any]] = {}
    raw = git(repo, "show", "--numstat", "--format=%H%x00%s", "--no-ext-diff", args.sha)
    for line in raw.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        ins_raw, del_raw, path = parts
        insertions = 0 if ins_raw == "-" else int(ins_raw)
        deletions = 0 if del_raw == "-" else int(del_raw)
        area = top_level_area_for_path(path)
        prefix = path_prefix(path, depth=args.prefix_depth)
        by_area.setdefault(
            area, {"group": area, "files": [], "insertions": 0, "deletions": 0}
        )
        by_area[area]["files"].append(path)
        by_area[area]["insertions"] += insertions
        by_area[area]["deletions"] += deletions
        by_prefix.setdefault(
            prefix, {"group": prefix, "files": [], "insertions": 0, "deletions": 0}
        )
        by_prefix[prefix]["files"].append(path)
        by_prefix[prefix]["insertions"] += insertions
        by_prefix[prefix]["deletions"] += deletions
    payload = {
        "sha": surface["sha"],
        "subject": surface["subject"],
        "scope": surface["scope"],
        "files_changed_count": surface["files_changed_count"],
        "insertions": surface["insertions"],
        "deletions": surface["deletions"],
        "churn": surface["churn"],
        "top_level_areas": surface["top_level_areas"],
        "parent": {
            "sha": parent_sha,
            "subject": subject_for_optional_sha(repo, parent_sha),
        },
        "child": {
            "sha": child_sha,
            "subject": subject_for_optional_sha(repo, child_sha),
        },
        "groups_by_top_level_area": sorted(
            by_area.values(), key=lambda item: (-len(item["files"]), item["group"])
        ),
        "groups_by_prefix": sorted(
            by_prefix.values(), key=lambda item: (-len(item["files"]), item["group"])
        ),
    }
    if args.output_json:
        write_json(Path(args.output_json).resolve(), payload)
    print(
        json.dumps(
            {
                "sha": payload["sha"],
                "subject": payload["subject"],
                "files_changed_count": payload["files_changed_count"],
                "groups_by_top_level_area": len(payload["groups_by_top_level_area"]),
                "groups_by_prefix": len(payload["groups_by_prefix"]),
            },
            indent=2,
        )
    )
    return 0


VALID_REBASE_ACTIONS = {
    "pick",
    "reword",
    "edit",
    "squash",
    "fixup",
    "drop",
    "break",
    "exec",
    "label",
    "reset",
    "merge",
}


def cmd_emit_rebase_todo(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve() if args.repo else None
    plan = load_json(Path(args.plan_json).resolve())
    operations = plan.get("operations")
    if not isinstance(operations, list):
        raise ValueError("plan_json must contain an 'operations' list")
    lines: list[str] = []
    for op in operations:
        if not isinstance(op, dict):
            raise ValueError("each operation must be an object")
        action = op.get("action")
        if action not in VALID_REBASE_ACTIONS:
            raise ValueError(f"unsupported action: {action}")
        comment = op.get("comment")
        if comment:
            lines.append(f"# {comment}")
        if action == "exec":
            command = op.get("command")
            if not command:
                raise ValueError("exec operation requires 'command'")
            lines.append(f"exec {command}")
            continue
        if action in {"break"}:
            lines.append("break")
            continue
        if action in {"label", "reset"}:
            target = op.get("target")
            if not target:
                raise ValueError(f"{action} operation requires 'target'")
            lines.append(f"{action} {target}")
            continue
        sha = op.get("sha")
        if not sha:
            raise ValueError(f"{action} operation requires 'sha'")
        subject = op.get("subject")
        if repo and not subject:
            subject = subject_for_optional_sha(repo, sha)
        suffix = f" # {subject}" if subject else ""
        lines.append(f"{action} {sha}{suffix}")
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n")
    print(
        json.dumps(
            {"operations": len(operations), "output": str(output_path)}, indent=2
        )
    )
    return 0


def range_rows_from_input(
    path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("range input must be a dict payload")
    owned = [row for row in payload.get("owned", []) if isinstance(row, dict)]
    context = [row for row in payload.get("context", []) if isinstance(row, dict)]
    return payload, owned, context


def ordered_window_starts(total: int, window_size: int, slide: int) -> list[int]:
    if total <= 0:
        return []
    if total <= window_size:
        return [0]
    starts = list(range(0, total - window_size + 1, slide))
    tail_start = total - window_size
    if starts[-1] != tail_start:
        starts.append(tail_start)
    return sorted(dict.fromkeys(starts))


def normalize_exclude_pathspec(pathspec: str) -> str:
    if pathspec.startswith(":("):
        return pathspec
    return f":(exclude){pathspec}"


def filtered_commit_patch(
    repo: Path,
    shas: list[str],
    *,
    unified: int,
    exclude_sqlx: bool,
    stat: bool,
    include_paths: list[str],
    exclude_paths: list[str],
) -> str:
    args = ["show", "--no-ext-diff", "--format=medium", f"--unified={unified}"]
    if stat:
        args.append("--stat")
    args.append("--patch")
    args.extend(shas)
    pathspecs: list[str] = []
    if include_paths:
        pathspecs.extend(include_paths)
    elif exclude_sqlx or exclude_paths:
        pathspecs.append(".")
    if exclude_sqlx:
        pathspecs.append(":(exclude).sqlx/**")
    for item in exclude_paths:
        pathspecs.append(normalize_exclude_pathspec(item))
    if pathspecs:
        args.extend(["--", *pathspecs])
    return git_output(repo, *args)


def cmd_build_review_bundles(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    range_input = Path(args.range_input).resolve()
    output_dir = Path(args.output_dir).resolve()
    payload, owned_rows, context_rows = range_rows_from_input(range_input)
    if not context_rows:
        raise ValueError("range input contains no context rows")
    starts = ordered_window_starts(len(context_rows), args.window_size, args.slide)
    bundles: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    owned_start = payload.get("owned_start", 0)
    owned_end = payload.get("owned_end", 0)
    for bundle_index, start in enumerate(starts, 1):
        end = min(start + args.window_size, len(context_rows))
        window_rows = context_rows[start:end]
        bundle_id = f"window-{bundle_index:02d}"
        bundle_dir = output_dir / bundle_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        shas = [row["sha"] for row in window_rows]
        owned_window_rows = [
            row
            for row in window_rows
            if owned_start <= row.get("selection_index", 0) <= owned_end
        ]
        summary = {
            "bundle_id": bundle_id,
            "window_size": len(window_rows),
            "requested_window_size": args.window_size,
            "slide": args.slide,
            "exclude_sqlx": args.exclude_sqlx,
            "selection_index_range": [
                window_rows[0].get("selection_index"),
                window_rows[-1].get("selection_index"),
            ],
            "history_index_range": [
                window_rows[0].get("history_index_from_head"),
                window_rows[-1].get("history_index_from_head"),
            ],
            "owned_selection_index_range": [owned_start, owned_end],
            "owned_commits_in_window": [
                row.get("selection_index") for row in owned_window_rows
            ],
            "commits": window_rows,
        }
        write_json(bundle_dir / "summary.json", summary)
        combined_patch = filtered_commit_patch(
            repo,
            shas,
            unified=args.unified,
            exclude_sqlx=args.exclude_sqlx,
            stat=args.include_stat,
            include_paths=args.include_path,
            exclude_paths=args.exclude_path,
        )
        (bundle_dir / "combined.patch").write_text(combined_patch)
        commit_files: list[str] = []
        for position, row in enumerate(window_rows, 1):
            patch_text = filtered_commit_patch(
                repo,
                [row["sha"]],
                unified=args.unified,
                exclude_sqlx=args.exclude_sqlx,
                stat=args.include_stat,
                include_paths=args.include_path,
                exclude_paths=args.exclude_path,
            )
            patch_name = f"{position:02d}-{row['sha'][:10]}.patch"
            (bundle_dir / patch_name).write_text(patch_text)
            commit_files.append(patch_name)
        bundles.append(
            {
                "bundle_id": bundle_id,
                "summary": str((bundle_dir / "summary.json").resolve()),
                "combined_patch": str((bundle_dir / "combined.patch").resolve()),
                "commit_patches": commit_files,
                "selection_index_range": summary["selection_index_range"],
                "owned_commits_in_window": summary["owned_commits_in_window"],
            }
        )
    index = {
        "repo": str(repo),
        "range_input": str(range_input),
        "output_dir": str(output_dir),
        "window_size": args.window_size,
        "slide": args.slide,
        "exclude_sqlx": args.exclude_sqlx,
        "include_paths": args.include_path,
        "exclude_paths": args.exclude_path,
        "bundle_count": len(bundles),
        "owned_rows": len(owned_rows),
        "context_rows": len(context_rows),
        "bundles": bundles,
    }
    write_json(output_dir / "bundles-index.json", index)
    print(
        json.dumps(
            {"bundle_count": len(bundles), "output_dir": str(output_dir)}, indent=2
        )
    )
    return 0


def build_ranges(
    rows: list[dict[str, Any]], owned_size: int, overlap: int
) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    total = len(rows)
    range_count = math.ceil(total / owned_size)
    for idx in range(range_count):
        owned_start = idx * owned_size + 1
        owned_end = min((idx + 1) * owned_size, total)
        context_start = max(1, owned_start - overlap)
        context_end = min(total, owned_end + overlap)
        range_id = f"range-{idx + 1:02d}"
        ranges.append(
            {
                "range_id": range_id,
                "owned_start": owned_start,
                "owned_end": owned_end,
                "context_start": context_start,
                "context_end": context_end,
                "owned_count": owned_end - owned_start + 1,
                "context_count": context_end - context_start + 1,
                "overlap": overlap,
                "owned": rows[owned_start - 1 : owned_end],
                "context": rows[context_start - 1 : context_end],
            }
        )
    return ranges


def cmd_prepare_wave(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    output_dir = Path(args.output_dir).resolve()
    if args.include_surface:
        rows = commit_rows_with_surface(
            repo, start_index=args.start_index, count=args.count
        )
    else:
        rows = iter_git_commits(repo, start_index=args.start_index, count=args.count)
    if args.index_field != "selection_index":
        for row in rows:
            row[args.index_field] = row.pop("selection_index")
    ranges = build_ranges(rows, owned_size=args.owned_size, overlap=args.overlap)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_ranges: list[dict[str, Any]] = []
    for range_payload in ranges:
        range_id = range_payload["range_id"]
        input_path = output_dir / f"{range_id}-input.json"
        output_path = output_dir / f"{range_id}-proposals.json"
        summary_path = output_dir / f"{range_id}-summary.json"
        write_json(input_path, range_payload)
        manifest_ranges.append(
            {
                "range_id": range_id,
                "owned_start": range_payload["owned_start"],
                "owned_end": range_payload["owned_end"],
                "context_start": range_payload["context_start"],
                "context_end": range_payload["context_end"],
                "input": str(input_path),
                "output": str(output_path),
                "summary": str(summary_path),
            }
        )
    manifest = {
        "wave": args.wave_name,
        "repo": str(repo),
        "start_index": args.start_index,
        "count": args.count,
        "owned_size": args.owned_size,
        "overlap": args.overlap,
        "include_surface": args.include_surface,
        "index_field": args.index_field,
        "ranges": manifest_ranges,
    }
    write_json(output_dir / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": "ok",
                "wave": args.wave_name,
                "ranges": len(manifest_ranges),
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return 0


def count_rows_if_exists(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return len(load_row_list(path))
    except Exception:
        return None


def cmd_wave_status(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    statuses: list[dict[str, Any]] = []
    for range_info in manifest["ranges"]:
        input_path = Path(range_info["input"])
        output_path = Path(range_info["output"])
        summary_path = Path(range_info["summary"])
        statuses.append(
            {
                "range_id": range_info["range_id"],
                "owned_start": range_info["owned_start"],
                "owned_end": range_info["owned_end"],
                "input_exists": input_path.exists(),
                "proposal_exists": output_path.exists(),
                "summary_exists": summary_path.exists(),
                "proposal_rows": count_rows_if_exists(output_path),
            }
        )
    result = {
        "wave": manifest.get("wave"),
        "manifest": str(manifest_path),
        "ranges_total": len(statuses),
        "ranges_with_proposals": sum(1 for row in statuses if row["proposal_exists"]),
        "ranges_with_summaries": sum(1 for row in statuses if row["summary_exists"]),
        "ranges": statuses,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"wave: {result['wave']}")
        print(f"manifest: {result['manifest']}")
        print(f"ranges: {result['ranges_total']}")
        print(f"with proposals: {result['ranges_with_proposals']}")
        print(f"with summaries: {result['ranges_with_summaries']}")
        for row in statuses:
            print(
                f"{row['range_id']}: owned={row['owned_start']}-{row['owned_end']} "
                f"input={row['input_exists']} proposals={row['proposal_exists']} "
                f"summary={row['summary_exists']} proposal_rows={row['proposal_rows']}"
            )
    return 0


def proposal_rows_by_sha(range_input_path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(range_input_path)
    owned_rows = payload.get("owned", []) if isinstance(payload, dict) else []
    return {
        row["sha"]: row
        for row in owned_rows
        if isinstance(row, dict) and row.get("sha")
    }


def normalize_proposal_row(
    row: dict[str, Any], base: dict[str, Any], range_id: str
) -> dict[str, Any]:
    sha = row.get("sha") or row.get("after_sha") or base.get("sha")
    if not sha:
        raise ValueError(f"proposal row in {range_id} missing sha/after_sha")
    full_patch_confirmed = row.get(
        "effective_full_patch_confirmed", row.get("full_patch_confirmed")
    )
    strict_process_attested = row.get(
        "effective_strict_process_attested", row.get("strict_process_attested")
    )
    full_patch_bool = parse_boolish(full_patch_confirmed)
    strict_bool = parse_boolish(strict_process_attested)
    surrounding_raw = row.get(
        "normalized_surrounding_context_label", row.get("surrounding_context_used")
    )
    surrounding_used, surrounding_label = normalize_surrounding_context(surrounding_raw)
    why_raw = row.get("normalized_why_basis", row.get("why_basis_recorded"))
    why_basis = normalize_why_basis(why_raw)
    notes = row.get("notes") or row.get("main_agent_notes")
    if strict_bool:
        review_status = "complete_strict"
        remaining_review_required = False
    elif (
        full_patch_bool
        or surrounding_used
        or why_basis != "not_recorded"
        or bool(notes)
    ):
        review_status = "complete_conservative"
        remaining_review_required = False
    else:
        review_status = "needs_review"
        remaining_review_required = True
    normalized = {
        "range_id": range_id,
        "history_index_from_head": base.get("history_index_from_head")
        or row.get("history_index_from_head"),
        "selection_index": base.get("selection_index")
        or base.get("wave2_index")
        or row.get("selection_index")
        or row.get("wave2_index")
        or row.get("global_index"),
        "sha": sha,
        "author_date_iso": base.get("author_date_iso"),
        "author_name": base.get("author_name"),
        "author_email": base.get("author_email"),
        "committer_name": base.get("committer_name"),
        "committer_email": base.get("committer_email"),
        "current_subject": base.get("current_subject"),
        "current_message": row.get("current_message") or base.get("current_message"),
        "proposed_message": row.get("proposed_message"),
        "proposed_trailer": row.get("proposed_trailer"),
        "attribution_bucket": row.get("attribution_bucket"),
        "attribution_confidence": row.get("attribution_confidence"),
        "full_patch_confirmed": full_patch_bool,
        "strict_process_attested": strict_bool,
        "surrounding_context_used": surrounding_used,
        "normalized_surrounding_context_label": surrounding_label,
        "why_basis_recorded": why_basis,
        "notes": notes,
        "review_status": review_status,
        "remaining_review_required": remaining_review_required,
    }
    normalized.update(preserve_base_surface_metadata(base))
    normalized.update(preserve_extra_worker_metadata(row))
    return normalized


def cmd_normalize_wave(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    normalized_rows: list[dict[str, Any]] = []
    missing_ranges: list[str] = []
    bad_ranges: list[dict[str, Any]] = []
    for range_info in manifest["ranges"]:
        range_id = range_info["range_id"]
        output_path = Path(range_info["output"])
        if not output_path.exists():
            missing_ranges.append(range_id)
            continue
        try:
            proposal_rows = load_row_list(output_path)
            base_map = proposal_rows_by_sha(Path(range_info["input"]))
            for proposal_row in proposal_rows:
                normalized_rows.append(
                    normalize_proposal_row(
                        proposal_row,
                        base_map.get(
                            proposal_row.get("sha") or proposal_row.get("after_sha"), {}
                        ),
                        range_id,
                    )
                )
        except Exception as exc:
            bad_ranges.append({"range_id": range_id, "error": str(exc)})
    normalized_rows.sort(
        key=lambda row: (
            row.get("selection_index") is None,
            row.get("selection_index") or 0,
            row["sha"],
        )
    )
    summary = {
        "wave": manifest.get("wave"),
        "manifest": str(manifest_path),
        "rows": len(normalized_rows),
        "ranges_total": len(manifest["ranges"]),
        "missing_ranges": missing_ranges,
        "bad_ranges": bad_ranges,
        "strict_rows": sum(
            1 for row in normalized_rows if row["strict_process_attested"] is True
        ),
        "conservative_rows": sum(
            1
            for row in normalized_rows
            if row["review_status"] == "complete_conservative"
        ),
        "needs_review_rows": sum(
            1 for row in normalized_rows if row["remaining_review_required"]
        ),
        "claude_trailers": sum(
            1
            for row in normalized_rows
            if row.get("proposed_trailer")
            == "Co-Authored-By: Claude <noreply@anthropic.com>"
        ),
        "codex_trailers": sum(
            1
            for row in normalized_rows
            if row.get("proposed_trailer") == "Co-Authored-By: Codex <codex@openai.com>"
        ),
        "rows_without_trailer": sum(
            1 for row in normalized_rows if not row.get("proposed_trailer")
        ),
    }
    if args.output_json:
        write_json(Path(args.output_json), normalized_rows)
    if args.output_csv:
        write_csv(Path(args.output_csv), normalized_rows)
    if args.summary_json:
        write_json(Path(args.summary_json), summary)
    print(json.dumps(summary, indent=2))
    return 0


def canonical_rows(path: Path) -> list[dict[str, Any]]:
    rows = load_row_list(path)
    return [row for row in rows if isinstance(row, dict)]


def normalize_commit_sha(value: str) -> str:
    return value.strip()


def body_word_count(body: str | None) -> int:
    return len((body or "").split())


def confidence_rank(value: str | None) -> int:
    return {"high": 2, "medium": 1, "low": 0}.get((value or "").lower(), -1)


def split_message_subject_body(message: str | None) -> tuple[str, str]:
    normalized = (message or "").strip()
    if not normalized:
        return "", ""
    if "\n" not in normalized:
        return normalized, ""
    subject, remainder = normalized.split("\n", 1)
    return subject.strip(), remainder.strip()


def message_from_surface_row(row: dict[str, Any]) -> tuple[str, str]:
    subject = (row.get("subject") or row.get("current_subject") or "").strip()
    body = (row.get("current_body") or "").strip()
    if not subject and row.get("current_message"):
        return split_message_subject_body(row.get("current_message"))
    if body:
        return subject, body
    if row.get("body_lines"):
        return subject, "\n".join(row["body_lines"]).strip()
    return subject, ""


def message_for_source(row: dict[str, Any], source: str) -> tuple[str, str]:
    if source == "current":
        return message_from_surface_row(row)
    if source == "rewritten":
        return split_message_subject_body(row.get("rewritten_message"))
    if source == "proposed":
        if row.get("proposed_subject") or row.get("proposed_body"):
            return (row.get("proposed_subject") or "").strip(), (
                row.get("proposed_body") or ""
            ).strip()
        if isinstance(row.get("message"), dict):
            message = row["message"]
            return (message.get("subject") or "").strip(), (
                message.get("body") or ""
            ).strip()
        return split_message_subject_body(row.get("proposed_message"))
    if source == "auto":
        for candidate in ("proposed", "rewritten", "current"):
            subject, body = message_for_source(row, candidate)
            if subject or body:
                return subject, body
        return "", ""
    raise ValueError(f"unsupported message source: {source}")


def has_effect_signal(text: str) -> bool:
    return bool(EFFECT_SIGNAL_RE.search(text.lower()))


def has_why_signal(text: str) -> bool:
    return bool(WHY_SIGNAL_RE.search(text.lower()))


def has_surface_signal(text: str) -> bool:
    return bool(SURFACE_TOKEN_RE.search(text))


def assess_commit_message_quality(subject: str, body: str) -> dict[str, Any]:
    normalized_subject = subject.strip()
    normalized_body = strip_known_git_trailers(body.strip())
    body_words = body_word_count(normalized_body)
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", normalized_body)
        if paragraph.strip()
    ]
    bullet_lines = [
        line for line in normalized_body.splitlines() if re.match(r"^\s*[-*]\s+", line)
    ]
    sentence_count = len(re.findall(r"[.!?](?:\s|$)", normalized_body)) or (
        1 if normalized_body else 0
    )
    subject_word_count = len(normalized_subject.split())
    subject_length = len(normalized_subject)
    effect_signal = has_effect_signal(f"{normalized_subject}\n{normalized_body}")
    why_signal = has_why_signal(normalized_body)
    surface_signal = has_surface_signal(f"{normalized_subject}\n{normalized_body}")
    filler_signal = bool(FILLER_PHRASE_RE.search(normalized_body))
    flags: list[str] = []
    score = 0

    if not normalized_body:
        flags.append("no_body")
    elif body_words < 20:
        flags.append("thin_body")
        score += 1
    elif body_words < 40:
        flags.append("light_body")
        score += 2
    elif body_words < 70:
        score += 3
    else:
        score += 4

    if len(paragraphs) >= 2:
        score += 2
    elif paragraphs and len(bullet_lines) >= 2:
        score += 1
    elif paragraphs:
        flags.append("single_paragraph")

    if len(bullet_lines) >= 2:
        score += 1
    elif normalized_body:
        flags.append("no_bullets")

    if effect_signal:
        score += 2
    else:
        flags.append("missing_effect_signal")

    if surface_signal:
        score += 1
    else:
        flags.append("missing_concrete_surface")

    if why_signal:
        score += 1

    if filler_signal:
        flags.append("filler_phrasing")
    else:
        score += 1

    if VAGUE_SUBJECT_RE.search(normalized_subject.lower()):
        flags.append("vague_subject")
    else:
        score += 1

    if "\\n" in normalized_subject:
        flags.append("literal_newline_escape_in_subject")
    if subject_length > 90:
        flags.append("long_subject")
    if subject_word_count > 14:
        flags.append("wordy_subject")

    if "no_body" in flags or body_words < 12:
        tier = "insufficient"
    elif (
        score >= 8
        and body_words >= 40
        and "missing_effect_signal" not in flags
        and "vague_subject" not in flags
        and "no_bullets" not in flags
        and "filler_phrasing" not in flags
    ):
        tier = "strong"
    elif score >= 5 and body_words >= 25:
        tier = "adequate"
    else:
        tier = "thin"

    return {
        "score": score,
        "tier": tier,
        "flags": flags,
        "body_word_count": body_words,
        "paragraph_count": len(paragraphs),
        "sentence_count": sentence_count,
        "subject_word_count": subject_word_count,
        "subject_length": subject_length,
        "effect_signal": effect_signal,
        "why_signal": why_signal,
        "surface_signal": surface_signal,
    }


def choose_best_batch_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    def score(candidate: dict[str, Any]) -> tuple[Any, ...]:
        qualities = [
            assess_commit_message_quality(
                item.get("proposed_subject") or "", item.get("proposed_body") or ""
            )
            for item in candidate["items"]
        ]
        counts = [quality["body_word_count"] for quality in qualities]
        quality_scores = [quality["score"] for quality in qualities]
        strong_count = sum(1 for quality in qualities if quality["tier"] == "strong")
        adequate_plus_count = sum(
            1 for quality in qualities if quality["tier"] in {"strong", "adequate"}
        )
        avg = sum(counts) / len(counts) if counts else 0.0
        return (
            sum(1 for item in candidate["items"] if item.get("full_patch_confirmed")),
            strong_count,
            adequate_plus_count,
            statistics.median(quality_scores) if quality_scores else 0,
            sum(quality_scores),
            statistics.median(counts) if counts else 0,
            avg,
            max(counts) if counts else 0,
            sum(confidence_rank(item.get("confidence")) for item in candidate["items"]),
            candidate["proposal_file"],
        )

    return max(candidates, key=score)


def build_message_from_subject_body(subject: str, body: str | None) -> str:
    normalized_subject = subject.strip()
    normalized_body = (body or "").strip()
    if normalized_body:
        return f"{normalized_subject}\n\n{normalized_body}\n"
    return normalized_subject + "\n"


def cmd_finalize_message_wave(args: argparse.Namespace) -> int:
    thin_corpus = load_json(Path(args.thin_corpus).resolve())
    proposals_dir = Path(args.proposals_dir).resolve()

    expected_commits = thin_corpus["commits"]
    expected_shas = [normalize_commit_sha(commit["sha"]) for commit in expected_commits]
    expected_sha_set = set(expected_shas)
    expected_index_by_sha = {
        normalize_commit_sha(commit["sha"]): commit["index"]
        for commit in expected_commits
    }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(proposals_dir.glob("*.json")):
        payload = load_json(path)
        batch_id = payload["batch_id"]
        items: list[dict[str, Any]] = []
        for row in payload["items"]:
            items.append(
                {
                    "sha": normalize_commit_sha(row["sha"]),
                    "original_subject": row["original_subject"],
                    "proposed_subject": row["proposed_subject"].strip(),
                    "proposed_body": (row.get("proposed_body") or "").strip(),
                    "full_patch_confirmed": bool(row.get("full_patch_confirmed")),
                    "adjacent_context_used": row.get("adjacent_context_used") or [],
                    "confidence": row.get("confidence") or "",
                    "why_basis": row.get("why_basis") or "",
                }
            )
        grouped[batch_id].append(
            {
                "proposal_file": path.name,
                "agent": payload.get("agent", ""),
                "batch_id": batch_id,
                "items": items,
            }
        )

    chosen_batches: list[dict[str, Any]] = []
    duplicate_resolution: list[dict[str, Any]] = []
    canonical_rows: list[dict[str, Any]] = []

    for batch_id in sorted(grouped):
        candidates = grouped[batch_id]
        chosen = choose_best_batch_candidate(candidates)
        chosen_batches.append(
            {
                "batch_id": batch_id,
                "proposal_file": chosen["proposal_file"],
                "agent": chosen["agent"],
            }
        )
        if len(candidates) > 1:
            duplicate_resolution.append(
                {
                    "batch_id": batch_id,
                    "chosen_file": chosen["proposal_file"],
                    "candidates": [
                        {
                            "proposal_file": candidate["proposal_file"],
                            "agent": candidate["agent"],
                            "item_count": len(candidate["items"]),
                            "body_word_median": statistics.median(
                                [
                                    body_word_count(item.get("proposed_body"))
                                    for item in candidate["items"]
                                ]
                            ),
                            "body_word_total": sum(
                                body_word_count(item.get("proposed_body"))
                                for item in candidate["items"]
                            ),
                        }
                        for candidate in candidates
                    ],
                }
            )
        for item in chosen["items"]:
            quality = assess_commit_message_quality(
                item["proposed_subject"], item["proposed_body"]
            )
            canonical_rows.append(
                {
                    "batch_id": batch_id,
                    "proposal_file": chosen["proposal_file"],
                    "agent": chosen["agent"],
                    **item,
                    "message_quality_score": quality["score"],
                    "message_quality_tier": quality["tier"],
                    "message_quality_flags": quality["flags"],
                    "rewritten_body_word_count": quality["body_word_count"],
                    "rewritten_message": build_message_from_subject_body(
                        item["proposed_subject"], item["proposed_body"]
                    ),
                }
            )

    canonical_shas = [row["sha"] for row in canonical_rows]
    duplicate_shas = sorted(
        {sha for sha in canonical_shas if canonical_shas.count(sha) > 1}
    )
    canonical_sha_set = set(canonical_shas)
    missing_shas = sorted(expected_sha_set - canonical_sha_set)
    unexpected_shas = sorted(canonical_sha_set - expected_sha_set)
    if duplicate_shas or missing_shas or unexpected_shas:
        payload = {
            "error": "canonical corpus mismatch",
            "duplicate_shas": duplicate_shas,
            "missing_count": len(missing_shas),
            "unexpected_count": len(unexpected_shas),
            "missing_shas": missing_shas[:20],
            "unexpected_shas": unexpected_shas[:20],
        }
        raise SystemExit(json.dumps(payload, indent=2))

    canonical_rows.sort(key=lambda row: expected_index_by_sha[row["sha"]])
    canonical_payload = {
        "head_sha": thin_corpus["head_sha"],
        "commit_count": thin_corpus["commit_count"],
        "thin_count": thin_corpus["thin_count"],
        "batch_size": thin_corpus["batch_size"],
        "proposal_file_count": sum(len(value) for value in grouped.values()),
        "canonical_batch_count": len(chosen_batches),
        "duplicate_resolution_count": len(duplicate_resolution),
        "chosen_batches": chosen_batches,
        "rows": canonical_rows,
    }
    rewrite_map = [
        {
            "sha": row["sha"],
            "rewritten_message": row["rewritten_message"],
            "source_file": str(Path(args.canonical_json).resolve()),
            "review_status": "complete_second_pass",
            "strict_process_attested": bool(row["full_patch_confirmed"]),
        }
        for row in canonical_rows
    ]
    summary = {
        "head_sha": thin_corpus["head_sha"],
        "thin_count": thin_corpus["thin_count"],
        "canonical_rows": len(canonical_rows),
        "canonical_batch_count": len(chosen_batches),
        "duplicate_resolution_count": len(duplicate_resolution),
        "proposal_file_count": sum(len(value) for value in grouped.values()),
        "quality_tiers": dict(
            Counter(row["message_quality_tier"] for row in canonical_rows)
        ),
        "median_rewritten_body_words": statistics.median(
            row["rewritten_body_word_count"] for row in canonical_rows
        )
        if canonical_rows
        else 0,
    }

    write_json(Path(args.canonical_json).resolve(), canonical_payload)
    if args.canonical_csv:
        write_csv(Path(args.canonical_csv).resolve(), canonical_rows)
    if args.duplicate_resolution_json:
        write_json(Path(args.duplicate_resolution_json).resolve(), duplicate_resolution)
    write_json(Path(args.rewrite_map_json).resolve(), rewrite_map)
    if args.summary_json:
        write_json(Path(args.summary_json).resolve(), summary)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_build_rewrite_map(args: argparse.Namespace) -> int:
    rows = canonical_rows(Path(args.proposals).resolve())
    rewrite_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    for row in rows:
        strict = parse_boolish(row.get("strict_process_attested"))
        review_required = parse_boolish(row.get("remaining_review_required"))
        if args.only_strict and not strict:
            skipped_rows.append(
                {"sha": row.get("sha") or row.get("after_sha"), "reason": "not_strict"}
            )
            continue
        if args.require_review_complete and review_required:
            skipped_rows.append(
                {
                    "sha": row.get("sha") or row.get("after_sha"),
                    "reason": "review_required",
                }
            )
            continue
        sha = row.get("sha") or row.get("after_sha")
        proposed_message = row.get("proposed_message")
        if not sha or not proposed_message:
            skipped_rows.append({"sha": sha, "reason": "missing_sha_or_message"})
            continue
        rewrite_rows.append(
            {
                "sha": sha,
                "current_message": row.get("current_message")
                or row.get("after_message"),
                "rewritten_message": compose_message(
                    proposed_message, row.get("proposed_trailer")
                ),
                "review_status": row.get("review_status"),
                "strict_process_attested": strict,
            }
        )
    output_path = Path(args.output_json).resolve()
    write_json(output_path, rewrite_rows)
    if args.output_csv:
        write_csv(Path(args.output_csv).resolve(), rewrite_rows)
    summary = {
        "input_rows": len(rows),
        "rewrite_rows": len(rewrite_rows),
        "skipped_rows": len(skipped_rows),
        "only_strict": args.only_strict,
        "require_review_complete": args.require_review_complete,
    }
    if args.summary_json:
        write_json(
            Path(args.summary_json).resolve(),
            {"summary": summary, "skipped": skipped_rows},
        )
    print(json.dumps(summary, indent=2))
    return 0


def cmd_derive_history_surface(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    full_log_path = out_dir / "git-log-full.txt"
    diff_log_path = out_dir / "git-log-with-diffs.txt"
    numstat_log_path = out_dir / "git-log-numstat.txt"
    surface_json_path = out_dir / "commit-surface.json"
    surface_csv_path = out_dir / "commit-surface.csv"
    summary_json_path = out_dir / "history-surface-summary.json"

    common_args = ["log", "--reverse", "--date=iso-strict"]
    if args.after:
        common_args.extend(["--after", args.after])
    if args.before:
        common_args.extend(["--before", args.before])
    branch = args.branch

    run_git_to_file(
        repo,
        full_log_path,
        *common_args,
        "--stat",
        "--summary",
        "--format=commit %H%nparents %P%nauthor %an <%ae>%ndate %aI%nsubject %s%nbody%n%b%n==END-COMMIT==",
        branch,
    )
    run_git_to_file(
        repo,
        diff_log_path,
        *common_args,
        "-p",
        "--format=commit %H%nparents %P%nauthor %an <%ae>%ndate %aI%nsubject %s%nbody%n%b",
        branch,
    )
    run_git_to_file(
        repo,
        numstat_log_path,
        *common_args,
        "--numstat",
        "--format=commit %H%nparents %P%nauthor %an <%ae>%ndate %aI%nsubject %s%nbody%n%b%n==END-COMMIT==",
        branch,
    )

    rows = parse_numstat_history_log(numstat_log_path)
    enrich_rows_with_patch_metrics(rows, diff_log_path)
    summary = summarize_history_surface(
        rows,
        repo=repo,
        branch=branch,
        after=args.after,
        before=args.before,
        per_commit_overhead_tokens=args.per_commit_overhead_tokens,
    )
    write_json(surface_json_path, rows)
    write_csv(surface_csv_path, rows)
    write_json(summary_json_path, summary)
    print(
        json.dumps(
            {
                "commit_count": summary["commit_count"],
                "merge_commit_count": summary["merge_commit_count"],
                "surface_json": str(surface_json_path),
                "summary_json": str(summary_json_path),
            },
            indent=2,
        )
    )
    return 0


def load_surface_rows(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if not isinstance(payload, list):
        raise ValueError("commit-surface-json must contain a list of rows")
    rows = [row for row in payload if isinstance(row, dict) and row.get("sha")]
    rows.sort(key=lambda row: (row.get("date") or "", row["sha"]))
    for index, row in enumerate(rows, 1):
        row.setdefault("history_sequence", index)
    return rows


def packet_prompt_family(kind: str) -> str:
    return {
        "normal": "message_rewrite_normal_v2",
        "heavy": "message_rewrite_heavy_v2",
        "merge": "message_rewrite_merge_v2",
        "jumbo": "message_rewrite_jumbo_chunk_v1",
    }.get(kind, "message_rewrite_normal_v2")


def packet_cost_tokens(row: dict[str, Any], per_commit_overhead_tokens: int) -> int:
    return max(
        120, int(row.get("approx_patch_tokens") or 0) + per_commit_overhead_tokens
    )


def edge_message_context(
    rows: list[dict[str, Any]], start_index: int, end_index: int, context_commits: int
) -> dict[str, list[dict[str, Any]]]:
    before_rows = rows[max(0, start_index - context_commits) : start_index]
    after_rows = rows[end_index + 1 : end_index + 1 + context_commits]

    def encode(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        encoded: list[dict[str, Any]] = []
        for row in items:
            subject, body = message_from_surface_row(row)
            encoded.append(
                {
                    "history_sequence": row.get("history_sequence"),
                    "sha": row["sha"],
                    "date": row.get("date"),
                    "subject": subject,
                    "body_word_count": body_word_count(body),
                    "current_message": current_message_from_subject_body(
                        subject, body.splitlines() if body else []
                    ),
                }
            )
        return encoded

    return {"before": encode(before_rows), "after": encode(after_rows)}


def split_patch_sections(patch_text: str) -> tuple[str, list[dict[str, Any]]]:
    lines = patch_text.splitlines(keepends=True)
    prelude: list[str] = []
    current: list[str] = []
    sections: list[dict[str, Any]] = []

    def flush_section() -> None:
        nonlocal current
        if not current:
            return
        header = current[0].rstrip("\n")
        match = DIFF_HEADER_RE.match(header)
        old_path = match.group(1) if match else ""
        new_path = match.group(2) if match else ""
        text = "".join(current)
        sections.append(
            {
                "header": header,
                "old_path": old_path,
                "new_path": new_path,
                "patch_text": text,
                "approx_patch_tokens": estimate_tokens_from_bytes(
                    len(text.encode("utf-8", errors="replace"))
                ),
            }
        )
        current = []

    for line in lines:
        if line.startswith("diff --git "):
            flush_section()
            current = [line]
            continue
        if current:
            current.append(line)
        else:
            prelude.append(line)
    flush_section()
    return "".join(prelude), sections


def chunk_diff_sections(
    sections: list[dict[str, Any]], target_tokens: int
) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    used = 0
    for section in sections:
        cost = max(120, int(section.get("approx_patch_tokens") or 0))
        if current and used + cost > target_tokens:
            chunks.append(current)
            current = []
            used = 0
        current.append(section)
        used += cost
    if current:
        chunks.append(current)
    return chunks


def materialize_jumbo_chunks(
    repo: Path,
    packet_dir: Path,
    sha: str,
    *,
    unified: int,
    include_stat: bool,
    exclude_sqlx: bool,
    jumbo_chunk_budget_tokens: int,
) -> list[dict[str, Any]]:
    patch_text = filtered_commit_patch(
        repo,
        [sha],
        unified=unified,
        exclude_sqlx=exclude_sqlx,
        stat=include_stat,
        include_paths=[],
        exclude_paths=[],
    )
    prelude, sections = split_patch_sections(patch_text)
    if not sections:
        chunk_path = packet_dir / "jumbo-chunk-01.patch"
        chunk_path.write_text(patch_text)
        return [
            {
                "chunk_id": "jumbo-chunk-01",
                "file": str(chunk_path),
                "path_count": 0,
                "paths": [],
                "approx_patch_tokens": estimate_tokens_from_bytes(
                    len(patch_text.encode("utf-8", errors="replace"))
                ),
            }
        ]

    chunk_rows: list[dict[str, Any]] = []
    for index, chunk_sections in enumerate(
        chunk_diff_sections(sections, jumbo_chunk_budget_tokens), 1
    ):
        chunk_id = f"jumbo-chunk-{index:02d}"
        chunk_text = prelude + "".join(
            section["patch_text"] for section in chunk_sections
        )
        chunk_path = packet_dir / f"{chunk_id}.patch"
        chunk_path.write_text(chunk_text)
        chunk_rows.append(
            {
                "chunk_id": chunk_id,
                "file": str(chunk_path),
                "path_count": len(chunk_sections),
                "paths": [
                    section["new_path"] or section["old_path"]
                    for section in chunk_sections
                ],
                "approx_patch_tokens": sum(
                    max(120, int(section["approx_patch_tokens"]))
                    for section in chunk_sections
                ),
            }
        )
    return chunk_rows


def cmd_build_message_packets(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    surface_rows = load_surface_rows(Path(args.commit_surface_json).resolve())
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    window_profile = resolve_window_profile(args.window_profile)
    full_diff_budget_tokens = args.full_diff_budget_tokens or int(
        window_profile["full_diff_budget_tokens"]
    )
    jumbo_threshold_tokens = args.jumbo_threshold_tokens or int(
        window_profile["jumbo_threshold_tokens"]
    )
    jumbo_chunk_budget_tokens = args.jumbo_chunk_budget_tokens or int(
        window_profile["jumbo_chunk_budget_tokens"]
    )
    edge_context_commits = args.edge_context_commits or int(
        window_profile["edge_context_commits"]
    )
    max_commits_per_normal_packet = args.max_commits_per_normal_packet
    if max_commits_per_normal_packet is None:
        profile_cap = window_profile.get("max_commits_per_normal_packet")
        max_commits_per_normal_packet = int(profile_cap) if profile_cap else None

    packets: list[dict[str, Any]] = []
    current_rows: list[dict[str, Any]] = []
    current_used = 0
    packet_index = 0

    def flush_normal_packet() -> None:
        nonlocal current_rows, current_used, packet_index
        if not current_rows:
            return
        packet_index += 1
        packets.append(
            {
                "packet_id": f"normal-{packet_index:04d}",
                "kind": "normal",
                "owned_rows": current_rows,
                "used_estimated_tokens": current_used,
            }
        )
        current_rows = []
        current_used = 0

    for row in surface_rows:
        cost = packet_cost_tokens(row, args.per_commit_overhead_tokens)
        kind = "normal"
        if row.get("merge_commit"):
            kind = "merge"
        elif cost > jumbo_threshold_tokens:
            kind = "jumbo"
        elif cost > full_diff_budget_tokens:
            kind = "heavy"

        if kind != "normal":
            flush_normal_packet()
            packet_index += 1
            packets.append(
                {
                    "packet_id": f"{kind}-{packet_index:04d}",
                    "kind": kind,
                    "owned_rows": [row],
                    "used_estimated_tokens": cost,
                }
            )
            continue

        if current_rows and (
            current_used + cost > full_diff_budget_tokens
            or (
                max_commits_per_normal_packet is not None
                and len(current_rows) >= max_commits_per_normal_packet
            )
        ):
            flush_normal_packet()
        current_rows.append(row)
        current_used += cost
    flush_normal_packet()

    packet_manifest: list[dict[str, Any]] = []
    for packet in packets:
        owned_rows = packet["owned_rows"]
        first_sequence = owned_rows[0]["history_sequence"] - 1
        last_sequence = owned_rows[-1]["history_sequence"] - 1
        packet_dir = out_dir / packet["packet_id"]
        packet_dir.mkdir(parents=True, exist_ok=True)
        patch_file: str | None = None
        jumbo_chunks: list[dict[str, Any]] = []
        if packet["kind"] == "jumbo":
            jumbo_chunks = materialize_jumbo_chunks(
                repo,
                packet_dir,
                owned_rows[0]["sha"],
                unified=args.unified,
                include_stat=args.include_stat,
                exclude_sqlx=args.exclude_sqlx,
                jumbo_chunk_budget_tokens=jumbo_chunk_budget_tokens,
            )
        else:
            patch_text = filtered_commit_patch(
                repo,
                [row["sha"] for row in owned_rows],
                unified=args.unified,
                exclude_sqlx=args.exclude_sqlx,
                stat=args.include_stat,
                include_paths=[],
                exclude_paths=[],
            )
            patch_path = packet_dir / "combined.patch"
            patch_path.write_text(patch_text)
            patch_file = str(patch_path)

        packet_payload = {
            "packet_id": packet["packet_id"],
            "kind": packet["kind"],
            "repo": str(repo),
            "budget_tokens": full_diff_budget_tokens,
            "used_estimated_tokens": packet["used_estimated_tokens"],
            "planning_profile": {
                "name": window_profile["name"],
                "description": window_profile["description"],
                "full_diff_budget_tokens": full_diff_budget_tokens,
                "jumbo_threshold_tokens": jumbo_threshold_tokens,
                "jumbo_chunk_budget_tokens": jumbo_chunk_budget_tokens,
                "edge_context_commits": edge_context_commits,
                "max_commits_per_normal_packet": max_commits_per_normal_packet,
            },
            "instructions": {
                "prompt_family": packet_prompt_family(packet["kind"]),
                "message_contract": "/realm/project/sinnix/dots/_ai/skills/history-cleanup/COMMIT_MESSAGE_CONTRACT.md",
                "message_policy": "changed code and paths primary; existing commit message secondary; edge context is message-only",
            },
            "edge_context": edge_message_context(
                surface_rows, first_sequence, last_sequence, edge_context_commits
            ),
            "owned_commits": [
                {
                    "history_sequence": row.get("history_sequence"),
                    "sha": row["sha"],
                    "date": row.get("date"),
                    "author": row.get("author"),
                    "subject": row.get("subject"),
                    "current_message": row.get("current_message"),
                    "files_touched": row.get("files_touched"),
                    "lines_changed": row.get("lines_changed"),
                    "patch_line_count": row.get("patch_line_count"),
                    "approx_patch_tokens": row.get("approx_patch_tokens"),
                    "path_roots": row.get("path_roots"),
                    "merge_commit": row.get("merge_commit"),
                }
                for row in owned_rows
            ],
            "artifacts": {
                "combined_patch_file": patch_file,
                "jumbo_chunks": jumbo_chunks,
            },
        }
        packet_json = packet_dir / "packet.json"
        write_json(packet_json, packet_payload)
        packet_manifest.append(
            {
                "packet_id": packet["packet_id"],
                "kind": packet["kind"],
                "commit_count": len(owned_rows),
                "used_estimated_tokens": packet["used_estimated_tokens"],
                "first_sha": owned_rows[0]["sha"],
                "last_sha": owned_rows[-1]["sha"],
                "packet_json": str(packet_json),
                "combined_patch_file": patch_file,
                "jumbo_chunk_count": len(jumbo_chunks),
            }
        )

    summary = {
        "repo": str(repo),
        "packet_count": len(packet_manifest),
        "kind_counts": dict(Counter(packet["kind"] for packet in packet_manifest)),
        "window_profile": {
            "name": window_profile["name"],
            "description": window_profile["description"],
        },
        "full_diff_budget_tokens": full_diff_budget_tokens,
        "jumbo_threshold_tokens": jumbo_threshold_tokens,
        "jumbo_chunk_budget_tokens": jumbo_chunk_budget_tokens,
        "edge_context_commits": edge_context_commits,
        "max_commits_per_normal_packet": max_commits_per_normal_packet,
        "packets": packet_manifest,
    }
    write_json(out_dir / "index.json", summary)
    print(
        json.dumps(
            {
                "packet_count": len(packet_manifest),
                "kind_counts": summary["kind_counts"],
                "index": str((out_dir / "index.json").resolve()),
            },
            indent=2,
        )
    )
    return 0


def cmd_message_quality_report(args: argparse.Namespace) -> int:
    input_path = Path(args.input_json).resolve()
    rows = canonical_rows(input_path)
    report_rows: list[dict[str, Any]] = []
    skipped_rows = 0
    for row in rows:
        subject, body = message_for_source(row, args.message_source)
        if not subject and not body:
            skipped_rows += 1
            continue
        quality = assess_commit_message_quality(subject, body)
        report_rows.append(
            {
                "sha": row.get("sha") or row.get("after_sha"),
                "message_source": args.message_source,
                "subject": subject,
                "body_word_count": quality["body_word_count"],
                "paragraph_count": quality["paragraph_count"],
                "subject_length": quality["subject_length"],
                "quality_score": quality["score"],
                "quality_tier": quality["tier"],
                "flags": quality["flags"],
            }
        )

    report_rows.sort(
        key=lambda row: (
            {"insufficient": 0, "thin": 1, "adequate": 2, "strong": 3}.get(
                row["quality_tier"], -1
            ),
            row["quality_score"],
            row.get("sha") or "",
        )
    )
    tier_counts = Counter(row["quality_tier"] for row in report_rows)
    flag_counts = Counter(
        flag for row in report_rows for flag in row.get("flags") or []
    )
    summary = {
        "input": str(input_path),
        "message_source": args.message_source,
        "rows": len(report_rows),
        "skipped_rows": skipped_rows,
        "tier_counts": dict(tier_counts),
        "flag_counts": dict(flag_counts.most_common()),
        "median_body_words": statistics.median(
            [row["body_word_count"] for row in report_rows]
        )
        if report_rows
        else 0,
        "median_quality_score": statistics.median(
            [row["quality_score"] for row in report_rows]
        )
        if report_rows
        else 0,
        "top_flagged_rows": report_rows[: args.top_n],
    }
    if args.output_json:
        write_json(Path(args.output_json).resolve(), report_rows)
    if args.output_csv:
        write_csv(Path(args.output_csv).resolve(), report_rows)
    if args.summary_json:
        write_json(Path(args.summary_json).resolve(), summary)
    print(json.dumps(summary, indent=2))
    return 0


def compact_message_preview(text: str, limit: int = 140) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def build_global_style_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "style_guide_version",
            "summary",
            "subject_rules",
            "body_rules",
            "preferred_verbs",
            "preferred_surface_terms",
            "anti_patterns",
            "packet_prompt_addendum",
        ],
        "properties": {
            "style_guide_version": {"type": "string", "const": "1"},
            "summary": {"type": "string", "minLength": 1, "maxLength": 1200},
            "subject_rules": {
                "type": "array",
                "minItems": 3,
                "maxItems": 12,
                "items": {"type": "string", "minLength": 1, "maxLength": 240},
            },
            "body_rules": {
                "type": "array",
                "minItems": 3,
                "maxItems": 12,
                "items": {"type": "string", "minLength": 1, "maxLength": 240},
            },
            "preferred_verbs": {
                "type": "array",
                "maxItems": 24,
                "items": {"type": "string", "minLength": 1, "maxLength": 64},
            },
            "preferred_surface_terms": {
                "type": "array",
                "maxItems": 40,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["surface", "preferred"],
                    "properties": {
                        "surface": {"type": "string", "minLength": 1, "maxLength": 120},
                        "preferred": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 120,
                        },
                        "notes": {"type": "string", "maxLength": 240},
                    },
                },
            },
            "anti_patterns": {
                "type": "array",
                "minItems": 3,
                "maxItems": 20,
                "items": {"type": "string", "minLength": 1, "maxLength": 240},
            },
            "packet_prompt_addendum": {
                "type": "array",
                "minItems": 3,
                "maxItems": 12,
                "items": {"type": "string", "minLength": 1, "maxLength": 240},
            },
        },
    }


def build_global_style_prompt(
    corpus_path: Path, schema_path: Path, corpus: dict[str, Any]
) -> str:
    top_roots = corpus.get("top_path_roots") or []
    root_lines = [
        f"- {row['path_root']}: {row['commit_count']} commits" for row in top_roots[:12]
    ] or ["- none"]
    tier_counts = corpus.get("current_quality_tier_counts") or {}
    tier_lines = [f"- {tier}: {count}" for tier, count in tier_counts.items()] or [
        "- none"
    ]
    sections = [
        "# Global Rewrite Style Derivation",
        "",
        "## Task",
        "Derive one repo-local style guide for future commit-message rewrite packets. Focus on canonical verbs, surface naming, body structure, and anti-pattern avoidance.",
        "",
        "## Required reading",
        f"- Corpus: {corpus_path}",
        "",
        "## Corpus summary",
        f"- Commit count: {corpus.get('commit_count') or 0}",
        f"- Target packet window profile: {corpus.get('target_window_profile') or 'unknown'}",
        "",
        "### Dominant path roots",
        *root_lines,
        "",
        "### Current message quality tiers",
        *tier_lines,
        "",
        "## Method",
        "- Use current history only to derive naming and structure policy, not as a template to imitate blindly.",
        "- Current low-quality messages are evidence of anti-patterns to avoid.",
        "- Prefer repo-local surface terms over generic nouns.",
        "- Optimize for future packet rewrites, not for one-off human prose.",
        "- The final guide should be short enough to include in every packet prompt.",
        "",
        "## Output contract",
        f"- Return JSON only, matching schema at {schema_path}.",
        "- `subject_rules` should describe how to name operation plus surface concretely.",
        "- `body_rules` should describe compact body structure and detail density.",
        "- `preferred_surface_terms` should map ambiguous/raw surfaces to preferred names.",
        "- `packet_prompt_addendum` should be immediately usable as extra prompt bullets in packet runs.",
        "",
    ]
    return "\n".join(sections) + "\n"


def cmd_prepare_global_style_pass(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    rows = load_surface_rows(Path(args.commit_surface_json).resolve())
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    window_profile = resolve_window_profile(args.window_profile)

    if args.max_commits:
        rows = rows[: args.max_commits]

    top_path_roots: Counter[str] = Counter()
    quality_tiers: Counter[str] = Counter()
    quality_flags: Counter[str] = Counter()
    corpus_commits: list[dict[str, Any]] = []
    for row in rows:
        subject, body = message_from_surface_row(row)
        quality = assess_commit_message_quality(subject, body)
        quality_tiers[quality["tier"]] += 1
        quality_flags.update(quality["flags"])
        for root in row.get("path_roots") or []:
            top_path_roots[root] += 1
        corpus_commits.append(
            {
                "history_sequence": row.get("history_sequence"),
                "sha": row.get("sha"),
                "subject": subject,
                "current_message": row.get("current_message"),
                "path_roots": row.get("path_roots") or [],
                "files_touched": row.get("files_touched"),
                "lines_changed": row.get("lines_changed"),
                "approx_patch_tokens": row.get("approx_patch_tokens"),
                "merge_commit": bool(row.get("merge_commit")),
                "current_quality_tier": quality["tier"],
                "current_quality_flags": quality["flags"],
            }
        )

    corpus = {
        "repo": str(repo),
        "commit_count": len(corpus_commits),
        "target_window_profile": window_profile["name"],
        "target_window_profile_description": window_profile["description"],
        "current_quality_tier_counts": dict(quality_tiers),
        "current_quality_flag_counts": dict(quality_flags.most_common(24)),
        "top_path_roots": [
            {"path_root": root, "commit_count": count}
            for root, count in top_path_roots.most_common(24)
        ],
        "commits": corpus_commits,
    }

    corpus_path = out_dir / "global-style-corpus.json"
    schema_path = out_dir / "output.schema.json"
    prompt_path = out_dir / "prompt.md"
    request_path = out_dir / "request.txt"
    run_script_path = out_dir / "run.sh"
    response_path = out_dir / "response.json"
    stderr_path = out_dir / "stderr.txt"
    manifest_path = out_dir / "manifest.json"

    write_json(corpus_path, corpus)
    write_json(schema_path, build_global_style_schema())
    prompt_path.write_text(build_global_style_prompt(corpus_path, schema_path, corpus))
    request_path.write_text(build_packet_exec_request(prompt_path) + "\n")

    skill_root = Path(__file__).resolve().parent
    add_dirs = [str(skill_root), str(out_dir)]
    if args.extra_add_dir:
        add_dirs.extend(str(Path(value).resolve()) for value in args.extra_add_dir)
    unique_add_dirs: list[str] = []
    seen_add_dirs: set[str] = set()
    for value in add_dirs:
        if value not in seen_add_dirs:
            seen_add_dirs.add(value)
            unique_add_dirs.append(value)

    command: list[str] = [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--sandbox",
        args.sandbox,
        "-C",
        str(repo),
    ]
    if args.model:
        command.extend(["--model", args.model])
    if args.reasoning_effort:
        command.extend(["-c", f'model_reasoning_effort="{args.reasoning_effort}"'])
    if args.profile:
        command.extend(["--profile", args.profile])
    for value in unique_add_dirs:
        command.extend(["--add-dir", value])
    command.extend(
        [
            "--output-schema",
            str(schema_path),
            "-o",
            str(response_path),
            request_path.read_text().strip(),
        ]
    )
    run_script_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"cd {shlex.quote(str(repo))}",
        "",
        " ".join(shlex.quote(part) for part in command)
        + f" 2> {shlex.quote(str(stderr_path))}",
    ]
    run_script_path.write_text("\n".join(run_script_lines) + "\n")
    run_script_path.chmod(0o755)

    manifest = {
        "repo": str(repo),
        "window_profile": {
            "name": window_profile["name"],
            "description": window_profile["description"],
        },
        "corpus_file": str(corpus_path),
        "schema_file": str(schema_path),
        "prompt_file": str(prompt_path),
        "request_file": str(request_path),
        "run_script": str(run_script_path),
        "response_file": str(response_path),
        "stderr_file": str(stderr_path),
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "sandbox": args.sandbox,
    }
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {"manifest": str(manifest_path), "commit_count": len(corpus_commits)},
            indent=2,
        )
    )
    return 0


def build_packet_exec_schema(packet: dict[str, Any]) -> dict[str, Any]:
    owned_shas = [commit["sha"] for commit in packet["owned_commits"]]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["batch_id", "items"],
        "properties": {
            "batch_id": {"type": "string", "const": packet["packet_id"]},
            "items": {
                "type": "array",
                "minItems": len(owned_shas),
                "maxItems": len(owned_shas),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "sha",
                        "original_subject",
                        "proposed_subject",
                        "proposed_body",
                        "full_patch_confirmed",
                        "adjacent_context_used",
                        "confidence",
                        "why_basis",
                    ],
                    "properties": {
                        "sha": {"type": "string", "enum": owned_shas},
                        "original_subject": {"type": "string", "minLength": 1},
                        "proposed_subject": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 120,
                        },
                        "proposed_body": {"type": "string"},
                        "full_patch_confirmed": {"type": "boolean"},
                        "adjacent_context_used": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 8,
                        },
                        "confidence": {"type": "string", "minLength": 1},
                        "why_basis": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }


def build_packet_exec_prompt(
    packet: dict[str, Any],
    packet_json_path: Path,
    schema_path: Path,
    style_guide_path: Path | None = None,
) -> str:
    kind_specific_lines = {
        "normal": [
            "- Read the full combined patch file before proposing any message.",
        ],
        "heavy": [
            "- This packet is a heavy single commit. Read the full combined patch file and do not collapse detail into a vague summary.",
        ],
        "merge": [
            "- This packet is a merge commit. Read the full combined patch and summarize the actual merge effect rather than writing generic merge noise.",
        ],
        "jumbo": [
            "- This packet is jumbo. Read every listed chunk patch before proposing any message.",
            "- Use the combined behavior across all chunk files, not any single chunk, when writing the final message.",
        ],
    }.get(packet["kind"], [])
    owned_commit_lines = [
        (
            f"- {commit['sha']} | "
            f"{compact_message_preview(normalized_subject_line(commit.get('current_message') or commit.get('subject') or ''))} | "
            f"roots: {', '.join(commit.get('path_roots') or []) or '-'} | "
            f"est_tokens: {commit.get('approx_patch_tokens') or 0}"
        )
        for commit in packet["owned_commits"]
    ]

    edge_before = packet.get("edge_context", {}).get("before") or []
    edge_after = packet.get("edge_context", {}).get("after") or []
    edge_lines = ["Before:"]
    if edge_before:
        edge_lines.extend(
            f"- {row['sha']} | {compact_message_preview(normalized_subject_line(row.get('current_message') or row.get('subject') or ''))}"
            for row in edge_before
        )
    else:
        edge_lines.append("- none")
    edge_lines.append("After:")
    if edge_after:
        edge_lines.extend(
            f"- {row['sha']} | {compact_message_preview(normalized_subject_line(row.get('current_message') or row.get('subject') or ''))}"
            for row in edge_after
        )
    else:
        edge_lines.append("- none")

    patch_lines = []
    combined_patch_file = packet.get("artifacts", {}).get("combined_patch_file")
    if combined_patch_file:
        patch_lines.append(f"- Combined patch: {combined_patch_file}")
    for chunk in packet.get("artifacts", {}).get("jumbo_chunks") or []:
        patch_lines.append(
            f"- {chunk['chunk_id']}: {chunk['file']} "
            f"(paths={chunk.get('path_count') or 0}, est_tokens={chunk.get('approx_patch_tokens') or 0})"
        )

    required_reading_lines = list(patch_lines)
    if style_guide_path is not None:
        required_reading_lines.append(f"- Style guide: {style_guide_path}")

    method_lines = [
        "- Changed code and touched paths are primary evidence.",
        "- Existing commit messages are secondary evidence.",
        "- Edge-context commit messages exist only for chronology and naming continuity.",
    ]
    if style_guide_path is not None:
        method_lines.append(
            "- Treat the style guide as repo-local naming policy; do not let it override patch facts."
        )
    method_lines.extend(
        [
            "- Output one item per owned commit, in the same order shown below.",
            "- Keep `original_subject` exactly equal to the current subject line shown below, without body text.",
            "- `proposed_body` must be body only: no repeated subject line, no trailer lines, no markdown fences.",
            "- If evidence is ambiguous, say less rather than inventing intent.",
            *kind_specific_lines,
        ]
    )

    sections = [
        f"# Message Rewrite Packet {packet['packet_id']}",
        "",
        "## Task",
        "Rewrite commit messages only. Do not edit files, do not run any history rewrite, and do not invent facts that are not supported by the diffs.",
        "",
        "## Required reading",
        *required_reading_lines,
        "",
        "## Method",
        *method_lines,
        "",
        "## Commit quality bar",
        "- Subject: operation + concrete surface. Avoid vague subjects like cleanup/finalize/complete/execute.",
        "- Prefer one terse lead sentence at most, then 2-4 bullets.",
        "- Bullets should usually cover concrete surfaces, main changes, and behavioral effect.",
        "- Avoid filler openings such as `This commit`, `This change`, `Behaviorally`, `The practical effect is`, or `After the refactor`.",
        "- Prefer compact audit-log structure over glossy prose.",
        "",
        "## Output contract",
        f"- Return JSON only, matching schema at {schema_path}.",
        "- Set `full_patch_confirmed` to true only if you read all owned diff material.",
        "- `adjacent_context_used` should record which edge context you relied on, if any.",
        "- `why_basis` should say what evidence the explanation is based on, e.g. `patch_only` or `patch_plus_adjacent_context`.",
        "",
        "## Owned commits",
        *owned_commit_lines,
        "",
        "## Edge context messages",
        *edge_lines,
        "",
    ]
    return "\n".join(sections) + "\n"


def build_packet_exec_request(prompt_file: Path) -> str:
    return f"Read @{prompt_file} and return only JSON matching the provided schema."


def validate_packet_exec_payload(
    packet: dict[str, Any], payload: dict[str, Any]
) -> list[dict[str, Any]]:
    if payload.get("batch_id") != packet["packet_id"]:
        raise ValueError(
            f"batch_id mismatch: expected {packet['packet_id']} got {payload.get('batch_id')!r}"
        )
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("payload.items must be a list")
    owned_commits = packet["owned_commits"]
    if len(items) != len(owned_commits):
        raise ValueError(
            f"item count mismatch: expected {len(owned_commits)} got {len(items)}"
        )

    normalized_items: list[dict[str, Any]] = []
    seen_shas: set[str] = set()
    for expected_commit, item in zip(owned_commits, items, strict=True):
        sha = normalize_commit_sha(item.get("sha"))
        if sha != expected_commit["sha"]:
            raise ValueError(
                f"sha order mismatch: expected {expected_commit['sha']} got {sha!r}"
            )
        if sha in seen_shas:
            raise ValueError(f"duplicate sha in payload: {sha}")
        seen_shas.add(sha)
        original_subject = normalized_subject_line(item.get("original_subject") or "")
        expected_original_subject = normalized_subject_line(
            expected_commit.get("current_message")
            or expected_commit.get("subject")
            or ""
        )
        if original_subject != expected_original_subject:
            raise ValueError(f"original_subject mismatch for {sha}")
        proposed_subject = (item.get("proposed_subject") or "").strip()
        if not proposed_subject:
            raise ValueError(f"missing proposed_subject for {sha}")
        if "\n" in proposed_subject:
            raise ValueError(f"proposed_subject contains newline for {sha}")
        proposed_body = strip_known_git_trailers(
            (item.get("proposed_body") or "").strip()
        )
        adjacent_context_used = item.get("adjacent_context_used")
        if not isinstance(adjacent_context_used, list):
            raise ValueError(f"adjacent_context_used must be a list for {sha}")
        why_basis = (item.get("why_basis") or "").strip()
        if not why_basis:
            raise ValueError(f"missing why_basis for {sha}")
        confidence = (item.get("confidence") or "").strip()
        if not confidence:
            raise ValueError(f"missing confidence for {sha}")
        normalized_items.append(
            {
                "sha": sha,
                "original_subject": original_subject,
                "proposed_subject": proposed_subject,
                "proposed_body": proposed_body,
                "full_patch_confirmed": bool(item.get("full_patch_confirmed")),
                "adjacent_context_used": [
                    str(value) for value in adjacent_context_used
                ],
                "confidence": confidence,
                "why_basis": why_basis,
            }
        )
    return normalized_items


def load_packet_exec_manifest(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("packets"), list):
        raise ValueError(f"unsupported packet exec manifest: {path}")
    return payload


def packet_exec_state(entry: dict[str, Any]) -> dict[str, Any]:
    status_path = Path(entry["status_file"])
    if status_path.exists():
        for attempt in range(5):
            try:
                payload = load_json(status_path)
                if isinstance(payload, dict):
                    return payload
            except JSONDecodeError:
                if attempt == 4:
                    raise
                time.sleep(0.05)
    state = {
        "packet_id": entry["packet_id"],
        "kind": entry["kind"],
        "commit_count": entry["commit_count"],
        "used_estimated_tokens": entry["used_estimated_tokens"],
        "state": "pending",
        "attempt_count": 0,
        "attempts": [],
        "proposal_file": entry["proposal_file"],
    }
    write_json(status_path, state)
    return state


def ns_to_ms(duration_ns: int) -> float:
    return round(duration_ns / 1_000_000, 3)


def write_packet_exec_summary(
    manifest: dict[str, Any], summary: dict[str, Any]
) -> None:
    write_json(Path(manifest["summary_file"]), summary)


def summarize_packet_exec_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    for entry in manifest["packets"]:
        state = packet_exec_state(entry)
        row = {
            "packet_id": entry["packet_id"],
            "kind": entry["kind"],
            "commit_count": entry["commit_count"],
            "used_estimated_tokens": entry["used_estimated_tokens"],
            "state": state.get("state", "pending"),
            "attempt_count": state.get("attempt_count", 0),
            "duration_seconds": state.get("duration_seconds"),
            "proposal_exists": Path(entry["proposal_file"]).exists(),
        }
        rows.append(row)
        state_counts[row["state"]] += 1
    summary = {
        "manifest": manifest["manifest_file"],
        "repo": manifest["repo"],
        "packet_count": len(rows),
        "state_counts": dict(state_counts),
        "rows": rows,
        "updated_at": utc_now_iso(),
    }
    write_packet_exec_summary(manifest, summary)
    return summary


def cmd_prepare_packet_exec(args: argparse.Namespace) -> int:
    packet_index_path = Path(args.packet_index).resolve()
    packet_index = load_json(packet_index_path)
    if not isinstance(packet_index, dict) or not isinstance(
        packet_index.get("packets"), list
    ):
        raise SystemExit(f"unsupported packet index: {packet_index_path}")
    repo = Path(packet_index["repo"]).resolve()
    style_guide_path = (
        Path(args.style_guide_file).resolve() if args.style_guide_file else None
    )
    out_dir = Path(args.out_dir).resolve()
    packets_dir = out_dir / "packets"
    proposals_dir = out_dir / "proposals"
    packets_dir.mkdir(parents=True, exist_ok=True)
    proposals_dir.mkdir(parents=True, exist_ok=True)

    skill_root = Path(__file__).resolve().parent
    run_root = packet_index_path.parent.parent
    manifest_packets: list[dict[str, Any]] = []
    thin_commits: list[dict[str, Any]] = []

    for sequence_index, packet_row in enumerate(packet_index["packets"], 1):
        packet_json_path = Path(packet_row["packet_json"]).resolve()
        packet = load_json(packet_json_path)
        packet_dir = packets_dir / packet["packet_id"]
        packet_dir.mkdir(parents=True, exist_ok=True)
        schema_path = packet_dir / "output.schema.json"
        prompt_path = packet_dir / "prompt.md"
        request_path = packet_dir / "request.txt"
        run_script_path = packet_dir / "run.sh"
        status_path = packet_dir / "status.json"
        events_path = packet_dir / "events.jsonl"
        stderr_path = packet_dir / "stderr.txt"
        last_message_path = packet_dir / "last-message.json"
        proposal_path = proposals_dir / f"{packet['packet_id']}.json"

        write_json(schema_path, build_packet_exec_schema(packet))
        prompt_path.write_text(
            build_packet_exec_prompt(
                packet, packet_json_path, schema_path, style_guide_path
            )
        )
        request_path.write_text(build_packet_exec_request(prompt_path) + "\n")

        add_dirs = [str(skill_root), str(run_root), str(out_dir)]
        if style_guide_path is not None:
            add_dirs.append(str(style_guide_path.parent))
        if args.extra_add_dir:
            add_dirs.extend(str(Path(value).resolve()) for value in args.extra_add_dir)
        unique_add_dirs: list[str] = []
        seen_add_dirs: set[str] = set()
        for value in add_dirs:
            if value not in seen_add_dirs:
                seen_add_dirs.add(value)
                unique_add_dirs.append(value)

        command: list[str] = [
            "codex",
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            args.sandbox,
            "-C",
            str(repo),
        ]
        if args.model:
            command.extend(["--model", args.model])
        if args.reasoning_effort:
            command.extend(["-c", f'model_reasoning_effort="{args.reasoning_effort}"'])
        if args.profile:
            command.extend(["--profile", args.profile])
        for value in unique_add_dirs:
            command.extend(["--add-dir", value])
        command.extend(
            [
                "--output-schema",
                str(schema_path),
                "-o",
                str(last_message_path),
                request_path.read_text().strip(),
            ]
        )
        run_script_lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            " ".join(shlex.quote(part) for part in command)
            + f" > {shlex.quote(str(events_path))} 2> {shlex.quote(str(stderr_path))}",
            "",
        ]
        run_script_path.write_text("\n".join(run_script_lines))
        run_script_path.chmod(0o755)

        entry = {
            "packet_id": packet["packet_id"],
            "kind": packet["kind"],
            "sequence_index": sequence_index,
            "commit_count": len(packet["owned_commits"]),
            "used_estimated_tokens": packet["used_estimated_tokens"],
            "packet_json": str(packet_json_path),
            "prompt_file": str(prompt_path),
            "schema_file": str(schema_path),
            "request_file": str(request_path),
            "run_script": str(run_script_path),
            "status_file": str(status_path),
            "events_file": str(events_path),
            "stderr_file": str(stderr_path),
            "last_message_file": str(last_message_path),
            "proposal_file": str(proposal_path),
            "command": command,
        }
        manifest_packets.append(entry)
        packet_exec_state(entry)
        for commit in packet["owned_commits"]:
            thin_commits.append(
                {
                    "index": len(thin_commits) + 1,
                    "sha": commit["sha"],
                    "subject": commit.get("subject") or "",
                    "batch_id": packet["packet_id"],
                }
            )

    thin_corpus = {
        "head_sha": git(repo, "rev-parse", "HEAD").strip(),
        "commit_count": len(thin_commits),
        "thin_count": len(thin_commits),
        "batch_size": 1,
        "commits": thin_commits,
    }
    thin_corpus_path = out_dir / "thin-corpus.json"
    write_json(thin_corpus_path, thin_corpus)

    manifest = {
        "manifest_file": str((out_dir / "manifest.json").resolve()),
        "repo": str(repo),
        "packet_index": str(packet_index_path),
        "packet_window_profile": packet_index.get("window_profile"),
        "skill_root": str(skill_root),
        "run_root": str(run_root),
        "out_dir": str(out_dir),
        "summary_file": str((out_dir / "status-summary.json").resolve()),
        "thin_corpus": str(thin_corpus_path),
        "proposals_dir": str(proposals_dir),
        "style_guide_file": str(style_guide_path) if style_guide_path else None,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "profile": args.profile,
        "sandbox": args.sandbox,
        "packets": manifest_packets,
        "prepared_at": utc_now_iso(),
    }
    write_json(out_dir / "manifest.json", manifest)
    summary = summarize_packet_exec_manifest(manifest)
    print(
        json.dumps(
            {
                "manifest": manifest["manifest_file"],
                "thin_corpus": manifest["thin_corpus"],
                "packet_count": len(manifest_packets),
                "state_counts": summary["state_counts"],
            },
            indent=2,
        )
    )
    return 0


def cmd_packet_exec_status(args: argparse.Namespace) -> int:
    manifest = load_packet_exec_manifest(Path(args.manifest).resolve())
    summary = summarize_packet_exec_manifest(manifest)
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    print(f"manifest: {summary['manifest']}")
    print(f"repo: {summary['repo']}")
    print(f"packets: {summary['packet_count']}")
    print("states:")
    for key, value in sorted(summary["state_counts"].items()):
        print(f"  {key}: {value}")
    if args.show_rows:
        for row in summary["rows"]:
            print(
                f"{row['packet_id']} kind={row['kind']} commits={row['commit_count']} "
                f"tokens={row['used_estimated_tokens']} state={row['state']} attempts={row['attempt_count']}"
            )
    return 0


def cmd_run_packet_exec(args: argparse.Namespace) -> int:
    manifest = load_packet_exec_manifest(Path(args.manifest).resolve())
    packet_filter = set(args.packet_id or [])
    runnable_states = {"pending"}
    if args.retry_failed:
        runnable_states.update({"failed_exit", "failed_launch", "invalid_output"})

    queue: list[dict[str, Any]] = []
    for entry in manifest["packets"]:
        if packet_filter and entry["packet_id"] not in packet_filter:
            continue
        state = packet_exec_state(entry)
        if state.get("state") in runnable_states:
            queue.append(entry)

    if args.limit:
        queue = queue[: args.limit]

    active: dict[str, dict[str, Any]] = {}
    completed = 0

    def launch(entry: dict[str, Any]) -> None:
        nonlocal active
        status_path = Path(entry["status_file"])
        state = packet_exec_state(entry)
        attempt_number = int(state.get("attempt_count") or 0) + 1
        launched_at = utc_now_iso_precise()
        attempt = {
            "attempt": attempt_number,
            "started_at": launched_at,
            "command": entry["command"],
            "events_file": entry["events_file"],
            "stderr_file": entry["stderr_file"],
            "last_message_file": entry["last_message_file"],
            "proposal_file": entry["proposal_file"],
        }
        attempts = list(state.get("attempts") or [])
        attempts.append(attempt)
        updated_state = {
            **state,
            "state": "running",
            "attempt_count": attempt_number,
            "attempts": attempts,
            "started_at": launched_at,
            "last_transition_at": launched_at,
        }
        write_json(status_path, updated_state)
        events_handle = Path(entry["events_file"]).open("w")
        stderr_handle = Path(entry["stderr_file"]).open("w")
        try:
            process = subprocess.Popen(
                entry["command"],
                stdout=events_handle,
                stderr=stderr_handle,
                text=True,
            )
        except OSError as exc:
            events_handle.close()
            stderr_handle.close()
            failed_at = utc_now_iso_precise()
            write_json(
                status_path,
                {
                    **updated_state,
                    "state": "failed_launch",
                    "error": str(exc),
                    "finished_at": failed_at,
                    "last_transition_at": failed_at,
                },
            )
            return
        attempts[-1]["pid"] = process.pid
        attempts[-1]["launch_completed_at"] = utc_now_iso_precise()
        attempts[-1]["poll_count"] = 0
        attempts[-1]["poll_timestamps"] = []
        attempts[-1]["timing_ns"] = {}
        updated_state["attempts"] = attempts
        updated_state["pid"] = process.pid
        write_json(status_path, updated_state)
        active[entry["packet_id"]] = {
            "entry": entry,
            "process": process,
            "events_handle": events_handle,
            "stderr_handle": stderr_handle,
            "started_monotonic_ns": time.monotonic_ns(),
        }
        print(
            f"started {entry['packet_id']} kind={entry['kind']} commits={entry['commit_count']}"
        )

    def finalize(packet_id: str) -> None:
        nonlocal completed
        runtime = active.pop(packet_id)
        entry = runtime["entry"]
        process = runtime["process"]
        runtime["events_handle"].close()
        runtime["stderr_handle"].close()
        status_path = Path(entry["status_file"])
        state = packet_exec_state(entry)
        finished_at = utc_now_iso_precise()
        finished_monotonic_ns = time.monotonic_ns()
        total_duration_ns = finished_monotonic_ns - runtime["started_monotonic_ns"]
        duration_seconds = round(total_duration_ns / 1_000_000_000, 3)
        attempts = list(state.get("attempts") or [])
        attempt = dict(attempts[-1]) if attempts else {}
        process_exited_at = utc_now_iso_precise()
        validation_started_ns = time.monotonic_ns()
        validation_started_at = utc_now_iso_precise()
        attempt.setdefault("timing_ns", {})
        attempt["process_exited_at"] = process_exited_at
        attempt["validation_started_at"] = validation_started_at
        attempt["timing_ns"]["launch_to_exit"] = (
            finished_monotonic_ns - runtime["started_monotonic_ns"]
        )

        if process.returncode != 0:
            validation_finished_ns = time.monotonic_ns()
            validation_finished_at = utc_now_iso_precise()
            attempt["validation_finished_at"] = validation_finished_at
            attempt["timing_ns"]["validation"] = (
                validation_finished_ns - validation_started_ns
            )
            attempt["timing_ns"]["total"] = (
                validation_finished_ns - runtime["started_monotonic_ns"]
            )
            attempt["timing_ms"] = {
                key: ns_to_ms(value) for key, value in attempt["timing_ns"].items()
            }
            attempts[-1] = attempt
            write_json(
                status_path,
                {
                    **state,
                    "state": "failed_exit",
                    "exit_code": process.returncode,
                    "finished_at": finished_at,
                    "duration_seconds": duration_seconds,
                    "last_transition_at": validation_finished_at,
                    "attempts": attempts,
                    "timing_ms": attempt["timing_ms"],
                },
            )
            print(f"failed {packet_id} exit={process.returncode}")
            return

        last_message_path = Path(entry["last_message_file"])
        if not last_message_path.exists():
            validation_finished_ns = time.monotonic_ns()
            validation_finished_at = utc_now_iso_precise()
            attempt["validation_finished_at"] = validation_finished_at
            attempt["timing_ns"]["validation"] = (
                validation_finished_ns - validation_started_ns
            )
            attempt["timing_ns"]["total"] = (
                validation_finished_ns - runtime["started_monotonic_ns"]
            )
            attempt["timing_ms"] = {
                key: ns_to_ms(value) for key, value in attempt["timing_ns"].items()
            }
            attempts[-1] = attempt
            write_json(
                status_path,
                {
                    **state,
                    "state": "invalid_output",
                    "error": "missing last-message output",
                    "finished_at": finished_at,
                    "duration_seconds": duration_seconds,
                    "last_transition_at": validation_finished_at,
                    "attempts": attempts,
                    "timing_ms": attempt["timing_ms"],
                },
            )
            print(f"invalid {packet_id} missing last-message output")
            return

        try:
            payload = json.loads(last_message_path.read_text())
            packet = load_json(Path(entry["packet_json"]))
            items = validate_packet_exec_payload(packet, payload)
        except Exception as exc:
            validation_finished_ns = time.monotonic_ns()
            validation_finished_at = utc_now_iso_precise()
            attempt["validation_finished_at"] = validation_finished_at
            attempt["timing_ns"]["validation"] = (
                validation_finished_ns - validation_started_ns
            )
            attempt["timing_ns"]["total"] = (
                validation_finished_ns - runtime["started_monotonic_ns"]
            )
            attempt["timing_ms"] = {
                key: ns_to_ms(value) for key, value in attempt["timing_ns"].items()
            }
            attempts[-1] = attempt
            write_json(
                status_path,
                {
                    **state,
                    "state": "invalid_output",
                    "error": str(exc),
                    "finished_at": finished_at,
                    "duration_seconds": duration_seconds,
                    "last_transition_at": validation_finished_at,
                    "attempts": attempts,
                    "timing_ms": attempt["timing_ms"],
                },
            )
            print(f"invalid {packet_id} error={exc}")
            return

        validation_finished_ns = time.monotonic_ns()
        validation_finished_at = utc_now_iso_precise()
        proposal_write_started_ns = time.monotonic_ns()
        proposal_payload = {
            "batch_id": entry["packet_id"],
            "agent": f"codex-exec:{manifest.get('model') or 'default'}",
            "packet_id": entry["packet_id"],
            "kind": entry["kind"],
            "items": items,
        }
        write_json(Path(entry["proposal_file"]), proposal_payload)
        proposal_write_finished_ns = time.monotonic_ns()
        proposal_write_finished_at = utc_now_iso_precise()
        attempt["validation_finished_at"] = validation_finished_at
        attempt["proposal_written_at"] = proposal_write_finished_at
        attempt["timing_ns"]["validation"] = (
            validation_finished_ns - validation_started_ns
        )
        attempt["timing_ns"]["proposal_write"] = (
            proposal_write_finished_ns - proposal_write_started_ns
        )
        attempt["timing_ns"]["total"] = (
            proposal_write_finished_ns - runtime["started_monotonic_ns"]
        )
        attempt["timing_ms"] = {
            key: ns_to_ms(value) for key, value in attempt["timing_ns"].items()
        }
        attempts[-1] = attempt
        write_json(
            status_path,
            {
                **state,
                "state": "completed",
                "exit_code": process.returncode,
                "finished_at": finished_at,
                "duration_seconds": duration_seconds,
                "proposal_row_count": len(items),
                "proposal_file": entry["proposal_file"],
                "last_transition_at": proposal_write_finished_at,
                "attempts": attempts,
                "timing_ms": attempt["timing_ms"],
            },
        )
        completed += 1
        print(f"completed {packet_id} rows={len(items)} duration_s={duration_seconds}")

    while queue or active:
        while queue and len(active) < args.jobs:
            launch(queue.pop(0))
        if not active:
            break
        time.sleep(0.25)
        for packet_id, runtime in list(active.items()):
            process = runtime["process"]
            status_path = Path(runtime["entry"]["status_file"])
            state = packet_exec_state(runtime["entry"])
            attempts = list(state.get("attempts") or [])
            if attempts:
                attempt = dict(attempts[-1])
                attempt["poll_count"] = int(attempt.get("poll_count") or 0) + 1
                timestamps = list(attempt.get("poll_timestamps") or [])
                timestamps.append(utc_now_iso_precise())
                if len(timestamps) > 64:
                    timestamps = timestamps[-64:]
                attempt["poll_timestamps"] = timestamps
                attempts[-1] = attempt
                write_json(
                    status_path,
                    {
                        **state,
                        "attempts": attempts,
                        "last_transition_at": timestamps[-1],
                    },
                )
            if process.poll() is not None:
                finalize(packet_id)

    summary = summarize_packet_exec_manifest(manifest)
    print(
        json.dumps(
            {
                "completed_now": completed,
                "state_counts": summary["state_counts"],
                "summary_file": manifest["summary_file"],
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Non-destructive history-cleanup helpers for commit-surface extraction, "
            "message-rewrite waves, and structural-prep artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_structural_subcommands(subparsers)

    derive_history_surface = subparsers.add_parser(
        "derive-history-surface",
        help="Dump raw history derivatives and compute per-commit diff-size metrics for one repository.",
    )
    derive_history_surface.add_argument(
        "--repo", default=".", help="Repository root containing the git history."
    )
    derive_history_surface.add_argument(
        "--branch", default="HEAD", help="Branch or revision range to inspect."
    )
    derive_history_surface.add_argument(
        "--after", help="Optional git log --after boundary."
    )
    derive_history_surface.add_argument(
        "--before", help="Optional git log --before boundary."
    )
    derive_history_surface.add_argument(
        "--out-dir",
        required=True,
        help="Directory where raw dumps and summaries will be written.",
    )
    derive_history_surface.add_argument(
        "--per-commit-overhead-tokens",
        type=int,
        default=80,
        help="Token overhead added per commit when simulating worker packet budgets.",
    )
    derive_history_surface.set_defaults(func=cmd_derive_history_surface)

    build_message_packets = subparsers.add_parser(
        "build-message-packets",
        help="Build prompt-ready rewrite packets with full owned diffs and message-only edge context.",
    )
    build_message_packets.add_argument(
        "--repo", default=".", help="Repository root containing the git history."
    )
    build_message_packets.add_argument(
        "--commit-surface-json", required=True, help="Path to commit-surface.json."
    )
    build_message_packets.add_argument(
        "--out-dir",
        required=True,
        help="Directory where packet materials will be written.",
    )
    build_message_packets.add_argument(
        "--window-profile",
        choices=tuple(sorted(WINDOW_PROFILES)),
        default="spark-128k",
        help="Packet sizing profile; explicit flag overrides still win.",
    )
    build_message_packets.add_argument(
        "--full-diff-budget-tokens",
        type=int,
        help="Target budget for normal full-diff packets; defaults from --window-profile.",
    )
    build_message_packets.add_argument(
        "--jumbo-threshold-tokens",
        type=int,
        help="Single-commit threshold above which a commit is chunked into jumbo sections; defaults from --window-profile.",
    )
    build_message_packets.add_argument(
        "--jumbo-chunk-budget-tokens",
        type=int,
        help="Target budget for each jumbo chunk; defaults from --window-profile.",
    )
    build_message_packets.add_argument(
        "--edge-context-commits",
        type=int,
        help="How many adjacent commit messages to include before and after each packet; defaults from --window-profile.",
    )
    build_message_packets.add_argument(
        "--max-commits-per-normal-packet",
        type=int,
        help="Optional hard cap on commit count per normal packet; defaults from --window-profile when provided there.",
    )
    build_message_packets.add_argument(
        "--per-commit-overhead-tokens",
        type=int,
        default=80,
        help="Token overhead added per commit during packet planning.",
    )
    build_message_packets.add_argument(
        "--unified", type=int, default=3, help="Unified diff context lines."
    )
    build_message_packets.add_argument(
        "--include-stat",
        action="store_true",
        help="Include --stat in packet patch files.",
    )
    build_message_packets.add_argument(
        "--exclude-sqlx",
        action="store_true",
        help="Exclude .sqlx/** from generated patch files.",
    )
    build_message_packets.set_defaults(func=cmd_build_message_packets)

    prepare_global_style_pass = subparsers.add_parser(
        "prepare-global-style-pass",
        help="Generate a repo-wide style-derivation corpus plus prompt/schema/run script for a wide-context worker.",
    )
    prepare_global_style_pass.add_argument(
        "--repo", default=".", help="Repository root containing the git history."
    )
    prepare_global_style_pass.add_argument(
        "--commit-surface-json", required=True, help="Path to commit-surface.json."
    )
    prepare_global_style_pass.add_argument(
        "--out-dir",
        required=True,
        help="Directory where style-pass materials will be written.",
    )
    prepare_global_style_pass.add_argument(
        "--window-profile",
        choices=tuple(sorted(WINDOW_PROFILES)),
        default="wide-1m-750k",
        help="Target packet profile the style guide should optimize for.",
    )
    prepare_global_style_pass.add_argument(
        "--max-commits",
        type=int,
        help="Optional cap on how many surface rows to include in the style corpus.",
    )
    prepare_global_style_pass.add_argument(
        "--model", default="", help="Optional model passed to codex exec."
    )
    prepare_global_style_pass.add_argument(
        "--reasoning-effort",
        default="xhigh",
        help="model_reasoning_effort override passed to codex exec.",
    )
    prepare_global_style_pass.add_argument(
        "--profile", help="Optional Codex profile name."
    )
    prepare_global_style_pass.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="read-only",
        help="Sandbox mode passed to codex exec.",
    )
    prepare_global_style_pass.add_argument(
        "--extra-add-dir",
        action="append",
        default=[],
        help="Additional readable directories to pass through to codex exec.",
    )
    prepare_global_style_pass.set_defaults(func=cmd_prepare_global_style_pass)

    message_quality_report = subparsers.add_parser(
        "message-quality-report",
        help="Score commit messages against the commit-message contract and flag thin/vague outputs.",
    )
    message_quality_report.add_argument(
        "--input-json",
        required=True,
        help="Input JSON containing current/proposed/rewritten messages.",
    )
    message_quality_report.add_argument(
        "--message-source",
        choices=("auto", "current", "proposed", "rewritten"),
        default="auto",
        help="Which message field set to score.",
    )
    message_quality_report.add_argument(
        "--output-json", help="Optional output path for per-row quality results."
    )
    message_quality_report.add_argument(
        "--output-csv", help="Optional CSV projection of the quality results."
    )
    message_quality_report.add_argument(
        "--summary-json", help="Optional output path for summary metrics."
    )
    message_quality_report.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="How many low-quality rows to retain in the summary.",
    )
    message_quality_report.set_defaults(func=cmd_message_quality_report)

    prepare_packet_exec = subparsers.add_parser(
        "prepare-packet-exec",
        help="Generate prompt/schema/request files plus a runnable Codex exec manifest for message packets.",
    )
    prepare_packet_exec.add_argument(
        "--packet-index", required=True, help="Path to message-packets/index.json."
    )
    prepare_packet_exec.add_argument(
        "--out-dir",
        required=True,
        help="Directory where execution materials will be written.",
    )
    prepare_packet_exec.add_argument(
        "--model", default="gpt-5.6-terra", help="Model passed to codex exec."
    )
    prepare_packet_exec.add_argument(
        "--reasoning-effort",
        default="xhigh",
        help="model_reasoning_effort override passed to codex exec.",
    )
    prepare_packet_exec.add_argument("--profile", help="Optional Codex profile name.")
    prepare_packet_exec.add_argument(
        "--style-guide-file",
        help="Optional derived repo-wide style guide JSON to include in every packet prompt.",
    )
    prepare_packet_exec.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="read-only",
        help="Sandbox mode passed to codex exec.",
    )
    prepare_packet_exec.add_argument(
        "--extra-add-dir",
        action="append",
        default=[],
        help="Additional readable directories to pass through to codex exec.",
    )
    prepare_packet_exec.set_defaults(func=cmd_prepare_packet_exec)

    packet_exec_status = subparsers.add_parser(
        "packet-exec-status",
        help="Summarize prepared packet-exec state across pending/running/completed/failed packets.",
    )
    packet_exec_status.add_argument(
        "--manifest", required=True, help="Path to packet-exec manifest.json."
    )
    packet_exec_status.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of text.",
    )
    packet_exec_status.add_argument(
        "--show-rows", action="store_true", help="Include one text row per packet."
    )
    packet_exec_status.set_defaults(func=cmd_packet_exec_status)

    run_packet_exec = subparsers.add_parser(
        "run-packet-exec",
        help="Run prepared packet exec jobs via codex exec and record per-packet status/proposal outputs.",
    )
    run_packet_exec.add_argument(
        "--manifest", required=True, help="Path to packet-exec manifest.json."
    )
    run_packet_exec.add_argument(
        "--jobs", type=int, default=1, help="Maximum concurrent codex exec processes."
    )
    run_packet_exec.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of packets to run this invocation.",
    )
    run_packet_exec.add_argument(
        "--packet-id", action="append", help="Optional packet id to run; repeatable."
    )
    run_packet_exec.add_argument(
        "--retry-failed", action="store_true", help="Also retry failed/invalid packets."
    )
    run_packet_exec.set_defaults(func=cmd_run_packet_exec)

    prepare_wave = subparsers.add_parser(
        "prepare-wave",
        help="Create a wave manifest and range input files from live git history.",
    )
    prepare_wave.add_argument(
        "--repo", default=".", help="Repository root containing the git history."
    )
    prepare_wave.add_argument(
        "--output-dir",
        required=True,
        help="Directory where manifest and range input files will be written.",
    )
    prepare_wave.add_argument(
        "--wave-name",
        required=True,
        help="Human name for the wave, written into manifest.json.",
    )
    prepare_wave.add_argument(
        "--start-index",
        type=int,
        required=True,
        help="1-based history index from HEAD where the wave starts.",
    )
    prepare_wave.add_argument(
        "--count",
        type=int,
        required=True,
        help="Number of consecutive commits to include.",
    )
    prepare_wave.add_argument(
        "--owned-size", type=int, required=True, help="Owned commit count per range."
    )
    prepare_wave.add_argument(
        "--overlap", type=int, required=True, help="Context overlap on each side."
    )
    prepare_wave.add_argument(
        "--include-surface",
        action="store_true",
        help="Enrich input rows with cheap git-show surface metadata (semantic/sqlx churn, scope, areas, paths).",
    )
    prepare_wave.add_argument(
        "--index-field",
        default="selection_index",
        help="Field name to use for range-local sequential indexing.",
    )
    prepare_wave.set_defaults(func=cmd_prepare_wave)

    wave_status = subparsers.add_parser(
        "wave-status", help="Report which range outputs exist for a wave manifest."
    )
    wave_status.add_argument("--manifest", required=True, help="Path to manifest.json.")
    wave_status.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of text.",
    )
    wave_status.set_defaults(func=cmd_wave_status)

    normalize_wave = subparsers.add_parser(
        "normalize-wave",
        help="Normalize raw worker proposal files into a canonical corpus.",
    )
    normalize_wave.add_argument(
        "--manifest", required=True, help="Path to manifest.json."
    )
    normalize_wave.add_argument("--output-json", help="Canonical JSON output path.")
    normalize_wave.add_argument("--output-csv", help="Canonical CSV output path.")
    normalize_wave.add_argument("--summary-json", help="Summary JSON output path.")
    normalize_wave.set_defaults(func=cmd_normalize_wave)

    finalize_message_wave = subparsers.add_parser(
        "finalize-message-wave",
        help="Resolve duplicate batch outputs, verify complete thin-corpus coverage, and emit a canonical rewrite map.",
    )
    finalize_message_wave.add_argument(
        "--thin-corpus", required=True, help="Path to the thin-commit-corpus.json file."
    )
    finalize_message_wave.add_argument(
        "--proposals-dir",
        required=True,
        help="Directory containing per-batch proposal JSON files.",
    )
    finalize_message_wave.add_argument(
        "--canonical-json",
        required=True,
        help="Output path for the canonical merged proposal corpus.",
    )
    finalize_message_wave.add_argument(
        "--canonical-csv",
        help="Optional CSV projection of the canonical merged corpus.",
    )
    finalize_message_wave.add_argument(
        "--duplicate-resolution-json",
        help="Optional output path for duplicate-batch resolution details.",
    )
    finalize_message_wave.add_argument(
        "--rewrite-map-json",
        required=True,
        help="Output path for the finalized rewrite map.",
    )
    finalize_message_wave.add_argument(
        "--summary-json", help="Optional output path for the finalization summary JSON."
    )
    finalize_message_wave.set_defaults(func=cmd_finalize_message_wave)

    build_rewrite_map = subparsers.add_parser(
        "build-rewrite-map",
        help="Turn canonical proposals into a machine-usable rewrite map.",
    )
    build_rewrite_map.add_argument(
        "--proposals", required=True, help="Canonical proposal JSON path."
    )
    build_rewrite_map.add_argument(
        "--output-json", required=True, help="Rewrite-map JSON output path."
    )
    build_rewrite_map.add_argument(
        "--output-csv", help="Optional CSV projection of the rewrite map."
    )
    build_rewrite_map.add_argument("--summary-json", help="Optional JSON summary path.")
    build_rewrite_map.add_argument(
        "--only-strict",
        action="store_true",
        help="Emit only rows with strict_process_attested=true.",
    )
    build_rewrite_map.add_argument(
        "--require-review-complete",
        action="store_true",
        help="Skip rows that still declare remaining_review_required=true.",
    )
    build_rewrite_map.set_defaults(func=cmd_build_rewrite_map)

    analyze_series = subparsers.add_parser(
        "analyze-series",
        help="Analyze a consecutive history band for split, merge, and reorder candidates.",
    )
    analyze_series.add_argument(
        "--repo", default=".", help="Repository root containing the git history."
    )
    analyze_series.add_argument(
        "--start-index",
        type=int,
        required=True,
        help="1-based history index from HEAD where analysis starts.",
    )
    analyze_series.add_argument(
        "--count",
        type=int,
        required=True,
        help="Number of consecutive commits to analyze.",
    )
    analyze_series.add_argument(
        "--split-files-threshold",
        type=int,
        default=80,
        help="Mark commits touching at least this many files as split candidates.",
    )
    analyze_series.add_argument(
        "--split-areas-threshold",
        type=int,
        default=5,
        help="Mark commits touching at least this many top-level areas as split candidates.",
    )
    analyze_series.add_argument(
        "--split-churn-threshold",
        type=int,
        default=3000,
        help="Mark commits with at least this total line churn as split candidates.",
    )
    analyze_series.add_argument(
        "--merge-min-score",
        type=int,
        default=2,
        help="Minimum adjacency score required to keep commits in the same merge cluster.",
    )
    analyze_series.add_argument(
        "--output-json", help="Optional path for the full analysis JSON."
    )
    analyze_series.add_argument(
        "--summary-json", help="Optional path for the compact summary JSON."
    )
    analyze_series.set_defaults(func=cmd_analyze_series)

    scaffold_split = subparsers.add_parser(
        "scaffold-split",
        help="Summarize one commit into file-group scaffolds for future split work.",
    )
    scaffold_split.add_argument(
        "--repo", default=".", help="Repository root containing the git history."
    )
    scaffold_split.add_argument(
        "--sha", required=True, help="Commit SHA to scaffold for splitting."
    )
    scaffold_split.add_argument(
        "--prefix-depth",
        type=int,
        default=2,
        help="How many path segments to include in prefix grouping.",
    )
    scaffold_split.add_argument(
        "--output-json", help="Optional path for the split scaffold JSON."
    )
    scaffold_split.set_defaults(func=cmd_scaffold_split)

    review_bundles = subparsers.add_parser(
        "build-review-bundles",
        help="Create sliding adjacent-commit review bundles with filtered patch files for one range input.",
    )
    review_bundles.add_argument(
        "--repo", default=".", help="Repository root containing the git history."
    )
    review_bundles.add_argument(
        "--range-input", required=True, help="Path to a range-XX-input.json file."
    )
    review_bundles.add_argument(
        "--output-dir",
        required=True,
        help="Directory where bundle files will be written.",
    )
    review_bundles.add_argument(
        "--window-size",
        type=int,
        default=4,
        help="Number of consecutive commits per bundle.",
    )
    review_bundles.add_argument(
        "--slide",
        type=int,
        default=3,
        help="How many commits to advance between bundles.",
    )
    review_bundles.add_argument(
        "--unified", type=int, default=3, help="Unified diff context lines."
    )
    review_bundles.add_argument(
        "--include-stat",
        action="store_true",
        help="Include --stat output in the generated patch files.",
    )
    review_bundles.add_argument(
        "--exclude-sqlx",
        action="store_true",
        help="Exclude .sqlx/** from generated patch files.",
    )
    review_bundles.add_argument(
        "--include-path",
        action="append",
        default=[],
        help="Optional positive pathspec to keep in generated patches. Repeatable.",
    )
    review_bundles.add_argument(
        "--exclude-path",
        action="append",
        default=[],
        help="Optional pathspec to exclude from generated patches. Repeatable; raw values become :(exclude)<value> unless already a pathspec.",
    )
    review_bundles.set_defaults(func=cmd_build_review_bundles)

    emit_rebase_todo = subparsers.add_parser(
        "emit-rebase-todo",
        help="Compile a simple JSON rebase plan into a git-rebase todo file.",
    )
    emit_rebase_todo.add_argument(
        "--plan-json", required=True, help="Plan JSON containing an operations array."
    )
    emit_rebase_todo.add_argument(
        "--output",
        required=True,
        help="Output path for the generated rebase todo file.",
    )
    emit_rebase_todo.add_argument(
        "--repo",
        help="Optional repository root used to look up missing subjects for comments.",
    )
    emit_rebase_todo.set_defaults(func=cmd_emit_rebase_todo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
