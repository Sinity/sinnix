from __future__ import annotations

import json
from typing import Any, Mapping, cast

from mcp.server import MCPServer

from .bindings import TargetToolBinding, TargetToolBindings
from .config import GatewayConfig
from .contracts import EffectMode, VerbFamily
from .registry import CatalogSearch, REGISTRY, RegistryError
from .results import ProtocolError
from .runtime import (
    IDEMPOTENT_MUTATION_TOOL,
    IDEMPOTENT_RUN_TOOL,
    READ_ONLY_TOOL,
    Runtime,
    _principal_contract,
    canonical_manifest,
    v2_tool_result,
)
from .schemas import V2ToolEnvelope


async def _query_owner(
    runtime: Runtime,
    action_name: str,
    reference: str | None,
    text: str | None,
    max_matches: int,
    parameters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Execute a declared read action; each case names one owner route."""
    values = dict(parameters or {})
    if action_name == "projects.query":
        if not isinstance(reference, str) or not isinstance(text, str):
            raise ProtocolError("invalid_request", "projects.query requires ref and query")
        return runtime.v2_query(reference, text, max_matches)
    if action_name == "beads.query":
        return runtime.v2_beads_query(values)
    if action_name == "projects.list":
        return runtime.projects.list()
    if action_name in {"projects.tree", "projects.read", "projects.diff"}:
        if not isinstance(reference, str):
            raise ProtocolError("invalid_request", f"{action_name} requires a canonical ref")
        project_id, checkout_id, canonical_ref = runtime._project_reference(reference, allow_checkout=True)
        if action_name == "projects.tree":
            return {"ref": canonical_ref, **runtime.projects.tree(project_id, str(values.get("path", ".")), int(values.get("max_entries", 500)), checkout_id)}
        if action_name == "projects.read":
            path = values.get("path")
            if not isinstance(path, str):
                raise ProtocolError("invalid_request", "projects.read requires parameters.path")
            return {"ref": canonical_ref, **runtime.projects.read(project_id, path, int(values.get("start_line", 1)), values.get("end_line"), int(values.get("max_bytes", 64_000)), checkout_id)}
        return {"ref": canonical_ref, **runtime.projects.diff(project_id, values.get("git_ref"), checkout_id)}
    if action_name == "machine.query":
        operation = values.get("operation")
        if not isinstance(operation, str):
            raise ProtocolError("invalid_request", "machine.query requires parameters.operation")
        return runtime.observe.machine_query(operation, int(values.get("cursor", 0)), int(values.get("limit", 100)))
    if action_name == "capabilities.query":
        if values.get("operation", "search") == "describe":
            name = values.get("name")
            if not isinstance(name, str):
                raise ProtocolError("invalid_request", "capability description requires parameters.name")
            return runtime.capability_index.describe(name, values.get("kind"))
        return runtime.capability_index.search(str(values.get("query", "")), values.get("kind"), values.get("enabled"), int(values.get("cursor", 0)), int(values.get("limit", 100)))
    if action_name == "mcp.query":
        if values.get("operation", "catalog") == "catalog":
            return await runtime.mcp_broker.catalog()
        server, tool, arguments = values.get("server"), values.get("tool"), values.get("arguments")
        if not isinstance(server, str) or not isinstance(tool, str) or not isinstance(arguments, Mapping):
            raise ProtocolError("invalid_request", "MCP read requires server, tool, and arguments")
        return await runtime.mcp_broker.call(server, tool, dict(arguments), write=False)
    if action_name == "desktop.query":
        if values.get("operation") == "capture":
            return runtime.desktop.capture_output(bool(values.get("fix_hdr", True)))
        operation = values.get("operation")
        if not isinstance(operation, str):
            raise ProtocolError("invalid_request", "desktop.query requires parameters.operation")
        return runtime.desktop.read(operation)
    if action_name == "terminals.query":
        operation = values.get("operation")
        if not isinstance(operation, str):
            raise ProtocolError("invalid_request", "terminals.query requires parameters.operation")
        arguments = values.get("arguments")
        return runtime.terminals.read(operation, dict(arguments) if isinstance(arguments, Mapping) else None)
    if action_name == "browser.query":
        if values.get("operation") == "capture":
            page_id = values.get("page_id")
            if not isinstance(page_id, str):
                raise ProtocolError("invalid_request", "browser capture requires parameters.page_id")
            return runtime.browser.capture(page_id, str(values.get("image_format", "png")), bool(values.get("full_page", False)), values.get("quality"))
        operation = values.get("operation")
        if not isinstance(operation, str):
            raise ProtocolError("invalid_request", "browser.query requires parameters.operation")
        return runtime.browser.read(operation, values.get("page_id"), values.get("selector"))
    if action_name == "files.query":
        operation, path = values.get("operation"), values.get("path")
        if not isinstance(operation, str) or not isinstance(path, str):
            raise ProtocolError("invalid_request", "files.query requires parameters.operation and parameters.path")
        return runtime.files.read(operation, path, offset=int(values.get("offset", 0)), max_bytes=int(values.get("max_bytes", 64_000)), max_entries=int(values.get("max_entries", 200)))
    if action_name == "sessions.query":
        operation = values.get("operation")
        if operation == "list":
            return runtime.sessions.list(str(values.get("provider")), int(values.get("limit", 100)))
        if operation == "read":
            return runtime.sessions.read(str(values.get("reference")), int(values.get("offset", 0)), int(values.get("max_bytes", 64_000)))
        if operation == "search":
            return runtime.sessions.search(str(values.get("provider")), str(values.get("query")), int(values.get("max_results", 100)))
        raise ProtocolError("invalid_request", "sessions.query operation is not recognized")
    if action_name == "memory.query":
        if values.get("operation", "search") == "get":
            return runtime.memory.get(str(values.get("reference")), int(values.get("offset", 0)), int(values.get("max_bytes", 64_000)))
        return runtime.memory.search(str(values.get("query")), values.get("providers"), int(values.get("limit", 100)))
    if action_name == "timeline.query":
        return runtime.timeline.query(values.get("start"), values.get("end"), values.get("query"), values.get("providers"), int(values.get("limit", 100)))
    if action_name == "artifacts.query":
        if values.get("operation", "list") == "read":
            artifact_id = values.get("artifact_id")
            if not isinstance(artifact_id, str):
                raise ProtocolError("invalid_request", "artifact read requires parameters.artifact_id")
            return runtime.artifacts.read(artifact_id, int(values.get("offset", 0)), int(values.get("max_bytes", 64_000)))
        return runtime.artifacts.list(int(values.get("limit", 100)))
    if action_name == "audit.verify":
        return runtime.audit.verify()
    if action_name == "captures.query":
        operation = values.pop("operation", "lanes")
        if operation == "lanes":
            if values:
                raise ProtocolError("invalid_request", "capture-lane listing accepts no other parameters")
            return runtime.captures.lanes_visible()
        if operation != "query":
            raise ProtocolError("invalid_request", "captures.query operation is not recognized")
        unsupported = set(values).difference({"lanes", "since", "limit"})
        if unsupported:
            raise ProtocolError("invalid_request", "captures.query received unsupported parameters")
        return runtime.captures.query(**values)
    raise ProtocolError("unsupported_capability", f"query action {action_name!r} has no owner handler")


def create_server(config: GatewayConfig, principal_name: str) -> MCPServer:
    runtime = Runtime.create(config, principal_name)
    mcp = MCPServer(
        name="sinnix-agent-gateway",
        title="Sinnix Agent Gateway",
        description="Principal-scoped project, machine, and attested-agent control plane.",
        instructions=(
            f"Active principal: {principal_name}. Start with catalog, then use canonical refs. "
            "All outputs are bounded; unavailable evidence is reported explicitly."
        ),
        version="0.2.0",
    )

    @mcp.resource("sinnix://gateway/instructions")
    def gateway_instructions() -> str:
        return (
            f"Principal {principal_name}. Projects are allowlisted. Paths are project-relative. "
            "Job IDs and artifact IDs are the only accepted control identities."
        )

    @mcp.resource("sinnix://gateway/v2/catalog")
    def gateway_v2_catalog() -> str:
        """Return the principal-filtered V2 contract catalog during migration."""
        return json.dumps(
            REGISTRY.search(CatalogSearch(principal=principal_name)),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://gateway/v2/documentation")
    def gateway_v2_documentation() -> str:
        """Return generated V2 resource and action documentation rows."""
        return json.dumps(
            REGISTRY.documentation_rows(principal_name),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://gateway/v2/actions/{action_name}")
    def gateway_v2_action_schema(action_name: str) -> str:
        """Return the generated schema and contract for one visible V2 action."""
        return json.dumps(
            REGISTRY.action_schema(action_name, principal_name),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://gateway/v2/resources/{resource_kind}")
    def gateway_v2_resource_contract(resource_kind: str) -> str:
        """Return the generated contract for one canonical V2 resource kind."""
        return json.dumps(
            REGISTRY.resource_contract(resource_kind, principal_name),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://results/{result_id}")
    def gateway_v2_result(result_id: str) -> str:
        """Return one immutable V2 result snapshot for the active principal."""
        return json.dumps(
            runtime.results.read(result_id),
            sort_keys=True,
            separators=(",", ":"),
        )

    @mcp.resource("sinnix://receipts/{receipt_id}")
    def gateway_v2_receipt(receipt_id: str) -> str:
        """Return one principal-scoped audit receipt behind its canonical ref."""
        return json.dumps(
            runtime.audit.receipt(receipt_id),
            sort_keys=True,
            separators=(",", ":"),
        )

    target_bindings = TargetToolBindings(
        REGISTRY,
        tuple(
            TargetToolBinding(
                tool_name=action.verb.value,
                action_name=action.name,
                owner=action.owner,
                route=action.route,
            )
            for action in REGISTRY.actions
        ),
    )

    def selector_failure(tool_name: str, error: RegistryError) -> ProtocolError:
        if "cannot invoke action" in str(error):
            return ProtocolError(
                "policy_denied",
                f"this principal cannot invoke the selected {tool_name} action",
            )
        return ProtocolError(
            "unsupported_capability",
            f"the selected {tool_name} action is not declared for this principal",
        )

    if target_bindings.is_visible("status", principal_name):

        @mcp.tool(title="Gateway status", annotations=READ_ONLY_TOOL)
        async def status(
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Return the current principal's gateway contract and availability observations."""
            action = target_bindings.action_for_tool("status", principal=principal_name)
            manifest = canonical_manifest(await mcp.list_tools())
            response = await runtime.execute_v2_async(
                action,
                lambda: runtime.gateway_status(
                    _principal_contract(principal_name),
                    manifest["sha256"],
                    REGISTRY.action_catalog_hash(principal_name),
                    REGISTRY.revision,
                ),
                {
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("catalog", principal_name):

        @mcp.tool(title="Gateway V2 catalog", annotations=READ_ONLY_TOOL)
        def catalog(
            text: str | None = None,
            domain: str | None = None,
            verb: str | None = None,
            effect: str | None = None,
            resource_kind: str | None = None,
            project: str | None = None,
            availability: str | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Search the principal-filtered V2 resource and executable action catalog."""
            action = target_bindings.action_for_tool("catalog", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.catalog(
                    CatalogSearch(
                        text=text,
                        domain=domain,
                        verb=VerbFamily(verb) if verb is not None else None,
                        effect=EffectMode(effect) if effect is not None else None,
                        resource_kind=resource_kind,
                        project=project,
                        availability=availability,
                        principal=principal_name,
                    )
                ),
                {
                    "text": text,
                    "domain": domain,
                    "verb": verb,
                    "effect": effect,
                    "resource_kind": resource_kind,
                    "project": project,
                    "availability": availability,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("get", principal_name):

        @mcp.tool(title="Get V2 resource", annotations=READ_ONLY_TOOL)
        def get(
            ref: str,
            projection: str = "summary",
            offset: int = 0,
            max_bytes: int = 64_000,
            includes: list[str] | None = None,
            as_of: str | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Resolve a canonical resource, including bounded daemon job status or output."""
            action = target_bindings.action_for_tool("get", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_get(ref, projection, offset, max_bytes, includes, as_of),
                {
                    "ref": ref,
                    "projection": projection,
                    "offset": offset,
                    "max_bytes": max_bytes,
                    "includes": includes,
                    "as_of": as_of,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("query", principal_name):

        @mcp.tool(title="Query canonical resource", annotations=READ_ONLY_TOOL)
        async def query(
            action_name: str = "projects.query",
            ref: str | None = None,
            query: str | None = None,
            max_matches: int = 200,
            parameters: dict[str, Any] | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Invoke one catalog-declared, principal-filtered read owner route."""
            try:
                action = target_bindings.action_for_tool("query", action_name, principal_name)
            except RegistryError as error:
                action = target_bindings.fallback_for_tool("query", principal_name)
                failure = selector_failure("query", error)

                async def callback() -> dict[str, Any]:
                    raise failure

            else:

                async def callback() -> dict[str, Any]:
                    return await _query_owner(
                        runtime, action.name, ref, query, max_matches, parameters
                    )

            response = await runtime.execute_v2_async(
                action,
                callback,
                {
                    "action_name": action_name,
                    "ref": ref,
                    "query": query,
                    "max_matches": max_matches,
                    "parameters": parameters,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("context", principal_name):

        @mcp.tool(title="Get V2 project context", annotations=READ_ONLY_TOOL)
        def context(
            ref: str,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Compose Git and bounded task orientation for one canonical project."""
            action = target_bindings.action_for_tool("context", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_context(ref),
                {
                    "ref": ref,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("events", principal_name):

        @mcp.tool(title="Get V2 audit events", annotations=READ_ONLY_TOOL)
        def events(
            limit: int = 100,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Read bounded audit events visible to the active principal."""
            action = target_bindings.action_for_tool("events", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_events(limit),
                {
                    "limit": limit,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("wait", principal_name):

        @mcp.tool(title="Wait for V2 job", annotations=READ_ONLY_TOOL)
        def wait(
            ref: str,
            timeout_seconds: int = 30,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Wait for a bounded interval on one daemon-owned job reference."""
            action = target_bindings.action_for_tool("wait", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_wait(ref, timeout_seconds),
                {
                    "ref": ref,
                    "timeout_seconds": timeout_seconds,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("run", principal_name):

        @mcp.tool(title="Run typed V2 job", annotations=IDEMPOTENT_RUN_TOOL)
        def run(
            action_name: str,
            idempotency_key: str,
            project_id: str | None = None,
            checkout_id: str | None = None,
            argv: list[str] | None = None,
            prompt: str | None = None,
            backend: str | None = None,
            model: str | None = None,
            reasoning_effort: str | None = None,
            credential_profile: str = "subscription",
            cwd: str = ".",
            timeout_seconds: int | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ToolEnvelope:
            """Start one catalog-declared shell or attested-agent job by action name."""
            request = {
                "action_name": action_name,
                "project_id": project_id,
                "checkout_id": checkout_id,
                "argv": argv,
                "prompt": prompt,
                "backend": backend,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "credential_profile": credential_profile,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "request_id": request_id,
                "actor": actor,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "deadline_at": deadline_at,
                "preconditions": preconditions,
            }
            try:
                action = target_bindings.action_for_tool(
                    "run", action_name, principal=principal_name
                )
            except RegistryError as error:
                action = target_bindings.fallback_for_tool("run", principal_name)
                failure = selector_failure("run", error)

                def callback() -> dict[str, Any]:
                    raise failure

            else:
                if action.name == "shell.run":
                    callback = lambda: runtime.v2_run_shell(
                        project_id=project_id,
                        checkout_id=checkout_id,
                        argv=argv,
                        cwd=cwd,
                        timeout_seconds=3_600 if timeout_seconds is None else timeout_seconds,
                    )
                elif action.name == "agents.run":
                    callback = lambda: runtime.v2_run_agent(
                        project_id=project_id,
                        checkout_id=checkout_id,
                        prompt=prompt,
                        backend=backend,
                        model=model,
                        reasoning_effort=reasoning_effort,
                        timeout_seconds=14_400 if timeout_seconds is None else timeout_seconds,
                        credential_profile=credential_profile,
                    )
                else:
                    raise RegistryError(f"run action {action.name!r} is not implemented")
            response = runtime.execute_v2(action, callback, request)
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("change", principal_name):

        @mcp.tool(title="Change canonical target", annotations=IDEMPOTENT_MUTATION_TOOL)
        async def change(
            action_name: str,
            ref: str,
            operation: str,
            idempotency_key: str,
            parameters: dict[str, Any] | None = None,
            preconditions: dict[str, Any] | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            deadline_at: float | None = None,
        ) -> V2ToolEnvelope:
            """Apply one catalog-declared mutation through its canonical owner route."""
            request = {
                "action_name": action_name,
                "ref": ref,
                "operation": operation,
                "parameters": parameters,
                "request_id": request_id,
                "actor": actor,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "deadline_at": deadline_at,
                "preconditions": preconditions,
            }
            try:
                action = target_bindings.action_for_tool(
                    "change", action_name, principal=principal_name
                )
            except RegistryError as error:
                action = target_bindings.fallback_for_tool("change", principal_name)
                failure = selector_failure("change", error)

                async def callback() -> dict[str, Any]:
                    raise failure

            else:
                async def callback() -> dict[str, Any]:
                    if action.name == "projects.change":
                        return runtime.v2_change(
                            reference=ref,
                            operation=operation,
                            path=parameters.get("path") if parameters else None,
                            content=parameters.get("content") if parameters else None,
                            patch=parameters.get("patch") if parameters else None,
                            preconditions=preconditions,
                        )
                    if action.name == "files.change":
                        return runtime.v2_file_change(
                            reference=ref,
                            operation=operation,
                            parameters=parameters,
                            preconditions=preconditions,
                        )
                    if action.name == "beads.change":
                        return runtime.v2_beads_change(
                            reference=ref,
                            operation=operation,
                            parameters=parameters,
                            preconditions=preconditions,
                        )
                    if action.name == "beads.changeset":
                        if preconditions is not None:
                            raise ProtocolError("invalid_request", "Beads changeset preconditions belong to individual actions")
                        return runtime.v2_beads_changeset(
                            reference=ref,
                            operation=operation,
                            parameters=parameters,
                        )
                    if action.name == "mcp.change":
                        return await runtime.v2_mcp_change(
                            reference=ref, operation=operation, parameters=parameters
                        )
                    raise RegistryError(f"change action {action.name!r} is not implemented")

            response = await runtime.execute_v2_async(action, callback, request)
            return cast(V2ToolEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("operate", principal_name):

        @mcp.tool(title="Operate canonical machine target", annotations=IDEMPOTENT_MUTATION_TOOL)
        def operate(
            action_name: str,
            ref: str,
            idempotency_key: str,
            operation: str | None = None,
            parameters: dict[str, Any] | None = None,
            reason: str | None = None,
            preconditions: dict[str, Any] | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            deadline_at: float | None = None,
        ) -> V2ToolEnvelope:
            """Run one catalog-declared machine or job operation against a canonical target."""
            request = {
                "action_name": action_name,
                "ref": ref,
                "operation": operation,
                "parameters": parameters,
                "request_id": request_id,
                "actor": actor,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "deadline_at": deadline_at,
                "preconditions": preconditions,
            }
            try:
                contract = target_bindings.action_for_tool(
                    "operate", action_name, principal=principal_name
                )
            except RegistryError as error:
                contract = target_bindings.fallback_for_tool("operate", principal_name)
                failure = selector_failure("operate", error)

                def callback() -> dict[str, Any]:
                    raise failure

            else:
                if contract.name == "machine.operate":
                    callback = lambda: runtime.v2_operate(
                        reference=ref,
                        action=operation,
                        parameters=parameters,
                        reason=reason,
                        idempotency_key=idempotency_key,
                        preconditions=preconditions,
                    )
                elif contract.name == "jobs.cancel":
                    callback = lambda: runtime.v2_cancel_job(
                        reference=ref,
                        preconditions=preconditions,
                    )
                elif contract.name == "desktop.operate":
                    callback = lambda: runtime.v2_desktop_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                elif contract.name == "terminals.operate":
                    callback = lambda: runtime.v2_terminal_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                elif contract.name == "browser.operate":
                    callback = lambda: runtime.v2_browser_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                elif contract.name == "beads.operate":
                    callback = lambda: runtime.v2_beads_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                else:
                    raise RegistryError(f"operate action {contract.name!r} is not implemented")
            response = runtime.execute_v2(contract, callback, request)
            return cast(V2ToolEnvelope, v2_tool_result(response))

    return mcp
