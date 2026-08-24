from __future__ import annotations

import argparse
from pathlib import Path

from sinnix_agent_gateway.gateway_codegen import check_artifacts, write_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate gateway V2 docs, skill, and fixtures")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.write:
        write_artifacts(root)
        return 0
    mismatches = check_artifacts(root)
    if mismatches:
        for mismatch in mismatches:
            print(mismatch)
        return 1
    print("gateway artifacts are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
