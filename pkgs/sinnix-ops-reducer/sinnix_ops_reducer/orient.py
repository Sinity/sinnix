"""`sinnix-ops-reducer orient` -- one-call system orientation for agents.

Thin, read-only composition over sources that are already authoritative
elsewhere: the reducer's own /v1/snapshot (which embeds the runtime
inventory and the live systemd unit list), /v1/health/lanes (the sentinel
sweep's believed status per key), and up to two Beads workspaces (this
repo's, resolved from the caller's CWD, and personal steering). No new
daemon and no new state -- every field here is a GET or a `bd ready`, and a
source that is unreachable renders as one "unavailable" line rather than a
traceback.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .reducer import now_iso

SCHEMA = "sinnix-orient-v1"

SOCKET_TIMEOUT = 3.0
BD_TIMEOUT = 8.0
BD_HEAD_LIMIT = 5
TITLE_MAX = 88

STEERING_BEADS_DIR = Path("/realm/project/steering/.beads")


def default_static_inventory_path() -> Path:
    """Honors SINNIX_RUNTIME_INVENTORY_FILE, the same override
    sinnix-observe's runtime_inventory.inventory_path() reads -- so hermetic
    tests and fixture hosts that already point that env var elsewhere also
    redirect orient's acknowledged-outages read."""
    return Path(
        os.environ.get("SINNIX_RUNTIME_INVENTORY_FILE", "/etc/sinnix/runtime-inventory.json")
    )


class UnixConnection(http.client.HTTPConnection):
    """HTTP over the reducer's Unix socket -- same shape as cli.py's, kept
    local so orient has no import-time dependency on the CLI module."""

    def __init__(self, path: str, timeout: float = SOCKET_TIMEOUT) -> None:
        super().__init__("localhost", timeout=timeout)
        self.path = path

    def connect(self) -> None:
        import socket

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def fetch_socket_json(
    socket_path: Path, route: str, timeout: float = SOCKET_TIMEOUT
) -> dict[str, Any] | None:
    """GET `route` over the reducer's socket. None on any failure: the
    reducer is not running, the socket is stale, the response is not JSON --
    all degrade to "unavailable" rather than raising."""
    connection: UnixConnection | None = None
    try:
        connection = UnixConnection(str(socket_path), timeout=timeout)
        connection.request("GET", route)
        response = connection.getresponse()
        body = response.read()
        if response.status >= 400:
            return None
        value = json.loads(body)
        return value if isinstance(value, dict) else None
    except (OSError, http.client.HTTPException, json.JSONDecodeError, ValueError):
        return None
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


def read_static_inventory(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def failed_and_attention_units(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Units in `failed` or `activating` -- the same two states pages/dashboard.py
    treats as needing attention, reimplemented here (not imported) so this
    module has no dependency on the hub page's own evolution."""
    units = state.get("systemd_units")
    if not isinstance(units, list):
        return []
    return [
        {
            "unit": entry.get("unit"),
            "manager": entry.get("manager"),
            "active_state": entry.get("active_state"),
            "sub_state": entry.get("sub_state"),
        }
        for entry in units
        if isinstance(entry, dict)
        and entry.get("active_state") in {"failed", "activating"}
    ]


def degraded_sources(sources: dict[str, Any] | None) -> list[str]:
    if not isinstance(sources, dict):
        return []
    return sorted(
        name
        for name, value in sources.items()
        if isinstance(value, dict) and value.get("status") == "unavailable"
    )


def system_verdict(
    units: list[dict[str, Any]], degraded: list[str]
) -> tuple[str, str]:
    """(status, one-line summary) -- the three-second read."""
    failed = [u for u in units if u.get("active_state") == "failed"]
    activating = [u for u in units if u.get("active_state") == "activating"]
    problems: list[str] = []
    if failed:
        names = ", ".join(str(u["unit"]) for u in failed[:3])
        problems.append(
            f"{len(failed)} unit{'s' if len(failed) != 1 else ''} failed ({names})"
        )
    if activating:
        problems.append(
            f"{len(activating)} unit{'s' if len(activating) != 1 else ''} stuck activating"
        )
    if degraded:
        problems.append(
            f"{len(degraded)} source{'s' if len(degraded) != 1 else ''} unavailable "
            f"({', '.join(degraded)})"
        )
    if problems:
        return "attention", "Needs attention: " + "; ".join(problems) + "."
    return "healthy", "The system is healthy."


def acknowledged_outages(inventory: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(inventory, dict):
        return []
    surfaces = inventory.get("surfaces")
    if not isinstance(surfaces, dict):
        return []
    rows = []
    for name, surface in sorted(surfaces.items()):
        if not isinstance(surface, dict):
            continue
        acked = surface.get("acknowledged")
        if not isinstance(acked, dict) or acked.get("down") is not True:
            continue
        rows.append(
            {
                "surface": name,
                "unit": surface.get("unit"),
                "reason": acked.get("reason") or "no reason recorded",
                "since": acked.get("since") or "?",
                "ref": acked.get("ref") or "?",
            }
        )
    return rows


def capture_freshness(lanes: dict[str, Any] | None) -> dict[str, Any]:
    """Counts plus the non-healthy list from the sentinel sweep's ledger
    (capture/payload/publisher/service/socket/mount keys alike -- the sweep
    already merges them into one state)."""
    if not isinstance(lanes, dict) or not isinstance(lanes.get("keys"), dict):
        return {"available": False}
    keys = lanes["keys"]
    non_healthy = sorted(
        (
            {"key": key, "status": value.get("status")}
            for key, value in keys.items()
            if isinstance(value, dict) and value.get("status") not in (None, "healthy")
        ),
        key=lambda row: row["key"],
    )
    return {
        "available": True,
        "total": len(keys),
        "healthy": len(keys) - len(non_healthy),
        "non_healthy": non_healthy,
    }


def bd_ready_head(
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    limit: int = BD_HEAD_LIMIT,
    timeout: float = BD_TIMEOUT,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Head of `bd ready --json`. `{"available": False}` on any failure --
    no resolvable workspace, `bd` missing, a timeout, malformed output --
    which is deliberately indistinguishable at this layer: every one of
    those means "nothing to show", never a traceback."""
    try:
        result = runner(
            ["bd", "ready", "--json"],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}
    if result.returncode != 0:
        return {"available": False}
    try:
        items = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"available": False}
    if not isinstance(items, list):
        return {"available": False}
    head = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "priority": item.get("priority"),
        }
        for item in items[:limit]
        if isinstance(item, dict)
    ]
    return {"available": True, "total": len(items), "ready": head}


def steering_ready_head(
    *,
    beads_dir: Path = STEERING_BEADS_DIR,
    limit: int = BD_HEAD_LIMIT,
    timeout: float = BD_TIMEOUT,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Same shape as `bd_ready_head`, pointed at the personal steering
    workspace via BEADS_DIR -- silently absent when that workspace does not
    exist on this host, matching sessionstart-steering.sh's own rule."""
    if not beads_dir.is_dir():
        return {"available": False}
    env = dict(os.environ)
    env["BEADS_DIR"] = str(beads_dir)
    return bd_ready_head(limit=limit, timeout=timeout, env=env, runner=runner)


def compose(
    *,
    socket_path: Path,
    static_inventory_path: Path | None = None,
    fetch: Callable[[Path, str], dict[str, Any] | None] = fetch_socket_json,
    read_static: Callable[[Path], dict[str, Any] | None] = read_static_inventory,
    bd_head: Callable[[], dict[str, Any]] = bd_ready_head,
    steering_head: Callable[[], dict[str, Any]] = steering_ready_head,
) -> dict[str, Any]:
    if static_inventory_path is None:
        static_inventory_path = default_static_inventory_path()
    snapshot = fetch(socket_path, "/v1/snapshot")
    lanes = fetch(socket_path, "/v1/health/lanes")
    state = snapshot.get("state") if isinstance(snapshot, dict) else None
    state = state if isinstance(state, dict) else {}

    inventory = state.get("runtime_inventory")
    if not isinstance(inventory, dict):
        inventory = read_static(static_inventory_path)

    result: dict[str, Any] = {"schema": SCHEMA, "generated_at": now_iso()}
    if not isinstance(snapshot, dict) or state == {}:
        result["system"] = {
            "status": "unavailable",
            "summary": "the ops-reducer snapshot is unavailable",
        }
    else:
        units = failed_and_attention_units(state)
        degraded = degraded_sources(
            snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
        )
        status, summary = system_verdict(units, degraded)
        result["system"] = {
            "status": status,
            "summary": summary,
            "sequence": snapshot.get("sequence"),
            "observed_at": snapshot.get("observed_at"),
            "failed_units": [u for u in units if u["active_state"] == "failed"],
            "attention_units": [u for u in units if u["active_state"] == "activating"],
            "degraded_sources": degraded,
        }
    result["acknowledged_outages"] = acknowledged_outages(inventory)
    result["capture_freshness"] = capture_freshness(lanes)
    result["beads"] = bd_head()
    result["steering"] = steering_head()
    return result


def _truncate(text: Any, width: int = TITLE_MAX) -> str:
    text = str(text)
    return text if len(text) <= width else text[: width - 1] + "…"


def render_human(data: dict[str, Any]) -> str:
    lines: list[str] = []
    system = data.get("system") or {}
    lines.append(f"sinnix orient — {data.get('generated_at', '?')}")
    lines.append("")
    lines.append(str(system.get("summary", "system status unknown")))
    for unit in system.get("failed_units") or []:
        lines.append(f"  FAILED      {unit.get('unit')} ({unit.get('manager')})")
    for unit in system.get("attention_units") or []:
        lines.append(f"  ACTIVATING  {unit.get('unit')} ({unit.get('manager')})")
    for name in system.get("degraded_sources") or []:
        lines.append(f"  SOURCE DOWN {name}")

    acked = data.get("acknowledged_outages") or []
    if acked:
        lines.append("")
        lines.append(f"Acknowledged outages ({len(acked)}, do not re-report as incidents):")
        for row in acked:
            lines.append(
                f"  - {row['surface']} ({row.get('unit') or '?'}) — {row['reason']} "
                f"[since {row['since']}, ref {row['ref']}]"
            )

    freshness = data.get("capture_freshness") or {}
    if freshness.get("available"):
        lines.append("")
        lines.append(
            f"Capture/health lanes: {freshness['healthy']}/{freshness['total']} healthy"
        )
        for row in freshness.get("non_healthy", []):
            lines.append(f"  - {row['key']} — {row['status']}")
    else:
        lines.append("")
        lines.append("Capture/health lanes: unavailable")

    beads = data.get("beads") or {}
    if beads.get("available"):
        lines.append("")
        lines.append(f"Beads ready ({len(beads['ready'])} of {beads['total']}):")
        for item in beads["ready"]:
            lines.append(f"  - {item['id']}  {_truncate(item['title'])}")

    steering = data.get("steering") or {}
    if steering.get("available"):
        lines.append("")
        lines.append(f"Steering ready ({len(steering['ready'])} of {steering['total']}):")
        for item in steering["ready"]:
            lines.append(f"  - {item['id']}  {_truncate(item['title'])}")

    return "\n".join(lines) + "\n"


def render_acknowledged_only(acked: list[dict[str, Any]]) -> str:
    """Byte-for-byte the sessionstart-acknowledged-outages.sh contract:
    empty string (print nothing) when there is nothing acknowledged."""
    if not acked:
        return ""
    lines = ["## Acknowledged outages (known-down, do not re-report as incidents)", ""]
    for row in acked:
        lines.append(
            f"- {row['surface']} ({row.get('unit') or '?'}) — {row['reason']} "
            f"[since {row['since']}, ref {row['ref']}]"
        )
    lines.append("")
    lines.append(
        "These are declared in the runtime inventory with a tracking reference. "
        "Treat them as\nexpected state. If one looks stale, check its reference "
        "rather than raising it as new."
    )
    return "\n".join(lines) + "\n"


def acknowledged_only_report(
    *,
    socket_path: Path,
    static_inventory_path: Path,
    fetch: Callable[[Path, str], dict[str, Any] | None] = fetch_socket_json,
    read_static: Callable[[Path], dict[str, Any] | None] = read_static_inventory,
) -> str:
    """The fast path the folded session-start hook actually takes: a direct
    static-file read, same as the shell hook it replaces, with the socket as
    fallback only -- so a healthy host pays no reducer round trip for
    something a `jq` one-liner used to answer alone."""
    inventory = read_static(static_inventory_path)
    if inventory is None:
        snapshot = fetch(socket_path, "/v1/snapshot")
        state = snapshot.get("state") if isinstance(snapshot, dict) else None
        inventory = state.get("runtime_inventory") if isinstance(state, dict) else None
    return render_acknowledged_only(acknowledged_outages(inventory))


def default_socket_path() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")) / "sinnix" / "ops.sock"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnix-ops-reducer orient")
    parser.add_argument(
        "--json", action="store_true", help="Emit the composed document as JSON."
    )
    parser.add_argument(
        "--acknowledged-only",
        action="store_true",
        help=(
            "Print only the acknowledged-outages block, in the exact format "
            "sessionstart-acknowledged-outages.sh printed; silent when there "
            "is nothing acknowledged."
        ),
    )
    parser.add_argument("--socket", type=Path, default=default_socket_path())
    parser.add_argument(
        "--inventory", type=Path, default=default_static_inventory_path()
    )
    args = parser.parse_args(argv)

    if args.acknowledged_only:
        text = acknowledged_only_report(
            socket_path=args.socket, static_inventory_path=args.inventory
        )
        if text:
            sys.stdout.write(text)
        return 0

    data = compose(socket_path=args.socket, static_inventory_path=args.inventory)
    if args.json:
        print(json.dumps(data, sort_keys=True))
    else:
        sys.stdout.write(render_human(data))
    return 0
