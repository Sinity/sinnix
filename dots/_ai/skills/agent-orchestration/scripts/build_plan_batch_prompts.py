#!/usr/bin/env python3
"""Generate prompt files from a generic batch plan JSON."""

import argparse
import json
from pathlib import Path


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _slug(value):
    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "batch"


def _render_default_prompt(batch_id, items, project_root, protocol_path, item_label):
    item_lines = "\n".join(f"- {x}" for x in items) if items else "- (none)"
    project_block = f"- {project_root}\n" if project_root else "- (set by caller)\n"
    protocol_line = f"- Follow protocol: {protocol_path}\n" if protocol_path else ""

    return f"""You are executing a batch coordination run.

Project root:
{project_block}{protocol_line}Batch id:
- {batch_id}

Batch {item_label}:
{item_lines}

Requirements:
1. Decompose work into independent worker tasks where possible.
2. Keep outputs deterministic and machine-ingestable.
3. Keep uncertainty explicit; do not force weak conclusions.
4. Report:
   - completed items
   - failed items
   - unresolved/ambiguous items
   - commands run and key outputs
"""


def main():
    parser = argparse.ArgumentParser(
        description="Generate prompt files from generic plan batches."
    )
    parser.add_argument(
        "--plan-json",
        required=True,
        help="Path to plan JSON containing a batches array",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory where *.prompt files will be written",
    )
    parser.add_argument(
        "--batch-key",
        default="batches",
        help="Key containing batch array (default: batches)",
    )
    parser.add_argument(
        "--id-key", default="batch_id", help="Batch id key (default: batch_id)"
    )
    parser.add_argument(
        "--items-key", default="shard_ids", help="Batch items key (default: shard_ids)"
    )
    parser.add_argument(
        "--item-label", default="items", help="Label shown in generated prompts"
    )
    parser.add_argument(
        "--name-prefix", default="batch", help="Prefix for prompt filenames"
    )
    parser.add_argument(
        "--project-root",
        default="",
        help="Optional project root path to embed in prompt",
    )
    parser.add_argument(
        "--protocol-path",
        default="",
        help="Optional protocol/runbook path to embed in prompt",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    plan = _load(args.plan_json)
    batches = plan.get(args.batch_key, [])
    if not isinstance(batches, list):
        raise SystemExit(f"{args.batch_key!r} is not a list in {args.plan_json}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for idx, batch in enumerate(batches, start=1):
        if not isinstance(batch, dict):
            continue
        batch_id = str(batch.get(args.id_key) or f"batch-{idx:02d}")
        items = batch.get(args.items_key) or []
        if not isinstance(items, list):
            items = [str(items)]

        filename = f"{args.name_prefix}-{idx:02d}-{_slug(batch_id)}.prompt"
        path = out_dir / filename
        if path.exists() and not args.overwrite:
            continue
        prompt = _render_default_prompt(
            batch_id=batch_id,
            items=[str(x) for x in items],
            project_root=args.project_root,
            protocol_path=args.protocol_path,
            item_label=args.item_label,
        )
        path.write_text(prompt, encoding="utf-8")
        generated.append(str(path))

    manifest = {
        "plan_json": str(Path(args.plan_json).resolve()),
        "out_dir": str(out_dir.resolve()),
        "generated_count": len(generated),
        "generated": generated,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
