from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import anyio
from jsonschema import Draft202012Validator

from .app import create_server
from .config import GatewayConfig
from .contracts import VerbFamily
from .registry import REGISTRY, RegistryError

MAX_INPUT_BYTES = 262_144
VERB_TO_TOOL = {verb.value: verb.value for verb in VerbFamily}


class CliInputError(ValueError):
    """A request that must be rejected before it reaches an owner route."""


def _read_bounded(stream: Any, limit: int, source: str) -> bytes:
    raw = (
        stream.buffer.read(limit + 1)
        if hasattr(stream, "buffer")
        else stream.read(limit + 1)
    )
    if isinstance(raw, str):
        raw = raw.encode()
    if len(raw) > limit:
        raise CliInputError(f"{source} exceeds the {limit}-byte JSON input bound")
    return raw


def load_json_input(
    *,
    inline: str | None = None,
    input_file: Path | None = None,
    use_stdin: bool = False,
    stdin: Any | None = None,
    max_bytes: int = MAX_INPUT_BYTES,
) -> dict[str, Any]:
    selected = sum(value is not None for value in (inline, input_file)) + int(use_stdin)
    if selected > 1:
        raise CliInputError("choose exactly one of --input, --input-file, or --stdin")
    if inline is not None:
        raw = inline.encode()
        if len(raw) > max_bytes:
            raise CliInputError(
                f"--input exceeds the {max_bytes}-byte JSON input bound"
            )
    elif input_file is not None:
        try:
            with input_file.open("rb") as handle:
                raw = handle.read(max_bytes + 1)
        except OSError as exc:
            raise CliInputError(
                f"cannot read --input-file {input_file}: {exc}"
            ) from exc
        if len(raw) > max_bytes:
            raise CliInputError(
                f"--input-file {input_file} exceeds the {max_bytes}-byte JSON input bound"
            )
    elif use_stdin:
        raw = _read_bounded(sys.stdin if stdin is None else stdin, max_bytes, "stdin")
    else:
        return {}
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliInputError("request input must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise CliInputError("request input must be a JSON object")
    return value


def _set_value(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if key in payload and payload[key] != value:
        raise CliInputError(
            f"request contains a different value for --{key.replace('_', '-')}"
        )
    payload[key] = value


def _json_object(value: str, flag: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CliInputError(f"{flag} must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise CliInputError(f"{flag} must be a JSON object")
    return parsed


def catalog_search_text(query: str) -> str:
    """Turn a human need into the bounded registry text filter it best matches."""
    terms = [term.casefold() for term in re.findall(r"[A-Za-z0-9_.:-]{3,}", query)]
    if not terms:
        return query
    rows = REGISTRY.documentation_rows()
    searchable = [
        " ".join(
            [
                row["name"],
                row["domain"],
                row["owner"],
                row["route"],
                row["documentation"],
                *row["resource_kinds"],
            ]
        ).casefold()
        for row in rows["actions"]
    ]
    ranked = sorted(
        terms,
        key=lambda term: (sum(term in text for text in searchable), len(term), term),
        reverse=True,
    )
    return ranked[0] if any(ranked[0] in text for text in searchable) else query


def build_request(
    command: str,
    *,
    inline: str | None = None,
    input_file: Path | None = None,
    use_stdin: bool = False,
    stdin: Any | None = None,
    action_name: str | None = None,
    ref: str | None = None,
    operation: str | None = None,
    parameters: str | None = None,
    query: str | None = None,
    request_id: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
    deadline_at: float | None = None,
    preconditions: str | None = None,
    preview: bool = False,
    apply: bool = False,
) -> dict[str, Any]:
    payload = load_json_input(
        inline=inline, input_file=input_file, use_stdin=use_stdin, stdin=stdin
    )
    _set_value(payload, "action_name", action_name)
    _set_value(payload, "ref", ref)
    _set_value(payload, "operation", operation)
    _set_value(payload, "request_id", request_id)
    _set_value(payload, "actor", actor)
    _set_value(payload, "reason", reason)
    _set_value(payload, "idempotency_key", idempotency_key)
    _set_value(payload, "deadline_at", deadline_at)
    if parameters is not None:
        _set_value(payload, "parameters", _json_object(parameters, "--parameters"))
    if query is not None:
        _set_value(
            payload,
            "text" if command == "catalog" else "query",
            catalog_search_text(query) if command == "catalog" else query,
        )
    if preconditions is not None:
        _set_value(
            payload, "preconditions", _json_object(preconditions, "--preconditions")
        )
    if preview and apply:
        raise CliInputError("--preview and --apply are mutually exclusive")
    if command == "change" and (preview or apply):
        selected = payload.get("action_name")
        if selected == "beads.changeset":
            _set_value(payload, "operation", "preview" if preview else "apply")
        elif selected == "beads.change":
            mutation = dict(payload.get("parameters") or {})
            _set_value(mutation, "mode", "preview" if preview else "apply")
            payload["parameters"] = mutation
        else:
            raise CliInputError("--preview and --apply require a Beads change action")
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    except (TypeError, ValueError) as exc:
        raise CliInputError("request input must be JSON serializable") from exc
    if len(encoded) > MAX_INPUT_BYTES:
        raise CliInputError(
            f"request exceeds the {MAX_INPUT_BYTES}-byte JSON input bound"
        )
    return payload


def _schema_payload(command: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt a ten-verb selector request to the selected action's input schema."""
    result = dict(payload)
    selected = result.get("action_name")
    if command in {"query", "run", "change", "operate"} and isinstance(selected, str):
        try:
            action = REGISTRY.action(selected)
        except RegistryError:
            return result
        if "action_name" not in action.input_schema.get("properties", {}):
            result.pop("action_name", None)
        if selected == "machine.operate" and "operation" in result:
            result["action"] = result.pop("operation")
    return result


def validate_request(command: str, payload: Mapping[str, Any], principal: str) -> None:
    if command not in VERB_TO_TOOL:
        return
    action_name = {
        "status": "gateway.status",
        "catalog": "gateway.catalog",
        "get": "resources.get",
        "context": "projects.context",
        "events": "audit.events",
        "wait": "jobs.wait",
    }.get(command, payload.get("action_name"))
    if not isinstance(action_name, str):
        raise CliInputError(f"{command} requires --action or input.action_name")
    try:
        action = REGISTRY.action(action_name)
    except RegistryError:
        return
    if principal not in action.principals:
        return
    candidate = _schema_payload(command, payload)
    validator = Draft202012Validator(action.input_schema)
    errors = sorted(
        validator.iter_errors(candidate), key=lambda error: list(error.path)
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "request"
        raise CliInputError(f"{location}: {error.message}")


def _structured_response(response: Any) -> dict[str, Any]:
    if isinstance(response, Mapping):
        return dict(response)
    structured = getattr(response, "structured_content", None)
    if isinstance(structured, Mapping):
        return dict(structured)
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        value = model_dump(mode="json", by_alias=True)
        if isinstance(value, dict):
            return value
    raise RuntimeError("gateway MCP call returned no structured normalized envelope")


async def invoke_mcp(
    config: GatewayConfig, principal: str, command: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    validate_request(command, payload, principal)
    server = create_server(config, principal)
    response = await server.call_tool(VERB_TO_TOOL[command], dict(payload))
    return _structured_response(response)


def invoke(
    config: GatewayConfig, principal: str, command: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    return anyio.run(invoke_mcp, config, principal, command, payload)


def _action_row(action_name: str, principal: str) -> dict[str, Any]:
    try:
        return REGISTRY.action_schema(action_name, principal)["action"]
    except RegistryError as exc:
        raise CliInputError(str(exc)) from exc


def catalog_display(
    *,
    principal: str,
    action_name: str | None = None,
    schema: bool = False,
    example: bool = False,
    explain: bool = False,
    complete: str | None = None,
) -> dict[str, Any]:
    if action_name is not None and (schema or example or explain):
        row = _action_row(action_name, principal)
        if schema:
            return {
                "revision": REGISTRY.revision,
                "action": row,
                "schema": row["input_schema"],
            }
        if example:
            return {
                "revision": REGISTRY.revision,
                "action": action_name,
                "examples": row["examples"],
            }
        return {
            "revision": REGISTRY.revision,
            "action": row,
            "request": row["examples"][0]["input"] if row["examples"] else None,
        }
    if complete is not None:
        prefix = complete.casefold()
        return {
            "revision": REGISTRY.revision,
            "resources": [
                row["contract_ref"]
                for row in REGISTRY.documentation_rows()["resources"]
                if row["contract_ref"].casefold().startswith(prefix)
            ],
            "actions": [
                row["schema_ref"]
                for row in REGISTRY.documentation_rows()["actions"]
                if row["schema_ref"].casefold().startswith(prefix)
            ],
        }
    raise CliInputError(
        "catalog display requires --schema, --example, --explain, or --complete"
    )
