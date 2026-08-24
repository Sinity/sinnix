from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class PromptSpec:
    name: str
    intent: str
    description: str
    required: tuple[str, ...] = ("ref",)


PROMPT_SPECS = (
    PromptSpec("orient-project", "project.orientation", "Orient on one project before acting."),
    PromptSpec("triage-beads", "project.triage", "Triage bounded Beads work for one project."),
    PromptSpec("work-bead", "bead.work", "Prepare to work one canonical Beads task."),
    PromptSpec("review-job", "job.review", "Review one daemon-owned job and its evidence."),
    PromptSpec("incident-orient", "incident", "Orient on current runtime incident evidence."),
)


class PromptGenerator:
    """Generate user-invoked guidance from the context and action registries."""

    def __init__(
        self,
        *,
        principal: str,
        catalog: Callable[[str], Mapping[str, Any]],
    ) -> None:
        self.principal = principal
        self.catalog = catalog
        self._specs = {spec.name: spec for spec in PROMPT_SPECS}

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "arguments": [
                    {"name": "ref", "description": "Canonical Sinnix target reference", "required": True},
                    {"name": "job_ref", "description": "Canonical assigned job reference", "required": False},
                ],
            }
            for spec in PROMPT_SPECS
        ]

    def generate(self, name: str, arguments: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            spec = self._specs[name]
        except KeyError as exc:
            raise ValueError(f"unknown gateway prompt: {name}") from exc
        values = dict(arguments or {})
        unknown = set(values) - {"ref", "job_ref"}
        if unknown:
            raise ValueError(f"prompt arguments are not recognized: {sorted(unknown)}")
        ref = values.get("ref")
        if not isinstance(ref, str) or not ref.startswith("sinnix://"):
            raise ValueError("prompt ref must be a canonical Sinnix reference")
        job_ref = values.get("job_ref")
        if job_ref is not None and (not isinstance(job_ref, str) or not job_ref.startswith("sinnix://jobs/")):
            raise ValueError("prompt job_ref must be a canonical job reference")
        catalog = self.catalog(self.principal)
        actions = [
            {
                "name": row.get("name"),
                "verb": row.get("verb"),
                "effect": row.get("effect"),
                "route": row.get("route"),
                "resource_kinds": row.get("resource_kinds", []),
            }
            for row in catalog.get("actions", [])
            if isinstance(row, Mapping)
        ]
        context_ref = ref
        body = {
            "schema": "sinnix.gateway-prompt.v1",
            "prompt": name,
            "intent": spec.intent,
            "principal": self.principal,
            "target_ref": ref,
            "job_ref": job_ref,
            "context_ref": context_ref,
            "action_catalog_revision": catalog.get("revision"),
            "actions": actions,
            "instructions": [
                f"Compose the {spec.intent} context for {context_ref} and use only evidence-bearing canonical refs from it.",
                "Treat unavailable and stale components as explicit evidence gaps.",
                "Select actions from this principal-filtered catalog. This prompt does not grant mutation authority or invoke an action.",
                "When evidence changes, re-read the owner resource and compare its source revision before proceeding.",
            ],
        }
        text = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return [{"role": "user", "content": {"type": "text", "text": text}}]
