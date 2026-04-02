from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=False) + "\n")


def iso_now() -> str:
    return datetime.now().astimezone().isoformat()


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).resolve()


def emit_journal_event(kind: str, **payload: Any) -> None:
    path = env_path("LYNCHPIN_HISTORY_JOURNAL_JSONL")
    if not path:
        return
    append_jsonl(path, {"timestamp": iso_now(), "kind": kind, **payload})


def emit_conflict_ledger_entry(**payload: Any) -> None:
    path = env_path("LYNCHPIN_HISTORY_CONFLICT_LEDGER_JSONL")
    if not path:
        return
    append_jsonl(path, {"timestamp": iso_now(), **payload})


def git(
    repo: Path,
    *args: str,
    text: bool = True,
    check: bool = True,
    input_data: str | bytes | None = None,
) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        text=text,
        input=input_data,
        capture_output=True,
    )


def git_stdout(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout


def git_optional_stdout(repo: Path, *args: str) -> str:
    result = git(repo, *args, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout


def git_bytes(repo: Path, *args: str) -> bytes:
    result = git(repo, *args, text=False)
    return result.stdout


def normalize_glob_lists(
    paths: list[str] | None = None, globs: list[str] | None = None
) -> tuple[list[str], list[str]]:
    literal_paths: list[str] = []
    glob_paths: list[str] = []
    seen: set[tuple[str, str]] = set()
    for raw in expand_diffstat_paths(paths or []):
        if not raw:
            continue
        if any(token in raw for token in ("*", "?", "[")):
            key = ("glob", raw)
            if key not in seen:
                seen.add(key)
                glob_paths.append(raw)
        else:
            key = ("path", raw)
            if key not in seen:
                seen.add(key)
                literal_paths.append(raw)
    for raw in globs or []:
        if not raw:
            continue
        key = ("glob", raw)
        if key not in seen:
            seen.add(key)
            glob_paths.append(raw)
    return literal_paths, glob_paths


BRACE_RENAME_RE = re.compile(
    r"^(?P<prefix>.*)\{(?P<old>[^{}]*) => (?P<new>[^{}]*)\}(?P<suffix>.*)$"
)


def expand_diffstat_path(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []
    brace_match = BRACE_RENAME_RE.match(raw)
    if brace_match:
        prefix = brace_match.group("prefix")
        old_part = brace_match.group("old")
        new_part = brace_match.group("new")
        suffix = brace_match.group("suffix")
        return [
            prefix + old_part + suffix,
            prefix + new_part + suffix,
        ]
    if " => " in raw and "{" not in raw and "}" not in raw:
        old_path, new_path = raw.split(" => ", 1)
        return [old_path.strip(), new_path.strip()]
    return [raw]


def expand_diffstat_paths(paths: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        for candidate in expand_diffstat_path(raw):
            if candidate and candidate not in seen:
                seen.add(candidate)
                expanded.append(candidate)
    return expanded


def pathspec_from_include(path: str) -> str:
    if any(token in path for token in ("*", "?", "[")):
        return f":(glob){path}"
    return path


def pathspec_from_exclude(path: str) -> str:
    if path.startswith(":("):
        return path
    if any(token in path for token in ("*", "?", "[")):
        return f":(exclude,glob){path}"
    return f":(exclude){path}"


def commit_meta(repo: Path, sha: str) -> dict[str, Any]:
    fmt = "%H%x00%P%x00%an%x00%ae%x00%aI%x00%cN%x00%cE%x00%cI%x00%B"
    raw = git_stdout(repo, "show", "-s", f"--format={fmt}", sha)
    parts = raw.split("\x00")
    if len(parts) < 9:
        raise ValueError(f"unexpected git show output for {sha}")
    (
        commit_sha,
        parents,
        author_name,
        author_email,
        author_date_iso,
        committer_name,
        committer_email,
        committer_date_iso,
        message,
    ) = parts[:9]
    return {
        "sha": commit_sha.strip(),
        "parent_sha": (parents.strip().split()[0] if parents.strip() else None),
        "author_name": author_name.strip(),
        "author_email": author_email.strip(),
        "author_date_iso": author_date_iso.strip(),
        "committer_name": committer_name.strip(),
        "committer_email": committer_email.strip(),
        "committer_date_iso": committer_date_iso.strip(),
        "message": message.rstrip("\n"),
    }


def commit_identity_fingerprint(meta: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(meta["author_name"]),
        str(meta["author_email"]),
        str(meta["author_date_iso"]),
        str(meta["message"]),
    )


def recent_rebase_done_pick_shas(repo: Path, count: int) -> list[str]:
    done_path = repo / ".git" / "rebase-merge" / "done"
    if count <= 0 or not done_path.exists():
        return []
    picks: list[str] = []
    for raw_line in reversed(done_path.read_text().splitlines()):
        line = raw_line.strip()
        if not line.startswith("pick "):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) >= 2:
            picks.append(git_stdout(repo, "rev-parse", parts[1].strip()).strip())
        if len(picks) >= count:
            break
    return list(reversed(picks))


def operation_is_empty_band_noop(operation: dict[str, Any]) -> bool:
    source_indices = {
        int(value) for value in operation.get("source_band_selection_indices") or []
    }
    if not source_indices:
        return False
    for child in operation.get("target_commits", []):
        units = child.get("units") or []
        if not units:
            return False
        for unit in units:
            if unit.get("kind") != "whole_selection":
                return False
            if int(unit.get("selection_index")) not in source_indices:
                return False
    return True


def head_order(repo: Path, ref: str = "HEAD") -> tuple[list[str], dict[str, int]]:
    shas = [
        line.strip()
        for line in git_stdout(
            repo, "rev-list", "--reverse", "--topo-order", ref
        ).splitlines()
        if line.strip()
    ]
    return shas, {sha: index for index, sha in enumerate(shas, 1)}


def parse_datetime_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def iso_add_seconds(value: str, seconds: int) -> str:
    return (parse_datetime_iso(value) + timedelta(seconds=seconds)).isoformat()


def compose_message(
    subject: str | None, message: str | None, body_lines: list[str] | None = None
) -> str:
    if message and message.strip():
        return message.rstrip() + "\n"
    if not subject:
        raise ValueError("cannot compose commit message without subject or message")
    body = "\n".join((body_lines or [])).strip()
    if body:
        return f"{subject.strip()}\n\n{body}\n"
    return subject.strip() + "\n"


def selection_maps_from_launch_pack(launch_pack_dir: Path) -> dict[str, dict[int, str]]:
    maps_dir = launch_pack_dir / "translated-selection-maps"
    result: dict[str, dict[int, str]] = {}
    for path in sorted(maps_dir.glob("*.json")):
        rows = load_json(path)
        namespace = path.stem
        mapping: dict[int, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            index = row.get("selection_index")
            rewritten_sha = row.get("rewritten_sha")
            current_sha = row.get("current_sha")
            if isinstance(index, int) and isinstance(rewritten_sha, str):
                mapping[index] = rewritten_sha
            elif isinstance(index, int) and isinstance(current_sha, str):
                mapping[index] = current_sha
        result[namespace] = mapping
    return result


def discover_default_inputs(launch_pack_dir: Path) -> dict[str, Any]:
    return {
        "primary_packs": [
            launch_pack_dir
            / "agent-work"
            / "wave4-final"
            / "current-executable-pack.json",
            launch_pack_dir
            / "agent-work"
            / "final-residue"
            / "wave2-manual-executable-specs.json",
            launch_pack_dir
            / "agent-work"
            / "final-residue"
            / "older-manual-residue.json",
        ],
        "fallback_packs": [
            launch_pack_dir / "deterministic-wave2-execution-plan.json",
            launch_pack_dir
            / "agent-work"
            / "first738-splits"
            / "deterministic-split-proposal.json",
            launch_pack_dir
            / "agent-work"
            / "final-residue"
            / "wave3-deterministic-split-proposal.json",
        ],
        "supersession_files": [
            launch_pack_dir / "agent-work" / "wave4-final" / "supersessions.json",
        ],
    }


def load_specs(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, dict):
        if isinstance(payload.get("specs"), list):
            return [item for item in payload["specs"] if isinstance(item, dict)]
        for key in ("items", "operations"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    raise ValueError(f"unsupported spec container in {path}")


def superseded_ids(paths: list[Path]) -> tuple[set[str], dict[str, str]]:
    ids: set[str] = set()
    reasons: dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        payload = load_json(path)
        for row in (
            payload.get("supersessions", []) if isinstance(payload, dict) else []
        ):
            spec_id = row.get("spec_id")
            if not isinstance(spec_id, str):
                continue
            ids.add(spec_id)
            reasons[spec_id] = row.get("reason") or f"superseded via {path.name}"
    return ids, reasons


def expand_scaffold_assignment(
    assignment: dict[str, Any], scaffold_path: Path | None
) -> tuple[list[str], list[str], list[str]]:
    include_paths = list(assignment.get("include_paths") or [])
    exclude_paths: list[str] = []
    if not scaffold_path or not scaffold_path.exists():
        literals, globs = normalize_glob_lists(include_paths, [])
        return literals, globs, exclude_paths
    scaffold = load_json(scaffold_path)
    grouped_files: set[str] = set()
    groups_by_collection: dict[str, dict[str, list[str]]] = {}
    for collection_name in ("groups_by_top_level_area", "groups_by_prefix"):
        collection_rows = scaffold.get(collection_name) or []
        lookup: dict[str, list[str]] = {}
        for row in collection_rows:
            if not isinstance(row, dict):
                continue
            group = row.get("group")
            files = row.get("files") or []
            if isinstance(group, str):
                lookup[group] = [str(item) for item in files if isinstance(item, str)]
        groups_by_collection[collection_name] = lookup
    for item in assignment.get("scaffold_groups") or []:
        if not isinstance(item, dict):
            continue
        collection = item.get("collection")
        group = item.get("group")
        if not isinstance(collection, str) or not isinstance(group, str):
            continue
        for path in groups_by_collection.get(collection, {}).get(group, []):
            grouped_files.add(path)
    literals, globs = normalize_glob_lists(include_paths + sorted(grouped_files), [])
    return literals, globs, exclude_paths


def normalize_child_units(
    namespace: str,
    selection_indices: list[int],
    child: dict[str, Any],
    scaffold_path: Path | None = None,
) -> list[dict[str, Any]]:
    local_selection_indices = [
        int(value)
        for value in (child.get("source_selection_indices") or selection_indices)
    ]
    if (
        child.get("selection_mode") == "whole_selection"
        and len(local_selection_indices) == 1
    ):
        return [
            {
                "kind": "whole_selection",
                "namespace": namespace,
                "selection_index": local_selection_indices[0],
            }
        ]
    if isinstance(child.get("source_assignment"), dict):
        include_paths, include_globs, exclude_paths = expand_scaffold_assignment(
            child["source_assignment"], scaffold_path
        )
    else:
        include_paths, include_globs = normalize_glob_lists(
            child.get("include_paths") or [], child.get("include_path_globs") or []
        )
        exclude_paths = list(child.get("exclude_paths") or [])
    if (
        not include_paths
        and not include_globs
        and len(local_selection_indices) == 1
        and not exclude_paths
    ):
        return [
            {
                "kind": "whole_selection",
                "namespace": namespace,
                "selection_index": local_selection_indices[0],
            }
        ]
    units: list[dict[str, Any]] = []
    for selection_index in local_selection_indices:
        units.append(
            {
                "kind": "partial_selection",
                "namespace": namespace,
                "selection_index": selection_index,
                "include_paths": include_paths,
                "include_path_globs": include_globs,
                "exclude_paths": exclude_paths,
            }
        )
    return units


def fragment_registry(
    selection_maps: dict[str, dict[int, str]],
    primary_specs: list[dict[str, Any]],
    fallback_specs: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    registry: dict[tuple[str, str], dict[str, Any]] = {}
    fragment_index_registry: dict[tuple[str, int, int], dict[str, Any]] = {}

    def register(
        namespace: str,
        atom_id: str | None,
        selection_index: int | None,
        fragment_index: int | None,
        fragment: dict[str, Any],
    ) -> None:
        if atom_id:
            registry[(namespace, atom_id)] = fragment
        if selection_index is not None and fragment_index is not None:
            fragment_index_registry[(namespace, selection_index, fragment_index)] = (
                fragment
            )

    for spec in primary_specs:
        namespace = spec["source_namespace"]
        selection_indices = spec["source_selection_indices"]
        for atom in spec.get("source_atoms") or []:
            if not isinstance(atom, dict):
                continue
            if (
                not atom.get("commit_message")
                and not atom.get("commit_subject")
                and not atom.get("source_selection_indices")
            ):
                continue
            if not atom.get("commit_message") and not atom.get("commit_subject"):
                continue
            atom_selection_indices = [
                int(value)
                for value in (atom.get("source_selection_indices") or selection_indices)
            ]
            units = normalize_child_units(namespace, atom_selection_indices, atom)
            fragment = {
                "origin": spec["spec_id"],
                "namespace": namespace,
                "units": units,
                "commit_message": compose_message(
                    atom.get("commit_subject"),
                    atom.get("commit_message"),
                    atom.get("commit_body_lines"),
                ),
            }
            atom_id = atom.get("atom_id")
            register(
                namespace,
                atom_id,
                atom_selection_indices[0] if len(atom_selection_indices) == 1 else None,
                None,
                fragment,
            )
        if spec["kind"] == "split":
            for child_index, child in enumerate(spec["target_commits"], 1):
                atom_id = child.get("atom_id")
                units = normalize_child_units(namespace, selection_indices, child)
                fragment = {
                    "origin": spec["spec_id"],
                    "namespace": namespace,
                    "units": units,
                    "commit_message": compose_message(
                        child.get("commit_subject"),
                        child.get("commit_message"),
                        child.get("commit_body_lines"),
                    ),
                }
                register(
                    namespace,
                    atom_id,
                    selection_indices[0] if len(selection_indices) == 1 else None,
                    child_index,
                    fragment,
                )

    for spec in fallback_specs:
        spec_type = spec.get("_fallback_type")
        if spec_type == "wave2_execution_plan":
            namespace = spec["source_namespace"]
            if spec["kind"] != "split":
                continue
            for child_index, child in enumerate(spec["target_commits"], 1):
                atom_id = child.get("atom_id")
                units = normalize_child_units(
                    namespace, spec["source_selection_indices"], child
                )
                fragment = {
                    "origin": spec["spec_id"],
                    "namespace": namespace,
                    "units": units,
                    "commit_message": compose_message(
                        child.get("commit_subject"),
                        child.get("commit_message"),
                        child.get("commit_body_lines"),
                    ),
                }
                register(
                    namespace,
                    atom_id,
                    spec["source_selection_indices"][0],
                    child_index,
                    fragment,
                )
        elif spec_type == "deterministic_split_proposal":
            resolved = spec["resolved_selection"]
            namespace = resolved["namespace"]
            selection_index = int(resolved["selection_index"])
            scaffold_path = (
                Path(spec.get("scaffold_path")) if spec.get("scaffold_path") else None
            )
            for child_index, child in enumerate(spec["target_commits"], 1):
                units = normalize_child_units(
                    namespace,
                    [selection_index],
                    child,
                    scaffold_path=scaffold_path,
                )
                fragment = {
                    "origin": spec["proposal_id"],
                    "namespace": namespace,
                    "units": units,
                    "commit_message": child.get("commit_message"),
                }
                fragment_index_registry[(namespace, selection_index, child_index)] = (
                    fragment
                )

    for key, value in fragment_index_registry.items():
        namespace, selection_index, fragment_index = key
        registry[(namespace, f"{selection_index}-{fragment_index}")] = value
    return registry


def load_fallback_specs(paths: list[Path]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        payload = load_json(path)
        if path.name == "deterministic-wave2-execution-plan.json":
            for item in payload.get("specs", []):
                if isinstance(item, dict):
                    spec = dict(item)
                    spec["_fallback_type"] = "wave2_execution_plan"
                    specs.append(spec)
        elif isinstance(payload, dict) and isinstance(payload.get("specs"), list):
            for item in payload.get("specs", []):
                if isinstance(item, dict) and isinstance(
                    item.get("resolved_selection"), dict
                ):
                    spec = dict(item)
                    spec["_fallback_type"] = "deterministic_split_proposal"
                    scaffold = item.get("scaffold") or {}
                    spec["scaffold_path"] = scaffold.get("path")
                    specs.append(spec)
    return specs


def flatten_ordered_selection_indices(
    target_commits: list[dict[str, Any]],
) -> list[int]:
    ordered: list[int] = []
    for child in target_commits:
        for value in child.get("ordered_source_selection_indices") or []:
            if isinstance(value, int):
                ordered.append(value)
    return ordered


def current_selection_order(
    namespace: str,
    selection_indices: list[int],
    selection_maps: dict[str, dict[int, str]],
    order_index: dict[str, int],
) -> list[int]:
    mapping = selection_maps[namespace]
    return sorted(selection_indices, key=lambda value: order_index[mapping[value]])


def normalize_primary_specs(paths: list[Path]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for path in paths:
        for item in load_specs(path):
            if item.get("executability") != "executable":
                continue
            spec = dict(item)
            if "source_selection_indices" not in spec or not spec.get(
                "source_selection_indices"
            ):
                resolved = spec.get("resolved_source_commits") or []
                selection_indices = [
                    int(row["selection_index"])
                    for row in resolved
                    if isinstance(row, dict) and row.get("selection_index") is not None
                ]
                if not selection_indices:
                    for row in resolved:
                        if not isinstance(row, dict):
                            continue
                        selection_range = row.get("selection_range")
                        if (
                            isinstance(selection_range, list)
                            and len(selection_range) == 2
                        ):
                            start, end = (
                                int(selection_range[0]),
                                int(selection_range[1]),
                            )
                            selection_indices.extend(range(start, end + 1))
                if selection_indices:
                    spec["source_selection_indices"] = selection_indices
            spec["_source_file"] = str(path)
            specs.append(spec)
    return specs


def overlap_components(specs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    unresolved = list(specs)
    components: list[list[dict[str, Any]]] = []
    while unresolved:
        seed = unresolved.pop(0)
        component = [seed]
        changed = True
        while changed:
            changed = False
            rest: list[dict[str, Any]] = []
            current_namespace = {item["source_namespace"] for item in component}
            current_indices = {
                index
                for item in component
                for index in item.get("source_selection_indices") or []
            }
            for candidate in unresolved:
                if candidate[
                    "source_namespace"
                ] in current_namespace and current_indices & set(
                    candidate.get("source_selection_indices") or []
                ):
                    component.append(candidate)
                    current_indices.update(
                        candidate.get("source_selection_indices") or []
                    )
                    changed = True
                else:
                    rest.append(candidate)
            unresolved = rest
        components.append(component)
    return components


def resolve_atom_reference(
    namespace: str,
    atom_ref: Any,
    registry: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(atom_ref, str):
        fragment = registry.get((namespace, atom_ref))
        if not fragment:
            raise KeyError(f"missing atom definition for {namespace}:{atom_ref}")
        return [dict(unit) for unit in fragment["units"]]
    if not isinstance(atom_ref, dict):
        raise KeyError(f"unsupported atom reference {atom_ref!r}")
    kind = atom_ref.get("kind")
    if kind == "selection":
        selection_index = int(atom_ref["selection_index"])
        return [
            {
                "kind": "whole_selection",
                "namespace": namespace,
                "selection_index": selection_index,
            }
        ]
    if kind == "range":
        start = int(atom_ref["start"])
        end = int(atom_ref["end"])
        return [
            {
                "kind": "whole_selection",
                "namespace": namespace,
                "selection_index": value,
            }
            for value in range(start, end + 1)
        ]
    if kind == "split_fragment":
        selection_index = int(atom_ref["selection_index"])
        fragment_index = int(atom_ref["fragment_index"])
        fragment = registry.get((namespace, f"{selection_index}-{fragment_index}"))
        if not fragment:
            raise KeyError(
                f"missing split fragment {namespace}:{selection_index}:{fragment_index}"
            )
        return [dict(unit) for unit in fragment["units"]]
    raise KeyError(f"unsupported atom reference kind {kind!r}")


def child_units_from_spec(
    spec: dict[str, Any],
    child: dict[str, Any],
    registry: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    namespace = spec["source_namespace"]
    if child.get("ordered_source_selection_indices"):
        return [
            {
                "kind": "whole_selection",
                "namespace": namespace,
                "selection_index": int(value),
            }
            for value in child["ordered_source_selection_indices"]
        ]
    if child.get("ordered_source_atoms"):
        units: list[dict[str, Any]] = []
        for atom_ref in child["ordered_source_atoms"]:
            units.extend(resolve_atom_reference(namespace, atom_ref, registry))
        return units
    return normalize_child_units(namespace, spec["source_selection_indices"], child)


def contributing_selection_indices(units: list[dict[str, Any]]) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    for unit in units:
        selection_index = int(unit["selection_index"])
        if selection_index not in seen:
            seen.add(selection_index)
            ordered.append(selection_index)
    return ordered


def merge_child_encodes_reorder(
    merge_spec: dict[str, Any], reorder_spec: dict[str, Any]
) -> bool:
    reorder_sequence = flatten_ordered_selection_indices(reorder_spec["target_commits"])
    if not reorder_sequence:
        return False
    for child in merge_spec["target_commits"]:
        merge_sequence = child.get("ordered_source_selection_indices") or []
        if not merge_sequence:
            continue
        for index in range(0, len(merge_sequence) - len(reorder_sequence) + 1):
            if (
                merge_sequence[index : index + len(reorder_sequence)]
                == reorder_sequence
            ):
                return True
    return False


def reorder_is_noop(
    spec: dict[str, Any],
    selection_maps: dict[str, dict[int, str]],
    order_index: dict[str, int],
) -> bool:
    flattened = flatten_ordered_selection_indices(spec["target_commits"])
    if not flattened:
        return False
    current = current_selection_order(
        spec["source_namespace"], flattened, selection_maps, order_index
    )
    return flattened == current


def build_primary_operations(
    primary_specs: list[dict[str, Any]],
    selection_maps: dict[str, dict[int, str]],
    order_index: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    selected_specs: list[dict[str, Any]] = []
    alternates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    filtered_specs: list[dict[str, Any]] = []
    for spec in primary_specs:
        if spec["kind"] == "reorder" and reorder_is_noop(
            spec, selection_maps, order_index
        ):
            skipped.append(
                {"spec_id": spec["spec_id"], "reason": "noop_reorder_checkpoint"}
            )
            continue
        filtered_specs.append(spec)
    for component in overlap_components(filtered_specs):
        split_specs = [spec for spec in component if spec["kind"] == "split"]
        merge_specs = [spec for spec in component if spec["kind"] == "merge"]
        reorder_specs = [spec for spec in component if spec["kind"] == "reorder"]
        split_ids = {spec["spec_id"] for spec in split_specs}
        merge_uses_split_ids = any(
            any(
                isinstance(atom, str) and atom in split_ids
                for atom in (spec.get("source_atoms") or [])
            )
            or any(
                any(
                    isinstance(atom, str) and atom in split_ids
                    for atom in (child.get("ordered_source_atoms") or [])
                )
                for child in spec.get("target_commits", [])
            )
            for spec in merge_specs
        )
        if len(component) == 1:
            selected_specs.extend(component)
            continue
        if split_specs and not merge_specs and not reorder_specs:
            combined = dict(split_specs[0])
            combined["spec_id"] = "+".join(
                spec["spec_id"]
                for spec in sorted(
                    split_specs, key=lambda item: min(item["source_selection_indices"])
                )
            )
            combined["source_selection_indices"] = sorted(
                {
                    index
                    for spec in split_specs
                    for index in spec["source_selection_indices"]
                }
            )
            combined["target_commits"] = [
                child
                for spec in sorted(
                    split_specs,
                    key=lambda item: (
                        min(item["source_selection_indices"]),
                        item["spec_id"],
                    ),
                )
                for child in spec["target_commits"]
            ]
            combined["_absorbed_spec_ids"] = [spec["spec_id"] for spec in split_specs]
            selected_specs.append(combined)
            continue
        if merge_specs and merge_uses_split_ids:
            selected_specs.extend(merge_specs)
            skipped.extend(
                {"spec_id": spec["spec_id"], "reason": "dependency_split_atom"}
                for spec in split_specs
            )
            skipped.extend(
                {"spec_id": spec["spec_id"], "reason": "subsumed_by_merge_component"}
                for spec in reorder_specs
            )
            continue
        if merge_specs and reorder_specs:
            kept_merges: list[dict[str, Any]] = []
            absorbed_reorders: set[str] = set()
            for merge_spec in merge_specs:
                kept_merges.append(merge_spec)
                for reorder_spec in reorder_specs:
                    if merge_spec["source_selection_indices"] == reorder_spec[
                        "source_selection_indices"
                    ] or merge_child_encodes_reorder(merge_spec, reorder_spec):
                        absorbed_reorders.add(reorder_spec["spec_id"])
            if kept_merges:
                selected_specs.extend(kept_merges)
                skipped.extend(
                    {"spec_id": spec_id, "reason": "absorbed_into_merge"}
                    for spec_id in sorted(absorbed_reorders)
                )
                for reorder_spec in reorder_specs:
                    if reorder_spec["spec_id"] not in absorbed_reorders:
                        selected_specs.append(reorder_spec)
                if split_specs:
                    selected_specs.extend(split_specs)
                    alternates.extend(
                        {
                            "spec_id": merge_spec["spec_id"],
                            "reason": "overlaps_primary_split",
                            "primary_split_ids": [
                                spec["spec_id"] for spec in split_specs
                            ],
                        }
                        for merge_spec in kept_merges
                    )
                continue
        if split_specs:
            selected_specs.extend(split_specs)
            alternates.extend(
                {
                    "spec_id": spec["spec_id"],
                    "reason": "alternate_overlap_with_split",
                    "primary_split_ids": [
                        split_spec["spec_id"] for split_spec in split_specs
                    ],
                }
                for spec in component
                if spec["spec_id"] not in split_ids
            )
            continue
        selected_specs.extend(component)
    return selected_specs, alternates, skipped


def source_selection_order_key(
    namespace: str,
    selection_index: int,
    selection_maps: dict[str, dict[int, str]],
    order_index: dict[str, int],
) -> tuple[int, int]:
    sha = selection_maps[namespace][selection_index]
    return order_index[sha], selection_index


def spec_band_range(
    spec: dict[str, Any],
    selection_maps: dict[str, dict[int, str]],
    order_index: dict[str, int],
) -> tuple[int, int]:
    namespace = spec["source_namespace"]
    positions = [
        source_selection_order_key(
            namespace, int(selection_index), selection_maps, order_index
        )[0]
        for selection_index in (spec.get("source_selection_indices") or [])
    ]
    if not positions:
        raise ValueError(f"spec {spec.get('spec_id')} has no source_selection_indices")
    return min(positions), max(positions)


def build_passthrough_child(
    namespace: str, selection_index: int, source_meta: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    meta = source_meta[selection_index]
    return {
        "kind": "passthrough",
        "commit_message": meta["message"].rstrip() + "\n",
        "units": [
            {
                "kind": "whole_selection",
                "namespace": namespace,
                "selection_index": selection_index,
            }
        ],
        "contributing_selection_indices": [selection_index],
        "_sort_key": (meta["_order_index"], 9999),
        "_single_selection_split_group": None,
    }


def child_commit_with_units(
    spec: dict[str, Any],
    child: dict[str, Any],
    registry: dict[tuple[str, str], dict[str, Any]],
    selection_maps: dict[str, dict[int, str]],
    order_index: dict[str, int],
    order_hint: int,
) -> dict[str, Any]:
    namespace = spec["source_namespace"]
    units = child_units_from_spec(spec, child, registry)
    units.sort(
        key=lambda unit: source_selection_order_key(
            namespace, int(unit["selection_index"]), selection_maps, order_index
        )
    )
    contributing = contributing_selection_indices(units)
    positions = [
        source_selection_order_key(namespace, index, selection_maps, order_index)[0]
        for index in contributing
    ]
    single_selection_split_group = (
        contributing[0]
        if len(contributing) == 1
        and all(
            unit["kind"] != "whole_selection" or len(contributing) == 1
            for unit in units
        )
        else None
    )
    return {
        "kind": "rewritten",
        "commit_message": compose_message(
            child.get("commit_subject"),
            child.get("commit_message"),
            child.get("commit_body_lines"),
        ),
        "units": units,
        "contributing_selection_indices": contributing,
        "_sort_key": (min(positions), order_hint),
        "_single_selection_split_group": single_selection_split_group,
    }


def source_meta_for_namespace(
    repo: Path,
    namespace: str,
    selection_map: dict[int, str],
    order_index: dict[str, int],
) -> dict[int, dict[str, Any]]:
    meta: dict[int, dict[str, Any]] = {}
    for selection_index, sha in selection_map.items():
        info = commit_meta(repo, sha)
        info["_order_index"] = order_index[sha]
        meta[selection_index] = info
    return meta


def assign_child_dates(
    children: list[dict[str, Any]], source_meta: dict[int, dict[str, Any]]
) -> None:
    split_group_offsets: defaultdict[int, int] = defaultdict(int)
    last_committer: datetime | None = None
    for child in children:
        contributing = child["contributing_selection_indices"]
        metas = [source_meta[index] for index in contributing]
        if child["kind"] == "passthrough":
            author_name = metas[0]["author_name"]
            author_email = metas[0]["author_email"]
            author_date_iso = metas[0]["author_date_iso"]
            committer_name = metas[0]["committer_name"]
            committer_email = metas[0]["committer_email"]
            committer_date_iso = metas[0]["committer_date_iso"]
        elif child.get("_single_selection_split_group") is not None:
            selection_index = child["_single_selection_split_group"]
            source = source_meta[selection_index]
            offset = split_group_offsets[selection_index]
            split_group_offsets[selection_index] += 1
            author_name = source["author_name"]
            author_email = source["author_email"]
            author_date_iso = source["author_date_iso"]
            committer_name = source["committer_name"]
            committer_email = source["committer_email"]
            committer_date_iso = iso_add_seconds(source["committer_date_iso"], offset)
        else:
            oldest = min(
                metas, key=lambda row: parse_datetime_iso(row["author_date_iso"])
            )
            newest = max(
                metas, key=lambda row: parse_datetime_iso(row["committer_date_iso"])
            )
            author_name = oldest["author_name"]
            author_email = oldest["author_email"]
            author_date_iso = oldest["author_date_iso"]
            committer_name = newest["committer_name"]
            committer_email = newest["committer_email"]
            committer_date_iso = newest["committer_date_iso"]
        current_committer = parse_datetime_iso(committer_date_iso)
        if last_committer is not None and current_committer <= last_committer:
            current_committer = last_committer + timedelta(seconds=1)
            committer_date_iso = current_committer.isoformat()
        last_committer = current_committer
        child["author"] = {
            "name": author_name,
            "email": author_email,
            "date_iso": author_date_iso,
        }
        child["committer"] = {
            "name": committer_name,
            "email": committer_email,
            "date_iso": committer_date_iso,
        }
        child.pop("_sort_key", None)
        child.pop("_single_selection_split_group", None)


def compile_operation(
    op_id: str,
    namespace: str,
    specs: list[dict[str, Any]],
    registry: dict[tuple[str, str], dict[str, Any]],
    selection_maps: dict[str, dict[int, str]],
    order_index: dict[str, int],
    order_list: list[str],
    source_meta: dict[str, dict[int, dict[str, Any]]],
) -> dict[str, Any]:
    selection_map = selection_maps[namespace]
    source_meta_ns = source_meta[namespace]
    all_selection_indices = sorted(
        {
            int(index)
            for spec in specs
            for index in spec.get("source_selection_indices") or []
        }
    )
    positions = [
        source_selection_order_key(namespace, index, selection_maps, order_index)[0]
        for index in all_selection_indices
    ]
    band_start = min(positions)
    band_end = max(positions)
    band_shas = order_list[band_start - 1 : band_end]
    band_selection_indices = [
        selection_index
        for selection_index, sha in selection_map.items()
        if sha in band_shas
    ]
    band_selection_indices.sort(
        key=lambda value: source_selection_order_key(
            namespace, value, selection_maps, order_index
        )
    )
    children: list[dict[str, Any]] = []
    if all(spec["kind"] == "split" for spec in specs):
        ordered_specs = sorted(
            specs,
            key=lambda item: (
                spec_band_range(item, selection_maps, order_index)[0],
                item["spec_id"],
            ),
        )
        for spec_index, spec in enumerate(ordered_specs, 1):
            for child_index, child in enumerate(spec["target_commits"], 1):
                children.append(
                    child_commit_with_units(
                        spec,
                        child,
                        registry,
                        selection_maps,
                        order_index,
                        order_hint=spec_index * 100 + child_index,
                    )
                )
    else:
        ordered_specs = sorted(
            specs,
            key=lambda item: spec_band_range(item, selection_maps, order_index)[0],
        )
        for spec_index, spec in enumerate(ordered_specs, 1):
            for child_index, child in enumerate(spec["target_commits"], 1):
                children.append(
                    child_commit_with_units(
                        spec,
                        child,
                        registry,
                        selection_maps,
                        order_index,
                        order_hint=spec_index * 100 + child_index,
                    )
                )
    consumed = {
        selection_index
        for child in children
        for selection_index in child["contributing_selection_indices"]
    }
    for selection_index in band_selection_indices:
        if selection_index not in consumed:
            children.append(
                build_passthrough_child(namespace, selection_index, source_meta_ns)
            )
    children.sort(key=lambda item: item["_sort_key"])
    assign_child_dates(children, source_meta_ns)
    return {
        "op_id": op_id,
        "namespace": namespace,
        "source_band_selection_indices": band_selection_indices,
        "source_band_current_shas": band_shas,
        "anchor_sha": band_shas[-1],
        "source_commit_count": len(band_shas),
        "source_spec_ids": [spec["spec_id"] for spec in ordered_specs],
        "target_commits": children,
    }


def compile_structural_plan(
    repo: Path, launch_pack_dir: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    defaults = discover_default_inputs(launch_pack_dir)
    primary_specs = normalize_primary_specs(defaults["primary_packs"])
    superseded, superseded_reasons = superseded_ids(defaults["supersession_files"])
    primary_specs = [
        spec
        for spec in primary_specs
        if spec["spec_id"] not in superseded and not spec.get("superseded_by")
    ]
    order_list, order_index = head_order(repo)
    selection_maps = selection_maps_from_launch_pack(launch_pack_dir)
    fallback_specs = load_fallback_specs(defaults["fallback_packs"])
    registry = fragment_registry(selection_maps, primary_specs, fallback_specs)
    selected_specs, alternates, skipped = build_primary_operations(
        primary_specs, selection_maps, order_index
    )
    source_meta: dict[str, dict[int, dict[str, Any]]] = {
        namespace: source_meta_for_namespace(repo, namespace, mapping, order_index)
        for namespace, mapping in selection_maps.items()
    }
    operations: list[dict[str, Any]] = []
    operation_index = 0
    pending_specs = selected_specs[:]
    while pending_specs:
        seed = pending_specs.pop(0)
        group = [seed]
        group_start, group_end = spec_band_range(seed, selection_maps, order_index)
        remaining = pending_specs
        while True:
            next_remaining: list[dict[str, Any]] = []
            changed = False
            for spec in remaining:
                if spec["source_namespace"] != seed["source_namespace"]:
                    next_remaining.append(spec)
                    continue
                spec_start, spec_end = spec_band_range(
                    spec, selection_maps, order_index
                )
                if spec_start <= group_end and spec_end >= group_start:
                    group.append(spec)
                    group_start = min(group_start, spec_start)
                    group_end = max(group_end, spec_end)
                    changed = True
                else:
                    next_remaining.append(spec)
            if not changed:
                pending_specs = next_remaining
                break
            remaining = next_remaining
        operation_index += 1
        op_id = f"{seed['source_namespace']}-op-{operation_index:03d}"
        operations.append(
            compile_operation(
                op_id=op_id,
                namespace=seed["source_namespace"],
                specs=group,
                registry=registry,
                selection_maps=selection_maps,
                order_index=order_index,
                order_list=order_list,
                source_meta=source_meta,
            )
        )
    operations.sort(key=lambda item: order_index[item["anchor_sha"]])
    summary = {
        "head_sha": git_stdout(repo, "rev-parse", "HEAD").strip(),
        "root_sha": order_list[0],
        "selected_operation_count": len(operations),
        "primary_spec_count": len(primary_specs),
        "selected_spec_count": len(selected_specs),
        "alternate_count": len(alternates),
        "skipped_count": len(skipped),
        "superseded_count": len(superseded),
    }
    plan = {
        "plan_version": "structural-execution-v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "repo": str(repo),
        "launch_pack_dir": str(launch_pack_dir),
        "head_sha": summary["head_sha"],
        "root_sha": summary["root_sha"],
        "primary_packs": [str(path) for path in defaults["primary_packs"]],
        "fallback_packs": [str(path) for path in defaults["fallback_packs"]],
        "supersession_files": [str(path) for path in defaults["supersession_files"]],
        "operations": operations,
        "alternates": alternates,
        "skipped_specs": skipped,
        "superseded_specs": [
            {"spec_id": spec_id, "reason": superseded_reasons.get(spec_id)}
            for spec_id in sorted(superseded)
        ],
    }
    return plan, summary


def compile_cmd(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    launch_pack_dir = Path(args.launch_pack_dir).resolve()
    plan, summary = compile_structural_plan(repo, launch_pack_dir)
    write_json(Path(args.output_json).resolve(), plan)
    if args.summary_json:
        write_json(Path(args.summary_json).resolve(), summary)
    print(json.dumps(summary, indent=2))
    return 0


def source_sha_from_todo_line(
    repo: Path, stripped_line: str
) -> tuple[str | None, str | None]:
    parts = stripped_line.split()
    if not parts:
        return None, None
    command = parts[0]
    sha_token: str | None = None
    if command in (
        "pick",
        "p",
        "reword",
        "r",
        "edit",
        "e",
        "squash",
        "s",
        "fixup",
        "f",
    ):
        if len(parts) >= 2:
            sha_token = parts[1]
    elif command in ("merge", "m"):
        for flag in ("-C", "-c"):
            if flag in parts:
                index = parts.index(flag)
                if index + 1 < len(parts):
                    sha_token = parts[index + 1]
                    break
    if not sha_token:
        return command, None
    resolved_sha = git_stdout(repo, "rev-parse", sha_token).strip()
    return command, resolved_sha


def patch_todo_cmd(args: argparse.Namespace) -> int:
    plan = load_json(Path(args.plan_json).resolve())
    todo_path = Path(args.todo_file).resolve()
    operations = plan.get("operations") or []
    anchor_to_ops: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    structural_band_shas: set[str] = set()
    for operation in operations:
        anchor_to_ops[operation["anchor_sha"]].append(operation)
        structural_band_shas.update(operation.get("source_band_current_shas") or [])
    lines = todo_path.read_text().splitlines()
    patched: list[str] = []
    cli_path = (
        Path(args.cli_path).resolve()
        if args.cli_path
        else Path(__file__).resolve().with_name("cli.py")
    )
    repo = Path(args.repo).resolve() if args.repo else Path(plan["repo"]).resolve()
    patched_count = 0
    preserved_count = 0
    for line in lines:
        patched.append(line)
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        command, resolved_source_sha = source_sha_from_todo_line(repo, stripped)
        if (
            resolved_source_sha
            and resolved_source_sha not in structural_band_shas
            and command
            in (
                "pick",
                "p",
                "reword",
                "r",
                "edit",
                "e",
                "squash",
                "s",
                "fixup",
                "f",
                "merge",
                "m",
            )
        ):
            preserve_command = (
                f"python3 {cli_path} preserve-picked-commit-committer "
                f"--repo {repo} "
                f"--source-sha {resolved_source_sha}"
            )
            patched.append(f"exec {preserve_command}")
            preserved_count += 1
        for operation in anchor_to_ops.get(resolved_source_sha or "", []):
            structural_command = (
                f"python3 {cli_path} apply-structural-op "
                f"--repo {repo} "
                f"--plan-json {Path(args.plan_json).resolve()} "
                f"--op-id {operation['op_id']}"
            )
            patched.append(f"exec {structural_command}")
            patched_count += 1
    todo_path.write_text("\n".join(patched).rstrip() + "\n")
    print(
        json.dumps(
            {
                "todo_file": str(todo_path),
                "operations_patched": patched_count,
                "committer_preservation_execs_patched": preserved_count,
            },
            indent=2,
        )
    )
    return 0


def unit_patch_bytes(
    repo: Path,
    unit: dict[str, Any],
    selection_maps: dict[str, dict[int, str]],
    source_meta: dict[str, dict[int, dict[str, Any]]],
) -> bytes:
    namespace = unit["namespace"]
    selection_index = int(unit["selection_index"])
    sha = selection_maps[namespace][selection_index]
    parent_sha = source_meta[namespace][selection_index]["parent_sha"]
    if not parent_sha:
        raise ValueError(
            f"selection {namespace}:{selection_index} points at a root commit; structural runner does not support root rewrites"
        )
    args = ["diff", "--binary", parent_sha, sha]
    if unit["kind"] == "partial_selection":
        pathspecs: list[str] = []
        include_paths, include_globs = normalize_glob_lists(
            unit.get("include_paths") or [], unit.get("include_path_globs") or []
        )
        pathspecs.extend(pathspec_from_include(path) for path in include_paths)
        pathspecs.extend(pathspec_from_include(path) for path in include_globs)
        if unit.get("exclude_paths"):
            if not pathspecs:
                pathspecs.append(".")
            pathspecs.extend(
                pathspec_from_exclude(path) for path in unit["exclude_paths"]
            )
        if pathspecs:
            args.extend(["--", *pathspecs])
    return git_bytes(repo, *args)


def chunked(values: list[str], size: int = 200) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def unit_pathspecs(unit: dict[str, Any]) -> list[str]:
    pathspecs: list[str] = []
    if unit["kind"] == "partial_selection":
        include_paths, include_globs = normalize_glob_lists(
            unit.get("include_paths") or [], unit.get("include_path_globs") or []
        )
        pathspecs.extend(pathspec_from_include(path) for path in include_paths)
        pathspecs.extend(pathspec_from_include(path) for path in include_globs)
        if unit.get("exclude_paths"):
            if not pathspecs:
                pathspecs.append(".")
            pathspecs.extend(
                pathspec_from_exclude(path) for path in unit["exclude_paths"]
            )
    return pathspecs


def unit_changed_paths(
    repo: Path,
    unit: dict[str, Any],
    selection_maps: dict[str, dict[int, str]],
    source_meta: dict[str, dict[int, dict[str, Any]]],
) -> tuple[str, str, list[str]]:
    namespace = unit["namespace"]
    if unit["kind"] == "whole_selection_range":
        start_selection_index = int(unit["start_selection_index"])
        end_selection_index = int(unit["end_selection_index"])
        sha = selection_maps[namespace][end_selection_index]
        parent_sha = source_meta[namespace][start_selection_index]["parent_sha"]
        selection_label = f"{start_selection_index}..{end_selection_index}"
    else:
        selection_index = int(unit["selection_index"])
        sha = selection_maps[namespace][selection_index]
        parent_sha = source_meta[namespace][selection_index]["parent_sha"]
        selection_label = str(selection_index)
    if not parent_sha:
        raise ValueError(
            f"selection {namespace}:{selection_label} points at a root commit; structural runner does not support root rewrites"
        )
    args = ["diff", "--name-only", "--no-renames", parent_sha, sha]
    pathspecs = unit_pathspecs(unit)
    if pathspecs:
        args.extend(["--", *pathspecs])
    changed_paths = [
        line.strip() for line in git_stdout(repo, *args).splitlines() if line.strip()
    ]
    return sha, parent_sha, changed_paths


def paths_present_in_tree(repo: Path, sha: str, paths: list[str]) -> set[str]:
    present: set[str] = set()
    for chunk in chunked(paths):
        result = git_stdout(repo, "ls-tree", "-r", "--name-only", sha, "--", *chunk)
        present.update(line.strip() for line in result.splitlines() if line.strip())
    return present


def blob_bytes(repo: Path, ref: str, path: str) -> bytes | None:
    result = git(repo, "show", f"{ref}:{path}", text=False, check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def tree_paths(repo: Path, ref: str) -> set[str]:
    return {
        line.strip()
        for line in git_stdout(repo, "ls-tree", "-r", "--name-only", ref).splitlines()
        if line.strip()
    }


def compare_repo_trees(
    left_repo: Path,
    right_repo: Path,
    *,
    left_ref: str = "HEAD",
    right_ref: str = "HEAD",
    sample_limit: int = 50,
) -> dict[str, Any]:
    left_files = tree_paths(left_repo, left_ref)
    right_files = tree_paths(right_repo, right_ref)
    only_left = sorted(left_files - right_files)
    only_right = sorted(right_files - left_files)
    differing: list[str] = []
    for path in sorted(left_files & right_files):
        left_blob = blob_bytes(left_repo, left_ref, path)
        right_blob = blob_bytes(right_repo, right_ref, path)
        if left_blob != right_blob:
            differing.append(path)
    return {
        "left_repo": str(left_repo),
        "right_repo": str(right_repo),
        "left_ref": left_ref,
        "right_ref": right_ref,
        "only_left_count": len(only_left),
        "only_right_count": len(only_right),
        "differing_count": len(differing),
        "union_problem_count": len(set(only_left) | set(only_right) | set(differing)),
        "only_left_sample": only_left[:sample_limit],
        "only_right_sample": only_right[:sample_limit],
        "differing_sample": differing[:sample_limit],
    }


def apply_unit_state(
    repo: Path,
    unit: dict[str, Any],
    selection_maps: dict[str, dict[int, str]],
    source_meta: dict[str, dict[int, dict[str, Any]]],
) -> bool:
    sha, _parent_sha, changed_paths = unit_changed_paths(
        repo, unit, selection_maps, source_meta
    )
    if not changed_paths:
        return False
    present_paths = sorted(paths_present_in_tree(repo, sha, changed_paths))
    absent_paths = sorted(path for path in changed_paths if path not in present_paths)
    for chunk in chunked(present_paths):
        git_stdout(
            repo, "restore", f"--source={sha}", "--staged", "--worktree", "--", *chunk
        )
    for chunk in chunked(absent_paths):
        git(repo, "rm", "-q", "-r", "-f", "--ignore-unmatch", "--", *chunk)
    return True


def ordered_child_units(
    operation: dict[str, Any], child: dict[str, Any]
) -> list[dict[str, Any]]:
    source_order = {
        int(selection_index): position
        for position, selection_index in enumerate(
            operation.get("source_band_selection_indices") or []
        )
    }
    ordered: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    for original_position, unit in enumerate(child["units"]):
        selection_index = unit.get("selection_index")
        if selection_index is None:
            ordered.append(((1, original_position, 0), unit))
            continue
        ordered.append(
            (
                (
                    0,
                    source_order.get(
                        int(selection_index), len(source_order) + original_position
                    ),
                    original_position,
                ),
                unit,
            )
        )
    return [unit for _key, unit in sorted(ordered, key=lambda item: item[0])]


def apply_structural_op_cmd(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    plan = load_json(Path(args.plan_json).resolve())
    launch_pack_dir = Path(plan["launch_pack_dir"]).resolve()
    selection_maps = selection_maps_from_launch_pack(launch_pack_dir)
    source_meta = {
        namespace: {
            selection_index: commit_meta(repo, sha)
            for selection_index, sha in mapping.items()
        }
        for namespace, mapping in selection_maps.items()
    }
    operation = next(
        (item for item in plan.get("operations", []) if item["op_id"] == args.op_id),
        None,
    )
    if not operation:
        raise ValueError(f"unknown operation id {args.op_id}")
    source_count = int(operation["source_commit_count"])
    actual_band = [
        line.strip()
        for line in git_stdout(
            repo, "rev-list", "--reverse", f"--max-count={source_count}", "HEAD"
        ).splitlines()
        if line.strip()
    ]
    if len(actual_band) != source_count:
        emit_journal_event(
            "structural_op_invalid_tail_count",
            repo=str(repo),
            op_id=args.op_id,
            expected_count=source_count,
            actual_count=len(actual_band),
        )
        raise ValueError(
            f"operation {args.op_id} expected {source_count} commits at HEAD tail, got {len(actual_band)}"
        )
    expected_band = [
        str(value).strip() for value in operation.get("source_band_current_shas") or []
    ]
    emit_journal_event(
        "structural_op_started",
        repo=str(repo),
        op_id=args.op_id,
        pre_head=git_stdout(repo, "rev-parse", "HEAD").strip(),
        base_sha=git_stdout(repo, "rev-parse", f"HEAD~{source_count}").strip(),
        source_count=source_count,
        expected_band=expected_band,
        actual_band=actual_band,
    )
    if expected_band:
        expected_meta = [commit_meta(repo, sha) for sha in expected_band]
        actual_meta = [commit_meta(repo, sha) for sha in actual_band]
        expected_fingerprints = [
            commit_identity_fingerprint(meta) for meta in expected_meta
        ]
        actual_fingerprints = [
            commit_identity_fingerprint(meta) for meta in actual_meta
        ]
        if actual_fingerprints != expected_fingerprints:
            recent_done = recent_rebase_done_pick_shas(repo, source_count)
            if recent_done == expected_band and operation_is_empty_band_noop(operation):
                emit_journal_event(
                    "structural_op_noop_empty_source_band",
                    repo=str(repo),
                    op_id=args.op_id,
                    expected_band=expected_band,
                    actual_tail_band=actual_band,
                )
                print(
                    json.dumps(
                        {
                            "op_id": args.op_id,
                            "status": "noop_empty_source_band",
                            "reason": "source picks were just replayed but landed empty; no structural rewrite needed",
                            "expected_band": expected_band,
                            "actual_tail_band": actual_band,
                        },
                        indent=2,
                    )
                )
                return 0
            emit_journal_event(
                "structural_op_band_mismatch",
                repo=str(repo),
                op_id=args.op_id,
                expected_band=expected_band,
                actual_band=actual_band,
            )
            raise ValueError(
                f"operation {args.op_id} expected source band fingerprint "
                f"{expected_band[0]}..{expected_band[-1]} but saw {actual_band[0]}..{actual_band[-1]}"
            )
    base_sha = git_stdout(repo, "rev-parse", f"HEAD~{source_count}").strip()
    git_stdout(repo, "reset", "--hard", base_sha)
    created_children = 0
    skipped_empty_children: list[str] = []
    for child in operation["target_commits"]:
        any_patch = False
        for unit in ordered_child_units(operation, child):
            any_patch = (
                apply_unit_state(repo, unit, selection_maps, source_meta) or any_patch
            )
        if not any_patch:
            emit_journal_event(
                "structural_op_empty_child",
                repo=str(repo),
                op_id=args.op_id,
                child_subject=child["commit_message"].splitlines()[0],
            )
            raise RuntimeError(
                f"operation {args.op_id} produced an empty child commit for message {child['commit_message'].splitlines()[0]}"
            )
        cached_diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--exit-code"],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        if cached_diff.returncode == 0:
            skipped_empty_children.append(child["commit_message"].splitlines()[0])
            continue
        if cached_diff.returncode not in (0, 1):
            raise subprocess.CalledProcessError(
                cached_diff.returncode,
                cached_diff.args,
                output=cached_diff.stdout,
                stderr=cached_diff.stderr,
            )
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write(child["commit_message"])
            message_path = Path(handle.name)
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": child["author"]["name"],
                "GIT_AUTHOR_EMAIL": child["author"]["email"],
                "GIT_AUTHOR_DATE": child["author"]["date_iso"],
                "GIT_COMMITTER_NAME": child["committer"]["name"],
                "GIT_COMMITTER_EMAIL": child["committer"]["email"],
                "GIT_COMMITTER_DATE": child["committer"]["date_iso"],
            }
        )
        try:
            subprocess.run(
                ["git", "commit", "-F", str(message_path)],
                cwd=repo,
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )
            created_children += 1
        finally:
            message_path.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "op_id": args.op_id,
                "source_band_replaced": actual_band,
                "created_commits": created_children,
                "skipped_empty_children": skipped_empty_children,
            },
            indent=2,
        )
    )
    emit_journal_event(
        "structural_op_completed",
        repo=str(repo),
        op_id=args.op_id,
        post_head=git_stdout(repo, "rev-parse", "HEAD").strip(),
        created_commits=created_children,
        skipped_empty_children=skipped_empty_children,
    )
    return 0


def compare_repo_trees_cmd(args: argparse.Namespace) -> int:
    left_repo = Path(args.left_repo).resolve()
    right_repo = Path(args.right_repo).resolve()
    scorecard = compare_repo_trees(
        left_repo,
        right_repo,
        left_ref=args.left_ref,
        right_ref=args.right_ref,
        sample_limit=args.sample_limit,
    )
    if args.output_json:
        write_json(Path(args.output_json).resolve(), scorecard)
    print(json.dumps(scorecard, indent=2))
    return 0


def load_excluded_op_ids(path: Path) -> list[str]:
    payload = load_json(path)
    if isinstance(payload, dict):
        values = (
            payload.get("exclude")
            or payload.get("excluded_operations")
            or payload.get("op_ids")
            or []
        )
    elif isinstance(payload, list):
        values = payload
    else:
        values = []
    result: list[str] = []
    for item in values:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and isinstance(item.get("op_id"), str):
            result.append(item["op_id"])
    return result


def filter_structural_plan_cmd(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan_json).resolve()
    plan = load_json(plan_path)
    excluded: set[str] = set(args.exclude_op_id or [])
    if args.exclude_op_list_json:
        excluded.update(load_excluded_op_ids(Path(args.exclude_op_list_json).resolve()))
    original_operations = plan.get("operations") or []
    kept_operations = [
        operation
        for operation in original_operations
        if operation.get("op_id") not in excluded
    ]
    removed_operations = [
        operation
        for operation in original_operations
        if operation.get("op_id") in excluded
    ]
    filtered_plan = dict(plan)
    filtered_plan["operations"] = kept_operations
    filtered_plan["filtered_from_plan"] = str(plan_path)
    filtered_plan["excluded_operations"] = [
        {
            "op_id": operation.get("op_id"),
            "namespace": operation.get("namespace"),
            "source_commit_count": operation.get("source_commit_count"),
        }
        for operation in removed_operations
    ]
    summary = {
        "source_plan": str(plan_path),
        "original_operation_count": len(original_operations),
        "kept_operation_count": len(kept_operations),
        "excluded_operation_count": len(removed_operations),
        "excluded_op_ids": [
            row["op_id"] for row in filtered_plan["excluded_operations"]
        ],
    }
    write_json(Path(args.output_json).resolve(), filtered_plan)
    if args.summary_json:
        write_json(Path(args.summary_json).resolve(), summary)
    print(json.dumps(summary, indent=2))
    return 0


def preserve_picked_commit_committer_cmd(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    source = commit_meta(repo, args.source_sha)
    env = os.environ.copy()
    env.update(
        {
            "GIT_COMMITTER_NAME": source["committer_name"],
            "GIT_COMMITTER_EMAIL": source["committer_email"],
            "GIT_COMMITTER_DATE": source["committer_date_iso"],
        }
    )
    subprocess.run(
        ["git", "commit", "--amend", "--no-edit", "--no-verify", "--allow-empty"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    payload = {
        "source_sha": source["sha"],
        "head_sha": git_stdout(repo, "rev-parse", "HEAD").strip(),
        "committer_name": source["committer_name"],
        "committer_email": source["committer_email"],
        "committer_date_iso": source["committer_date_iso"],
    }
    emit_journal_event("preserve_picked_commit_committer", **payload)
    print(json.dumps(payload, indent=2))
    return 0


def auto_resolve_rebase_conflicts(repo: Path) -> bool:
    raw = git_optional_stdout(repo, "ls-files", "-u")
    if not raw.strip():
        return False
    stages_by_path: defaultdict[str, set[int]] = defaultdict(set)
    stage_meta_by_path: defaultdict[str, dict[int, tuple[str, str]]] = defaultdict(dict)
    for line in raw.splitlines():
        if "\t" not in line:
            return False
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) < 3:
            return False
        blob_sha = parts[0]
        stage = int(parts[2])
        stages_by_path[path].add(stage)
        stage_meta_by_path[path][stage] = (blob_sha, meta)
    if not stages_by_path:
        return False
    rebase_head = git_optional_stdout(repo, "rev-parse", "REBASE_HEAD").strip()
    rebase_subject = ""
    if rebase_head:
        rebase_subject = git_optional_stdout(
            repo, "show", "-s", "--format=%s", rebase_head
        ).strip()
    all_paths = sorted(stages_by_path.keys())
    path_fingerprint = hashlib.sha1("\n".join(all_paths).encode("utf-8")).hexdigest()[
        :16
    ]
    add_paths: list[str] = []
    remove_paths: list[str] = []
    unresolved_paths: list[str] = []
    for path, stages in sorted(stages_by_path.items()):
        if stages == {3}:
            add_paths.append(path)
            continue
        if stages == {2}:
            remove_paths.append(path)
            continue
        if stages == {1, 2}:
            base_sha = stage_meta_by_path[path][1][0]
            ours_sha = stage_meta_by_path[path][2][0]
            if base_sha == ours_sha:
                remove_paths.append(path)
                continue
        if stages == {1, 3}:
            base_sha = stage_meta_by_path[path][1][0]
            theirs_sha = stage_meta_by_path[path][3][0]
            if base_sha == theirs_sha:
                add_paths.append(path)
                continue
        unresolved_paths.append(path)
    test_lane_subject = bool(
        rebase_subject
        and re.search(r"^(fix|refactor)\((tests?|test-utils)\):", rebase_subject)
    )
    if (
        unresolved_paths
        and test_lane_subject
        and all(path.startswith("test/") for path in unresolved_paths)
    ):
        git(repo, "checkout", "--theirs", "--", *unresolved_paths)
        git(repo, "add", "--", *unresolved_paths)
        payload = {
            "strategy": "test_lane_take_theirs",
            "rebase_head": rebase_head,
            "rebase_subject": rebase_subject,
            "paths": unresolved_paths,
            "add": add_paths,
            "remove": remove_paths,
            "path_fingerprint": path_fingerprint,
        }
        emit_conflict_ledger_entry(
            kind="auto_resolved_conflict",
            strategy="test_lane_take_theirs",
            rebase_head=rebase_head,
            rebase_subject=rebase_subject,
            path_fingerprint=path_fingerprint,
            paths=unresolved_paths,
        )
        emit_journal_event("auto_resolved_conflict", **payload)
        print(
            json.dumps(
                {"auto_resolved_conflicts": payload},
                indent=2,
            )
        )
        if add_paths:
            git(repo, "add", "--", *add_paths)
        if remove_paths:
            git(repo, "rm", "-q", "-r", "-f", "--ignore-unmatch", "--", *remove_paths)
        return True
    if unresolved_paths:
        emit_conflict_ledger_entry(
            kind="unresolved_conflict",
            strategy="manual_required",
            rebase_head=rebase_head,
            rebase_subject=rebase_subject,
            path_fingerprint=path_fingerprint,
            paths=unresolved_paths,
        )
        emit_journal_event(
            "unresolved_conflict",
            strategy="manual_required",
            rebase_head=rebase_head,
            rebase_subject=rebase_subject,
            path_fingerprint=path_fingerprint,
            paths=unresolved_paths,
        )
        return False
    if add_paths:
        git(repo, "add", "--", *add_paths)
    if remove_paths:
        git(repo, "rm", "-q", "-r", "-f", "--ignore-unmatch", "--", *remove_paths)
    if add_paths or remove_paths:
        emit_conflict_ledger_entry(
            kind="auto_resolved_conflict",
            strategy="stage_shape_only",
            rebase_head=rebase_head,
            rebase_subject=rebase_subject,
            path_fingerprint=path_fingerprint,
            paths=all_paths,
            add=add_paths,
            remove=remove_paths,
        )
        emit_journal_event(
            "auto_resolved_conflict",
            strategy="stage_shape_only",
            rebase_head=rebase_head,
            rebase_subject=rebase_subject,
            path_fingerprint=path_fingerprint,
            paths=all_paths,
            add=add_paths,
            remove=remove_paths,
        )
    print(
        json.dumps(
            {
                "auto_resolved_conflicts": {
                    "add": add_paths,
                    "remove": remove_paths,
                }
            },
            indent=2,
        )
    )
    return bool(add_paths or remove_paths)


def run_structural_plan_cmd(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    cli_path = (
        Path(args.cli_path).resolve()
        if args.cli_path
        else Path(__file__).resolve().with_name("cli.py")
    )
    editor_command = f"python3 {cli_path} patch-rebase-todo --repo {repo} --plan-json {Path(args.plan_json).resolve()}"
    initial_env = os.environ.copy()
    initial_env["GIT_SEQUENCE_EDITOR"] = editor_command
    if args.journal_jsonl:
        initial_env["LYNCHPIN_HISTORY_JOURNAL_JSONL"] = str(
            Path(args.journal_jsonl).resolve()
        )
    if args.conflict_ledger_jsonl:
        initial_env["LYNCHPIN_HISTORY_CONFLICT_LEDGER_JSONL"] = str(
            Path(args.conflict_ledger_jsonl).resolve()
        )
    continue_env = os.environ.copy()
    continue_env["GIT_EDITOR"] = "true"
    if args.journal_jsonl:
        continue_env["LYNCHPIN_HISTORY_JOURNAL_JSONL"] = str(
            Path(args.journal_jsonl).resolve()
        )
    if args.conflict_ledger_jsonl:
        continue_env["LYNCHPIN_HISTORY_CONFLICT_LEDGER_JSONL"] = str(
            Path(args.conflict_ledger_jsonl).resolve()
        )
    command = [
        "git",
        "rebase",
        "-i",
        "--rebase-merges",
        "--reschedule-failed-exec",
        "--root",
    ]
    env = initial_env
    emit_journal_event(
        "run_structural_plan_started",
        repo=str(repo),
        plan_json=str(Path(args.plan_json).resolve()),
        cli_path=str(cli_path),
    )
    while True:
        emit_journal_event("rebase_command_started", repo=str(repo), command=command)
        result = subprocess.run(command, cwd=repo, check=False, env=env)
        if result.returncode == 0:
            emit_journal_event(
                "run_structural_plan_completed",
                repo=str(repo),
                head_sha=git_stdout(repo, "rev-parse", "HEAD").strip(),
            )
            return 0
        if not auto_resolve_rebase_conflicts(repo):
            emit_journal_event(
                "run_structural_plan_stopped_unresolved",
                repo=str(repo),
                command=command,
                head_sha=git_optional_stdout(repo, "rev-parse", "HEAD").strip(),
            )
            raise subprocess.CalledProcessError(result.returncode, command)
        command = ["git", "rebase", "--continue"]
        env = continue_env


def verify_rollback_drill_cmd(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    backup_ref = args.backup_ref
    bundle = Path(args.bundle).resolve() if args.bundle else None
    result: dict[str, Any] = {
        "repo": str(repo),
        "backup_ref": backup_ref,
        "bundle": str(bundle) if bundle else None,
        "checks": [],
    }
    with tempfile.TemporaryDirectory(prefix="history-cleanup-rollback-") as tmp:
        tmp_root = Path(tmp)
        if backup_ref:
            checkout_dir = tmp_root / "backup-ref"
            git(repo, "worktree", "add", "--detach", str(checkout_dir), backup_ref)
            try:
                result["checks"].append(
                    {
                        "kind": "backup_ref",
                        "restored_head": git_stdout(
                            checkout_dir, "rev-parse", "HEAD"
                        ).strip(),
                        "restored_tree": git_stdout(
                            checkout_dir, "rev-parse", "HEAD^{tree}"
                        ).strip(),
                    }
                )
            finally:
                git(repo, "worktree", "remove", "--force", str(checkout_dir))
        if bundle:
            clone_dir = tmp_root / "bundle-clone"
            subprocess.run(
                ["git", "clone", str(bundle), str(clone_dir)],
                check=True,
                text=True,
                capture_output=True,
            )
            result["checks"].append(
                {
                    "kind": "bundle",
                    "restored_head": git_stdout(clone_dir, "rev-parse", "HEAD").strip(),
                    "restored_tree": git_stdout(
                        clone_dir, "rev-parse", "HEAD^{tree}"
                    ).strip(),
                }
            )
    result["ok"] = bool(result["checks"])
    if args.output_json:
        write_json(Path(args.output_json).resolve(), result)
    print(json.dumps(result, indent=2))
    return 0


def register_structural_subcommands(subparsers: Any) -> None:
    compile_plan = subparsers.add_parser(
        "compile-structural-plan",
        help="Compile sinex structural packs into a canonical operations[] execution plan.",
    )
    compile_plan.add_argument(
        "--repo", default=".", help="Repository root to compile against."
    )
    compile_plan.add_argument(
        "--launch-pack-dir",
        required=True,
        help="Launch-pack directory containing translated selection maps and structural packs.",
    )
    compile_plan.add_argument(
        "--output-json",
        required=True,
        help="Output path for the compiled operations plan.",
    )
    compile_plan.add_argument(
        "--summary-json", help="Optional output path for the compact summary JSON."
    )
    compile_plan.set_defaults(func=compile_cmd)

    patch_todo = subparsers.add_parser(
        "patch-rebase-todo",
        help="Patch a git-rebase todo file by inserting exec lines for compiled structural operations.",
    )
    patch_todo.add_argument(
        "--repo", help="Repository root. Defaults to the repo recorded in the plan."
    )
    patch_todo.add_argument(
        "--plan-json", required=True, help="Compiled structural plan JSON."
    )
    patch_todo.add_argument(
        "--cli-path", help="Path to cli.py used in inserted exec commands."
    )
    patch_todo.add_argument("todo_file", help="Todo file path provided by git rebase.")
    patch_todo.set_defaults(func=patch_todo_cmd)

    apply_op = subparsers.add_parser(
        "apply-structural-op",
        help="Apply one compiled structural band rewrite during an interactive rebase exec step.",
    )
    apply_op.add_argument(
        "--repo", default=".", help="Repository root being rewritten."
    )
    apply_op.add_argument(
        "--plan-json", required=True, help="Compiled structural plan JSON."
    )
    apply_op.add_argument("--op-id", required=True, help="Operation id to apply.")
    apply_op.set_defaults(func=apply_structural_op_cmd)

    preserve_committer = subparsers.add_parser(
        "preserve-picked-commit-committer",
        help="Amend the just-replayed commit back to the original committer metadata for a source SHA.",
    )
    preserve_committer.add_argument(
        "--repo", default=".", help="Repository root being rewritten."
    )
    preserve_committer.add_argument(
        "--source-sha",
        required=True,
        help="Original source commit SHA whose committer metadata should be preserved.",
    )
    preserve_committer.set_defaults(func=preserve_picked_commit_committer_cmd)

    compare_trees = subparsers.add_parser(
        "compare-repo-trees",
        help="Compare tracked-tree shape and content between two repos/refs and emit a scorecard.",
    )
    compare_trees.add_argument(
        "--left-repo", required=True, help="Reference repo path."
    )
    compare_trees.add_argument(
        "--right-repo", required=True, help="Candidate rewritten repo path."
    )
    compare_trees.add_argument(
        "--left-ref", default="HEAD", help="Git ref to compare in the left repo."
    )
    compare_trees.add_argument(
        "--right-ref", default="HEAD", help="Git ref to compare in the right repo."
    )
    compare_trees.add_argument(
        "--sample-limit",
        type=int,
        default=50,
        help="Maximum sample entries to retain per category.",
    )
    compare_trees.add_argument(
        "--output-json", help="Optional output path for the scorecard JSON."
    )
    compare_trees.set_defaults(func=compare_repo_trees_cmd)

    filter_plan = subparsers.add_parser(
        "filter-structural-plan",
        help="Filter a compiled structural operations plan down to a reduced candidate set.",
    )
    filter_plan.add_argument(
        "--plan-json", required=True, help="Compiled structural plan JSON to filter."
    )
    filter_plan.add_argument(
        "--exclude-op-id",
        action="append",
        default=[],
        help="Operation id to exclude. Repeatable.",
    )
    filter_plan.add_argument(
        "--exclude-op-list-json", help="JSON file containing operation ids to exclude."
    )
    filter_plan.add_argument(
        "--output-json", required=True, help="Output path for the filtered plan JSON."
    )
    filter_plan.add_argument(
        "--summary-json",
        help="Optional output path for the filtered-plan summary JSON.",
    )
    filter_plan.set_defaults(func=filter_structural_plan_cmd)

    run_plan = subparsers.add_parser(
        "run-structural-plan",
        help="Run git rebase --rebase-merges --root with the compiled structural execution plan injected automatically.",
    )
    run_plan.add_argument(
        "--repo", default=".", help="Repository root being rewritten."
    )
    run_plan.add_argument(
        "--plan-json", required=True, help="Compiled structural plan JSON."
    )
    run_plan.add_argument(
        "--cli-path",
        help="Path to cli.py. Defaults to the portable history_cleanup cli.py.",
    )
    run_plan.add_argument(
        "--journal-jsonl",
        help="Optional JSONL journal path for structural replay progress.",
    )
    run_plan.add_argument(
        "--conflict-ledger-jsonl",
        help="Optional JSONL ledger path for conflict classifications and resolutions.",
    )
    run_plan.set_defaults(func=run_structural_plan_cmd)

    rollback_drill = subparsers.add_parser(
        "verify-rollback-drill",
        help="Verify that backup refs and/or bundles can be restored and report recovered HEAD/tree hashes.",
    )
    rollback_drill.add_argument(
        "--repo", default=".", help="Repository root whose backups are being checked."
    )
    rollback_drill.add_argument(
        "--backup-ref", help="Local backup ref to restore in a disposable worktree."
    )
    rollback_drill.add_argument("--bundle", help="Git bundle path to clone and verify.")
    rollback_drill.add_argument(
        "--output-json", help="Optional output path for the rollback verification JSON."
    )
    rollback_drill.set_defaults(func=verify_rollback_drill_cmd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Structural history-rewrite helpers for compiled split/merge/reorder plans."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_structural_subcommands(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
