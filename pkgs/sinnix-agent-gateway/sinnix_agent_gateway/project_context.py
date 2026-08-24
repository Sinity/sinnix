from __future__ import annotations

import json
from typing import Any

from .beads import BeadsError, BeadsService
from .capabilities import Capability, Principal
from .projects import ProjectService
from .redaction import public_error


class ProjectContextService:
    def __init__(
        self,
        principal: Principal,
        projects: ProjectService,
        beads: BeadsService,
    ):
        self.principal = principal
        self.projects = projects
        self.beads = beads

    def context(self, project_id: str) -> dict[str, Any]:
        self.principal.require(Capability.PROJECT_READ)
        summary = self.projects.summary(project_id)
        if self.principal.name == "agent-control":
            tasks: dict[str, Any] = {
                "availability": "unavailable",
                "reason": "assigned Beads context requires a bound job reference",
            }
        elif Capability.TASK_READ not in self.principal.capabilities:
            tasks: dict[str, Any] = {
                "availability": "unavailable",
                "reason": "task.read is not granted to this principal",
            }
        else:
            try:
                tasks = {
                    "availability": "available",
                    **self.beads.query(project_ids=[project_id], view="ready", limit=20),
                }
            except BeadsError as exc:
                tasks = {
                    "availability": "unavailable",
                    "reason": public_error(exc),
                    "next_route": "query:beads.query",
                }
        response = {
            "project": summary,
            "tasks": tasks,
            "next_routes": [
                "project_tree",
                "project_read",
                "query",
                "project_diff",
                "query:beads.query",
            ],
        }
        encoded = json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) <= self.projects.config.max_result_bytes:
            return response
        return {
            "project": summary,
            "tasks": {
                "availability": "unavailable",
                "reason": "ready task result exceeded project context response bound",
                "next_route": "query:beads.query",
            },
            "next_routes": response["next_routes"],
        }
