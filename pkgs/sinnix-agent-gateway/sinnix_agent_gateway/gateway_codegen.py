"""Generate the reference, skill, fixtures and docs section from the actions."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import actions as action_set
from .contracts import VerbFamily

BEGIN_MARKER = "<!-- BEGIN GENERATED GATEWAY V2 REFERENCE -->"
END_MARKER = "<!-- END GENERATED GATEWAY V2 REFERENCE -->"
REFERENCE_PATH = Path("docs/generated/agent-gateway-reference.md")
SKILL_PATH = Path("dots/_ai/skills/agent-gateway/SKILL.md")
FIXTURE_PATH = Path("pkgs/sinnix-agent-gateway/fixtures/v2-examples.json")
DOCS_PATH = Path("docs/agent-gateway.md")
PRINCIPAL = "operator"


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


def catalog_payload() -> dict[str, Any]:
    return {
        "schema": "sinnix.gateway-generated-catalog.v2",
        "revision": action_set.REVISION,
        "action_catalog_hash": action_set.catalog_hash(PRINCIPAL),
        "resources": action_set.resource_rows(PRINCIPAL),
        "actions": [action.catalog_row() for action in action_set.visible(PRINCIPAL)],
    }


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    """Column-aligned pipe table, the shape prettier leaves unchanged."""
    widths = [
        max(len(cell) for cell in column) for column in zip(header, *rows, strict=True)
    ]

    def line(cells: list[str]) -> str:
        padded = (c.ljust(w) for c, w in zip(cells, widths, strict=True))
        return "| " + " | ".join(padded) + " |"

    return [line(header), line(["-" * w for w in widths]), *(line(r) for r in rows)]


def _action_table(rows: list[dict[str, Any]]) -> list[str]:
    return _table(
        ["Action", "Family", "Owner", "Principals", "Summary"],
        [
            [
                f"`{row['name']}`",
                f"`{row['verb']}`",
                f"`{row['owner']}`",
                f"`{', '.join(row['principals'])}`",
                row["documentation"],
            ]
            for row in rows
        ],
    )


def _resource_table(rows: list[dict[str, Any]]) -> list[str]:
    return _table(
        ["Resource", "Owner", "Canonical reference", "Actions"],
        [
            [
                f"`{row['kind']}`",
                f"`{row['owner']}`",
                f"`{row['ref_template']}`",
                ", ".join(f"`{name}`" for name in row["actions"]) or "-",
            ]
            for row in rows
        ],
    )


def render_reference() -> str:
    catalog = catalog_payload()
    lines = [
        "<!-- GENERATED FILE. DO NOT EDIT. -->",
        f"<!-- gateway-catalog-revision: {catalog['revision']} -->",
        f"<!-- gateway-catalog-sha256: {catalog['action_catalog_hash']} -->",
        "# Sinnix Agent Gateway reference",
        "",
        "Generated from `sinnix_agent_gateway.actions`. Every action is one MCP tool "
        "whose `tools/list` input schema is the one below; the catalog hash changes "
        "when an action, schema, principal set, example or affordance changes.",
        "",
        f"Revision: `{catalog['revision']}`. Catalog SHA-256: `{catalog['action_catalog_hash']}`.",
        "",
        "## Invocation",
        "",
        "MCP: call the tool named after the action. CLI: "
        "`sinnix-agent-gateway call <action> --input '<json>'` or `--set key=value`; "
        "`sinnix-agent-gateway catalog <action> --schema` prints the live schemas.",
        "",
        "## Resources",
        "",
        *_resource_table(catalog["resources"]),
        "",
        "## Actions",
        "",
        *_action_table(catalog["actions"]),
        "",
    ]
    for row in catalog["actions"]:
        lines.extend(
            [
                f"### `{row['name']}`",
                "",
                row["documentation"],
                "",
                f"Family: `{row['verb']}`. Owner: `{row['owner']}`. "
                f"Principals: `{', '.join(row['principals'])}`. "
                f"Typed failures: `{', '.join(row['typed_failures'])}`.",
                "",
            ]
        )
        if row["aliases"]:
            lines.extend([f"Aliases: {', '.join(row['aliases'])}.", ""])
        if row["affordances"]:
            lines.extend(
                [
                    "Follow-up actions: "
                    + ", ".join(f"`{name}`" for name in row["affordances"])
                    + ".",
                    "",
                ]
            )
        lines.extend(
            [
                "Input schema:",
                "",
                "```json",
                _json(row["input_schema"]),
                "```",
                "",
                "Output: the response envelope's `data` field is `"
                + action_set.BY_NAME[row["name"]].Output.__name__
                + "`; the full envelope schema is the `sinnix://gateway/v2/actions/"
                + row["name"]
                + "` resource and `sinnix-agent-gateway catalog "
                + row["name"]
                + " --schema`.",
                "",
                "Examples:",
                "",
            ]
        )
        for example in row["examples"]:
            lines.extend(
                [
                    f"{example['title']}:",
                    "",
                    "```json",
                    _json(example["input"]),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_skill() -> str:
    catalog = catalog_payload()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in catalog["actions"]:
        grouped[row["verb"]].append(row)
    index = []
    for family in VerbFamily:
        rows = grouped.get(family.value)
        if not rows:
            continue
        index.append(f"### {family.value}")
        index.append("")
        for row in rows:
            index.append(f"- `{row['name']}` — {row['documentation']}")
        index.append("")
    body = "\n".join(index).rstrip()
    return f"""---
name: agent-gateway
description: Use when invoking, inspecting, or documenting Sinnix Agent Gateway actions through their typed MCP tools or the sinnix-agent-gateway CLI.
---

<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: {catalog["revision"]} -->
<!-- gateway-catalog-sha256: {catalog["action_catalog_hash"]} -->

# Agent Gateway

Every gateway action is one MCP tool named after the action; its input schema in `tools/list` is the contract and its output envelope schema is the `sinnix://gateway/v2/actions/<name>` resource. Paths, ids, titles and unit names are accepted where a canonical `sinnix://` ref is; responses return the canonical ref and `affordances` naming the next actions. Images arrive as image content blocks, other binary as resource blocks.

## Invocation

- MCP: call the tool by action name with the fields of its input schema.
- CLI: `sinnix-agent-gateway call <action> --input '{{...}}'` or `--set key=value` (values parse as JSON); `--principal` selects authority. `sinnix-agent-gateway catalog <action> --schema` prints the live schemas, `--example` the examples, `catalog --complete <prefix>` lists names.
- Discovery: `gateway.catalog` with a plain-words `query` finds actions, resources and brokered MCP tools; `gateway.status` reports contract hashes and route availability.

Effectful actions (families change, operate, run) require `idempotency_key`; replaying the same key with the same request returns the stored response. Preconditions such as `expected_sha256` or checkout `head` fail with `precondition_failed` instead of overwriting.

## Actions

{body}

The complete schemas and examples are in `docs/generated/agent-gateway-reference.md`.

Catalog revision: `{catalog["revision"]}`. Catalog SHA-256: `{catalog["action_catalog_hash"]}`.
"""


def render_fixtures() -> dict[str, Any]:
    catalog = catalog_payload()
    return {
        "schema": "sinnix.gateway-cli-fixtures.v2",
        "revision": catalog["revision"],
        "action_catalog_hash": catalog["action_catalog_hash"],
        "examples": [
            {
                "action": row["name"],
                "family": row["verb"],
                "title": example["title"],
                "input": example["input"],
            }
            for row in catalog["actions"]
            for example in row["examples"]
        ],
    }


def render_docs_section() -> str:
    catalog = catalog_payload()
    lines = [
        BEGIN_MARKER,
        "",
        "## Generated reference",
        "",
        f"This section is generated from the action set. Revision `{catalog['revision']}`, catalog SHA-256 `{catalog['action_catalog_hash']}`.",
        "",
        "The full schemas and examples are in [the generated gateway reference](generated/agent-gateway-reference.md). The matching agent skill is [agent-gateway](../dots/_ai/skills/agent-gateway/SKILL.md).",
        "",
        *_action_table(catalog["actions"]),
        "",
        END_MARKER,
    ]
    return "\n".join(lines) + "\n"


def update_docs(text: str) -> str:
    generated = render_docs_section().rstrip("\n")
    if BEGIN_MARKER in text and END_MARKER in text:
        before = text.split(BEGIN_MARKER, 1)[0].rstrip("\n")
        after = text.split(END_MARKER, 1)[1].lstrip("\n")
    else:
        before, after = text.rstrip("\n"), ""
    head = f"{before}\n\n" if before else ""
    return f"{head}{generated}\n{after}"


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
            mismatches.append(
                f"stale or corrupt generated artifact: {path.relative_to(root)}"
            )
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate gateway docs, skill, and fixtures"
    )
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


if __name__ == "__main__":
    raise SystemExit(main())
