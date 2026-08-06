from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import anyio

from .app import create_server
from .capabilities import PROFILE_CAPABILITIES
from .config import GatewayConfig


def canonical_manifest(tools: list[Any]) -> dict[str, Any]:
    rows = [
        tool.model_dump(by_alias=True, exclude_none=True, mode="json") for tool in tools
    ]
    rows.sort(key=lambda row: row["name"])
    payload = {"schema": "sinnix.gateway-tools.v1", "tools": rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


async def build_manifest(config: GatewayConfig, profile: str) -> dict[str, Any]:
    return canonical_manifest(await create_server(config, profile).list_tools())


def migrate_legacy(config: GatewayConfig, source: Path) -> dict[str, Any]:
    config.initialize_state()
    destination = config.state_dir / "legacy" / "sinnix-agent-gateway"
    if not source.exists():
        return {"migrated": False, "reason": "legacy state absent"}
    if destination.exists():
        return {"migrated": False, "reason": "legacy state already archived"}
    source.rename(destination)
    destination.chmod(0o700)
    return {"migrated": True, "destination": "legacy/sinnix-agent-gateway"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="sinnix-agent-gateway")
    result.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ["SINNIX_AGENT_GATEWAY_CONFIG"])
        if "SINNIX_AGENT_GATEWAY_CONFIG" in os.environ
        else None,
    )
    result.add_argument(
        "--profile", choices=sorted(PROFILE_CAPABILITIES), default="remote-readonly"
    )
    subcommands = result.add_subparsers(dest="command")
    subcommands.add_parser("serve")
    subcommands.add_parser("manifest")
    subcommands.add_parser("info")
    migrate = subcommands.add_parser("migrate-state")
    migrate.add_argument(
        "--source",
        type=Path,
        default=Path.home() / ".local" / "state" / "sinnix-agent-gateway",
    )
    return result


def main() -> None:
    arguments = parser().parse_args()
    config = GatewayConfig.load(arguments.config)
    command = arguments.command or "serve"
    if command == "serve":
        create_server(config, arguments.profile).run("stdio")
    elif command == "manifest":
        print(json.dumps(anyio.run(build_manifest, config, arguments.profile), indent=2))
    elif command == "info":
        print(
            json.dumps(
                {
                    "version": "0.2.0",
                    "profile": arguments.profile,
                    "transport": "stdio",
                    "state": str(config.state_dir),
                },
                indent=2,
            )
        )
    elif command == "migrate-state":
        print(json.dumps(migrate_legacy(config, arguments.source), indent=2))


if __name__ == "__main__":
    main()
