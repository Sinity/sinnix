"""ActivityWatch bucket-event rollup (sinnix-9pd Phase 3a, 3.6).

ActivityWatch (aw-server-rust, wired in modules/features/desktop/
activitywatch.nix) keeps its own SQLite database under
~/.local/share/activitywatch -- a persisted home directory, NOT the
captures lake. The `activitywatch` runtime surface declared in that
module's captures list has always pointed at
`${capturesRoot}/activitywatch` with a 1h staleness budget, but nothing
ever wrote there: the surface was silently, permanently stale. This
script is the missing rollup -- a periodic, incremental pull of new
bucket events over AW's own REST API (127.0.0.1:5600, aw-server-rust's
default bind), written into that lane as sinnix-capture-v1 envelopes via
the shared `sinnix-capture` CLI (same shell-out pattern as
pkgs/capture-mpris/monitor.py -- no Python dependency beyond stdlib).

Incrementality: per-bucket last-synced-through timestamps live in a small
JSON state file outside the capture lane itself (mirroring url-ledger's
separate state/derived split). Each run only fetches events with
timestamp + duration <= now - GRACE_SECONDS: AW's watchers keep mutating
the *current* (still-open) event's duration in place as time passes, so
without the grace window a rollup could capture a not-yet-final version
of the latest event and never see its true end state. Leaving that one
event for the following run is deliberate, not a bug.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRACE_SECONDS = 30.0


def log(msg: str) -> None:
    print(f"capture-aw-rollup: {msg}", file=sys.stderr, flush=True)


def api_get(api_base: str, path: str, timeout: float) -> object:
    with urllib.request.urlopen(f"{api_base}{path}", timeout=timeout) as resp:
        return json.load(resp)


def load_state(state_file: Path) -> dict:
    try:
        return json.loads(state_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(state_file)


def parse_iso(ts: str) -> float:
    # AW timestamps are RFC3339 with a trailing "Z"; Python's fromisoformat
    # only accepts "+00:00" before 3.11 stdlib support for "Z" landed.
    from datetime import datetime

    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def to_iso(ts: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def write_envelope(sinnix_capture_bin: str, capture_root: str, lane: str, payload: dict) -> bool:
    try:
        proc = subprocess.run(
            [
                sinnix_capture_bin,
                "write",
                "--capture-root",
                capture_root,
                "--lane",
                lane,
                "--payload",
                json.dumps(payload),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log(f"sinnix-capture write failed to launch: {exc}")
        return False
    if proc.returncode != 0:
        log(f"sinnix-capture write failed (rc={proc.returncode}): {proc.stderr.strip()}")
        return False
    return True


def rollup_bucket(
    api_base: str,
    bucket_id: str,
    bucket_meta: dict,
    since: float,
    until: float,
    timeout: float,
) -> tuple[list[dict], float]:
    # No `limit` param: the aw-server-rust endpoint takes it as an
    # Option<u64> and returns every matching event when it's absent --
    # a bare -1 (aw-client's Python convention for "unlimited") isn't a
    # valid u64 and would either fail to parse or get misread as a cap.
    events = api_get(
        api_base,
        f"/api/0/buckets/{urllib.parse.quote(bucket_id, safe='')}/events"
        f"?start={urllib.parse.quote(to_iso(since))}&end={urllib.parse.quote(to_iso(until))}",
        timeout,
    )
    if not isinstance(events, list) or not events:
        return [], since

    kept = [e for e in events if parse_iso(e["timestamp"]) + float(e.get("duration") or 0.0) <= until]
    if not kept:
        return [], since

    new_watermark = max(parse_iso(e["timestamp"]) + float(e.get("duration") or 0.0) for e in kept)
    return kept, new_watermark


def run(args: argparse.Namespace) -> int:
    now = time.time()
    until = now - GRACE_SECONDS
    if until <= 0:
        log("clock looks wrong (now <= GRACE_SECONDS); skipping run")
        return 1

    try:
        buckets = api_get(args.api_base, "/api/0/buckets", args.timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log(f"cannot reach AW server at {args.api_base}: {exc}")
        return 1

    if not isinstance(buckets, dict):
        log(f"unexpected /api/0/buckets response shape: {type(buckets)!r}")
        return 1

    state = load_state(args.state_file)
    wrote = 0
    for bucket_id, meta in buckets.items():
        default_since = parse_iso(meta["created"]) if isinstance(meta.get("created"), str) else 0.0
        since = float(state.get(bucket_id, default_since))
        if since >= until:
            continue

        try:
            events, watermark = rollup_bucket(args.api_base, bucket_id, meta, since, until, args.timeout)
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as exc:
            log(f"bucket {bucket_id}: fetch failed: {exc}")
            continue

        if not events:
            continue

        payload = {
            "bucket_id": bucket_id,
            "bucket_type": meta.get("type"),
            "client": meta.get("client"),
            "hostname": meta.get("hostname"),
            "event_count": len(events),
            "range_start": to_iso(since),
            "range_end": to_iso(watermark),
            "events": events,
        }
        if write_envelope(args.sinnix_capture_bin, str(args.capture_root), args.lane, payload):
            state[bucket_id] = watermark
            wrote += 1

    save_state(args.state_file, state)
    log(f"synced {wrote}/{len(buckets)} bucket(s) with new events")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capture-aw-rollup", description=__doc__)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--lane", default="activitywatch")
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--api-base", default="http://127.0.0.1:5600")
    parser.add_argument("--sinnix-capture-bin", default="sinnix-capture")
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
