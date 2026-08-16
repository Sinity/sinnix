#!/usr/bin/env python3
"""Positive control for unit_path_audit.py.

Run after any change to the auditor:

    python3 dots/_ai/tools/unit_path_audit_test.py

This exists because a scanner that finds nothing is indistinguishable from a
scanner that cannot see. An earlier version of the auditor was blind to the
exact defect it exists to catch (CMD_RE lacked re.M, so only the first line of
each script was examined) and reported a plausible-looking handful of false
positives with zero real hits -- which read exactly like "the class is clean".

The fixture reproduces the borgbackup-check bug as it actually was: a script
calling jq from inside a function body, with a PATH that has borg but no jq.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location(
    "unit_path_audit", os.path.join(HERE, "unit_path_audit.py")
)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)

FIXTURE = """#!/bin/sh
set -euo pipefail
write_receipt() {
  jq -cn --arg s "$1" '{state:$s}' > /tmp/receipt.json
}
write_receipt running
borg check --repository-only /repo
"""


def main() -> int:
    tmp = tempfile.mkdtemp()
    script = os.path.join(tmp, "unit-script-fixture-start")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(FIXTURE)
    binaries = os.path.join(tmp, "bin")
    os.makedirs(binaries)
    open(os.path.join(binaries, "borg"), "w", encoding="utf-8").close()

    audit.unit_property = lambda unit, prop, user=False: (
        script if prop == "ExecStart" else f"PATH={binaries}"
    )
    hits = audit.scan_unit("fixture.service", False)

    if not any("jq" in hit for hit in hits):
        print(f"FAIL: auditor missed the jq gap. hits={hits}", file=sys.stderr)
        return 1
    if any("borg" in hit for hit in hits):
        print(
            f"FAIL: false positive on a binary that IS present. hits={hits}",
            file=sys.stderr,
        )
        return 1
    print("PASS: catches the real defect, no false positive on a present binary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
