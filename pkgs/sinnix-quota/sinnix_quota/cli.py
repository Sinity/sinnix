from __future__ import annotations

import argparse
import json
from pathlib import Path

from .normalize import normalize_cost, normalize_usage, redact_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["normalize"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--source", choices=["codexbar", "caut"], required=True)
    parser.add_argument("--kind", choices=["usage", "cost"], default="usage")
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(raw, (dict, list)):
        raise SystemExit("quota input must be a JSON object or array")
    rows = (
        normalize_usage(raw, args.source)
        if args.kind == "usage"
        else normalize_cost(raw, args.source)
    )
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.raw_output.open("a", encoding="utf-8") as handle:
        json.dump(redact_json(raw), handle, sort_keys=True)
        handle.write("\n")
    args.output.write_text(
        json.dumps({"schema": "sinnix-quota-v1", "rows": rows}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
