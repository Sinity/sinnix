"""Generate the agent skill from the actions; render the reference on demand.

The full reference (every schema and example) is printed by `--reference`
rather than tracked: `sinnix-agent-gateway catalog <action> --schema` serves
the same contract live.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import actions as action_set
from .orientation import ORIENTATION

SKILL_PATH = Path("dots/_ai/skills/agent-gateway/SKILL.md")


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


def catalog_payload() -> dict[str, Any]:
    return {
        "schema": "sinnix.gateway-generated-catalog.v2",
        "revision": action_set.REVISION,
        "action_catalog_hash": action_set.catalog_hash(),
        "resources": action_set.resource_rows(),
        "actions": [action.catalog_row() for action in action_set.ALL_ACTIONS],
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
        ["Action", "Family", "Owner", "Summary"],
        [
            [
                f"`{row['name']}`",
                f"`{row['family']}`",
                f"`{row['owner']}`",
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
        "when any action catalog row changes, including its schema, example or "
        "next action.",
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
                f"Family: `{row['family']}`. Owner: `{row['owner']}`. "
                f"Typed failures: `{', '.join(row['typed_failures'])}`.",
                "",
            ]
        )
        if row["aliases"]:
            lines.extend([f"Aliases: {', '.join(row['aliases'])}.", ""])
        if row["next_actions"]:
            lines.extend(
                [
                    "Follow-up actions: "
                    + ", ".join(f"`{name}`" for name in row["next_actions"])
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
                + "`; the full envelope schema is the `sinnix://gateway/actions/"
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
    return f"""---
name: agent-gateway
description: Use when invoking, inspecting, or documenting Sinnix Agent Gateway actions through their typed MCP tools or the sinnix-agent-gateway CLI.
---

<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: {catalog["revision"]} -->
<!-- gateway-catalog-sha256: {catalog["action_catalog_hash"]} -->

# Agent Gateway

Every gateway action is one MCP tool named after the action; its input schema in `tools/list` is the contract and its output envelope schema is the `sinnix://gateway/actions/<name>` resource. Paths, ids, titles and unit names are accepted where a canonical `sinnix://` ref is; responses return the canonical ref and `next_actions` naming the next actions. Images arrive as image content blocks, other binary as resource blocks.

## Orientation

{ORIENTATION}

## Invocation

- MCP: call the tool by action name with the fields of its input schema.
- CLI: `sinnix-agent-gateway call <action> --input '{{...}}'` or `--set key=value` (values parse as JSON); `sinnix-agent-gateway catalog <action> --schema` prints the live schemas, `--example` the examples, `catalog --complete <prefix>` lists names.
- Discovery: `gateway.catalog` with a plain-words `query` finds actions, resources and brokered MCP tools; `gateway.status` reports contract hashes and route availability.

Effectful actions (families change, operate, run) require `idempotency_key`. Confirmed responses replay unchanged. Pending calls refuse concurrent execution; interrupted calls become indeterminate and never retry their effects automatically. `operations.run` and `shell.run` reconcile through durable agentctl launch identities; hub-backed machine actions and process stop reconcile only exact confirmed owner receipts. Other interrupted mutations remain indeterminate. Preconditions are owner-specific checks, best effort unless the owner explicitly guarantees atomic comparison and mutation.

Run ordinary commands through `shell.run` and declared jobs through `operations.run`. `terminals.open` and `terminals.run` operate graphical Kitty windows; use them when the task needs an interactive terminal. If a checkout is unregistered, register its project and environment before running its jobs.

## Workflows

- Read the relevant action schema before calling it. Discover actions with `gateway.catalog`; use `gateway.describe` for an exact name. When a client has not loaded a typed tool, `gateway.read`, `gateway.change` and `gateway.run` accept the exact action name and its ordinary input in `arguments`.
- Resolve locators once, then use the returned canonical refs. A conflict lists candidates; choose from those using the task context. A stale browser element needs a new page snapshot.
- Before changing a file or checkout, read it and pass its returned hash or revision as the action's precondition. Preconditions have the owner's guarantees; inspect partial filesystem receipts before continuing.
- Keep both job identifiers: numeric `task_id` is pueue's queue position, while string `job_id` follows the job across a reorder. Include both in subsequent `jobs.*` targets. Batch worker and landing rows carry the same pair.
- Wait on the returned job handle. `running` and `queued` are continuations. Use the continuation's `target` and previous `output.next_offset` as `jobs.wait`'s `target` and `output_offset` to receive new bytes. Inspect the terminal result before retrying.
- Choose an `idempotency_key` before an effectful call. If its response is lost, query `audit.operation` with the action and key before doing anything else. A confirmed response is recoverable; pending or indeterminate effects require owner evidence.
- Read large responses through their `snapshot_ref` or artifact refs; preserve cursors and offsets. Component coverage distinguishes empty data from unavailable evidence.

## Contract and troubleshooting

The live catalog owns action names, schemas, examples and follow-up actions. `sinnix-agent-gateway-generate --reference` prints the complete reference from the same declarations. Read `/realm/project/sinnix/repo/docs/agent-gateway.md` for authority, deployment, connector refresh and upstream ownership; load `agent-runtime` for job and batch recovery.

`gateway.status` compares live, packaged and last-recorded connector hashes. The saved connector snapshot does not prove which tools the current client loaded. After a refresh, inspect the client's actual schema before recording its observed hash. A numeric `job_id` schema is stale: the current contract uses a string and a separate numeric `task_id`.

Catalog revision: `{catalog["revision"]}`. Catalog SHA-256: `{catalog["action_catalog_hash"]}`.
"""


def generated_files(root: Path) -> dict[Path, str]:
    doc = root / "docs/agent-gateway.md"
    files = {root / SKILL_PATH: render_skill()}
    if doc.exists():
        before, rest = doc.read_text().split("<!-- orientation:start -->", 1)
        _, after = rest.split("<!-- orientation:end -->", 1)
        files[doc] = (
            before
            + "<!-- orientation:start -->\n"
            + ORIENTATION
            + "\n<!-- orientation:end -->"
            + after
        )
    return files


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
        description="Generate the gateway skill, or print the reference"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument(
        "--reference", action="store_true", help="print the full reference"
    )
    args = parser.parse_args()
    if args.reference:
        print(render_reference(), end="")
        return 0
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
