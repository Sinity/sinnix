"""Turn an ``Action`` into one MCP tool with the action's real schemas."""

from __future__ import annotations

import functools
import inspect
import json
from typing import TYPE_CHECKING, Any

import anyio
from mcp.server.mcpserver.tools.base import Tool
from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError, create_model

from .action import Action, ActionResult
from .results import ProtocolError

if TYPE_CHECKING:
    from .runtime import Runtime


def _validation_error(exc: ValidationError) -> ProtocolError:
    problems = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error.get("loc", ()))
        problems.append({"field": location, "problem": error.get("msg", "")})
    return ProtocolError(
        "invalid_request",
        "request does not match the action schema",
        details={"problems": problems[:32]},
    )


def _text_block(envelope: dict[str, Any]) -> TextContent:
    return TextContent(
        type="text",
        text=json.dumps(envelope, sort_keys=True, separators=(",", ":")),
    )


def build_tool(action: Action, runtime: Runtime) -> Tool:
    envelope_model = action.envelope_model()
    # The SDK validates arguments before calling the tool; a permissive model
    # lets every call reach the gateway kernel so schema failures are typed,
    # receipted and audited like any other failure.
    arg_model = create_model(
        f"{action.Input.__name__}Args",
        __base__=ArgModelBase,
        __config__=None,
        **{
            name: (Any, None)
            for name in action.Input.model_fields
        },
    )
    arg_model.model_config = {**ArgModelBase.model_config, "extra": "allow"}

    async def invoke(**kwargs: Any) -> Any:
        try:
            request_input = action.Input.model_validate(
                {key: value for key, value in kwargs.items() if value is not None}
            )
        except ValidationError as exc:
            failure = _validation_error(exc)

            async def failing() -> Any:
                raise failure

            response = await runtime.execute_v2_async(action, failing, {})
            return _project(response, [])

        request = request_input.model_dump(mode="json")

        blocks: list[Any] = []

        async def callback() -> Any:
            if action.is_async:
                raw = await action.handler(runtime, request_input)
            else:
                raw = await anyio.to_thread.run_sync(
                    functools.partial(action.handler, runtime, request_input)
                )
            if isinstance(raw, ActionResult):
                blocks.extend(raw.blocks)
                raw = raw.data
            if isinstance(raw, action.Output):
                return raw.model_dump(mode="json")
            try:
                validated = action.Output.model_validate(raw)
            except ValidationError as exc:
                raise ProtocolError(
                    "owner_failed",
                    "owner result does not match the declared output",
                    details={"problems": exc.errors(include_url=False)[:8]},
                ) from exc
            return validated.model_dump(mode="json")

        response = await runtime.execute_v2_async(action, callback, request)
        return _project(response, blocks)

    def _project(response: dict[str, Any], blocks: list[Any]) -> Any:
        if response["result"]["outcome"] == "ok":
            if not blocks:
                return response
            return CallToolResult(
                content=[_text_block(response), *blocks],
                structured_content=response,
            )
        return CallToolResult(
            content=[_text_block(response)],
            structured_content=response,
            is_error=True,
        )

    invoke.__name__ = action.name
    invoke.__doc__ = action.summary
    metadata = FuncMetadata(
        arg_model=arg_model,
        output_model=envelope_model,
        output_schema=envelope_model.model_json_schema(by_alias=True),
        wrap_output=False,
    )
    tool = Tool(
        fn=invoke,
        name=action.name,
        title=action.summary,
        description=_description(action),
        parameters=action.input_schema(),
        fn_metadata=metadata,
        is_async=True,
        context_kwarg=None,
        annotations=action.annotations,
        meta={
            "sinnix.family": action.family.value,
            "sinnix.owner": action.owner,
            "sinnix.affordances": list(action.affordances),
        },
    )
    return tool


def _description(action: Action) -> str:
    lines = [action.summary]
    if action.documentation:
        lines.append(action.documentation)
    if action.examples:
        example = action.examples[0]
        lines.append(
            f"Example ({example.title}): "
            + json.dumps(example.input, sort_keys=True, separators=(",", ":"))
        )
    if action.affordances:
        lines.append("Follow-up actions: " + ", ".join(action.affordances))
    return "\n".join(lines)


def tool_signature_matches(tool: Tool, action: Action) -> bool:
    """Canary: the published parameters equal the Input model schema."""
    published = tool.parameters
    declared = action.input_schema()
    accepted = set(tool.fn_metadata.arg_model.model_fields)
    return (
        published == declared
        and accepted == set(action.Input.model_fields)
        and inspect.iscoroutinefunction(tool.fn)
    )
