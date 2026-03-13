#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from structural import register_structural_subcommands

def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


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
    if "patch" in lowered and "context" in lowered and ("behavior" in lowered or "reason" in lowered):
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
            raise ValueError(f"unexpected git log record at selection index {selection_index}")
        sha, author_date_iso, author_name, author_email, committer_name, committer_email, current_subject, current_message = parts[:8]
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
    tokens = [slugify(token) for token in re.split(r"[, ]+", normalized) if token.strip()]
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


def commit_rows_with_surface(repo: Path, start_index: int, count: int) -> list[dict[str, Any]]:
    rows = iter_git_commits(repo, start_index=start_index, count=count)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        surface = collect_commit_surface(repo, row["sha"])
        enriched.append({**row, **surface})
    return enriched


def split_candidate_reasons(row: dict[str, Any], files_threshold: int, areas_threshold: int, churn_threshold: int) -> list[str]:
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
    return len(set(left.get("semantic_top_level_areas") or []) & set(right.get("semantic_top_level_areas") or []))


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
    if any(token in (right.get("subject") or "").lower() for token in ("fix", "follow-up", "followup", "leftover", "remaining", "docs", "test")):
        score += 1
    return score


def reorder_reason(left: dict[str, Any], right: dict[str, Any]) -> str | None:
    left_subject = (left.get("subject") or "").lower()
    right_subject = (right.get("subject") or "").lower()
    if any(token in left_subject for token in ("remove", "drop")) and any(token in right_subject for token in ("restore", "reintroduce", "bring back")):
        return "remove_then_restore"
    if any(token in right_subject for token in ("leftover", "remaining", "follow-up", "followup")) and (scopes_overlap(left, right) or shared_area_count(left, right) >= 1):
        return "followup_leftovers_after_primary_change"
    if any(token in right_subject for token in ("docs", "test")) and (scopes_overlap(left, right) or shared_area_count(left, right) >= 1):
        return "docs_or_tests_interleaved_with_same_scope_change"
    return None


def cmd_analyze_series(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    rows = commit_rows_with_surface(repo, start_index=args.start_index, count=args.count)
    split_candidates: list[dict[str, Any]] = []
    merge_clusters: list[dict[str, Any]] = []
    reorder_candidates: list[dict[str, Any]] = []
    for row in rows:
        reasons = split_candidate_reasons(row, args.split_files_threshold, args.split_areas_threshold, args.split_churn_threshold)
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
                    "semantic_top_level_area_count": row["semantic_top_level_area_count"],
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
                    "areas_union": sorted({area for item in active_cluster for area in item.get("semantic_top_level_areas") or []}),
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
                    "areas_union": sorted({area for item in active_cluster for area in item.get("semantic_top_level_areas") or []}),
                    "subjects": [item["subject"] for item in active_cluster],
                    "shas": [item["sha"] for item in active_cluster],
                }
        )
    for left, right in zip(rows, rows[1:]):
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
    child_line = git_optional(repo, "rev-list", "--children", "-n", "1", args.sha).strip()
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
        by_area.setdefault(area, {"group": area, "files": [], "insertions": 0, "deletions": 0})
        by_area[area]["files"].append(path)
        by_area[area]["insertions"] += insertions
        by_area[area]["deletions"] += deletions
        by_prefix.setdefault(prefix, {"group": prefix, "files": [], "insertions": 0, "deletions": 0})
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
        "groups_by_top_level_area": sorted(by_area.values(), key=lambda item: (-len(item["files"]), item["group"])),
        "groups_by_prefix": sorted(by_prefix.values(), key=lambda item: (-len(item["files"]), item["group"])),
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


VALID_REBASE_ACTIONS = {"pick", "reword", "edit", "squash", "fixup", "drop", "break", "exec", "label", "reset", "merge"}


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
    print(json.dumps({"operations": len(operations), "output": str(output_path)}, indent=2))
    return 0


def range_rows_from_input(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
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
        owned_window_rows = [row for row in window_rows if owned_start <= row.get("selection_index", 0) <= owned_end]
        summary = {
            "bundle_id": bundle_id,
            "window_size": len(window_rows),
            "requested_window_size": args.window_size,
            "slide": args.slide,
            "exclude_sqlx": args.exclude_sqlx,
            "selection_index_range": [window_rows[0].get("selection_index"), window_rows[-1].get("selection_index")],
            "history_index_range": [window_rows[0].get("history_index_from_head"), window_rows[-1].get("history_index_from_head")],
            "owned_selection_index_range": [owned_start, owned_end],
            "owned_commits_in_window": [row.get("selection_index") for row in owned_window_rows],
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
    print(json.dumps({"bundle_count": len(bundles), "output_dir": str(output_dir)}, indent=2))
    return 0


def build_ranges(rows: list[dict[str, Any]], owned_size: int, overlap: int) -> list[dict[str, Any]]:
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
        rows = commit_rows_with_surface(repo, start_index=args.start_index, count=args.count)
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
    print(json.dumps({"status": "ok", "wave": args.wave_name, "ranges": len(manifest_ranges), "output_dir": str(output_dir)}, indent=2))
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
    return {row["sha"]: row for row in owned_rows if isinstance(row, dict) and row.get("sha")}


def normalize_proposal_row(row: dict[str, Any], base: dict[str, Any], range_id: str) -> dict[str, Any]:
    sha = row.get("sha") or row.get("after_sha") or base.get("sha")
    if not sha:
        raise ValueError(f"proposal row in {range_id} missing sha/after_sha")
    full_patch_confirmed = row.get("effective_full_patch_confirmed", row.get("full_patch_confirmed"))
    strict_process_attested = row.get("effective_strict_process_attested", row.get("strict_process_attested"))
    full_patch_bool = parse_boolish(full_patch_confirmed)
    strict_bool = parse_boolish(strict_process_attested)
    surrounding_raw = row.get("normalized_surrounding_context_label", row.get("surrounding_context_used"))
    surrounding_used, surrounding_label = normalize_surrounding_context(surrounding_raw)
    why_raw = row.get("normalized_why_basis", row.get("why_basis_recorded"))
    why_basis = normalize_why_basis(why_raw)
    notes = row.get("notes") or row.get("main_agent_notes")
    if strict_bool:
        review_status = "complete_strict"
        remaining_review_required = False
    elif full_patch_bool or surrounding_used or why_basis != "not_recorded" or bool(notes):
        review_status = "complete_conservative"
        remaining_review_required = False
    else:
        review_status = "needs_review"
        remaining_review_required = True
    normalized = {
        "range_id": range_id,
        "history_index_from_head": base.get("history_index_from_head") or row.get("history_index_from_head"),
        "selection_index": base.get("selection_index") or base.get("wave2_index") or row.get("selection_index") or row.get("wave2_index") or row.get("global_index"),
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
                normalized_rows.append(normalize_proposal_row(proposal_row, base_map.get(proposal_row.get("sha") or proposal_row.get("after_sha"), {}), range_id))
        except Exception as exc:
            bad_ranges.append({"range_id": range_id, "error": str(exc)})
    normalized_rows.sort(key=lambda row: (row.get("selection_index") is None, row.get("selection_index") or 0, row["sha"]))
    summary = {
        "wave": manifest.get("wave"),
        "manifest": str(manifest_path),
        "rows": len(normalized_rows),
        "ranges_total": len(manifest["ranges"]),
        "missing_ranges": missing_ranges,
        "bad_ranges": bad_ranges,
        "strict_rows": sum(1 for row in normalized_rows if row["strict_process_attested"] is True),
        "conservative_rows": sum(1 for row in normalized_rows if row["review_status"] == "complete_conservative"),
        "needs_review_rows": sum(1 for row in normalized_rows if row["remaining_review_required"]),
        "claude_trailers": sum(1 for row in normalized_rows if row.get("proposed_trailer") == "Co-Authored-By: Claude <noreply@anthropic.com>"),
        "codex_trailers": sum(1 for row in normalized_rows if row.get("proposed_trailer") == "Co-Authored-By: Codex <codex@openai.com>"),
        "rows_without_trailer": sum(1 for row in normalized_rows if not row.get("proposed_trailer")),
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


def choose_best_batch_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    def score(candidate: dict[str, Any]) -> tuple[Any, ...]:
        counts = [body_word_count(item.get("proposed_body")) for item in candidate["items"]]
        avg = sum(counts) / len(counts) if counts else 0.0
        return (
            sum(1 for item in candidate["items"] if item.get("full_patch_confirmed")),
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
    expected_index_by_sha = {normalize_commit_sha(commit["sha"]): commit["index"] for commit in expected_commits}

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
                                [body_word_count(item.get("proposed_body")) for item in candidate["items"]]
                            ),
                            "body_word_total": sum(body_word_count(item.get("proposed_body")) for item in candidate["items"]),
                        }
                        for candidate in candidates
                    ],
                }
            )
        for item in chosen["items"]:
            canonical_rows.append(
                {
                    "batch_id": batch_id,
                    "proposal_file": chosen["proposal_file"],
                    "agent": chosen["agent"],
                    **item,
                    "rewritten_message": build_message_from_subject_body(item["proposed_subject"], item["proposed_body"]),
                }
            )

    canonical_shas = [row["sha"] for row in canonical_rows]
    duplicate_shas = sorted({sha for sha in canonical_shas if canonical_shas.count(sha) > 1})
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
            skipped_rows.append({"sha": row.get("sha") or row.get("after_sha"), "reason": "not_strict"})
            continue
        if args.require_review_complete and review_required:
            skipped_rows.append({"sha": row.get("sha") or row.get("after_sha"), "reason": "review_required"})
            continue
        sha = row.get("sha") or row.get("after_sha")
        proposed_message = row.get("proposed_message")
        if not sha or not proposed_message:
            skipped_rows.append({"sha": sha, "reason": "missing_sha_or_message"})
            continue
        rewrite_rows.append(
            {
                "sha": sha,
                "current_message": row.get("current_message") or row.get("after_message"),
                "rewritten_message": compose_message(proposed_message, row.get("proposed_trailer")),
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
        write_json(Path(args.summary_json).resolve(), {"summary": summary, "skipped": skipped_rows})
    print(json.dumps(summary, indent=2))
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

    prepare_wave = subparsers.add_parser("prepare-wave", help="Create a wave manifest and range input files from live git history.")
    prepare_wave.add_argument("--repo", default=".", help="Repository root containing the git history.")
    prepare_wave.add_argument("--output-dir", required=True, help="Directory where manifest and range input files will be written.")
    prepare_wave.add_argument("--wave-name", required=True, help="Human name for the wave, written into manifest.json.")
    prepare_wave.add_argument("--start-index", type=int, required=True, help="1-based history index from HEAD where the wave starts.")
    prepare_wave.add_argument("--count", type=int, required=True, help="Number of consecutive commits to include.")
    prepare_wave.add_argument("--owned-size", type=int, required=True, help="Owned commit count per range.")
    prepare_wave.add_argument("--overlap", type=int, required=True, help="Context overlap on each side.")
    prepare_wave.add_argument(
        "--include-surface",
        action="store_true",
        help="Enrich input rows with cheap git-show surface metadata (semantic/sqlx churn, scope, areas, paths).",
    )
    prepare_wave.add_argument("--index-field", default="selection_index", help="Field name to use for range-local sequential indexing.")
    prepare_wave.set_defaults(func=cmd_prepare_wave)

    wave_status = subparsers.add_parser("wave-status", help="Report which range outputs exist for a wave manifest.")
    wave_status.add_argument("--manifest", required=True, help="Path to manifest.json.")
    wave_status.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of text.")
    wave_status.set_defaults(func=cmd_wave_status)

    normalize_wave = subparsers.add_parser("normalize-wave", help="Normalize raw worker proposal files into a canonical corpus.")
    normalize_wave.add_argument("--manifest", required=True, help="Path to manifest.json.")
    normalize_wave.add_argument("--output-json", help="Canonical JSON output path.")
    normalize_wave.add_argument("--output-csv", help="Canonical CSV output path.")
    normalize_wave.add_argument("--summary-json", help="Summary JSON output path.")
    normalize_wave.set_defaults(func=cmd_normalize_wave)

    finalize_message_wave = subparsers.add_parser(
        "finalize-message-wave",
        help="Resolve duplicate batch outputs, verify complete thin-corpus coverage, and emit a canonical rewrite map.",
    )
    finalize_message_wave.add_argument("--thin-corpus", required=True, help="Path to the thin-commit-corpus.json file.")
    finalize_message_wave.add_argument("--proposals-dir", required=True, help="Directory containing per-batch proposal JSON files.")
    finalize_message_wave.add_argument("--canonical-json", required=True, help="Output path for the canonical merged proposal corpus.")
    finalize_message_wave.add_argument("--canonical-csv", help="Optional CSV projection of the canonical merged corpus.")
    finalize_message_wave.add_argument("--duplicate-resolution-json", help="Optional output path for duplicate-batch resolution details.")
    finalize_message_wave.add_argument("--rewrite-map-json", required=True, help="Output path for the finalized rewrite map.")
    finalize_message_wave.add_argument("--summary-json", help="Optional output path for the finalization summary JSON.")
    finalize_message_wave.set_defaults(func=cmd_finalize_message_wave)

    build_rewrite_map = subparsers.add_parser("build-rewrite-map", help="Turn canonical proposals into a machine-usable rewrite map.")
    build_rewrite_map.add_argument("--proposals", required=True, help="Canonical proposal JSON path.")
    build_rewrite_map.add_argument("--output-json", required=True, help="Rewrite-map JSON output path.")
    build_rewrite_map.add_argument("--output-csv", help="Optional CSV projection of the rewrite map.")
    build_rewrite_map.add_argument("--summary-json", help="Optional JSON summary path.")
    build_rewrite_map.add_argument("--only-strict", action="store_true", help="Emit only rows with strict_process_attested=true.")
    build_rewrite_map.add_argument("--require-review-complete", action="store_true", help="Skip rows that still declare remaining_review_required=true.")
    build_rewrite_map.set_defaults(func=cmd_build_rewrite_map)

    analyze_series = subparsers.add_parser("analyze-series", help="Analyze a consecutive history band for split, merge, and reorder candidates.")
    analyze_series.add_argument("--repo", default=".", help="Repository root containing the git history.")
    analyze_series.add_argument("--start-index", type=int, required=True, help="1-based history index from HEAD where analysis starts.")
    analyze_series.add_argument("--count", type=int, required=True, help="Number of consecutive commits to analyze.")
    analyze_series.add_argument("--split-files-threshold", type=int, default=80, help="Mark commits touching at least this many files as split candidates.")
    analyze_series.add_argument("--split-areas-threshold", type=int, default=5, help="Mark commits touching at least this many top-level areas as split candidates.")
    analyze_series.add_argument("--split-churn-threshold", type=int, default=3000, help="Mark commits with at least this total line churn as split candidates.")
    analyze_series.add_argument("--merge-min-score", type=int, default=2, help="Minimum adjacency score required to keep commits in the same merge cluster.")
    analyze_series.add_argument("--output-json", help="Optional path for the full analysis JSON.")
    analyze_series.add_argument("--summary-json", help="Optional path for the compact summary JSON.")
    analyze_series.set_defaults(func=cmd_analyze_series)

    scaffold_split = subparsers.add_parser("scaffold-split", help="Summarize one commit into file-group scaffolds for future split work.")
    scaffold_split.add_argument("--repo", default=".", help="Repository root containing the git history.")
    scaffold_split.add_argument("--sha", required=True, help="Commit SHA to scaffold for splitting.")
    scaffold_split.add_argument("--prefix-depth", type=int, default=2, help="How many path segments to include in prefix grouping.")
    scaffold_split.add_argument("--output-json", help="Optional path for the split scaffold JSON.")
    scaffold_split.set_defaults(func=cmd_scaffold_split)

    review_bundles = subparsers.add_parser(
        "build-review-bundles",
        help="Create sliding adjacent-commit review bundles with filtered patch files for one range input.",
    )
    review_bundles.add_argument("--repo", default=".", help="Repository root containing the git history.")
    review_bundles.add_argument("--range-input", required=True, help="Path to a range-XX-input.json file.")
    review_bundles.add_argument("--output-dir", required=True, help="Directory where bundle files will be written.")
    review_bundles.add_argument("--window-size", type=int, default=4, help="Number of consecutive commits per bundle.")
    review_bundles.add_argument("--slide", type=int, default=3, help="How many commits to advance between bundles.")
    review_bundles.add_argument("--unified", type=int, default=3, help="Unified diff context lines.")
    review_bundles.add_argument("--include-stat", action="store_true", help="Include --stat output in the generated patch files.")
    review_bundles.add_argument("--exclude-sqlx", action="store_true", help="Exclude .sqlx/** from generated patch files.")
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

    emit_rebase_todo = subparsers.add_parser("emit-rebase-todo", help="Compile a simple JSON rebase plan into a git-rebase todo file.")
    emit_rebase_todo.add_argument("--plan-json", required=True, help="Plan JSON containing an operations array.")
    emit_rebase_todo.add_argument("--output", required=True, help="Output path for the generated rebase todo file.")
    emit_rebase_todo.add_argument("--repo", help="Optional repository root used to look up missing subjects for comments.")
    emit_rebase_todo.set_defaults(func=cmd_emit_rebase_todo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
