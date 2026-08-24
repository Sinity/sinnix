#!/usr/bin/env python3
"""Validate skill package structure without judging natural-language style."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
DESCRIPTION_WORD_LIMIT = 35


def frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}, ["missing opening frontmatter delimiter"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, ["missing closing frontmatter delimiter"]
    values: dict[str, str] = {}
    current_key: str | None = None
    for line in lines[1:end]:
        if not line.strip() or line[0].isspace():
            if current_key and line.strip():
                values[current_key] = f"{values[current_key]} {line.strip()}".strip()
            continue
        if ":" not in line:
            errors.append("malformed frontmatter line")
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        parsed = value.strip().strip('"')
        values[current_key] = "" if parsed in {">", "|"} else parsed
    for key in ("name", "description"):
        if not values.get(key):
            errors.append(f"missing frontmatter field: {key}")
    return values, errors


def validate(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    names: dict[str, Path] = {}
    for directory in sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ):
        skill_file = directory / "SKILL.md"
        if not skill_file.exists():
            continue
        values, errors = frontmatter(skill_file)
        for error in errors:
            findings.append({"path": str(skill_file), "error": error})
        name = values.get("name", "")
        description_words = len(values.get("description", "").split())
        if description_words > DESCRIPTION_WORD_LIMIT:
            findings.append(
                {
                    "path": str(skill_file),
                    "error": (
                        f"description has {description_words} words; "
                        f"limit is {DESCRIPTION_WORD_LIMIT}"
                    ),
                }
            )
        if name in names and name:
            findings.append(
                {
                    "path": str(skill_file),
                    "error": f"duplicate skill name; first at {names[name]}",
                }
            )
        elif name:
            names[name] = skill_file
        if len(skill_file.read_text(encoding="utf-8").splitlines()) > 500:
            findings.append(
                {"path": str(skill_file), "error": "SKILL.md exceeds 500 lines"}
            )
        for target in LINK_RE.findall(skill_file.read_text(encoding="utf-8")):
            if "://" not in target and not (skill_file.parent / target).exists():
                findings.append(
                    {"path": str(skill_file), "error": f"broken reference: {target}"}
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skills_root", type=Path)
    args = parser.parse_args()
    findings = validate(args.skills_root)
    print(
        json.dumps(
            {"skills_root": str(args.skills_root), "findings": findings},
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
