"""Canonical resource kinds and their ``sinnix://`` reference templates."""

from __future__ import annotations

from sinnix_mcp.refs import RefTemplate, SinnixRef

from .contracts import ResourceSpec


class RegistryError(ValueError):
    """Raised when resource declarations cannot form one contract."""


def _templates_overlap(left: RefTemplate, right: RefTemplate) -> bool:
    if len(left.segments) != len(right.segments):
        return False
    for left_segment, right_segment in zip(left.segments, right.segments, strict=True):
        left_variable = left_segment.startswith("{") and left_segment.endswith("}")
        right_variable = right_segment.startswith("{") and right_segment.endswith("}")
        if not left_variable and not right_variable and left_segment != right_segment:
            return False
    return True


class ResourceRegistry:
    """The resource kinds every action's refs are parsed and rendered against."""

    def __init__(self, resources: tuple[ResourceSpec, ...]) -> None:
        self.resources = resources
        self._by_kind = {resource.kind: resource for resource in resources}
        if len(self._by_kind) != len(resources):
            raise RegistryError("resource kinds must be unique")
        for index, left in enumerate(resources):
            for right in resources[index + 1 :]:
                if _templates_overlap(left.ref_template, right.ref_template):
                    raise RegistryError(
                        f"resource templates overlap: {left.kind} and {right.kind}"
                    )

    def resource(self, kind: str) -> ResourceSpec:
        try:
            return self._by_kind[kind]
        except KeyError as exc:
            raise RegistryError(f"unknown resource kind {kind!r}") from exc

    def reference(self, kind: str, values: dict[str, str]) -> str:
        return str(self.resource(kind).ref_template.format(values))

    def resolve(
        self, reference: str | SinnixRef
    ) -> tuple[ResourceSpec, dict[str, str]]:
        parsed = SinnixRef.parse(reference) if isinstance(reference, str) else reference
        matches = [
            (resource, values)
            for resource in self.resources
            if (values := resource.ref_template.match(parsed)) is not None
        ]
        if not matches:
            raise RegistryError(f"no resource template matches {parsed}")
        if len(matches) > 1:
            raise RegistryError(f"ambiguous resource reference: {parsed}")
        return matches[0]


def build_registry() -> ResourceRegistry:
    resources = (
        ResourceSpec(
            "project",
            RefTemplate("project", "sinnix://projects/{project_id}"),
            "projects",
            ("summary", "git", "tree"),
            True,
        ),
        ResourceSpec(
            "checkout",
            RefTemplate(
                "checkout", "sinnix://projects/{project_id}/checkouts/{checkout_id}"
            ),
            "projects",
            ("summary", "git", "files"),
            True,
        ),
        ResourceSpec(
            "bead",
            RefTemplate("bead", "sinnix://projects/{project_id}/beads/{bead_id}"),
            "beads",
            ("summary", "history", "graph"),
            True,
        ),
        ResourceSpec(
            "task_authority",
            RefTemplate(
                "task_authority", "sinnix://projects/{project_id}/task-authority"
            ),
            "beads",
            ("status",),
            False,
        ),
        ResourceSpec(
            "job",
            RefTemplate("job", "sinnix://jobs/{job_id}"),
            "jobs",
            ("summary", "output", "manifest"),
            True,
        ),
        ResourceSpec(
            "artifact",
            RefTemplate("artifact", "sinnix://artifacts/{artifact_id}"),
            "artifacts",
            ("metadata", "content"),
            True,
        ),
        ResourceSpec(
            "receipt",
            RefTemplate("receipt", "sinnix://receipts/{receipt_id}"),
            "audit",
            ("summary",),
            True,
        ),
        ResourceSpec(
            "result",
            RefTemplate("result", "sinnix://results/{result_id}"),
            "results",
            ("metadata", "page"),
            True,
        ),
        ResourceSpec(
            "machine_unit",
            RefTemplate("machine_unit", "sinnix://machine/units/{manager}/{unit}"),
            "machine",
            ("status", "health"),
            True,
        ),
        ResourceSpec(
            "browser_page",
            RefTemplate("browser_page", "sinnix://browser/pages/{page_id}"),
            "browser",
            ("summary", "content"),
            True,
        ),
        ResourceSpec(
            "browser_workspace",
            RefTemplate("browser_workspace", "sinnix://browser/agent-workspace"),
            "browser",
            ("summary",),
            False,
            principals=frozenset({"operator"}),
        ),
        ResourceSpec(
            "process",
            RefTemplate("process", "sinnix://processes/{pid}/{start_ticks}"),
            "machine",
            ("status",),
            True,
        ),
        ResourceSpec(
            "terminal",
            RefTemplate("terminal", "sinnix://terminals/{terminal_id}"),
            "terminals",
            ("summary", "scrollback"),
            True,
        ),
        ResourceSpec(
            "desktop",
            RefTemplate("desktop", "sinnix://desktop/current"),
            "desktop",
            ("summary",),
            True,
            principals=frozenset({"observer", "operator"}),
        ),
        ResourceSpec(
            "host_file",
            RefTemplate("host_file", "sinnix://files/{file_token}"),
            "files",
            ("summary",),
            True,
            principals=frozenset({"observer", "operator"}),
        ),
        ResourceSpec(
            "mcp_tool",
            RefTemplate("mcp_tool", "sinnix://mcp/{server}/tools/{tool}"),
            "mcp-broker",
            ("summary",),
            True,
            principals=frozenset({"observer", "operator"}),
        ),
        ResourceSpec(
            "capture_lane",
            RefTemplate("capture_lane", "sinnix://captures/{lane}"),
            "captures",
            ("summary", "query"),
            True,
        ),
        ResourceSpec(
            "capability",
            RefTemplate("capability", "sinnix://capabilities/{name}"),
            "capability-index",
            ("summary",),
            True,
        ),
        ResourceSpec(
            "session",
            RefTemplate("session", "sinnix://sessions/{provider}/{session_id}"),
            "sessions",
            ("summary", "messages"),
            True,
        ),
        ResourceSpec(
            "context_snapshot",
            RefTemplate("context_snapshot", "sinnix://contexts/{snapshot_id}"),
            "context",
            ("summary", "sources"),
            True,
        ),
    )
    return ResourceRegistry(resources)


REGISTRY = build_registry()
