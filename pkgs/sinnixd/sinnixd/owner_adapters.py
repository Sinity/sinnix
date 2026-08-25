from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Mapping

from sinnix_mcp import (
    RequestEnvelope,
    ResponseEnvelope,
    SinnixRef,
    SourceBinding,
    response_envelope_from_dict,
)
from sinnix_mcp.execution import (
    EnvironmentProfile,
    ExecutionProfile,
    OwnerExecution,
    OwnerRoute,
)
from sinnix_mcp.protocol import DEFAULT_INLINE_PAYLOAD_BYTES

from .projects import ProjectAdapter, ProjectOwnerAdapter


class OwnerAdapterError(ValueError):
    """A declared owner adapter returned no valid response for its request."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class DeclaredOwnerAdapters:
    """Run only project-declared owner adapters through transient user services."""

    execution: OwnerExecution
    max_response_bytes: int = DEFAULT_INLINE_PAYLOAD_BYTES + 32_768

    def call(
        self,
        *,
        project: ProjectAdapter,
        adapter: ProjectOwnerAdapter,
        request: RequestEnvelope,
    ) -> ResponseEnvelope:
        forward_request, expected_source_binding = self._forward_request(request)
        if (
            expected_source_binding is not None
            and expected_source_binding.source_ref != adapter.source_ref
        ):
            raise OwnerAdapterError(
                "invalid_argument",
                "expected_source_binding names a different source",
            )
        environment = project.environment.values()
        environment.update(
            {
                "SINNIXD_CORRELATION_ID": request.correlation_id,
                "SINNIXD_OWNER": adapter.spec.owner,
                "SINNIXD_OPERATION": request.operation,
            }
        )
        command = [
            "/run/current-system/sw/bin/systemd-run",
            "--user",
            "--quiet",
            "--collect",
            "--wait",
            "--pipe",
            f"--unit=sinnixd-owner-{request.request_id}.service",
            "--slice=agent.slice",
            f"--property=WorkingDirectory={project.root}",
            f"--property=RuntimeMaxSec={adapter.timeout_seconds}s",
            "--",
            "/run/current-system/sw/bin/env",
            "-i",
            *[f"{key}={value}" for key, value in sorted(environment.items())],
            *project.environment.command,
            *adapter.command,
        ]
        result = self.execution.run(
            command,
            ExecutionProfile(
                route=OwnerRoute("declared-owner-adapter", EnvironmentProfile.USER_BUS),
                timeout_seconds=adapter.timeout_seconds + 5,
                max_stdout_bytes=self.max_response_bytes,
                max_stderr_bytes=8_192,
                max_combined_output_bytes=self.max_response_bytes + 8_192,
                cwd=project.root,
                stdin_bytes=json.dumps(
                    forward_request.to_dict(), sort_keys=True, separators=(",", ":")
                ).encode(),
            ),
        )
        if result.failure_class is not None:
            code = (
                "owner_unavailable"
                if result.failure_class.startswith("command_unavailable")
                else "operation_failed"
            )
            raise OwnerAdapterError(
                code,
                f"owner adapter {adapter.spec.owner!r} failed: {result.failure_class}",
            )
        try:
            response = response_envelope_from_dict(result.decode_json())
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise OwnerAdapterError(
                "result_invalid",
                f"owner adapter {adapter.spec.owner!r} returned an invalid response",
            ) from error
        self._validate_response(adapter, request, response, expected_source_binding)
        return response

    @staticmethod
    def _forward_request(
        request: RequestEnvelope,
    ) -> tuple[RequestEnvelope, SourceBinding | None]:
        arguments = dict(request.arguments)
        expected = arguments.pop("expected_source_binding", None)
        if expected is None:
            return request, None
        if not isinstance(expected, Mapping) or set(expected) != {
            "source_ref",
            "generation",
            "root_digest",
        }:
            raise OwnerAdapterError(
                "invalid_argument", "expected_source_binding has invalid fields"
            )
        source_ref = expected["source_ref"]
        generation = expected["generation"]
        root_digest = expected["root_digest"]
        if not all(
            isinstance(value, str) for value in (source_ref, generation, root_digest)
        ):
            raise OwnerAdapterError(
                "invalid_argument", "expected_source_binding fields must be strings"
            )
        try:
            binding = SourceBinding(
                source_ref=SinnixRef.parse(source_ref),
                generation=generation,
                root_digest=root_digest,
            )
        except ValueError as error:
            raise OwnerAdapterError(
                "invalid_argument", f"expected_source_binding is invalid: {error}"
            ) from error
        return replace(request, arguments=arguments), binding

    @staticmethod
    def _validate_response(
        adapter: ProjectOwnerAdapter,
        request: RequestEnvelope,
        response: ResponseEnvelope,
        expected_source_binding: SourceBinding | None,
    ) -> None:
        if (
            response.request_id != request.request_id
            or response.correlation_id != request.correlation_id
        ):
            raise OwnerAdapterError(
                "result_invalid", "owner adapter response does not match the request"
            )
        if response.owner != adapter.spec.owner:
            raise OwnerAdapterError(
                "authority_mismatch", "owner adapter response names the wrong owner"
            )
        if response.ok:
            if len(response.source_bindings) != 1:
                raise OwnerAdapterError(
                    "result_invalid",
                    "source-scoped owner responses require exactly one source binding",
                )
            binding = response.source_bindings[0]
            if binding.source_ref != adapter.source_ref:
                raise OwnerAdapterError(
                    "authority_mismatch",
                    "owner adapter response names the wrong source",
                )
            if (
                expected_source_binding is not None
                and binding != expected_source_binding
            ):
                raise OwnerAdapterError(
                    "authority_mismatch",
                    "owner adapter response does not match expected source binding",
                )
