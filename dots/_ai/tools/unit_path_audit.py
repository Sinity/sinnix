#!/usr/bin/env python3
"""Find systemd units whose scripts call binaries absent from their PATH.

The failure this catches is exit 127 at runtime, days or weeks after the
change that introduced it. Two instances on sinnix-prime, both found by
accident and both silent for weeks:

  borgbackup-check     called jq, path had none  -> no integrity receipt
                       written since 2026-08-09; backups reported red.
  lynchpin-materialize called gh, path had none  -> "gh_not_found" for all
                       16 repos, nightly.

Both come from the same shape: a systemd unit built with `script = ''...''`
and a hand-maintained `path = [ ... ]` list that drifts from what the script
actually invokes. `pkgs.writeShellApplication` does not have this failure
mode (runtimeInputs are the path, and shellcheck runs at build time), so the
structural fix is converting such units; this tool exists for the ones that
have not been converted.

Run it against the LIVE host -- it reads systemd's resolved ExecStart and
Environment, so it sees what will actually run, not what the Nix source
suggests:

    python3 dots/_ai/tools/unit_path_audit.py

HEURISTIC, and deliberately noisy rather than silent. Known false-positive
classes, all of which look like a command at the start of a line:
  - `case` labels          -> filtered, but nested/odd spellings can survive
  - container image refs   -> `podman run ghcr.io/...` reports run, ghcr.io
  - words inside strings   -> filtered, but one unbalanced quote earlier in
                              the file desynchronises the pairing for the rest
Verify every hit against the script before believing it. A hit is real when
the word is genuinely executed and genuinely missing from the unit's PATH.

There is a positive control next to this file (unit_path_audit_test.py).
Run it after ANY change here: an earlier version of this scanner was blind
to the very defect it exists to catch -- CMD_RE was missing re.M, so "^"
anchored to the start of the whole script and only the first line was ever
examined. It reported a tidy handful of false positives and zero real ones,
which is indistinguishable from working.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

BUILTINS = set(
    """
: . [ [[ alias bg bind break builtin caller cd command compgen complete
continue declare dirs disown echo enable eval exec exit export false fc fg
getopts hash help history if fi jobs kill let local logout mapfile popd
printf pushd pwd read readarray readonly return set shift shopt source
suspend test then times trap true type typeset ulimit umask unalias unset
until wait while do done case esac for in function select time elif else
coproc
""".split()
)

# Command position: start of line, after a pipe/;/&&/||/(, or after `exec`,
# `then`, `do`, `else`, `!`, `time`, xargs-style wrappers.
# re.M is load-bearing: without it "^" anchors to the start of the whole
# script and the scan sees only the first line plus post-delimiter positions,
# which made an earlier version of this tool silently blind to the very
# defect it exists to catch.
CMD_RE = re.compile(
    r"(?:^|[|;&(]|\b(?:exec|then|do|else|time|xargs|command)\s+)\s*"
    r"([A-Za-z_][A-Za-z0-9_.-]*)\b",
    re.M,
)
FUNC_RE = re.compile(r"^\s*(?:function\s+)?([A-Za-z_][A-Za-z0-9_-]*)\s*\(\)", re.M)
ASSIGN_RE = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*=", re.M)


def unit_property(unit: str, prop: str, user: bool = False) -> str:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd += ["show", unit, "-p", prop, "--value"]
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except Exception:
        return ""


def path_dirs(environment: str) -> list[str]:
    for chunk in environment.split():
        if chunk.startswith("PATH="):
            return chunk[len("PATH=") :].split(":")
    return []


def resolvable(cmd: str, dirs: list[str]) -> bool:
    return any(os.path.exists(os.path.join(d, cmd)) for d in dirs)


def scan_unit(unit: str, user: bool) -> list[str]:
    execs = unit_property(unit, "ExecStart", user)
    # Generated NixOS unit scripts live at /nix/store/...-unit-script-<name>
    scripts = re.findall(r"(/[^ ;\"]*unit-script[^ ;\"]*)", execs)
    scripts += re.findall(r"(/[^ ;\"]*-start\b)", execs)
    scripts = [s for s in dict.fromkeys(scripts) if os.path.isfile(s)]
    if not scripts:
        return []
    dirs = path_dirs(unit_property(unit, "Environment", user))
    if not dirs:
        return []
    missing: list[str] = []
    for script in scripts:
        try:
            raw = open(script, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        defined = set(FUNC_RE.findall(raw))
        # Strip comments and quoted strings first. Without this the scan
        # reports every English word inside an echo or a comment ("skipping",
        # "refusing", "the") as a missing command.
        text = re.sub(r"(?m)(?<!\\)#.*$", " ", raw)
        text = re.sub(r"'[^']*'", " '' ", text)
        text = re.sub(r'"(?:[^"\\]|\\.)*"', ' "" ', text, flags=re.S)
        # Arithmetic expansion is not a command position: the "(" in $(( ))
        # otherwise makes every variable inside it look like a command.
        text = re.sub(r"\$\(\([^)]*\)\)", " 0 ", text)
        # Heredoc bodies are data, not code.
        text = re.sub(
            r"<<-?\s*'?([A-Za-z_][A-Za-z0-9_]*)'?\n.*?\n\1", " ", text, flags=re.S
        )
        # `case` labels look exactly like command positions at start of line.
        text = re.sub(r"(?m)^\s*[A-Za-z_][A-Za-z0-9_.|*?-]*\)\s*$", " ", text)
        # Loop and read variables are names, not commands: `read -r a b c`
        # and `for x in ...` both bind words that never get executed.
        bound = set(re.findall(r"\bread\s+(?:-[A-Za-z]+\s+)*([A-Za-z0-9_ ]+)", text))
        bound_words = {w for chunk in bound for w in chunk.split()}
        bound_words |= set(re.findall(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b", text))
        defined = defined | bound_words
        seen: set[str] = set()
        for m in CMD_RE.finditer(text):
            word = m.group(1)
            if word in seen or word in BUILTINS or word in defined:
                continue
            seen.add(word)
            # A word that only ever appears as VAR=... is an assignment.
            if re.search(rf"^\s*{re.escape(word)}=", text, re.M) and not re.search(
                rf"(?:^|[|;&(]\s*|\bexec\s+){re.escape(word)}\s", text, re.M
            ):
                continue
            if not resolvable(word, dirs):
                missing.append(f"{unit}: {word}  (script={os.path.basename(script)})")
    return missing


def main() -> int:
    out: list[str] = []
    for user in (False, True):
        cmd = (
            ["systemctl"]
            + (["--user"] if user else [])
            + ["list-units", "--type=service", "--all", "--no-legend", "--plain"]
        )
        try:
            listing = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            ).stdout
        except Exception:
            continue
        for line in listing.splitlines():
            unit = line.split()[0] if line.split() else ""
            if not unit.endswith(".service"):
                continue
            out.extend(scan_unit(unit, user))
    for row in sorted(set(out)):
        print(row)
    print(f"\n{len(set(out))} suspect command(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
