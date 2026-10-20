"""One command surface over the distinct filesystem data owners."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="sinnix fs", description=__doc__)
    parser.add_argument("command", choices=("scan", "refresh", "status", "query", "classify", "catalog", "links", "layout", "maintain"))
    if not argv or argv[0] in ("-h", "--help"):
        parser.print_help()
        return 0 if argv else 2
    command = parser.parse_args(argv[:1]).command
    if command == "maintain":
        from .maintenance import main as run
        return run(argv[1:])
    if command == "catalog":
        from .catalog import main as run
        return run(argv[1:])
    if command == "layout":
        from .layout import main as run
        return run(argv[1:])
    if command == "links":
        if argv[1:2] == ["notes"]:
            from .inventory import main as run
            return run(["notes", *argv[2:]])
        from .catalog import main as run
        return run(["links", *argv[1:]])
    from .inventory import main as run
    return run(argv)
