#!/usr/bin/env python3
"""Resolve every declared frequent location from a clean profile.

argv: <bookmarks-file> <sandbox-root> <json list of declared paths>

The check runs in an empty $HOME, so the bookmarks file under test is the one
Home Manager renders and nothing else. Each entry is parsed as a URI, mirrored
under the sandbox root, and resolved through GIO -- the same layer the file
manager sidebar and the portal file chooser use.
"""

import json
import os
import pathlib
import subprocess
import sys
import urllib.parse

bookmarks_file, sandbox_root, declared_json = sys.argv[1:4]
declared = json.loads(declared_json)

lines = [
    line
    for line in pathlib.Path(bookmarks_file).read_text().splitlines()
    if line.strip()
]
if len(lines) != len(declared):
    sys.exit(
        f"bookmarks file has {len(lines)} entries, {len(declared)} places are declared: {lines}"
    )

failures = []
for line, declared_path in zip(lines, declared, strict=True):
    uri, _, label = line.partition(" ")
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "file" or parsed.netloc:
        failures.append(f"{uri}: not a local file:// URI")
        continue
    path = urllib.parse.unquote(parsed.path)
    if path != declared_path:
        failures.append(f"{uri}: resolves to {path}, declared {declared_path}")
        continue
    if not label.strip():
        failures.append(f"{uri}: no sidebar label")
        continue

    mirrored = pathlib.Path(sandbox_root + path)
    mirrored.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(
        ["gio", "info", "-a", "standard::type", mirrored.as_uri()],
        capture_output=True,
        text=True,
        env=dict(os.environ, GIO_USE_VFS="local"),
    )
    if run.returncode != 0 or "standard::type: 2" not in run.stdout:
        failures.append(
            f"{uri}: GIO did not resolve it to a directory: {run.stderr.strip()}"
        )
    else:
        print(f"ok {label.strip()} -> {path}")

if failures:
    sys.exit("\n".join(failures))
