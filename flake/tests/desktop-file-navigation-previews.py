#!/usr/bin/env python3
"""Run the declared preview helpers against real files of the types they claim.

argv: <thumbnailers-dir> <fixtures-dir> <json list of {mime, fixture}>

A helper is only useful if some `.thumbnailer` entry claims the type *and* its
registered command produces a PNG for a real file, so both are checked here.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

thumbnailer_dir, fixture_dir, cases_json = sys.argv[1:4]
cases = json.loads(cases_json)

entries = []
for path in sorted(pathlib.Path(thumbnailer_dir).glob("*.thumbnailer")):
    fields = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep:
            fields[key.strip()] = value.strip()
    entries.append((path, fields))

if not entries:
    sys.exit(f"no .thumbnailer entries under {thumbnailer_dir}")

failures = []
for case in cases:
    mime, fixture = case["mime"], case["fixture"]
    claiming = [
        (path, fields)
        for path, fields in entries
        if mime in fields.get("MimeType", "").split(";")
    ]
    if not claiming:
        failures.append(f"{mime}: no declared preview helper claims this type")
        continue

    source = pathlib.Path(fixture_dir, fixture)
    with tempfile.TemporaryDirectory() as tmp:
        output = pathlib.Path(tmp, "thumb.png")
        path, fields = claiming[0]
        argv = [
            token.replace("%i", str(source))
            .replace("%u", source.as_uri())
            .replace("%o", str(output))
            .replace("%s", "256")
            for token in fields["Exec"].split()
        ]
        env = dict(os.environ, HOME=tmp, XDG_CACHE_HOME=tmp)
        run = subprocess.run(argv, capture_output=True, text=True, env=env)
        if run.returncode != 0:
            failures.append(f"{mime}: {path.name} exited {run.returncode}: {run.stderr.strip()}")
        elif not output.exists() or output.stat().st_size == 0:
            failures.append(f"{mime}: {path.name} produced no thumbnail")
        elif output.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            failures.append(f"{mime}: {path.name} produced a non-PNG thumbnail")
        else:
            print(f"ok {mime} -> {path.name} ({output.stat().st_size} bytes)")

if failures:
    sys.exit("\n".join(failures))
