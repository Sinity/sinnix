from __future__ import annotations

import argparse
import os
from pathlib import Path

from .reducer import Reducer, observe_source
from .server import ensure_token, serve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")),
    )
    parser.add_argument(
        "--state-dir", type=Path, default=Path("/realm/state/sinnix-ops")
    )
    parser.add_argument(
        "--observe-command",
        nargs="+",
        default=["sinnix-observe", "--format", "json", "--limit", "10"],
    )
    parser.add_argument("--interval", type=float, default=10.0)
    args = parser.parse_args()
    observe_command = list(args.observe_command)
    if len(observe_command) == 1:
        observe_command += ["--format", "json", "--limit", "10"]
    root = args.runtime_dir / "sinnix"
    root.mkdir(parents=True, exist_ok=True)
    token = ensure_token(root / "ops.token")
    reducer = Reducer(
        root / "status.json",
        root / "ops.token",
        observe_source(observe_command),
        args.state_dir / "reducer.json",
    )
    fds = list(range(3, 3 + int(os.environ.get("LISTEN_FDS", "0"))))
    serve(reducer, token, fds, args.interval)
