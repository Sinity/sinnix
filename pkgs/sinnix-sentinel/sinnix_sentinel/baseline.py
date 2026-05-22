"""Baseline state file: load/save the rolling samples JSON.

Wire-format contract (bash sentinel ``read_baselines`` / ``write_baselines``,
script lines 186-233):

* On-disk path: ``$SINNIX_BASELINE_FILE`` or ``/var/lib/sinnix-sentinel/baselines.json``.
* Shape: ``{<key>: [<sample_str>, ...]}`` — every sample is stored as a
  string, because the bash version uses ``jq --arg v "samples" '.[$k] = ($v | split(" "))'``
  which produces JSON strings. We preserve that.
* Trim policy: keep the last ``max_samples`` values (default 144 = 24h at 10min).
* Atomic write: write to ``<path>.tmp`` then ``rename`` (mv).
* Trailing newline after the JSON body (matches ``printf '%s\\n'``).
* Empty / unreadable / corrupt file => represented as ``{}``.

The Python representation mirrors the JSON shape: ``dict[str, list[str]]``.
Callers that need numeric stats use :mod:`statistics_compat`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_BASELINE_PATH = "/var/lib/sinnix-sentinel/baselines.json"
DEFAULT_MAX_SAMPLES = 144


def baseline_path() -> Path:
    return Path(os.environ.get("SINNIX_BASELINE_FILE", DEFAULT_BASELINE_PATH))


def read_baselines(path: Optional[Path] = None) -> Dict[str, List[str]]:
    """Load the baselines JSON. Returns ``{}`` on any error (bash parity)."""

    p = path if path is not None else baseline_path()
    try:
        if not p.is_file():
            return {}
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    # Normalize: ensure every value is a list[str]; drop malformed keys silently
    # (matches bash behaviour where jq would coerce or skip).
    out: Dict[str, List[str]] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, list):
            continue
        out[key] = [str(v) for v in value]
    return out


def write_baselines(
    baselines: Dict[str, List[str]],
    path: Optional[Path] = None,
) -> None:
    """Persist baselines atomically (``.tmp`` -> ``rename``). Silent on error."""

    p = path if path is not None else baseline_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # mirrors bash `can_write_parent` -> best-effort
        return
    tmp = p.with_suffix(p.suffix + ".tmp")
    payload = json.dumps(baselines, separators=(",", ":")) + "\n"
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return


def baseline_append(
    key: str,
    value: float | int | str,
    max_samples: int = DEFAULT_MAX_SAMPLES,
    path: Optional[Path] = None,
) -> Dict[str, List[str]]:
    """Append ``value`` to the rolling series ``key`` and persist.

    Values are stored as strings (bash sentinel uses awk/jq string handling
    throughout). Returns the updated baselines dict.
    """

    baselines = read_baselines(path)
    series = list(baselines.get(key, []))
    series.append(str(value))
    if len(series) > max_samples:
        series = series[-max_samples:]
    baselines[key] = series
    write_baselines(baselines, path)
    return baselines
