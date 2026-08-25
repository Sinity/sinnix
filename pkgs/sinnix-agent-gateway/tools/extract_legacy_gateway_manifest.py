#!/usr/bin/env python3
"""Extract the retired Gateway V1 public tool set from its pinned source commit."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path

LEGACY_COMMIT = "e5980a67eae343f954f695c46a8fadda83961a03"
LEGACY_APP_PATH = "pkgs/sinnix-agent-gateway/sinnix_agent_gateway/app.py"


def legacy_tool_names(source: str) -> list[str]:
    module = ast.parse(source)
    tools: list[str] = []

    class ToolVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_tool(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_tool(node)
            self.generic_visit(node)

        def _visit_tool(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            if any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "tool"
                for decorator in node.decorator_list
            ):
                tools.append(node.name)

    ToolVisitor().visit(module)
    return tools


def historical_manifest(repo: Path) -> dict[str, object]:
    source = subprocess.run(
        ["git", "-C", str(repo), "show", f"{LEGACY_COMMIT}:{LEGACY_APP_PATH}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        "schema": "sinnix.gateway-legacy-tool-list.v1",
        "source_commit": LEGACY_COMMIT,
        "tools": legacy_tool_names(source),
    }


def migration_tool_names(parity_module: Path) -> list[str]:
    """Read the ordered V1 keys from the checked-in migration map.

    This deliberately parses source rather than importing the gateway package:
    the CI provenance check must be able to run before its dependencies are
    built, and it must compare the map directly with the historical source.
    """
    module = ast.parse(parity_module.read_text(), filename=str(parity_module))
    for node in module.body:
        if not (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "V2_MIGRATIONS"
                for target in node.targets
            )
            and isinstance(node.value, ast.Dict)
        ):
            continue
        names: list[str] = []
        for key in node.value.keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                raise ValueError("V2_MIGRATIONS keys must be string literals")
            names.append(key.value)
        return names
    raise ValueError("could not find V2_MIGRATIONS in parity module")


def canonical_manifest_bytes(manifest: object) -> int:
    if not isinstance(manifest, dict):
        raise ValueError("legacy operator manifest must be an object")
    tools = manifest.get("tools")
    if manifest.get("schema") != "sinnix.gateway-tools.v1" or not isinstance(
        tools, list
    ):
        raise ValueError("legacy operator manifest must contain schema and tools")
    payload = json.dumps(
        {"schema": manifest["schema"], "tools": tools},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return len(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--extract-only", action="store_true")
    arguments = parser.parse_args()
    manifest = historical_manifest(arguments.repo)
    if arguments.extract_only:
        if arguments.verify is not None:
            parser.error("--extract-only cannot be combined with --verify")
        print(json.dumps(manifest, sort_keys=True))
        return
    operator_manifest = json.loads(
        subprocess.run(
            [
                "nix",
                "run",
                f"git+{arguments.repo.resolve().as_uri()}?rev={LEGACY_COMMIT}"
                "#sinnix-agent-gateway",
                "--",
                "--principal",
                "operator",
                "manifest",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    measured_bytes = canonical_manifest_bytes(operator_manifest)
    manifest["canonical_bytes"] = measured_bytes
    if arguments.verify is not None:
        expected = json.loads(arguments.verify.read_text())
        if manifest != expected:
            raise SystemExit(
                "checked-in legacy manifest does not match the pinned source"
            )
        migration_tools = migration_tool_names(arguments.verify.parent / "parity.py")
        historical_tools = manifest["tools"]
        if migration_tools != historical_tools:
            raise SystemExit(
                "checked-in parity map does not match the pinned source in order"
            )
        print(f"verified {measured_bytes} canonical legacy manifest bytes")
        print(f"verified {len(manifest['tools'])} legacy Gateway V1 tools")
        print("verified parity map names and order against the pinned source")
        return
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
