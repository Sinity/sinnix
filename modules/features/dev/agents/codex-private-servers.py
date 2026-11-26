"""Drop tool-server tables from Codex's private config that replace a
generated one with a different command.

Codex reads the generated system config and then its private
~/.codex/config.toml, and the private file wins. Codex itself, `codex mcp
add`, and other programs' setup steps write tool servers into the private
file; one named like a registry server and launching something else silently
replaces the declared launcher. Such a table is removed, with its subtables.
A private table that agrees with the generated one, or only adds settings to
it, is left alone, and so is everything else in the file.

The edit is textual so the rest of the file keeps its bytes, and is written
only when the result parses to exactly the old content minus the dropped
tables. Anything unexpected leaves the file untouched and says why.

Usage: codex-private-servers.py PRIVATE_CONFIG GENERATED_CONFIG
"""

import os
import re
import sys

import tomllib

# What decides which program a tool server is.
LAUNCH_KEYS = ("command", "args", "url")


def replaced_servers(private, generated):
    names = []
    for name, declared in generated.get("mcp_servers", {}).items():
        own = private.get("mcp_servers", {}).get(name)
        if isinstance(own, dict) and any(
            key in own and own[key] != declared.get(key) for key in LAUNCH_KEYS
        ):
            names.append(name)
    return names


def without_tables(text, names):
    """The text without the `[mcp_servers.<name>]` tables and their subtables."""
    keys = "|".join(
        f"{re.escape(name)}|\"{re.escape(name)}\"|'{re.escape(name)}'" for name in names
    )
    dropped = re.compile(
        rf"^\s*\[\s*mcp_servers\s*\.\s*(?:{keys})\s*(?:\.[^\]]*)?\]\s*(?:#.*)?$"
    )
    header = re.compile(r"^\s*\[")
    kept = []
    dropping = False
    for line in text.splitlines(keepends=True):
        if header.match(line):
            dropping = bool(dropped.match(line.rstrip("\n")))
        if not dropping:
            kept.append(line)
    return "".join(kept)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    private_path, generated_path = argv[1], argv[2]
    try:
        with open(private_path, encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        return 0
    with open(generated_path, "rb") as handle:
        generated = tomllib.load(handle)
    try:
        private = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        print(
            f"codex: {private_path} is not valid TOML ({error}); left as it is",
            file=sys.stderr,
        )
        return 0
    names = replaced_servers(private, generated)
    if not names:
        return 0
    expected = dict(private)
    expected["mcp_servers"] = {
        name: table
        for name, table in private["mcp_servers"].items()
        if name not in names
    }
    new_text = without_tables(text, names)
    try:
        result = tomllib.loads(new_text)
        result.setdefault("mcp_servers", {})
    except tomllib.TOMLDecodeError:
        result = None
    if result != expected:
        print(
            f"codex: could not remove {', '.join(names)} from {private_path} cleanly; left as it is",
            file=sys.stderr,
        )
        return 0
    temp = f"{private_path}.sinnix-new"
    mode = os.stat(private_path).st_mode & 0o777
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(new_text)
    os.chmod(temp, mode)
    os.replace(temp, private_path)
    for name in names:
        print(
            f"codex: removed the private {name} tool server, which replaced the generated one",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
