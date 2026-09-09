"""Contract tests for the /realm taxonomy ratchet.

The manifest is never restated here: the fixture tree is built from the
MISSING lines the script itself emits against an empty tree, so a taxonomy
change needs no edit in this file and cannot be ratified by one.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "scripts" / "lake-lint"

ROOTS = ("realm", "outer-realm")


def run(prefix: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT)],
        env={**os.environ, "LAKE_LINT_ROOT_PREFIX": str(prefix)},
        capture_output=True,
        text=True,
    )


def required_nodes(prefix: Path) -> list[str]:
    """The manifest, as the script reports it against bare roots."""
    for root in ROOTS:
        (prefix / root).mkdir(parents=True, exist_ok=True)
    result = run(prefix)
    assert result.returncode == 1, result.stdout
    missing = [
        line.split("MISSING required node: ", 1)[1]
        for line in result.stdout.splitlines()
        if "MISSING required node: " in line
    ]
    # /realm is created above as a root, so it is not reported missing.
    assert missing, result.stdout
    return missing


def build_lake(prefix: Path) -> list[str]:
    nodes = required_nodes(prefix)
    for node in nodes:
        Path(node).mkdir(parents=True, exist_ok=True)
    return nodes


def test_matching_tree_passes(tmp_path):
    prefix = tmp_path / "lake"
    build_lake(prefix)
    result = run(prefix)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "all roots match taxonomy" in result.stdout


def test_node_on_disk_that_the_manifest_does_not_name_fails(tmp_path):
    prefix = tmp_path / "lake"
    build_lake(prefix)
    node = prefix / "realm" / "unratified"
    node.mkdir()
    result = run(prefix)
    assert result.returncode == 1
    assert f"UNEXPECTED node: {node}" in result.stdout


def test_manifest_node_missing_from_disk_fails(tmp_path):
    prefix = tmp_path / "lake"
    nodes = build_lake(prefix)
    victim = next(node for node in nodes if node.endswith("/realm/activity"))
    Path(victim).rmdir()
    result = run(prefix)
    assert result.returncode == 1
    assert f"MISSING required node: {victim}" in result.stdout


def test_half_finished_rename_fails_from_both_ends(tmp_path):
    """The failure this ratchet exists for: data moved, manifest not, or vice versa."""
    prefix = tmp_path / "lake"
    build_lake(prefix)
    (prefix / "realm" / "activity").rename(prefix / "realm" / "captures")
    result = run(prefix)
    assert result.returncode == 1
    assert str(prefix / "realm/captures") in result.stdout
    assert str(prefix / "realm/activity") in result.stdout


def test_a_regenerable_tool_cache_is_not_a_node(tmp_path):
    prefix = tmp_path / "lake"
    build_lake(prefix)
    cache = prefix / "realm" / ".pytest_cache"
    cache.mkdir()
    (cache / "CACHEDIR.TAG").write_text("Signature: 8a477f597d28d172789f06886806bc55\n")
    result = run(prefix)
    assert result.returncode == 0, result.stdout

    # Untagged debris under the same name still fails.
    (cache / "CACHEDIR.TAG").unlink()
    assert run(prefix).returncode == 1


def test_absent_roots_are_skipped_not_failed(tmp_path):
    result = run(tmp_path / "nowhere")
    assert result.returncode == 0
    assert result.stderr.count("SKIP") == len(ROOTS)


def test_canonical_node_cannot_be_an_alias(tmp_path):
    prefix = tmp_path / "lake"
    build_lake(prefix)
    node = prefix / "realm" / "journal"
    node.rmdir()
    node.symlink_to(prefix / "realm" / "notes", target_is_directory=True)
    result = run(prefix)
    assert result.returncode == 1
    assert f"SYMLINK at canonical node: {node}" in result.stdout


def test_dangling_unexpected_alias_is_reported(tmp_path):
    prefix = tmp_path / "lake"
    build_lake(prefix)
    node = prefix / "realm" / "obsolete-alias"
    node.symlink_to(prefix / "missing")
    result = run(prefix)
    assert result.returncode == 1
    assert f"UNEXPECTED node: {node}" in result.stdout
