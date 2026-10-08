"""Bounded authored classification reads; payloads and native stores are not opened."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

# Read authored definitions directly. These operations neither inspect payloads
# nor require a multi-million-row inventory/materialization to be current.
JUDGMENT_FACETS = ("topic", "role", "maintenance_owner", "preservation")
JUDGMENT_LIMIT_BYTES = 8 << 20

# A small controlled role is distinct from the original descriptive wording.
# The ledger retains detail and attributed source decisions; categories never
# grant deletion permission or establish backup, lifecycle, or claim validity.
from .taxonomy import ROLE_VOCABULARY, ROLE_VOCABULARY_VERSION, LEGACY_ROLES


def validate_role_decisions(ledger: dict) -> list[dict]:
    """Validate known role values on explicit import, not historical reads."""
    issues = []
    for entry in ledger["valid"]:
        record = entry["record"]
        if record["field"] != "role" or (record.get("observation") or "known") != "known":
            continue
        value = record["value"]
        if not isinstance(value, str) or value not in ROLE_VOCABULARY:
            issues.append({"line": entry["line"], "value": value,
                           "reason": "noncanonical role; choose a vocabulary value and retain wording in detail"})
        elif "detail" in record and not isinstance(record["detail"], str):
            issues.append({"line": entry["line"], "reason": "role detail must be text"})
    return issues


def effective_role_audit(ledger: dict, targets: list[str]) -> dict:
    counts, noncanonical = Counter(), []
    for path in targets:
        result = resolve_judgments(ledger, path).get("role", {})
        status, value = result.get("status", "not-recorded"), result.get("value")
        if status != "known":
            counts["[" + status + "]"] += 1
        elif isinstance(value, str) and value in ROLE_VOCABULARY:
            counts[value] += 1
        else:
            noncanonical.append({"path": path, "via": result.get("via"), "value": value})
    return {"vocabulary": ROLE_VOCABULARY_VERSION, "counts": dict(sorted(counts.items())),
            "noncanonical": noncanonical}



def judgment_target(target: str) -> tuple[str, str]:
    if target.startswith("sha256:"):
        digest = target[7:]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("sha256 target is not a 64-digit full digest")
        return "sha256", digest.lower()
    if not target.startswith("prefix:"):
        raise ValueError("target must be prefix:/absolute/path or sha256:<full digest>")
    path = target[7:]
    if not path.startswith("/") or any(ord(c) < 32 for c in path):
        raise ValueError("prefix target requires an absolute path without control characters")
    if path.startswith("//") or os.path.normpath(path) != path.rstrip("/") and path != "/":
        raise ValueError("prefix target must be normalized; dot segments are not interpreted")
    return "prefix", path.rstrip("/") or "/"


def read_judgments(path: Path) -> dict:
    with path.open("rb") as handle:
        raw = handle.read(JUDGMENT_LIMIT_BYTES + 1)
    if len(raw) > JUDGMENT_LIMIT_BYTES:
        raise ValueError("judgment ledger exceeds the 8 MiB read bound")
    valid, issues, total = [], [], 0
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        total += 1
        if total > 25000:
            raise ValueError("judgment ledger exceeds the 25,000-record bound")
        try:
            record = json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except ValueError as exc:
            raise ValueError(f"Malformed JSON at ledger line {number}; no partial result") from exc
        try:
            if not isinstance(record, dict):
                raise ValueError("record is not an object")
            for key in ("target", "field", "method", "ts", "evidence"):
                if not isinstance(record.get(key), str) or not record[key].strip():
                    raise ValueError(f"missing or non-text {key}")
            if "value" not in record:
                raise ValueError("record has no value")
            kind, address = judgment_target(record["target"])
            timestamp = dt.datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("timestamp must state a timezone")
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            valid.append({"record": record, "line": number,
                          "record_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
                          "kind": kind, "address": address, "timestamp": timestamp.timestamp()})
        except (ValueError, TypeError) as exc:
            issues.append({"line": number, "reason": str(exc)})
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "records": total, "valid": valid, "issues": issues}


def resolve_judgments(ledger: dict, path: str) -> dict:
    """Per target: operator tier, then decision time. Per field: specificity.

    Equal-priority conflicting decisions remain ambiguous, rather than using
    iteration order as a hidden policy. Unknown/withheld child rules mask an
    inherited value. Path lookup does not guess or calculate a content digest.
    """
    _, path = judgment_target("prefix:" + path)
    grouped = {}
    for entry in ledger["valid"]:
        prefix = entry["address"]
        if entry["kind"] != "prefix" or not (path == prefix or path.startswith(prefix.rstrip("/") + "/")):
            continue
        grouped.setdefault((prefix, entry["record"]["field"]), []).append(entry)
    candidates = {}
    for (prefix, field), entries in grouped.items():
        rank = lambda e: (e["record"]["method"] == "operator", e["timestamp"])
        best = max(map(rank, entries))
        selected = [e for e in entries if rank(e) == best]
        candidates.setdefault(field, []).append((prefix, selected))
    output = {}
    for field, options in sorted(candidates.items()):
        prefix, selected = max(options, key=lambda item: len(item[0]))
        def signature(entry):
            record = entry["record"]
            value = record["value"]
            status = record.get("observation") or "known"
            if field == "role" and status == "known" and isinstance(value, str):
                value = LEGACY_ROLES.get(value, value)
            return json.dumps([value, status], sort_keys=True)
        signatures = {signature(entry) for entry in selected}
        evidence = [{"line": e["line"], "record_sha256": e["record_sha256"],
                     "decision": e["record"]} for e in sorted(selected,key=lambda e:e["line"])]
        if len(signatures) > 1:
            output[field] = {"status": "ambiguous", "via": prefix, "evidence": evidence}
        else:
            record = selected[0]["record"]
            output[field] = {"status": record.get("observation") or "known",
                             "value": record["value"], "via": prefix, "evidence": evidence}
            details = list(dict.fromkeys(e["record"].get("detail") for e in selected
                                         if isinstance(e["record"].get("detail"), str)))
            if field == "role":
                details = list(dict.fromkeys([
                    *(e["record"]["value"] for e in selected
                      if isinstance(e["record"]["value"], str)
                      and LEGACY_ROLES.get(e["record"]["value"], e["record"]["value"]) != e["record"]["value"]),
                    *details,
                ]))
            if details:
                output[field]["details"] = details
    role = output.get("role", {})
    if role.get("status") == "known" and isinstance(role.get("value"), str) and role["value"] in LEGACY_ROLES:
        original = role["value"]
        role["value"] = LEGACY_ROLES[original]
        if original != role["value"]:
            role["details"] = list(dict.fromkeys([original, *role.get("details", [])]))
    if role:
        role["vocabulary"] = ROLE_VOCABULARY_VERSION
    return output
