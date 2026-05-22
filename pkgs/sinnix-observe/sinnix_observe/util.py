"""Generic helpers shared across collectors."""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def run_cmd(
    args: list[str], timeout: float = 5.0
) -> subprocess.CompletedProcess[str] | None:
    if shutil.which(args[0]) is None:
        return None
    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def split_props(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key] = value
    return props


def read_text(path: str | Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_proc_cmdline(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def float_or_zero(value: Any) -> float:
    parsed = float_or_none(value)
    return 0.0 if parsed is None else parsed


def parse_counts(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def normalize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if re.fullmatch(r"\d+(\.\d+)?", text):
        try:
            return (
                dt.datetime.fromtimestamp(float(text), dt.UTC)
                .replace(microsecond=0)
                .isoformat()
            )
        except (OSError, ValueError):
            return text
    return text


def words(value: str | None) -> list[str]:
    if not value:
        return []
    return [part for part in value.split() if part]
