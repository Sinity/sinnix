from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import inspect
import json
from contextlib import asynccontextmanager
from typing import Any

import anyio
from mcp.server import MCPServer
from mcp.server.subscriptions import InMemorySubscriptionBus
from mcp.types import (
    ListResourceTemplatesResult,
    PaginatedRequestParams,
    ResourceTemplate,
)

from . import actions as action_set
from .actions import visible as visible_actions
from .config import GatewayConfig
from .prompts import PROMPT_SPECS, PromptGenerator
from .registry import REGISTRY
from .results import ProtocolError, derive_cursor_key
from .runtime import Runtime, canonical_manifest
from .subscriptions import (
    EVENTS_RESOURCE_URI,
    EventSpoolPublisher,
    OwnerRevisionPublisher,
)
from .tooling import build_tool


def _bounded_resource_json(runtime: Runtime, payload: Any, kind: str) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) <= runtime.config.max_result_bytes:
        return encoded.decode()
    artifact = runtime.artifacts.register_json(
        payload,
        kind=f"gateway-{kind}",
        owner_id="gateway",
        source="gateway-resource",
        target={"resource": kind},
    )
    envelope = {
        "schema": "sinnix.gateway-resource-artifact.v1",
        "resource": kind,
        "truncated": True,
        "artifact": artifact,
    }
    encoded_envelope = json.dumps(
        envelope, sort_keys=True, separators=(",", ":")
    ).encode()
    if len(encoded_envelope) > runtime.config.max_result_bytes:
        return json.dumps(
            {"artifact_id": artifact["artifact_id"], "truncated": True},
            sort_keys=True,
            separators=(",", ":"),
        )
    return encoded_envelope.decode()


def create_server(config: GatewayConfig, principal_name: str) -> MCPServer:
    runtime = Runtime.create(config, principal_name)
    subscription_bus = InMemorySubscriptionBus()
    revision_publisher = OwnerRevisionPublisher(runtime, subscription_bus)
    event_publisher = EventSpoolPublisher(config.event_spool, subscription_bus)

    @asynccontextmanager
    async def gateway_lifespan(_server: MCPServer):
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(revision_publisher.run, 1.0)
            task_group.start_soon(event_publisher.run, 1.0)
            yield {}
            task_group.cancel_scope.cancel()

    mcp = MCPServer(
        name="sinnix-agent-gateway",
        tools=[
            build_tool(action, runtime) for action in visible_actions(principal_name)
        ],
        title="Sinnix Agent Gateway",
        description="Principal-scoped project, machine, and job control plane.",
        instructions=(
            f"Active principal: {principal_name}. Start with catalog, then use canonical refs. "
            "All outputs are bounded; unavailable evidence is reported explicitly."
        ),
        version="0.3.0",
        subscriptions=subscription_bus,
        lifespan=gateway_lifespan,
    )
    mcp._sinnix_revision_publisher = revision_publisher

    async def tool_manifest() -> dict[str, Any]:
        return canonical_manifest(await mcp.list_tools())

    runtime.tool_manifest = tool_manifest
    mcp._sinnix_event_publisher = event_publisher

    @mcp.resource("sinnix://gateway/instructions")
    def gateway_instructions() -> str:
        return (
            f"Principal {principal_name}. Projects are allowlisted. Paths are project-relative. "
            "Job IDs and artifact IDs are the only accepted control identities."
        )

    def _catalog_rows() -> dict[str, Any]:
        rows = []
        for action in visible_actions(principal_name):
            row = action.catalog_row()
            row.pop("input_schema")
            row.pop("output_schema")
            rows.append(row)
        return {
            "revision": action_set.REVISION,
            "catalog_sha256": action_set.catalog_hash(principal_name),
            "actions": rows,
            "resources": action_set.resource_rows(principal_name),
        }

    @mcp.resource("sinnix://gateway/v2/catalog")
    def gateway_v2_catalog() -> str:
        """Return the principal-visible action and resource catalog."""
        return _bounded_resource_json(runtime, _catalog_rows(), "catalog")

    @mcp.resource(EVENTS_RESOURCE_URI)
    def gateway_v2_events() -> str:
        """Return the bounded event page signalled by completion pushes."""
        return _bounded_resource_json(runtime, runtime.v2_events(100), "events")

    @mcp.resource("sinnix://gateway/v2/actions/{action_name}")
    def gateway_v2_action_schema(action_name: str) -> str:
        """Return the full contract, schemas and examples of one visible action."""
        action = action_set.BY_NAME.get(action_name)
        if action is None or principal_name not in action.principals:
            raise ProtocolError("not_found", "action is not visible to this principal")
        return _bounded_resource_json(
            runtime,
            {"revision": action_set.REVISION, "action": action.catalog_row()},
            "action-schema",
        )

    @mcp.resource("sinnix://gateway/v2/resources/{resource_kind}")
    def gateway_v2_resource_contract(resource_kind: str) -> str:
        """Return one canonical resource kind with the actions that use it."""
        row = next(
            (
                row
                for row in action_set.resource_rows(principal_name)
                if row["kind"] == resource_kind
            ),
            None,
        )
        if row is None:
            raise ProtocolError("not_found", "resource kind is not visible")
        return _bounded_resource_json(
            runtime,
            {"revision": action_set.REVISION, "resource": row},
            "resource-contract",
        )

    @mcp.resource("sinnix://results/{result_id}")
    def gateway_v2_result(result_id: str) -> str:
        """Return one immutable V2 result snapshot for the active principal."""
        return _bounded_resource_json(
            runtime, runtime.results.read(result_id), "result"
        )

    @mcp.resource("sinnix://receipts/{receipt_id}")
    def gateway_v2_receipt(receipt_id: str) -> str:
        """Return one principal-scoped audit receipt behind its canonical ref."""
        return _bounded_resource_json(
            runtime, runtime.audit.receipt(receipt_id), "receipt"
        )

    def register_canonical_templates() -> None:
        """Register only principal-visible canonical owner templates."""
        for resource in REGISTRY.resources:
            if principal_name not in resource.principals or resource.kind in {
                "result",
                "receipt",
            }:
                continue
            variables = resource.ref_template.variables

            async def read_template(_resource=resource, **values: str) -> str:
                reference = str(_resource.ref_template.format(values))
                if _resource.kind == "mcp_tool":
                    catalog = await runtime.mcp_broker.catalog()
                    match = next(
                        (
                            tool
                            for server in catalog.get("servers", [])
                            if server.get("name") == values["server"]
                            for tool in server.get("tools", [])
                            if tool.get("name") == values["tool"]
                        ),
                        None,
                    )
                    if match is None:
                        raise ProtocolError(
                            "not_found",
                            "MCP tool is not in the current admitted catalog",
                        )
                    payload = {"ref": reference, "kind": "mcp_tool", "tool": match}
                else:
                    payload = runtime.v2_get(reference)
                return _bounded_resource_json(runtime, payload, _resource.kind)

            # MCPServer validates template parameters with inspect.signature.
            # A kwargs closure keeps registration compact while exposing the
            # exact URI variable names to the SDK.
            read_template.__signature__ = inspect.Signature(
                [
                    inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    for name in variables
                ]
            )
            mcp.resource(
                resource.ref_template.template,
                name=f"{resource.kind}-resource",
                description=f"Canonical {resource.kind} owner resource.",
                mime_type="application/json",
            )(read_template)

    register_canonical_templates()

    template_cursor_key = derive_cursor_key(
        runtime.results.cursor_key, "resource-templates", principal_name
    )

    def template_cursor(offset: int) -> str:
        body = json.dumps(
            {
                "revision": action_set.REVISION,
                "principal": principal_name,
                "offset": offset,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        encoded = base64.urlsafe_b64encode(body).decode().rstrip("=")
        mac = hmac.new(
            template_cursor_key, encoded.encode(), hashlib.sha256
        ).hexdigest()
        cursor = f"{encoded}.{mac}"
        if len(cursor.encode()) > 4_096:
            raise ProtocolError(
                "response_bound", "resource template cursor exceeds its size bound"
            )
        return cursor

    def template_offset(cursor: str | None) -> int:
        if cursor is None:
            return 0
        try:
            if len(cursor.encode()) > 4_096:
                raise ValueError
            encoded, mac = cursor.rsplit(".", 1)
            expected = hmac.new(
                template_cursor_key, encoded.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(mac, expected):
                raise ValueError
            body = json.loads(
                base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
            )
            if (
                body.get("revision") != action_set.REVISION
                or body.get("principal") != principal_name
            ):
                raise ValueError
            offset = body.get("offset")
            if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
                raise ValueError
            return offset
        except (
            ValueError,
            TypeError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            binascii.Error,
        ) as exc:
            raise ProtocolError(
                "stale_cursor", "resource template cursor is stale or out of scope"
            ) from exc

    async def list_resource_templates(
        _ctx: Any, params: PaginatedRequestParams
    ) -> ListResourceTemplatesResult:
        templates = await mcp.list_resource_templates()
        offset = template_offset(params.cursor)
        page_size = 16
        page = templates[offset : offset + page_size]
        next_cursor = (
            template_cursor(offset + page_size)
            if offset + page_size < len(templates)
            else None
        )
        return ListResourceTemplatesResult(
            resource_templates=[
                ResourceTemplate(
                    uri_template=template.uri_template,
                    name=template.name,
                    title=template.title,
                    description=template.description,
                    mime_type=template.mime_type,
                    icons=template.icons,
                    annotations=template.annotations,
                    _meta=template.meta,
                )
                for template in page
            ],
            next_cursor=next_cursor,
        )

    # MCP 2.0.0 exposes the low-level replacement seam, while its default
    # MCPServer handler ignores PaginatedRequestParams for this method.
    mcp._lowlevel_server.add_request_handler(
        "resources/templates/list", PaginatedRequestParams, list_resource_templates
    )

    prompt_generator = PromptGenerator(
        principal=principal_name,
        catalog=lambda principal: _catalog_rows(),
    )
    for prompt_spec in PROMPT_SPECS:

        def make_prompt(name: str):
            def generated_prompt(
                ref: str, job_ref: str | None = None
            ) -> list[dict[str, Any]]:
                return prompt_generator.generate(name, {"ref": ref, "job_ref": job_ref})

            generated_prompt.__name__ = name
            return generated_prompt

        mcp.prompt(
            name=prompt_spec.name,
            description=prompt_spec.description,
        )(make_prompt(prompt_spec.name))

    return mcp
