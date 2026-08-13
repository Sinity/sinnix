"""Entry point: `sinnix-cockpit --port PORT`."""

from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(prog="sinnix-cockpit")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SINNIX_COCKPIT_PORT", "8791")),
    )
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    import uvicorn

    from .app import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
