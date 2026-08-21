from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import anyio

from .app import canonical_manifest, create_server
from .capabilities import PRINCIPAL_CAPABILITIES
from .config import GatewayConfig

async def build_manifest(config: GatewayConfig, principal_name: str) -> dict[str, Any]:
    return canonical_manifest(await create_server(config, principal_name).list_tools())


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
        "--principal", choices=sorted(PRINCIPAL_CAPABILITIES), default="observer"
    )
    subcommands = result.add_subparsers(dest="command")
    subcommands.add_parser("serve")
    subcommands.add_parser("manifest")
    subcommands.add_parser("info")
    return result


def main() -> None:
    arguments = parser().parse_args()
    config = GatewayConfig.load(arguments.config)
    command = arguments.command or "serve"
    if command == "serve":
        create_server(config, arguments.principal).run("stdio")
    elif command == "manifest":
        print(
            json.dumps(anyio.run(build_manifest, config, arguments.principal), indent=2)
        )
    elif command == "info":
        print(
            json.dumps(
                {
                    "version": "0.2.0",
                    "principal": arguments.principal,
                    "transport": "stdio",
                    "state": str(config.state_dir),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
