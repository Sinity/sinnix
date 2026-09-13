"""Pure parsers for Linux ``/proc`` and pressure-control text files.

The functions in this module deliberately accept text rather than paths.  They
do not read the filesystem and they do not attach policy to a parsed value;
callers decide whether an absent or malformed observation is actionable.

Malformed records are ignored and never raise.  This is useful for procfs,
where a process can disappear between the directory walk and a file read, and
where kernel versions may add fields.  The individual functions document the
slightly stricter rules for formats whose identity matters.
"""

from __future__ import annotations

from typing import TypeAlias

PSIValue: TypeAlias = float | int
PSIRecord: TypeAlias = dict[str, PSIValue]


def parse_psi(text: str | None) -> dict[str, PSIRecord]:
    """Parse Linux PSI text into ``{record: {field: value}}``.

    ``some`` and ``full`` records are returned with their ``avg10``, ``avg60``,
    ``avg300`` and ``total`` fields when those fields contain valid numbers.
    Average values are ``float`` seconds-per-second; ``total`` is an ``int``
    microsecond counter.  Unknown record or field names are retained, which
    lets newer kernels pass through without a library change.  Blank lines,
    fields without ``=``, and fields with invalid numbers are ignored.  A
    missing input or a text containing no valid fields returns ``{}``.
    Duplicate fields use the last valid value.  A field named ``total`` must
    be an integer; other fields use a float.
    """

    records: dict[str, PSIRecord] = {}
    if not text:
        return records
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[0]:
            continue
        record = records.setdefault(parts[0], {})
        for field in parts[1:]:
            key, separator, raw_value = field.partition("=")
            if not separator or not key or not raw_value:
                continue
            try:
                value: PSIValue
                if key == "total":
                    value = int(raw_value, 10)
                else:
                    value = float(raw_value)
            except ValueError:
                continue
            record[key] = value
        if not record:
            records.pop(parts[0], None)
    return records


def parse_colon_numeric(text: str | None) -> dict[str, int]:
    """Parse ``key: integer [unit]`` records such as ``/proc/meminfo``.

    The first whitespace-delimited value after the colon must be a signed
    base-10 integer; an optional trailing unit (for example ``kB``) is ignored
    and is not converted.  Keys and values are stripped.  Blank lines, lines
    without a colon, empty keys, and non-integer values are ignored.  Duplicate
    valid keys use the last value.  Missing input returns ``{}``.
    """

    values: dict[str, int] = {}
    if not text:
        return values
    for line in text.splitlines():
        key, separator, raw_value = line.partition(":")
        key = key.strip()
        if not separator or not key:
            continue
        token = raw_value.strip().split(maxsplit=1)
        if not token:
            continue
        try:
            values[key] = int(token[0], 10)
        except ValueError:
            continue
    return values


def parse_cgroup_v2(text: str | None) -> str | None:
    """Return a sole cgroup-v2 path from ``/proc/<pid>/cgroup`` text.

    The accepted record is exactly one nonblank line of the form
    ``0::<absolute-path>``.  Empty input, malformed records, multiple v2
    records, and mixed v1/v2 membership all return ``None``.  In particular,
    a v1 line alongside a valid v2 line is not silently collapsed to v2: the
    caller must decide how to handle a mixed hierarchy.  A root membership
    (``0::/``) is valid.
    """

    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    parts = lines[0].split(":", 2)
    if len(parts) != 3 or parts[0] != "0" or parts[1] != "":
        return None
    path = parts[2]
    if not path.startswith("/") or "\x00" in path:
        return None
    return path


def parse_stat_start_time(text: str | None) -> int | None:
    """Parse field 22 (start time in clock ticks) from ``/proc/<pid>/stat``.

    The process ``comm`` field is enclosed in parentheses and may itself
    contain spaces or parentheses.  The final ``)`` is therefore used as the
    delimiter, after requiring an opening ``(``; the twentieth token after it
    is field 22.  Missing, malformed, or too-short input returns ``None``.
    """

    if not text:
        return None
    opening = text.find("(")
    closing = text.rfind(")")
    if opening < 0 or closing <= opening:
        return None
    fields = text[closing + 1 :].split()
    if len(fields) <= 19:
        return None
    try:
        return int(fields[19], 10)
    except ValueError:
        return None


__all__ = [
    "PSIRecord",
    "PSIValue",
    "parse_cgroup_v2",
    "parse_colon_numeric",
    "parse_psi",
    "parse_stat_start_time",
]
