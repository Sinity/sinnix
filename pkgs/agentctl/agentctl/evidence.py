"""Read original native evidence records, including their exact retained artifacts."""

from __future__ import annotations

import hashlib
import heapq
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import job_queries
from .job_queries import JobError

if TYPE_CHECKING:
    from .config import Config

RECORD_SCHEMA_VERSION = 1
MAX_EVIDENCE_BYTES = 256 * 1024
MAX_RECORDS = 1_000
MAX_PAGE_SIZE = 100
MAX_ARTIFACT_BYTES = (
    100 * job_queries.MAX_OUTCOME_BYTES
    + job_queries.MAX_LAUNCH_INPUT_BYTES
    + MAX_EVIDENCE_BYTES
)


def _records_dir(config: Config) -> Path:
    return config.state_dir / "native-evidence"


def get_record(config: Config, project_id: str, evidence_id: str) -> dict[str, Any]:
    """Retrieve one immutable evidence artifact and verify its content identity."""
    if not re.fullmatch(r"[0-9a-f]{32}", evidence_id):
        raise JobError("invalid native evidence id")
    path = _records_dir(config) / f"{evidence_id}.json"
    raw = job_queries.read_bounded(path, MAX_EVIDENCE_BYTES + 1)
    if raw is None or len(raw) > MAX_EVIDENCE_BYTES:
        raise JobError(
            f"native evidence record is unavailable or oversized: {evidence_id}"
        )
    try:
        pointer = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise JobError(f"invalid native evidence reference: {evidence_id}") from error
    if not isinstance(pointer, dict) or pointer.get("evidence_id") != evidence_id:
        raise JobError(f"invalid native evidence reference: {evidence_id}")
    if pointer.get("project") != project_id:
        raise JobError(
            f"native evidence record does not belong to project {project_id}"
        )
    if (
        pointer.get("kind") == "native_evidence_reference"
        and pointer.get("schema_version") == 2
    ):
        artifact_name = pointer.get("artifact")
        if artifact_name != f"{evidence_id}.artifact.json":
            raise JobError("native evidence reference has an invalid artifact path")
        artifact_raw = job_queries.read_bounded(
            _records_dir(config) / artifact_name, MAX_ARTIFACT_BYTES + 1
        )
        if artifact_raw is None or len(artifact_raw) > MAX_ARTIFACT_BYTES:
            raise JobError(
                f"native evidence artifact is unavailable or oversized: {evidence_id}"
            )
        if len(artifact_raw) != pointer.get("bytes"):
            raise JobError(f"native evidence artifact size mismatch: {evidence_id}")
        if hashlib.sha256(artifact_raw).hexdigest() != pointer.get("sha256"):
            raise JobError(f"native evidence artifact identity mismatch: {evidence_id}")
        try:
            value = json.loads(artifact_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise JobError(
                f"invalid native evidence artifact: {evidence_id}"
            ) from error
        if (
            not isinstance(value, dict)
            or value.get("evidence_id") != evidence_id
            or value.get("project") != project_id
        ):
            raise JobError(
                f"native evidence artifact does not match its reference: {evidence_id}"
            )
        return value
    if (
        pointer.get("kind") == "native_evidence"
        and pointer.get("schema_version") == RECORD_SCHEMA_VERSION
    ):
        return pointer
    raise JobError(f"invalid native evidence reference: {evidence_id}")


def list_records(
    config: Config,
    project_id: str,
    *,
    cursor: str | None = None,
    limit: int = MAX_PAGE_SIZE,
) -> dict[str, Any]:
    """Return bounded summaries; cursor advances through the shared record directory."""
    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise JobError(f"native evidence list limit must be 1..{MAX_PAGE_SIZE}")
    if cursor is not None and (
        not isinstance(cursor, str)
        or len(cursor) > 255
        or not re.fullmatch(r"[A-Za-z0-9._-]+", cursor)
    ):
        raise JobError("invalid native evidence list cursor")
    directory = _records_dir(config)
    document: dict[str, Any] = {
        "schema_version": 1,
        "owner": "agentctl",
        "interface": "agentctl.evidence.list",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "project": project_id,
        "records": [],
        "coverage": "retained_records",
        "gaps": [],
        "next_cursor": None,
    }
    try:
        entries = os.scandir(directory)
    except FileNotFoundError:
        return document
    except OSError as error:
        return {**document, "coverage": "unavailable", "gaps": [str(error)]}
    records: list[dict[str, Any]] = []
    try:
        paths = heapq.nsmallest(
            MAX_RECORDS + 1,
            (
                entry.name
                for entry in entries
                if entry.name.endswith(".json")
                and not entry.name.endswith(".artifact.json")
                and (cursor is None or entry.name > cursor)
            ),
        )
        page_paths = paths[:MAX_RECORDS]
        scanned: list[str] = []
        for path_name in page_paths:
            scanned.append(path_name)
            path = directory / path_name
            raw = job_queries.read_bounded(path, MAX_EVIDENCE_BYTES + 1)
            if raw is None or len(raw) > MAX_EVIDENCE_BYTES:
                document["coverage"] = "partial"
                document["gaps"].append(f"unreadable or oversized record: {path.name}")
                continue
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                document["coverage"] = "partial"
                document["gaps"].append(f"invalid record: {path.name}")
                continue
            if not isinstance(value, dict):
                document["coverage"] = "partial"
                document["gaps"].append(f"invalid record: {path.name}")
                continue
            if value.get("project") != project_id:
                continue
            if (
                value.get("kind") == "native_evidence_reference"
                and value.get("schema_version") == 2
            ):
                if (
                    not re.fullmatch(
                        r"[0-9a-f]{32}", str(value.get("evidence_id") or "")
                    )
                    or path_name != f"{value.get('evidence_id')}.json"
                    or value.get("artifact")
                    != f"{value.get('evidence_id')}.artifact.json"
                    or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256") or ""))
                    or type(value.get("bytes")) is not int
                    or not 0 < value["bytes"] <= MAX_ARTIFACT_BYTES
                ):
                    document["coverage"] = "partial"
                    document["gaps"].append(f"invalid reference: {path.name}")
                    continue
                records.append(
                    {
                        key: value.get(key)
                        for key in (
                            "evidence_id",
                            "project",
                            "recorded_at",
                            "sha256",
                            "bytes",
                        )
                    }
                )
            elif (
                value.get("schema_version") == RECORD_SCHEMA_VERSION
                and value.get("kind") == "native_evidence"
            ):
                encoded = json.dumps(
                    value, sort_keys=True, separators=(",", ":")
                ).encode()
                records.append(
                    {
                        "evidence_id": value.get("evidence_id"),
                        "project": project_id,
                        "recorded_at": value.get("recorded_at"),
                        "sha256": hashlib.sha256(encoded).hexdigest(),
                        "bytes": len(encoded),
                    }
                )
            else:
                document["coverage"] = "partial"
                document["gaps"].append(f"unsupported record: {path.name}")
            if len(records) >= limit:
                break
        if len(paths) > len(scanned) and scanned:
            document["next_cursor"] = scanned[-1]
            document["coverage"] = "partial"
            document["gaps"].append(
                "more retained records are available; continue with next_cursor"
            )
    except OSError as error:
        return {**document, "coverage": "unavailable", "gaps": [str(error)]}
    finally:
        entries.close()
    document["records"] = sorted(
        records, key=lambda row: str(row.get("evidence_id") or "")
    )
    return document
