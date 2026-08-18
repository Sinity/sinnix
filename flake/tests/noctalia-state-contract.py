"""Cross-component contract: panel bindings vs the reducer's published state.

The Noctalia ops plugin renders `snapshot.state.<key>` values that originate
in two producers: sinnix-observe's collect_report() dict (passed through by
the reducer) and the reducer's own state additions in Reducer.refresh().
A key the plugin binds but neither producer publishes can only ever render
a placeholder -- which is exactly how the panel rotted into "reported"/"?"
rows. Both sides are read from their own source (Python via ast, Luau via
the literal-key access conventions), so this is an agreement between two
components, not a restated list.

Kill-mutation (verified): binding stateValue("gpu") in panel.luau fails this
check with `bound state key "gpu" is not published`.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path


def observe_report_keys(observe_root: Path) -> set[str]:
    """Keys of the dict collect_report() returns in sinnix-observe's cli."""
    tree = ast.parse((observe_root / "sinnix_observe/cli.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "collect_report":
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                    return {
                        key.value
                        for key in stmt.value.keys
                        if isinstance(key, ast.Constant) and isinstance(key.value, str)
                    }
    raise SystemExit("could not find collect_report's returned dict in cli.py")


def reducer_state_keys(reducer_root: Path) -> set[str]:
    """Keys the reducer adds on top of the observe report in refresh()."""
    tree = ast.parse((reducer_root / "sinnix_ops_reducer/reducer.py").read_text())
    keys: set[str] = set()
    for node in ast.walk(tree):
        # `report["attention"] = ...` style additions.
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "report"
                    and isinstance(target.slice, ast.Constant)
                    and isinstance(target.slice.value, str)
                ):
                    keys.add(target.slice.value)
        # `{**report, "ambient_intelligence": ..., ...}` -- the state dict.
        if isinstance(node, ast.Dict) and any(key is None for key in node.keys):
            spreads_report = any(
                key is None and isinstance(value, ast.Name) and value.id == "report"
                for key, value in zip(node.keys, node.values, strict=True)
            )
            if spreads_report:
                keys.update(
                    key.value
                    for key in node.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
    if not keys:
        raise SystemExit("could not find reducer state additions in reducer.py")
    return keys


BINDING_PATTERNS = (
    re.compile(r'stateValue\(\s*"([A-Za-z0-9_]+)"\s*\)'),
    re.compile(r"snapshot\.state\.([A-Za-z0-9_]+)"),
    re.compile(r'snapshot\.state\[\s*"([A-Za-z0-9_]+)"\s*\]'),
)


def plugin_bound_keys(plugin_root: Path) -> dict[str, list[str]]:
    """Every snapshot-state key each plugin entry binds, by file."""
    bound: dict[str, list[str]] = {}
    for entry in sorted(plugin_root.glob("*.luau")):
        text = entry.read_text()
        keys = sorted(
            {match for pattern in BINDING_PATTERNS for match in pattern.findall(text)}
        )
        if keys:
            bound[entry.name] = keys
    if not bound:
        raise SystemExit(
            "no state bindings found in any plugin entry; extractor broken?"
        )
    return bound


def main() -> int:
    plugin_root = Path(os.environ["NOCTALIA_OPS_PLUGIN"])
    reducer_root = Path(os.environ["NOCTALIA_OPS_REDUCER"])
    observe_root = Path(os.environ["NOCTALIA_OPS_OBSERVE"])
    published = observe_report_keys(observe_root) | reducer_state_keys(reducer_root)
    failures = []
    for entry, keys in plugin_bound_keys(plugin_root).items():
        for key in keys:
            if key not in published:
                failures.append(
                    f'{entry}: bound state key "{key}" is not published by the reducer'
                )
    if failures:
        print("\n".join(failures), file=sys.stderr)
        print(
            "published keys: " + ", ".join(sorted(published)),
            file=sys.stderr,
        )
        return 1
    print(f"state contract holds: {len(published)} published keys cover every binding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
