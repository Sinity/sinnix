"""Integration tests for sinnix-census's transitive @-edge reachability.

A script inherits "usedness" from a directly-used script's own
`# runtimeInputs: @name` edges (a wrapper's helper scripts should not read as
dead just because nobody types the helper's name at a shell). This exercises
the real script end-to-end via subprocess against a throwaway fixture repo,
because the propagation loop lives inline in main() rather than in a
separately callable function.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "sinnix-census"


def _write_script(scripts_dir: Path, name: str, runtime_inputs_edges: str = "") -> None:
    edges = f" {runtime_inputs_edges}" if runtime_inputs_edges else ""
    (scripts_dir / name).write_text(
        "#!/usr/bin/env bash\n"
        "# @sinnix-package\n"
        f"# description: fixture script {name}\n"
        f"# runtimeInputs: coreutils{edges}\n"
    )


def _make_atuin_db(path: Path, commands: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE history (command TEXT, timestamp INTEGER)")
    now_ns = int(time.time() * 1_000_000_000)
    conn.executemany(
        "INSERT INTO history (command, timestamp) VALUES (?, ?)",
        [(c, now_ns) for c in commands],
    )
    conn.commit()
    conn.close()


def _polylogue_free_path() -> str:
    # Keep the census run hermetic against whatever real polylogue archive
    # this host happens to have: strip any PATH entry that resolves
    # `polylogue`, so the script sees it as genuinely unavailable (the
    # documented "evidence source missing -> degrade honestly" path) rather
    # than depending on live chat-log content for synthetic fixture names.
    return os.pathsep.join(
        p
        for p in os.environ.get("PATH", "").split(os.pathsep)
        if not (Path(p) / "polylogue").exists()
    )


def run_census(repo: Path, home: Path, jsonl_out: Path) -> list[dict]:
    env = {
        **os.environ,
        "SINNIX_REPO": str(repo),
        "HOME": str(home),
        "PATH": _polylogue_free_path(),
    }
    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--classes",
            "scripts",
            "--jsonl-out",
            str(jsonl_out),
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        cwd=str(repo),
    )
    return [json.loads(line) for line in jsonl_out.read_text().splitlines()]


def _by_name(rows: list[dict]) -> dict[str, dict]:
    return {row["name"]: row for row in rows if row["class"] == "scripts"}


def test_transitive_edges_reach_two_hops_and_orphan_stays_unused(tmp_path):
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)
    (repo / "modules").mkdir()  # empty: no static_refs noise
    (repo / "flake").mkdir()

    # sinnix-root --@mid--> sinnix-mid --@leaf--> sinnix-leaf
    # Edge tokens are declared WITHOUT the "sinnix-" prefix, exercising the
    # `target = edge if edge in scripts else f"sinnix-{edge}"` fallback that
    # resolves the real repo naming convention.
    _write_script(scripts_dir, "sinnix-root", "@mid")
    _write_script(scripts_dir, "sinnix-mid", "@leaf")
    _write_script(scripts_dir, "sinnix-leaf")
    _write_script(scripts_dir, "sinnix-orphan")

    home = tmp_path / "home"
    _make_atuin_db(home / ".local/share/atuin/history.db", ["sinnix-root"])

    rows = _by_name(run_census(repo, home, tmp_path / "out.jsonl"))

    assert rows["sinnix-root"]["verdict"] == "active"

    # One-hop propagation.
    assert rows["sinnix-mid"]["used_via_edges"] is True
    assert rows["sinnix-mid"]["verdict"] == "referenced-only"

    # Two-hop propagation: leaf is only reachable via mid, which is itself
    # only reachable via root. Anti-vacuity: replacing the fixed-point
    # `while changed:` loop with a single non-repeating pass over `pending`
    # would leave used_roots = {root, mid} after one pass and never add
    # leaf, so this assertion is exactly what would catch that regression
    # while test_transitive_edges above (one hop) still passed.
    assert rows["sinnix-leaf"]["used_via_edges"] is True
    assert rows["sinnix-leaf"]["verdict"] == "referenced-only"

    # Not referenced by any edge and never run: must not inherit usedness.
    assert rows["sinnix-orphan"]["used_via_edges"] is False
    assert rows["sinnix-orphan"]["verdict"] == "unused-in-window"


def test_edge_to_nonexistent_target_does_not_crash_or_falsely_propagate(tmp_path):
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)
    (repo / "modules").mkdir()
    (repo / "flake").mkdir()

    # A near-miss for the prefix fallback: the edge token itself, and its
    # "sinnix-"-prefixed form, both fail to name any real script. This must
    # not raise (KeyError/lookup crash) and must not cause the used root to
    # be misclassified.
    _write_script(scripts_dir, "sinnix-root", "@does-not-exist")

    home = tmp_path / "home"
    _make_atuin_db(home / ".local/share/atuin/history.db", ["sinnix-root"])

    rows = _by_name(run_census(repo, home, tmp_path / "out.jsonl"))

    assert rows["sinnix-root"]["verdict"] == "active"
    assert set(rows) == {"sinnix-root"}
