from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .contracts import VerbFamily
from .registry import REGISTRY


BEGIN_MARKER = "<!-- BEGIN GENERATED GATEWAY V2 REFERENCE -->"
END_MARKER = "<!-- END GENERATED GATEWAY V2 REFERENCE -->"
REFERENCE_PATH = Path("docs/generated/agent-gateway-reference.md")
SKILL_PATH = Path("dots/_ai/skills/agent-gateway/SKILL.md")
FIXTURE_PATH = Path("pkgs/sinnix-agent-gateway/fixtures/v2-examples.json")
DOCS_PATH = Path("docs/agent-gateway.md")


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


def catalog_payload() -> dict[str, Any]:
    rows = REGISTRY.documentation_rows()
    for row in rows["actions"]:
        for example in row["examples"]:
            if row["name"] == "projects.change" and "parameters" not in example["input"]:
                example["input"]["parameters"] = {
                    key: example["input"].pop(key)
                    for key in ("path", "content", "patch")
                    if key in example["input"]
                }
    return {
        "schema": "sinnix.gateway-generated-catalog.v1",
        "revision": REGISTRY.revision,
        "action_catalog_hash": REGISTRY.action_catalog_hash(),
        "resources": rows["resources"],
        "actions": rows["actions"],
    }


def _action_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Action | Verb | Owner | Route | Schema |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['name']}` | `{row['verb']}` | `{row['owner']}` | `{row['route']}` | [`{row['schema_ref']}`]({row['schema_ref']}) |"
        )
    return lines


def _resource_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Resource | Owner | Canonical reference | Query |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['kind']}` | `{row['owner']}` | `{row['ref_template']}` | `{str(row['supports_query']).lower()}` |"
        )
    return lines


def render_reference() -> str:
    catalog = catalog_payload()
    lines = [
        "<!-- GENERATED FILE. DO NOT EDIT. -->",
        f"<!-- gateway-catalog-revision: {catalog['revision']} -->",
        f"<!-- gateway-catalog-sha256: {catalog['action_catalog_hash']} -->",
        "# Sinnix Agent Gateway V2 reference",
        "",
        "This reference is generated from `sinnix_agent_gateway.registry.REGISTRY`. The catalog hash changes when an action, resource, schema, route, principal, bound, or example changes.",
        "",
        f"Revision: `{catalog['revision']}`. Catalog SHA-256: `{catalog['action_catalog_hash']}`.",
        "",
        "## Ten CLI verbs",
        "",
        "Each verb calls the matching MCP tool through the same runtime and principal. Requests accept `--input`, `--input-file`, or `--stdin`; common request controls can be supplied as flags. Mutating requests require the idempotency key declared by their selected action.",
        "",
        "| Verb | CLI subcommand | MCP tool |",
        "| --- | --- | --- |",
    ]
    for verb in VerbFamily:
        lines.append(f"| `{verb.value}` | `sinnix-agent-gateway {verb.value}` | `{verb.value}` |")
    lines.extend(["", "## Resources", "", *_resource_table(catalog["resources"]), "", "## Actions", "", *_action_table(catalog["actions"]), ""])
    for row in catalog["actions"]:
        lines.extend(
            [
                f"### `{row['name']}`",
                "",
                row["documentation"],
                "",
                f"Owner route: `{row['route']}`. Principals: `{', '.join(row['principals'])}`. Typed failures: `{', '.join(row['typed_failures'])}`.",
                "",
                "Input schema:",
                "",
                "```json",
                _json(row["input_schema"]),
                "```",
                "",
                "Examples:",
                "",
            ]
        )
        if row["examples"]:
            for example in row["examples"]:
                lines.extend(["```json", _json(example["input"]), "```", ""])
        else:
            lines.append("No example is declared. Discover the live schema before invoking this action.\n")
    return "\n".join(lines).rstrip() + "\n"


def _action_name(rows: list[dict[str, Any]], name: str, fallback: str) -> str:
    return name if any(row["name"] == name for row in rows) else fallback


def render_skill() -> str:
    catalog = catalog_payload()
    context = _action_name(catalog["actions"], "projects.context", "gateway.catalog")
    triage = _action_name(catalog["actions"], "beads.query", "gateway.catalog")
    changeset = _action_name(catalog["actions"], "beads.changeset", "gateway.catalog")
    agent = _action_name(catalog["actions"], "agent.for_bead", "gateway.catalog")
    machine = _action_name(catalog["actions"], "machine.query", "gateway.catalog")
    browser = _action_name(catalog["actions"], "browser.operate", "gateway.catalog")
    desktop = _action_name(catalog["actions"], "desktop.operate", "gateway.catalog")
    return f'''---
name: agent-gateway
description: Use when invoking, inspecting, or documenting Sinnix Agent Gateway V2 resources and actions through its ten-verb CLI or MCP contract.
---

<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: {catalog['revision']} -->
<!-- gateway-catalog-sha256: {catalog['action_catalog_hash']} -->
# Agent Gateway V2

Use `sinnix-agent-gateway` when a local agent needs the same principal-scoped routes and normalized envelopes as MCP. The complete action schemas and examples are in `docs/generated/agent-gateway-reference.md`.

## Invocation

Start with `sinnix-agent-gateway catalog --query "<need>" --principal <principal>` when the route is unknown. Catalog discovery is optional when a canonical action and resource reference are already known. Use `catalog --schema <action>` for the live input schema and `catalog --example <action>` for executable examples.

Every request accepts one bounded JSON source: `--input '{{"ref":"..."}}'`, `--input-file request.json`, or `--stdin`. Common controls include `--request-id`, `--actor`, `--reason`, `--idempotency-key`, `--deadline-at`, and `--preconditions`. Outputs are normalized V2 envelopes with result, receipt, refs, source metadata, and typed errors.

The CLI invokes the matching MCP verb through the same server runtime and principal. It does not create an alternate owner route. Invalid JSON, non-object JSON, unknown fields, schema violations, and inputs larger than 262144 bytes are rejected before owner dispatch.

## Workflow prompts

- Project orientation: call `{context}` with a canonical `sinnix://projects/<project>` ref and `intent=project`, then follow the returned checkout and task-authority refs.
- Beads triage: call `{triage}` with bounded project IDs, a view or native filters, and only the includes needed for the decision.
- Bulk Beads changes: call `{changeset}` with `operation=preview`, inspect every planned step and source revision, then replay the same request with the returned preview digest and `operation=apply`.
- Work or review a bead: use `{agent}` only with the canonical bead ref and explicit checkout. Use `projects.context` with `intent=bead.work` or `bead.review` to inspect assignment and evidence.
- Incident orientation: use `machine.query` for one bounded owner-selected section and `audit.events` for recent gateway receipts. Do not reconstruct a whole-machine view locally.
- Browser or desktop manipulation: discover or use the canonical gateway-owned browser page or desktop ref, then invoke `{browser}` or `{desktop}` as operator. Existing operator tabs are never accepted as implicit targets.
- Machine action: discover a canonical machine target, supply the owner-required revision, reason, idempotency key, and preconditions, then use `machine.operate`.

## Beads direct-owner fallback

The gateway is the preferred route for typed, principal-scoped Beads work. The direct owner fallback is `bd 1.1.0-dev` against the project’s canonical standalone Dolt workspace, resolved through the project’s canonical worktree and `.beads/redirect`. Dolt is the authority for ordinary mutations. `issues.jsonl` is an optional JSONL export, not a write authority. Use the gateway `beads.operate` action with `snapshot.publish` when an explicit deterministic snapshot is required. Snapshot publication does not imply a Git commit or a Dolt push. Use `sync.push` or `sync.pull` explicitly for Dolt synchronization. Never hand-author `bd` argv when the gateway catalog exposes the needed action.

Catalog revision: `{catalog['revision']}`. Catalog SHA-256: `{catalog['action_catalog_hash']}`.
'''


def _fixture_input(row: dict[str, Any]) -> dict[str, Any]:
    if row["examples"]:
        value = dict(row["examples"][0]["input"])
    else:
        value = {}
    if row["verb"] in {verb.value for verb in (VerbFamily.QUERY, VerbFamily.RUN, VerbFamily.CHANGE, VerbFamily.OPERATE)}:
        value.setdefault("action_name", row["name"])
    if row["name"] == "machine.operate" and "action" in value:
        value["operation"] = value.pop("action")
    if row["name"] == "projects.change" and "parameters" not in value:
        value["parameters"] = {
            key: value.pop(key)
            for key in ("path", "content", "patch")
            if key in value
        }
    return value


def render_fixtures() -> dict[str, Any]:
    catalog = catalog_payload()
    return {
        "schema": "sinnix.gateway-cli-fixtures.v1",
        "revision": catalog["revision"],
        "action_catalog_hash": catalog["action_catalog_hash"],
        "examples": [
            {
                "action": row["name"],
                "verb": row["verb"],
                "input": dict(row["examples"][0]["input"]) if row["examples"] else {},
                "cli_input": _fixture_input(row),
            }
            for row in catalog["actions"]
        ],
    }


def render_docs_section() -> str:
    catalog = catalog_payload()
    lines = [
        BEGIN_MARKER,
        "## Generated V2 reference",
        "",
        f"This section is generated from the canonical gateway registry. Revision `{catalog['revision']}`, catalog SHA-256 `{catalog['action_catalog_hash']}`.",
        "",
        "The full schemas and executable examples are in [the generated gateway reference](generated/agent-gateway-reference.md). The matching agent skill is [agent-gateway](../dots/_ai/skills/agent-gateway/SKILL.md).",
        "",
        *_action_table(catalog["actions"]),
        "",
        "Direct-owner fallback semantics: `bd 1.1.0-dev` uses the canonical standalone Dolt workspace resolved through the canonical worktree and `.beads/redirect`; Dolt remains authoritative, JSONL is an optional export, and snapshot publication is explicit through `beads.operate` with `snapshot.publish`.",
        END_MARKER,
    ]
    return "\n".join(lines) + "\n"


def update_docs(text: str) -> str:
    generated = render_docs_section().rstrip("\n")
    if BEGIN_MARKER in text and END_MARKER in text:
        before = text.split(BEGIN_MARKER, 1)[0].rstrip("\n")
        after = text.split(END_MARKER, 1)[1].lstrip("\n")
        return f"{before}\n{generated}\n{after}" if after else f"{before}\n{generated}\n"
    return text.rstrip("\n") + "\n\n" + generated + "\n"


def generated_files(root: Path) -> dict[Path, str]:
    return {
        root / REFERENCE_PATH: render_reference(),
        root / SKILL_PATH: render_skill(),
        root / FIXTURE_PATH: _json(render_fixtures()) + "\n",
        root / DOCS_PATH: update_docs((root / DOCS_PATH).read_text()),
    }


def write_artifacts(root: Path) -> None:
    for path, content in generated_files(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def check_artifacts(root: Path) -> list[str]:
    mismatches: list[str] = []
    for path, expected in generated_files(root).items():
        if not path.exists():
            mismatches.append(f"missing generated artifact: {path.relative_to(root)}")
        elif path.read_text() != expected:
            mismatches.append(f"stale or corrupt generated artifact: {path.relative_to(root)}")
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate gateway V2 docs, skill, and fixtures")
    parser.add_argument("--root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.write:
        write_artifacts(root)
        return 0
    mismatches = check_artifacts(root)
    if mismatches:
        for mismatch in mismatches:
            print(mismatch)
        return 1
    print("gateway artifacts are current")
    return 0
