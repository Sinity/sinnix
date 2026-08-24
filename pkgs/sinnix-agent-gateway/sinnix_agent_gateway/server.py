from __future__ import annotations

import json
from typing import Any, Mapping, cast

from mcp.server import MCPServer

from .bindings import TargetToolBinding, TargetToolBindings
from .config import GatewayConfig
from .contracts import ActionSpec, EffectMode, OwnerRoute, VerbFamily
from .registry import CatalogSearch, REGISTRY, RegistryError
from .results import ProtocolError
from .runtime import (
    AUDITED_READ_TOOL,
    IDEMPOTENT_MUTATION_TOOL,
    IDEMPOTENT_RUN_TOOL,
    Runtime,
    _principal_contract,
    canonical_manifest,
    v2_tool_result,
)
from .parity import legacy_parity_contract
from .mcp_broker import McpEnvironmentError
from .schemas import V2ManifestEnvelope


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
    encoded_envelope = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded_envelope) > runtime.config.max_result_bytes:
        return json.dumps(
            {"artifact_id": artifact["artifact_id"], "truncated": True},
            sort_keys=True,
            separators=(",", ":"),
        )
    return encoded_envelope.decode()


async def _query_owner(
    runtime: Runtime,
    action: ActionSpec | str,
    reference: str | None,
    text: str | None,
    max_matches: int,
    parameters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Execute a declared read action through its typed owner route."""
    if isinstance(action, str):
        action = REGISTRY.action(action)
    values = dict(parameters or {})
    route = action.route
    if route is OwnerRoute.PROJECTS_SEARCH:
        if not isinstance(reference, str) or not isinstance(text, str):
            raise ProtocolError("invalid_request", "projects.query requires ref and query")
        return runtime.v2_query(reference, text, max_matches)
    if route is OwnerRoute.BEADS_QUERY:
        return runtime.v2_beads_query(values)
    if route is OwnerRoute.PROJECTS_LIST:
        return runtime.projects.list()
    if route in {
        OwnerRoute.PROJECTS_TREE,
        OwnerRoute.PROJECTS_READ,
        OwnerRoute.PROJECTS_DIFF,
    }:
        if not isinstance(reference, str):
            raise ProtocolError("invalid_request", f"{action.name} requires a canonical ref")
        project_id, checkout_id, canonical_ref = runtime._project_reference(reference, allow_checkout=True)
        if route is OwnerRoute.PROJECTS_TREE:
            return {"ref": canonical_ref, **runtime.projects.tree(project_id, str(values.get("path", ".")), int(values.get("max_entries", 500)), checkout_id)}
        if route is OwnerRoute.PROJECTS_READ:
            path = values.get("path")
            if not isinstance(path, str):
                raise ProtocolError("invalid_request", "projects.read requires parameters.path")
            return {"ref": canonical_ref, **runtime.projects.read(project_id, path, int(values.get("start_line", 1)), values.get("end_line"), int(values.get("max_bytes", 64_000)), checkout_id)}
        return {"ref": canonical_ref, **runtime.projects.diff(project_id, values.get("git_ref"), checkout_id)}
    if route is OwnerRoute.OBSERVE_MACHINE_QUERY:
        operation = values.get("operation")
        if not isinstance(operation, str):
            raise ProtocolError("invalid_request", "machine.query requires parameters.operation")
        return runtime.observe.machine_query(operation, int(values.get("cursor", 0)), int(values.get("limit", 100)))
    if route is OwnerRoute.CAPABILITY_INDEX_QUERY:
        if values.get("operation", "search") == "describe":
            name = values.get("name")
            if not isinstance(name, str):
                raise ProtocolError("invalid_request", "capability description requires parameters.name")
            return runtime.capability_index.describe(name, values.get("kind"))
        return runtime.capability_index.search(str(values.get("query", "")), values.get("kind"), values.get("enabled"), int(values.get("cursor", 0)), int(values.get("limit", 100)))
    if route is OwnerRoute.MCP_CALL_READ:
        if values.get("operation", "catalog") == "catalog":
            if reference is not None:
                raise ProtocolError("invalid_request", "MCP catalog does not accept a target ref")
            if set(values) - {"operation"}:
                raise ProtocolError("invalid_request", "MCP catalog accepts no tool arguments")
            return await runtime.mcp_broker.catalog()
        if values.get("operation") != "call" or not isinstance(reference, str):
            raise ProtocolError("invalid_request", "MCP calls require operation=call and a canonical tool ref")
        if set(values) - {"operation", "arguments"}:
            raise ProtocolError("invalid_request", "MCP calls accept only declared tool arguments")
        arguments = values.get("arguments")
        if not isinstance(arguments, Mapping):
            raise ProtocolError("invalid_request", "MCP calls require arguments")
        _resource, target, _canonical_ref = runtime._resource_reference(
            reference, {"mcp_tool"}, "MCP calls require a canonical admitted tool ref"
        )
        try:
            result = await runtime.mcp_broker.call(
                target["server"], target["tool"], dict(arguments), write=False
            )
        except McpEnvironmentError as exc:
            raise ProtocolError("unavailable", str(exc)) from exc
        return {"ref": _canonical_ref, **result}
    if route is OwnerRoute.DESKTOP_READ:
        if not isinstance(reference, str):
            raise ProtocolError("invalid_request", "desktop.query requires the canonical desktop ref")
        _resource, _target, canonical_ref = runtime._resource_reference(
            reference, {"desktop"}, "desktop.query requires the canonical desktop ref"
        )
        if values.get("operation") == "capture":
            return {
                "ref": canonical_ref,
                **runtime.desktop.capture_output(bool(values.get("fix_hdr", True))),
            }
        operation = values.get("operation")
        if not isinstance(operation, str):
            raise ProtocolError("invalid_request", "desktop.query requires parameters.operation")
        return {"ref": canonical_ref, **runtime.desktop.read(operation)}
    if route is OwnerRoute.TERMINALS_READ:
        operation = values.get("operation")
        if not isinstance(operation, str):
            raise ProtocolError("invalid_request", "terminals.query requires parameters.operation")
        if operation == "list":
            if reference is not None:
                raise ProtocolError("invalid_request", "terminal list does not accept a target ref")
            return runtime.terminals.read(operation)
        if operation != "capture" or not isinstance(reference, str):
            raise ProtocolError("invalid_request", "terminal capture requires a canonical terminal ref")
        _resource, target, canonical_ref = runtime._resource_reference(
            reference, {"terminal"}, "terminal capture requires a canonical terminal ref"
        )
        arguments = values.get("arguments")
        if not isinstance(arguments, Mapping):
            arguments = {}
        if "match" in arguments:
            raise ProtocolError("invalid_request", "terminal match is derived from the canonical ref")
        return {
            "ref": canonical_ref,
            **runtime.terminals.read(
                operation,
                {"match": f"id:{target['terminal_id']}", **dict(arguments)},
            ),
        }
    if route is OwnerRoute.BROWSER_READ:
        operation = values.get("operation")
        if not isinstance(operation, str):
            raise ProtocolError("invalid_request", "browser.query requires parameters.operation")
        if operation in {"status", "list", "list_tabs"}:
            if reference is not None:
                raise ProtocolError("invalid_request", f"browser {operation} does not accept a target ref")
            return runtime.browser.read(operation)
        if not isinstance(reference, str):
            raise ProtocolError("invalid_request", "browser target reads require a canonical browser page ref")
        _resource, target, canonical_ref = runtime._resource_reference(
            reference, {"browser_page"}, "browser target reads require a canonical browser page ref"
        )
        if values.get("page_id") is not None:
            raise ProtocolError("invalid_request", "browser page_id is derived from the canonical ref")
        page_id = target["page_id"]
        if operation == "capture":
            return {
                "ref": canonical_ref,
                **runtime.browser.capture(
                    page_id,
                    str(values.get("image_format", "png")),
                    bool(values.get("full_page", False)),
                    values.get("quality"),
                ),
            }
        return {
            "ref": canonical_ref,
            **runtime.browser.read(operation, page_id, values.get("selector")),
        }
    if route is OwnerRoute.FILES_READ:
        operation = values.get("operation")
        if not isinstance(operation, str) or not isinstance(reference, str):
            raise ProtocolError("invalid_request", "files.query requires operation and a canonical host-file ref")
        _resource, target, canonical_ref = runtime._resource_reference(
            reference, {"host_file"}, "files.query requires a canonical host-file ref"
        )
        if values.get("path") is not None:
            raise ProtocolError("invalid_request", "file path is derived from the canonical ref")
        return {
            "ref": canonical_ref,
            **runtime.files.read(
                operation,
                runtime._decode_file_token(target["file_token"]),
                offset=int(values.get("offset", 0)),
                max_bytes=int(values.get("max_bytes", 64_000)),
                max_entries=int(values.get("max_entries", 200)),
            ),
        }
    if route is OwnerRoute.SESSIONS_QUERY:
        operation = values.get("operation")
        if operation == "list":
            return runtime.sessions.list(str(values.get("provider")), int(values.get("limit", 100)))
        if operation == "read":
            return runtime.sessions.read(str(values.get("reference")), int(values.get("offset", 0)), int(values.get("max_bytes", 64_000)))
        if operation == "search":
            return runtime.sessions.search(str(values.get("provider")), str(values.get("query")), int(values.get("max_results", 100)))
        raise ProtocolError("invalid_request", "sessions.query operation is not recognized")
    if route is OwnerRoute.MEMORY_QUERY:
        if values.get("operation", "search") == "get":
            return runtime.memory.get(str(values.get("reference")), int(values.get("offset", 0)), int(values.get("max_bytes", 64_000)))
        return runtime.memory.search(str(values.get("query")), values.get("providers"), int(values.get("limit", 100)))
    if route is OwnerRoute.TIMELINE_QUERY:
        return runtime.timeline.query(values.get("start"), values.get("end"), values.get("query"), values.get("providers"), int(values.get("limit", 100)))
    if route is OwnerRoute.ARTIFACTS_QUERY:
        if values.get("operation", "list") == "read":
            artifact_id = values.get("artifact_id")
            if not isinstance(artifact_id, str):
                raise ProtocolError("invalid_request", "artifact read requires parameters.artifact_id")
            return runtime.artifacts.read(artifact_id, int(values.get("offset", 0)), int(values.get("max_bytes", 64_000)))
        return runtime.artifacts.list(int(values.get("limit", 100)))
    if route is OwnerRoute.AUDIT_VERIFY:
        return runtime.audit.verify()
    if route is OwnerRoute.JOB_LIST:
        return runtime.v2_jobs_query(values.get("parameters"))
    if route is OwnerRoute.CAPTURES_QUERY:
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
    raise ProtocolError("unsupported_capability", f"query action {action.name!r} has no owner handler")


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
        return _bounded_resource_json(
            runtime, REGISTRY.search(CatalogSearch(principal=principal_name)), "catalog"
        )

    @mcp.resource("sinnix://gateway/v2/documentation")
    def gateway_v2_documentation() -> str:
        """Return generated V2 resource and action documentation rows."""
        return _bounded_resource_json(
            runtime, REGISTRY.documentation_rows(principal_name), "documentation"
        )

    @mcp.resource("sinnix://gateway/v2/legacy-parity")
    def gateway_v2_legacy_parity() -> str:
        """Return the executable legacy-to-V2 parity contract."""
        return _bounded_resource_json(
            runtime, legacy_parity_contract(REGISTRY), "legacy-parity"
        )

    @mcp.resource("sinnix://gateway/v2/actions/{action_name}")
    def gateway_v2_action_schema(action_name: str) -> str:
        """Return the generated schema and contract for one visible V2 action."""
        return _bounded_resource_json(
            runtime,
            REGISTRY.action_schema(action_name, principal_name),
            "action-schema",
        )

    @mcp.resource("sinnix://gateway/v2/resources/{resource_kind}")
    def gateway_v2_resource_contract(resource_kind: str) -> str:
        """Return the generated contract for one canonical V2 resource kind."""
        return _bounded_resource_json(
            runtime,
            REGISTRY.resource_contract(resource_kind, principal_name),
            "resource-contract",
        )

    @mcp.resource("sinnix://results/{result_id}")
    def gateway_v2_result(result_id: str) -> str:
        """Return one immutable V2 result snapshot for the active principal."""
        return _bounded_resource_json(runtime, runtime.results.read(result_id), "result")

    @mcp.resource("sinnix://receipts/{receipt_id}")
    def gateway_v2_receipt(receipt_id: str) -> str:
        """Return one principal-scoped audit receipt behind its canonical ref."""
        return _bounded_resource_json(runtime, runtime.audit.receipt(receipt_id), "receipt")

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

        @mcp.tool(title="Gateway status", annotations=AUDITED_READ_TOOL)
        async def status(
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ManifestEnvelope:
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
            return cast(V2ManifestEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("catalog", principal_name):

        @mcp.tool(title="Gateway V2 catalog", annotations=AUDITED_READ_TOOL)
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
        ) -> V2ManifestEnvelope:
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
            return cast(V2ManifestEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("get", principal_name):

        @mcp.tool(title="Get V2 resource", annotations=AUDITED_READ_TOOL)
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
        ) -> V2ManifestEnvelope:
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
            return cast(V2ManifestEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("query", principal_name):

        @mcp.tool(title="Query canonical resource", annotations=AUDITED_READ_TOOL)
        async def query(
            action_name: str,
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
        ) -> V2ManifestEnvelope:
            """Invoke the exact read action_name returned by catalog.

            Use projects.list with no ref, query, or parameters to list every
            principal-visible project.  Other actions describe their required
            arguments in the catalog and action-schema resource.
            """
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
                        runtime, action, ref, query, max_matches, parameters
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
            return cast(V2ManifestEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("context", principal_name):

        @mcp.tool(title="Get V2 project context", annotations=AUDITED_READ_TOOL)
        def context(
            ref: str,
            intent: str = "project",
            job_ref: str | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ManifestEnvelope:
            """Compose project, assigned Beads-task, or evidence-review context."""
            action = target_bindings.action_for_tool("context", principal=principal_name)
            response = runtime.execute_v2(
                action,
                lambda: runtime.v2_context(ref, intent, job_ref),
                {
                    "ref": ref,
                    "intent": intent,
                    "job_ref": job_ref,
                    "request_id": request_id,
                    "actor": actor,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "deadline_at": deadline_at,
                    "preconditions": preconditions,
                },
            )
            return cast(V2ManifestEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("events", principal_name):

        @mcp.tool(title="Get V2 audit events", annotations=AUDITED_READ_TOOL)
        def events(
            limit: int = 100,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ManifestEnvelope:
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
            return cast(V2ManifestEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("wait", principal_name):

        @mcp.tool(title="Wait for V2 job", annotations=AUDITED_READ_TOOL)
        def wait(
            ref: str,
            timeout_seconds: int = 30,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            idempotency_key: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ManifestEnvelope:
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
            return cast(V2ManifestEnvelope, v2_tool_result(response))

    if target_bindings.is_visible("run", principal_name):

        @mcp.tool(title="Run typed V2 job", annotations=IDEMPOTENT_RUN_TOOL)
        def run(
            action_name: str,
            idempotency_key: str,
            ref: str | None = None,
            project_id: str | None = None,
            checkout_id: str | None = None,
            argv: list[str] | None = None,
            prompt: str | None = None,
            backend: str | None = None,
            model: str | None = None,
            reasoning_effort: str | None = None,
            credential_profile: str = "subscription",
            claim_mode: str = "none",
            assignment_ref: str | None = None,
            instructions: str | None = None,
            cwd: str = ".",
            timeout_seconds: int | None = None,
            operation: str | None = None,
            workspace_id: str | None = None,
            parameters: dict[str, Any] | None = None,
            request_id: str | None = None,
            actor: str | None = None,
            reason: str | None = None,
            deadline_at: float | None = None,
            preconditions: dict[str, Any] | None = None,
        ) -> V2ManifestEnvelope:
            """Start one catalog-declared shell or attested-agent job by action name."""
            request = {
                "action_name": action_name,
                "ref": ref,
                "project_id": project_id,
                "checkout_id": checkout_id,
                "argv": argv,
                "prompt": prompt,
                "backend": backend,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "credential_profile": credential_profile,
                "claim_mode": claim_mode,
                "assignment_ref": assignment_ref,
                "instructions": instructions,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "operation": operation,
                "workspace_id": workspace_id,
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
                    "run", action_name, principal=principal_name
                )
            except RegistryError as error:
                action = target_bindings.fallback_for_tool("run", principal_name)
                failure = selector_failure("run", error)

                def callback() -> dict[str, Any]:
                    raise failure

            else:
                if action.route is OwnerRoute.JOB_SHELL_START:
                    callback = lambda: runtime.v2_run_shell(
                        project_id=project_id,
                        checkout_id=checkout_id,
                        argv=argv,
                        cwd=cwd,
                        timeout_seconds=3_600 if timeout_seconds is None else timeout_seconds,
                    )
                elif action.route is OwnerRoute.JOB_AGENT_START:
                    callback = lambda: runtime.v2_run_for_bead(
                        reference=ref,
                        checkout_id=checkout_id,
                        claim_mode=claim_mode,
                        assignment_ref=assignment_ref,
                        instructions=instructions,
                        backend=backend,
                        model=model,
                        reasoning_effort=reasoning_effort,
                        timeout_seconds=3_600 if timeout_seconds is None else timeout_seconds,
                        credential_profile=credential_profile,
                        request_id=request_id,
                    )
                elif action.route is OwnerRoute.JOB_START:
                    if any(
                        value is not None
                        for value in (
                            checkout_id,
                            argv,
                            prompt,
                            backend,
                            model,
                            reasoning_effort,
                            timeout_seconds,
                        )
                    ) or credential_profile != "subscription" or cwd != ".":
                        def callback() -> dict[str, Any]:
                            raise ProtocolError(
                                "invalid_request",
                                "declared operations do not accept command, agent, or timeout overlays",
                            )
                    else:
                        callback = lambda: runtime.v2_run_declared_operation(
                            project_id=project_id,
                            operation=operation,
                            workspace_id=workspace_id,
                            parameters=parameters,
                        )
                else:
                    raise RegistryError(f"run action {action.name!r} is not implemented")
            response = runtime.execute_v2(action, callback, request)
            return cast(V2ManifestEnvelope, v2_tool_result(response))

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
        ) -> V2ManifestEnvelope:
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
                    if action.route is OwnerRoute.PROJECTS_CHANGE:
                        return runtime.v2_change(
                            reference=ref,
                            operation=operation,
                            path=parameters.get("path") if parameters else None,
                            content=parameters.get("content") if parameters else None,
                            patch=parameters.get("patch") if parameters else None,
                            preconditions=preconditions,
                        )
                    if action.route is OwnerRoute.FILES_CHANGE:
                        return runtime.v2_file_change(
                            reference=ref,
                            operation=operation,
                            parameters=parameters,
                            preconditions=preconditions,
                        )
                    if action.route is OwnerRoute.BEADS_WRITE:
                        return runtime.v2_beads_change(
                            reference=ref,
                            operation=operation,
                            parameters=parameters,
                            preconditions=preconditions,
                        )
                    if action.route is OwnerRoute.BEADS_CHANGESET:
                        if preconditions is not None:
                            raise ProtocolError("invalid_request", "Beads changeset preconditions belong to individual actions")
                        return runtime.v2_beads_changeset(
                            reference=ref,
                            operation=operation,
                            parameters=parameters,
                        )
                    if action.route is OwnerRoute.MCP_CALL_WRITE:
                        return await runtime.v2_mcp_change(
                            reference=ref, operation=operation, parameters=parameters
                        )
                    raise RegistryError(f"change action {action.name!r} is not implemented")

            response = await runtime.execute_v2_async(action, callback, request)
            return cast(V2ManifestEnvelope, v2_tool_result(response))

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
        ) -> V2ManifestEnvelope:
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
                if contract.route is OwnerRoute.OPS_ACTIONS_EXECUTE:
                    callback = lambda: runtime.v2_operate(
                        reference=ref,
                        action=operation,
                        parameters=parameters,
                        reason=reason,
                        idempotency_key=idempotency_key,
                        preconditions=preconditions,
                    )
                elif contract.route is OwnerRoute.JOB_CANCEL:
                    callback = lambda: runtime.v2_cancel_job(
                        reference=ref,
                        preconditions=preconditions,
                    )
                elif contract.route is OwnerRoute.DESKTOP_ACTION:
                    callback = lambda: runtime.v2_desktop_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                elif contract.route is OwnerRoute.TERMINALS_ACTION:
                    callback = lambda: runtime.v2_terminal_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                elif contract.route is OwnerRoute.BROWSER_ACTION:
                    callback = lambda: runtime.v2_browser_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                elif contract.route is OwnerRoute.BEADS_MAINTENANCE:
                    callback = lambda: runtime.v2_beads_operate(
                        reference=ref, operation=operation, parameters=parameters
                    )
                else:
                    raise RegistryError(f"operate action {contract.name!r} is not implemented")
            response = runtime.execute_v2(contract, callback, request)
            return cast(V2ManifestEnvelope, v2_tool_result(response))

    return mcp
