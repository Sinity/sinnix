#!/usr/bin/env python3
# @sinnix-package: skip
"""Exercise the Python validator embedded in the generated startup condition."""

import copy
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

MODULE = Path(
    os.environ.get(
        "SINNIX_CLODEX_MODULE",
        Path(__file__).resolve().parents[2] / "modules/services/clodex.nix",
    )
)
SOURCE = MODULE.read_text()
VALIDATOR = textwrap.dedent(
    SOURCE.split("python3 -c '\n", 1)[1].split("\n              '", 1)[0]
)
# Produced by Clodex 2.18.10 computePatchConfigHash, transform version 15.
NATIVE_HASH = "c6ab7483c28d0103f58540699a756233f821ca79cae2a04afca1d0894d108f09"
MODEL = {
    "id": "clodex:test:sample",
    "aliases": ["alpha", "beta"],
    "displayName": "Sample (Test)",
    "context": {"effective": 872000},
    "effort": {"levels": ["low", "medium", "high", "max"], "default": "medium"},
}


class PatchCheckTest(unittest.TestCase):
    def check_rows(self, rows, preferences=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps({"configHash": NATIVE_HASH}))
            (root / "config.json").write_text(json.dumps(preferences or {}))
            return subprocess.run(
                [
                    sys.executable,
                    "-c",
                    VALIDATOR,
                    str(root / "manifest.json"),
                    str(root / "config.json"),
                ],
                input=json.dumps(rows),
                text=True,
                capture_output=True,
                check=False,
            )

    def test_matches_native_hash_with_projected_effort(self):
        result = self.check_rows([MODEL])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_changes_require_repatch(self):
        variants = []
        for change in ("secondary_alias", "context", "label", "effort"):
            row = copy.deepcopy(MODEL)
            if change == "secondary_alias":
                row["aliases"][1] = "gamma"
            elif change == "context":
                row["context"]["effective"] = 272000
            elif change == "label":
                row["displayName"] = "Renamed (Test)"
            else:
                row["effort"]["levels"].remove("max")
            variants.append((change, [row]))
        variants.append(("favorite_removed", []))
        for change, rows in variants:
            with self.subTest(change=change):
                result = self.check_rows(rows)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("patch is stale", result.stderr)

    def test_new_local_patch_configuration_is_stale(self):
        result = self.check_rows([MODEL], {"localPatchesEnabled": True})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("patch is stale", result.stderr)

    def test_malformed_models_fail_closed(self):
        result = self.check_rows([{"id": "clodex:test:sample"}])
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
