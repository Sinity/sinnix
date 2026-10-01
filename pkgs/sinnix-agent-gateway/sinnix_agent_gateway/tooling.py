"""Turn an ``Action`` into one MCP tool with the action's real schemas."""

from __future__ import annotations

import inspect
import json
from typing import TYPE_CHECKING, Any

import anyio
from mcp.server.mcpserver.tools.base import Tool
from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
from mcp.types import CallToolResult, TextContent
from pydantic import ConfigDict, ValidationError, create_model

from . import calllog
from .action import Action, ActionResult, RequestControls
from .actions import BY_NAME
from .contracts import EffectMode
from .results import ProtocolError
from .revisions import lossless_revisions

# The transport served to the OpenAI tunnel. Its control plane drops any
# response later than TUNNEL_RESPONSE_DEADLINE_SECONDS after the tunnel polled
# the command, so remote calls answer inside a budget below it.
REMOTE_TRANSPORT = "streamable_http_unix"
# A read that has not finished by then answers with a typed deadline error;
# the rest of the tunnel deadline covers queueing and response delivery.
REMOTE_READ_BUDGET_SECONDS = 100
# Waits return their own timeout outcome and continuation inside the budget.
REMOTE_WAIT_CAP_SECONDS = 90

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
        return {key: value for key, value in values.items() if key in self.model_fields_set}


def _safe_failure_controls(arguments: dict[str, Any]) -> dict[str, Any]:
    """Retain only independently valid attribution after action input fails."""
    safe: dict[str, Any] = {}
    for key in RequestControls.model_fields:
        if key not in arguments:
            continue
        try:
            control = RequestControls.model_validate({key: arguments[key]})
        except ValidationError:
            continue
        safe[key] = control.model_dump(mode="json")[key]
    return safe


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

    async def invoke(sinnix_context: Any = None, **kwargs: Any) -> Any:
        if action.name in {"gateway.read", "gateway.change", "gateway.run"}:
            return await _dispatch_core(action, runtime, kwargs, sinnix_context)
        remote = runtime.transport == REMOTE_TRANSPORT
        record = calllog.CallRecord(
            action=action.name,
            effect=action.effect.value,
            arguments=kwargs,
            http=calllog.http_request(sinnix_context),
        )
        if remote:
            kwargs = _clamp_remote_wait(action, kwargs, record)
            if action.effect is EffectMode.READ:
                record.budget_seconds = REMOTE_READ_BUDGET_SECONDS
        try:
            response, blocks = await _execute(kwargs, record)
        except BaseException as exc:
            if remote:
                cancelled = isinstance(exc, anyio.get_cancelled_exc_class())
                calllog.emit(
                    record.finish(outcome="cancelled" if cancelled else "failed")
                )
            raise
        if remote:
            calllog.emit(
                record.finish(
                    outcome=_call_outcome(action, response), response=response
                )
            )
        return _project(response, blocks)

    async def _execute(
        kwargs: dict[str, Any], record: calllog.CallRecord
    ) -> tuple[dict[str, Any], list[Any]]:
        try:
            request_input = action.Input.model_validate(kwargs)
        except ValidationError as exc:
            failure = _validation_error(exc, action)

            async def failing() -> Any:
                raise failure

            return await runtime.execute_v2_async(
                action,
                failing,
                _safe_failure_controls(kwargs),
                validation_failure=failure,
            ), []

        request = request_input.model_dump(mode="json")

        blocks: list[Any] = []

        def run_sync_handler() -> Any:
            record.mark_thread_started()
            return action.handler(runtime, request_input)

        async def run_handler() -> Any:
            if action.is_async:
                return await action.handler(runtime, request_input)
            # A budgeted read may leave its worker thread running once the
            # caller has its answer; a mutation always finishes its effect.
            return await anyio.to_thread.run_sync(
                run_sync_handler,
                abandon_on_cancel=record.budget_seconds is not None,
            )

        async def callback() -> Any:
            page = None
            if record.budget_seconds is None:
                raw = await run_handler()
            else:
                with anyio.move_on_after(record.budget_seconds) as scope:
                    raw = await run_handler()
                if scope.cancelled_caught:
                    record.budget_exceeded = True
                    raise ProtocolError(
                        "deadline",
                        f"{action.name} did not finish within the "
                        f"{record.budget_seconds} s remote response budget; the "
                        "tunnel drops responses after about "
                        f"{calllog.TUNNEL_RESPONSE_DEADLINE_SECONDS} s. Narrow the "
                        "request, or start the work as a job and follow it with "
                        "jobs.wait.",
                        details={"budget_seconds": record.budget_seconds},
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

        return await runtime.execute_v2_async(action, callback, request), blocks

    def _project(response: dict[str, Any], blocks: list[Any]) -> CallToolResult:
        # Revisions leave as exact strings: a double-decoding client would
        # otherwise round a 64-bit row revision and fail its next guard.
        response = lossless_revisions(response)
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
        # The SDK passes its request context here; the call log reads the
        # HTTP request's arrival time and correlation headers from it.
        context_kwarg="sinnix_context",
        annotations=action.annotations,
        meta={
            "sinnix.family": action.family.value,
            "sinnix.owner": action.owner,
            "sinnix.affordances": list(action.affordances),
        },
    )
    return tool


async def _dispatch_core(
    core: Action, runtime: Runtime, arguments: dict[str, Any], context: Any
) -> CallToolResult:
    """Select a leaf, then enter its ordinary tool path exactly once."""
    try:
        try:
            request = core.Input.model_validate(
                {
                    key: value
                    for key, value in arguments.items()
                    if value is not None or key not in core.Input.model_fields
                }
            )
        except ValidationError as exc:
            raise _validation_error(exc, core) from exc
        leaf = BY_NAME.get(request.action)
        if leaf is None or runtime.principal_name not in leaf.principals:
            raise ProtocolError("not_found", "action is not visible to this principal")
        if leaf.name in {"gateway.read", "gateway.change", "gateway.run"}:
            raise ProtocolError("invalid_request", "recursive core dispatch is refused")
        admitted = (
            leaf.effect is EffectMode.READ
            if core.name == "gateway.read"
            else (
                leaf.effect in {EffectMode.CHANGE, EffectMode.OPERATE}
                if core.name == "gateway.change"
                else leaf.effect is EffectMode.RUN
            )
        )
        if not admitted:
            raise ProtocolError(
                "policy_denied", "action effect does not match core route"
            )
        controls = {
            key: value
            for key, value in request.model_dump(mode="json").items()
            if key not in {"action", "arguments"} and value is not None
        }
        if set(request.arguments) & (
            set(core.Input.model_fields) - {"action", "arguments"}
        ):
            raise ProtocolError(
                "invalid_request", "request controls must be top level only"
            )
        # The selected wrapper performs its own Input/Output checks, runtime
        # admission, idempotency, auditing and native content projection.
        return await build_tool(leaf, runtime).fn(
            sinnix_context=context, **{**request.arguments, **controls}
        )
    except ProtocolError as failure:

        async def failing() -> Any:
            raise failure

        refusal_context = {
            key: value
            for key, value in arguments.items()
            if key in core.Input.model_fields and key not in {"action", "arguments"}
        }
        envelope = await runtime.execute_v2_async(core, failing, refusal_context)
        return CallToolResult(
            content=[_text_block(envelope)], structured_content=envelope, is_error=True
        )


# The states in which a call answered with a continuation rather than a result.
CONTINUATION_OUTCOMES = frozenset({"running", "queued"})


def _call_outcome(action: Action, response: dict[str, Any]) -> str:
    """The call log's outcome: the envelope's, or the state of unfinished work.

    A shell that is still running when its call answers is not an `ok` call to
    a reader of the journal; logging it as one hid a lane full of long jobs
    behind a column of successes.
    """
    outcome = response["result"]["outcome"]
    field = action.progress_field
    data = response.get("data")
    if outcome == "ok" and field is not None and isinstance(data, dict):
        state = data.get(field)
        if state in CONTINUATION_OUTCOMES:
            return str(state)
    return outcome


def _clamp_remote_wait(
    action: Action, kwargs: dict[str, Any], record: calllog.CallRecord
) -> dict[str, Any]:
    """Keep a remote wait inside the tunnel deadline; its timeout says so."""
    name = action.remote_wait_field
    if name is None:
        return kwargs
    requested = kwargs.get(name)
    if (
        isinstance(requested, (int, float))
        and not isinstance(requested, bool)
        and requested > REMOTE_WAIT_CAP_SECONDS
    ):
        record.clamped = {
            name: {"requested": requested, "used": REMOTE_WAIT_CAP_SECONDS}
        }
        return {**kwargs, name: REMOTE_WAIT_CAP_SECONDS}
    return kwargs


def _description(action: Action) -> str:
    lines = [action.summary]
    if action.documentation:
        lines.append(action.documentation)
    if action.remote_wait_field is not None:
        lines.append(
            f"Through the remote tunnel, {action.remote_wait_field} above "
            f"{REMOTE_WAIT_CAP_SECONDS} is reduced to {REMOTE_WAIT_CAP_SECONDS} so "
            "the answer arrives before the tunnel's response deadline; a timeout "
            "returns a continuation to wait again."
        )
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
