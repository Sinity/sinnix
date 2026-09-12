"""Agent result contracts: the worker result and the reviewer verdict.

Both schemas live beside the agent definitions
(`dots/claude/agents/schemas/*.schema.json`) for the backends' structured
output flags; the same documents are embedded here so validation needs no
checkout. Neither carries a `$schema` key: `claude --json-schema` rejects
it. The validator covers the JSON Schema subset those documents use:
object/array/string/number/boolean types, required, additionalProperties,
enum, pattern, minItems, minLength, minimum and maximum.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

SHA_PATTERN = "^[0-9a-f]{40}$"
RESULT_SCHEMA_VERSION = 2

USAGE_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "properties": {
        "input_tokens": {"type": "integer", "minimum": 0},
        "output_tokens": {"type": "integer", "minimum": 0},
        "total_tokens": {"type": "integer", "minimum": 0},
        "duration_seconds": {"type": "number", "minimum": 0},
    },
}

WORKER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidate_sha", "beads", "unresolved", "verification"],
    "properties": {
        # Version one is intentionally still accepted: old results carry
        # unknown provenance rather than invented evidence. Version two makes
        # machine-readable campaign evidence explicit below.
        "schema_version": {"type": "integer", "enum": [RESULT_SCHEMA_VERSION]},
        "planned_model": {"type": "string", "minLength": 1},
        # Absent means the executor did not report a model; never infer it
        # from a launch's requested model.
        "actual_executor_model": {"type": "string", "minLength": 1},
        "actual_executor_observed_by": {
            "type": "string",
            "enum": ["runner", "external_harness", "native"],
        },
        "execution": {"type": "string", "enum": ["queued", "external", "native"]},
        "parent_session_ref": {"type": "string", "minLength": 1},
        "child_session_ref": {"type": "string", "minLength": 1},
        "attempt": {"type": "integer", "minimum": 1},
        "model_segments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["attempt"],
                "properties": {
                    "attempt": {"type": "integer", "minimum": 1},
                    "planned_model": {"type": "string", "minLength": 1},
                    "actual_executor_model": {"type": "string", "minLength": 1},
                    "actual_executor_observed_by": {
                        "type": "string",
                        "enum": ["runner", "external_harness", "native"],
                    },
                    "measured_usage": USAGE_SCHEMA,
                },
            },
        },
        "measured_usage": USAGE_SCHEMA,
        "candidate_sha": {"type": "string", "pattern": SHA_PATTERN},
        "beads": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "criteria"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "bead_revision": {"type": "string", "minLength": 1},
                    "criteria": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["text", "status", "evidence"],
                            "properties": {
                                "ac_id": {"type": "string", "minLength": 1},
                                "text": {"type": "string", "minLength": 1},
                                "status": {
                                    "type": "string",
                                    "enum": ["satisfied", "unsatisfied", "superseded"],
                                },
                                "evidence": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "unresolved": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "verification": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["command", "receipt"],
                "properties": {
                    "command": {"type": "string", "minLength": 1},
                    "receipt": {"type": "string"},
                    "tested_sha": {"type": "string", "pattern": SHA_PATTERN},
                    "status": {
                        "type": "string",
                        "enum": ["passed", "failed", "skipped"],
                    },
                    "coverage": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["ac_ids", "scope"],
                        "properties": {
                            "ac_ids": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1},
                            },
                            "scope": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        },
    },
}

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "verdict",
        "confidence",
        "evidence",
        "refutation_attempted",
        "unsupported",
    ],
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail", "unsupported"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "refutation_attempted": {"type": "boolean"},
        "unsupported": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}

SCHEMAS: dict[str, dict[str, Any]] = {"worker": WORKER_SCHEMA, "judge": JUDGE_SCHEMA}

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "null": (type(None),),
}


def _type_ok(value: Any, name: str | Sequence[str]) -> bool:
    if isinstance(name, Sequence) and not isinstance(name, str):
        return any(_type_ok(value, candidate) for candidate in name)
    if name in {"number", "integer"} and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[name])


def validate(schema: Mapping[str, Any], value: Any, *, path: str = "$") -> list[str]:
    """Every violation of ``schema`` in ``value`` as a ``<path>: <reason>`` line."""
    errors: list[str] = []
    expected = schema.get("type")
    if isinstance(expected, (str, list)) and not _type_ok(value, expected):
        return [f"{path}: expected {expected}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            errors.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above {schema['maximum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        items = schema.get("items")
        if isinstance(items, Mapping):
            for index, item in enumerate(value):
                errors.extend(validate(items, item, path=f"{path}[{index}]"))
    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for name in schema.get("required") or ():
            if name not in value:
                errors.append(f"{path}: missing {name}")
        if schema.get("additionalProperties") is False:
            for name in value:
                if name not in properties:
                    errors.append(f"{path}: unexpected {name}")
        for name, subschema in properties.items():
            if name in value:
                errors.extend(validate(subschema, value[name], path=f"{path}.{name}"))
    return errors


def validate_worker_result(obj: Any) -> list[str]:
    """Errors against the worker result schema; an empty list means valid."""
    errors = validate(WORKER_SCHEMA, obj)
    # Never add semantic diagnostics by traversing an object that structural
    # validation already proved malformed.
    if errors:
        return errors
    if (
        not isinstance(obj, Mapping)
        or obj.get("schema_version") != RESULT_SCHEMA_VERSION
    ):
        return errors
    for field in ("execution", "attempt", "model_segments", "measured_usage"):
        if field not in obj:
            errors.append(f"$: version {RESULT_SCHEMA_VERSION} missing {field}")
    if "actual_executor_model" in obj and "actual_executor_observed_by" not in obj:
        errors.append(
            f"$: version {RESULT_SCHEMA_VERSION} actual_executor_model missing actual_executor_observed_by"
        )
    for bead_index, bead in enumerate(obj.get("beads") or ()):
        if not isinstance(bead, Mapping):
            continue
        if "bead_revision" not in bead:
            errors.append(
                f"$.beads[{bead_index}]: version {RESULT_SCHEMA_VERSION} missing bead_revision"
            )
        ac_ids: set[str] = set()
        for criterion_index, criterion in enumerate(bead.get("criteria") or ()):
            if isinstance(criterion, Mapping) and "ac_id" not in criterion:
                errors.append(
                    f"$.beads[{bead_index}].criteria[{criterion_index}]: version {RESULT_SCHEMA_VERSION} missing ac_id"
                )
            elif isinstance(criterion, Mapping):
                ac_id = criterion.get("ac_id")
                if isinstance(ac_id, str) and ac_id in ac_ids:
                    errors.append(
                        f"$.beads[{bead_index}].criteria[{criterion_index}]: duplicate ac_id {ac_id}"
                    )
                elif isinstance(ac_id, str):
                    ac_ids.add(ac_id)
    for verification_index, verification in enumerate(obj.get("verification") or ()):
        if not isinstance(verification, Mapping):
            continue
        for field in ("tested_sha", "status", "coverage"):
            if field not in verification:
                errors.append(
                    f"$.verification[{verification_index}]: version {RESULT_SCHEMA_VERSION} missing {field}"
                )
    for segment_index, segment in enumerate(obj.get("model_segments") or ()):
        if (
            isinstance(segment, Mapping)
            and "actual_executor_model" in segment
            and "actual_executor_observed_by" not in segment
        ):
            errors.append(
                f"$.model_segments[{segment_index}]: actual_executor_model missing actual_executor_observed_by"
            )
    return errors


def validate_judge_verdict(obj: Any) -> list[str]:
    """Errors against the reviewer verdict schema; an empty list means valid."""
    return validate(JUDGE_SCHEMA, obj)


def load_result(path: Path, *, kind: str) -> tuple[Any, list[str]]:
    """The JSON document at ``path`` and its errors against ``kind``'s schema.

    A backend that prints a JSON envelope around the structured output
    (`claude --output-format json`) is unwrapped by the runner; here a
    document whose top level is that envelope is still read through its
    ``structured_output`` field so a raw capture validates the same way.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        return None, [f"{path}: {error}"]
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        return None, [f"{path}: not JSON ({error})"]
    if isinstance(value, dict) and "structured_output" in value:
        value = value["structured_output"]
    if kind == "worker":
        return value, validate_worker_result(value)
    return value, validate(SCHEMAS[kind], value)


def write_schema(path: Path, kind: str) -> Path:
    """Write ``kind``'s schema document for a backend's structured-output flag."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SCHEMAS[kind], indent=2) + "\n")
    return path


def satisfied_beads(results: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    """Per bead named in any result: whether every criterion is satisfied.

    A bead with no criteria at all is not satisfied: acceptance needs evidence.
    A criterion marked superseded counts as satisfied.
    """
    verdicts: dict[str, bool] = {}
    for result in results:
        for entry in result.get("beads") or ():
            bead_id = str(entry.get("id") or "")
            criteria = entry.get("criteria") or []
            satisfied = bool(criteria) and all(
                item.get("status") in {"satisfied", "superseded"} for item in criteria
            )
            verdicts[bead_id] = verdicts.get(bead_id, True) and satisfied
    return verdicts
