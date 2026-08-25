from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .registry import REGISTRY, RegistryError

MAX_PROMPT_REF_BYTES = 2_048
MAX_PROMPT_INPUT_BYTES = 8_192
MAX_PROMPT_OUTPUT_BYTES = 32_768


@dataclass(frozen=True)
class PromptSpec:
    name: str
    intent: str
    description: str
    required: tuple[str, ...] = ("ref",)


PROMPT_SPECS = (
    PromptSpec(
        "orient-project", "project.orientation", "Orient on one project before acting."
    ),
    PromptSpec(
        "triage-beads", "project.triage", "Triage bounded Beads work for one project."
    ),
    PromptSpec("work-bead", "bead.work", "Prepare to work one canonical Beads task."),
    PromptSpec(
        "review-job", "job.review", "Review one daemon-owned job and its evidence."
    ),
    PromptSpec(
        "incident-orient", "incident", "Orient on current runtime incident evidence."
    ),
)

PROMPT_KINDS = {
    "project.orientation": frozenset({"project", "checkout"}),
    "project.triage": frozenset({"project", "checkout"}),
    "bead.work": frozenset({"bead"}),
    "bead.review": frozenset({"bead"}),
    "job.review": frozenset({"job"}),
    "incident": frozenset({"project"}),
}


class PromptGenerator:
    """Generate principal-visible guidance from canonical registry references."""

    def __init__(
        self, *, principal: str, catalog: Callable[[str], Mapping[str, Any]]
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
                    {
                        "name": "ref",
                        "description": "Canonical Sinnix target reference",
                        "required": True,
                    },
                    {
                        "name": "job_ref",
                        "description": "Canonical assigned job reference",
                        "required": False,
                    },
                ],
            }
            for spec in PROMPT_SPECS
        ]

    def _resolve_visible(self, reference: str) -> tuple[Any, dict[str, str]]:
        if len(reference.encode()) > MAX_PROMPT_REF_BYTES:
            raise ValueError("prompt reference exceeds its input bound")
        try:
            resource, values = REGISTRY.resolve(reference)
        except (RegistryError, ValueError) as exc:
            raise ValueError(
                "prompt ref is not a canonical registry reference"
            ) from exc
        if self.principal not in resource.principals:
            raise ValueError("prompt ref is not visible to this principal")
        if str(resource.ref_template.format(values)) != reference:
            raise ValueError("prompt ref is not canonical")
        return resource, values

    def generate(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        try:
            spec = self._specs[name]
        except KeyError as exc:
            raise ValueError(f"unknown gateway prompt: {name}") from exc
        values = dict(arguments or {})
        if (
            len(json.dumps(values, sort_keys=True, default=str).encode())
            > MAX_PROMPT_INPUT_BYTES
        ):
            raise ValueError("prompt arguments exceed their input bound")
        unknown = set(values) - {"ref", "job_ref"}
        if unknown:
            raise ValueError(f"prompt arguments are not recognized: {sorted(unknown)}")
        ref = values.get("ref")
        if not isinstance(ref, str):
            raise ValueError("prompt ref must be a canonical Sinnix reference")
        resource, _ = self._resolve_visible(ref)
        if resource.kind not in PROMPT_KINDS[spec.intent]:
            raise ValueError(
                f"prompt {spec.name} does not accept resource kind {resource.kind!r}"
            )
        job_ref = values.get("job_ref")
        if job_ref is not None:
            if not isinstance(job_ref, str):
                raise ValueError("prompt job_ref must be a canonical job reference")
            job_resource, _ = self._resolve_visible(job_ref)
            if job_resource.kind != "job":
                raise ValueError("prompt job_ref must resolve to a job resource")
            if spec.intent not in {"bead.review", "job.review", "bead.work"}:
                raise ValueError("this prompt does not accept a job_ref")
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
        body = {
            "schema": "sinnix.gateway-prompt.v1",
            "prompt": name,
            "intent": spec.intent,
            "principal": self.principal,
            "target_ref": ref,
            "job_ref": job_ref,
            "context_ref": ref,
            "action_catalog_revision": catalog.get("revision"),
            "actions": actions,
            "instructions": [
                f"Compose the {spec.intent} context for {ref} and use only evidence-bearing canonical refs from it.",
                "Treat unavailable components as explicit evidence gaps.",
                "Select actions from this principal-filtered catalog. This prompt does not grant mutation authority or invoke an action.",
                "When evidence changes, re-read the owner resource and compare its source revision before proceeding.",
            ],
        }
        text = json.dumps(body, sort_keys=True, separators=(",", ":"))
        if len(text.encode()) > MAX_PROMPT_OUTPUT_BYTES:
            raise ValueError("prompt output exceeds its bound")
        return [{"role": "user", "content": {"type": "text", "text": text}}]
