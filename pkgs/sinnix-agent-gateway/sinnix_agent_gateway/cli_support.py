from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import anyio
from pydantic import ValidationError

from . import actions as action_set
from .action import Action
from .app import create_server
from .config import GatewayConfig

MAX_INPUT_BYTES = 262_144


class CliInputError(ValueError):
    pass


def _read_bounded(stream: Any, limit: int, source: str) -> bytes:
    data = stream.read(limit + 1)
    if isinstance(data, str):
        data = data.encode()
    if len(data) > limit:
        raise CliInputError(f"{source} exceeds the {limit}-byte JSON input bound")
    return data


def load_json_input(
    *,
    inline: str | None = None,
    input_file: Path | None = None,
    use_stdin: bool = False,
    stdin: Any | None = None,
) -> dict[str, Any]:
    sources = [value for value in (inline, input_file, use_stdin or None) if value]
    if len(sources) > 1:
        raise CliInputError("give at most one of --input, --input-file, --stdin")
    if inline is not None:
        raw = inline.encode()
        if len(raw) > MAX_INPUT_BYTES:
            raise CliInputError(f"--input exceeds the {MAX_INPUT_BYTES}-byte bound")
    elif input_file is not None:
        with input_file.open("rb") as handle:
            raw = _read_bounded(handle, MAX_INPUT_BYTES, "--input-file")
    elif use_stdin:
        raw = _read_bounded(stdin or sys.stdin.buffer, MAX_INPUT_BYTES, "--stdin")
    else:
        return {}
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise CliInputError("request input is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise CliInputError("request input must be a JSON object")
    return payload


def _set_value(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if key in payload and payload[key] != value:
        raise CliInputError(f"{key} is given twice with different values")
    payload[key] = value


def _coerce(value: str) -> Any:
    try:
        return json.loads(value)
    except ValueError:
        return value


def build_request(
    *,
    inline: str | None = None,
    input_file: Path | None = None,
    use_stdin: bool = False,
    stdin: Any | None = None,
    assignments: list[str] | None = None,
    request_id: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
    deadline_at: float | None = None,
) -> dict[str, Any]:
    """Merge the JSON source with ``--set key=value`` pairs and request controls."""
    payload = load_json_input(
        inline=inline, input_file=input_file, use_stdin=use_stdin, stdin=stdin
    )
    for assignment in assignments or []:
        key, separator, value = assignment.partition("=")
        if not separator or not key:
            raise CliInputError("--set expects key=value (value may be JSON)")
        _set_value(payload, key, _coerce(value))
    _set_value(payload, "request_id", request_id)
    _set_value(payload, "actor", actor)
    _set_value(payload, "reason", reason)
    _set_value(payload, "idempotency_key", idempotency_key)
    _set_value(payload, "deadline_at", deadline_at)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_INPUT_BYTES:
        raise CliInputError(f"request exceeds the {MAX_INPUT_BYTES}-byte input bound")
    return payload


def select_action(action_name: str, principal: str) -> Action:
    action = action_set.BY_NAME.get(action_name)
    if action is None:
        candidates = sorted(
            name for name in action_set.BY_NAME if action_name.casefold() in name
        )
        hint = f"; did you mean {', '.join(candidates[:5])}" if candidates else ""
        raise CliInputError(f"unknown action {action_name!r}{hint}")
    if principal not in action.principals:
        raise CliInputError(
            f"principal {principal!r} cannot invoke {action_name}; allowed: "
            + ", ".join(sorted(action.principals))
        )
    return action


def validate_request(action: Action, payload: Mapping[str, Any]) -> None:
    try:
        action.Input.model_validate(dict(payload))
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "request"
        raise CliInputError(f"{location}: {first.get('msg')}") from exc


def _structured_response(response: Any) -> dict[str, Any]:
    if isinstance(response, Mapping):
        return dict(response)
    structured = getattr(response, "structured_content", None)
    if isinstance(structured, Mapping):
        return dict(structured)
    raise RuntimeError("gateway MCP call returned no structured envelope")


async def invoke_mcp(
    config: GatewayConfig, principal: str, action_name: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    action = select_action(action_name, principal)
    validate_request(action, payload)
    server = create_server(config, principal)
    return _structured_response(await server.call_tool(action.name, dict(payload)))


def invoke(
    config: GatewayConfig, principal: str, action_name: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    return anyio.run(invoke_mcp, config, principal, action_name, payload)


def catalog_display(
    *,
    principal: str,
    action_name: str | None = None,
    schema: bool = False,
    example: bool = False,
    complete: str | None = None,
) -> dict[str, Any]:
    revision = action_set.REVISION
    if action_name is not None:
        action = select_action(action_name, principal)
        if schema:
            return {
                "revision": revision,
                "action": action.name,
                "input_schema": action.input_schema(),
                "output_schema": action.output_schema(),
            }
        if example:
            return {
                "revision": revision,
                "action": action.name,
                "examples": [item.model_dump() for item in action.examples],
            }
        row = action.catalog_row()
        row.pop("input_schema")
        row.pop("output_schema")
        return {"revision": revision, "action": row}
    prefix = (complete or "").casefold()
    return {
        "revision": revision,
        "actions": [
            {
                "name": action.name,
                "family": action.family.value,
                "summary": action.summary,
            }
            for action in action_set.visible(principal)
            if action.name.casefold().startswith(prefix)
        ],
    }
