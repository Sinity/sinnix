"""Fixture inventories in the shape Home Manager renders, plus the two
scripts under test resolved the way the packaged suite lays them out."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
KEYBINDS = ROOT / "scripts" / "sinnix-rank-keybinds"
FORGE = ROOT / "scripts" / "sinnix-deck-forge"
RANK = ROOT / "scripts" / "sinnix-rank"
BINDINGS_NIX = ROOT / "modules" / "features" / "desktop" / "hyprland" / "bindings.nix"

# (chord, intent, action). The actions carry a /nix/store path on purpose:
# identity must survive a rebuild that only moves the store hash.
FIXTURE_BINDINGS = [
    (
        "SUPER + O",
        "Open the unified reading picker",
        'hl.dsp.exec_cmd("uwsm app -- /nix/store/'
        + "0" * 32
        + '-sinnix-picker/bin/sinnix-picker")',
    ),
    ("SUPER + Q", "Close the focused window", "hl.dsp.window.close()"),
    (
        "F7",
        "Switch to or leave the agent browser workspace",
        'hl.dsp.exec_cmd("sinnix-chrome-control toggle-agent-workspace")',
    ),
    ("SUPER + G", "Group or ungroup the window", "hl.dsp.group.toggle()"),
    (
        "SUPER + V",
        "Browse clipboard history",
        'hl.dsp.exec_cmd("uwsm app -- kitty --class clipse -e clipse")',
    ),
]


def render_lua(bindings, *, extra_flags: dict | None = None) -> str:
    """The subset of the rendered config the adapter reads."""
    lines = ["-- settings.bind"]
    for chord, intent, action in bindings:
        lines.append(f'hl.bind("{chord}", ({action}), {{')
        flag_lines = [f'  ["description"] = "{intent}"']
        for key, value in (extra_flags or {}).items():
            flag_lines.append(f'  ["{key}"] = {value}')
        lines.append(",\n".join(flag_lines))
        lines.append("})")
    return "\n".join(lines) + "\n"


class Adapter:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.rank_root = tmp_path / "ranking"
        self.env = dict(os.environ)
        self.env["PYTHONPATH"] = str(ROOT / "pkgs" / "sinnix-rank-core")
        self.env["SINNIX_RANK_ROOT"] = str(self.rank_root)
        self.env["SINNIX_DERIVED_ROOT"] = str(tmp_path / "derived")
        self.env["SINNIX_PHONE_STATE_DIR"] = str(tmp_path / "phone")
        self.env["HOME"] = str(tmp_path / "home")
        (tmp_path / "home").mkdir(parents=True, exist_ok=True)
        self.inventory = tmp_path / "hyprland.lua"
        self.write_inventory(FIXTURE_BINDINGS)

    def write_inventory(self, bindings, **kwargs) -> None:
        self.inventory.write_text(render_lua(bindings, **kwargs))

    def run(
        self, *argv: str, script: Path | None = None
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script or KEYBINDS), *argv],
            capture_output=True,
            text=True,
            env=self.env,
            timeout=120,
        )

    def ok(self, *argv: str, script: Path | None = None) -> subprocess.CompletedProcess:
        result = self.run(*argv, script=script)
        assert result.returncode == 0, f"{argv} failed: {result.stderr}"
        return result

    def adapter(self, *argv: str) -> subprocess.CompletedProcess:
        return self.ok("--inventory", str(self.inventory), *argv)

    def inventory_records(self) -> list[dict]:
        return json.loads(self.adapter("inventory", "--json").stdout)

    def manifest(self, *argv: str) -> dict:
        return json.loads(self.adapter("manifest", "--json", *argv).stdout)

    def record(self, domain: str, winner: str, loser: str, times: int = 1) -> None:
        for _ in range(times):
            result = subprocess.run(
                [
                    sys.executable,
                    str(RANK),
                    "record",
                    domain,
                    "--set",
                    f"{winner},{loser}",
                    "--winner",
                    winner,
                ],
                capture_output=True,
                text=True,
                env=self.env,
                timeout=120,
            )
            assert result.returncode == 0, result.stderr

    def write_usage(self, counts: dict) -> None:
        path = self.tmp / "usage.json"
        path.write_text(json.dumps({"counts": counts}))
        self.adapter("usage", "--source", "file", "--usage-file", str(path))


@pytest.fixture
def adapter(tmp_path: Path) -> Adapter:
    return Adapter(tmp_path)
