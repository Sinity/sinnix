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
from pydantic import ConfigDict, ValidationError, create_model

from .action import Action, ActionResult
from .results import ProtocolError

if TYPE_CHECKING:
    from .runtime import Runtime


class _GatewayArgModel(ArgModelBase):
    """Keep SDK arguments intact until the gateway validates the action input.

    MCP's argument adapter normally projects a validated model back to only its
    declared fields.  Gateway actions own validation and must see unknown keys
    so a misspelled field produces a typed receipt instead of being ignored.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def model_dump_one_level(self) -> dict[str, Any]:
        values = super().model_dump_one_level()
        values.update(self.model_extra or {})
        return values


def _validation_error(exc: ValidationError, action: Action) -> ProtocolError:
    """A schema failure that carries the shape the caller should have sent.

    A cold client that nests the request under `parameters`, or sends a
    locator's own fields at the top level, learns the accepted envelope from
    the refusal instead of guessing again.
    """
    problems = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error.get("loc", ()))
        problems.append({"field": location, "problem": error.get("msg", "")})
    details: dict[str, Any] = {
        "problems": problems[:32],
        "accepted_fields": sorted(action.Input.model_fields),
    }
    if action.examples:
        details["example"] = action.examples[0].input
    return ProtocolError(
        "invalid_request",
        f"request does not match the {action.name} schema",
        details=details,
    )


def _text_block(envelope: dict[str, Any]) -> TextContent:
    return TextContent(
        type="text",
        text=json.dumps(envelope, sort_keys=True, separators=(",", ":")),
    )


def build_tool(action: Action, runtime: Runtime) -> Tool:
    # The SDK validates arguments before calling the tool; a permissive model
    # lets every call reach the gateway kernel so schema failures are typed,
    # receipted and audited like any other failure.
    arg_model = create_model(
        f"{action.Input.__name__}Args",
        __base__=_GatewayArgModel,
        **dict.fromkeys(action.Input.model_fields, (Any, None)),
    )

    async def invoke(**kwargs: Any) -> Any:
        try:
            request_input = action.Input.model_validate(
                {
                    key: value
                    for key, value in kwargs.items()
                    if value is not None or key not in action.Input.model_fields
                }
            )
        except ValidationError as exc:
            failure = _validation_error(exc, action)

            async def failing() -> Any:
                raise failure

            response = await runtime.execute_v2_async(action, failing, {})
            return _project(response, [])

        request = request_input.model_dump(mode="json")

        blocks: list[Any] = []

        async def callback() -> Any:
            page = None
            if action.is_async:
                raw = await action.handler(runtime, request_input)
            else:
                raw = await anyio.to_thread.run_sync(
                    functools.partial(action.handler, runtime, request_input)
                )
            if isinstance(raw, ActionResult):
                blocks.extend(raw.blocks)
                page = raw.page
                raw = raw.data
            try:
                validated = action.Output.model_validate(raw)
            except ValidationError as exc:
                raise ProtocolError(
                    "owner_failed",
                    "owner result does not match the declared output",
                    details={"problems": exc.errors(include_url=False)[:8]},
                ) from exc
            data = validated.model_dump(mode="json", by_alias=True)
            return ActionResult(data, page=page) if page is not None else data

        response = await runtime.execute_v2_async(action, callback, request)
        return _project(response, blocks)

    def _project(response: dict[str, Any], blocks: list[Any]) -> CallToolResult:
        ok = response["result"]["outcome"] == "ok"
        return CallToolResult(
            content=[_text_block(response), *(blocks if ok else [])],
            structured_content=response,
            is_error=not ok,
        )

    invoke.__name__ = action.name
    invoke.__doc__ = action.summary
    # The envelope is validated by the runtime and documented once; publishing
    # it per tool would multiply the manifest several times over.
    metadata = FuncMetadata(arg_model=arg_model, output_model=None, output_schema=None)
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
