from __future__ import annotations

import os
from collections.abc import Iterable, Mapping

DEFAULT_PATH = "/run/current-system/sw/bin"


def build_environment(
    *,
    inherit: Iterable[str] = (),
    unset: Iterable[str] = (),
    values: Mapping[str, str] | None = None,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an env -i environment without conflating missing and empty values."""

    inherited = os.environ if source is None else source
    removed = set(unset)
    environment = {
        key: inherited[key]
        for key in inherit
        if key in inherited and key not in removed
    }
    if "PATH" not in removed and "PATH" not in environment:
        environment["PATH"] = inherited["PATH"] if "PATH" in inherited else DEFAULT_PATH
    for key, value in (values or {}).items():
        if key not in removed:
            environment[key] = value
    return environment
