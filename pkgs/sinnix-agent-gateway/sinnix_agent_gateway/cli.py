from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import anyio

from .app import canonical_manifest, create_server
from .capabilities import PRINCIPAL_CAPABILITIES
from .config import GatewayConfig
from .registry import REGISTRY

async def build_manifest(config: GatewayConfig, principal_name: str) -> dict[str, Any]:
    return canonical_manifest(await create_server(config, principal_name).list_tools())


def verify_approval(config: GatewayConfig, principal_name: str) -> dict[str, object]:
    if config.approved_manifest_principal != principal_name:
        raise ValueError(
            "approval principal does not match the selected gateway principal"
        )
    if (
        config.approved_manifest_hash is None
        or config.approved_action_catalog_hash is None
    ):
        raise ValueError("both tool manifest and action catalog approvals are required")
    live_manifest_hash = anyio.run(build_manifest, config, principal_name)["sha256"]
    live_catalog_hash = REGISTRY.action_catalog_hash(principal_name)
    mismatches = []
    if live_manifest_hash != config.approved_manifest_hash:
        mismatches.append(
            "tool manifest drift: "
            f"expected {config.approved_manifest_hash}, got {live_manifest_hash}"
        )
    if live_catalog_hash != config.approved_action_catalog_hash:
        mismatches.append(
            "action catalog drift: "
            f"expected {config.approved_action_catalog_hash}, got {live_catalog_hash}"
        )
    if mismatches:
        raise ValueError("; ".join(mismatches))
    return {
        "principal": principal_name,
        "tool_manifest_hash": live_manifest_hash,
        "action_catalog_hash": live_catalog_hash,
    }


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
    subcommands.add_parser("catalog-hash")
    subcommands.add_parser("approval-check")
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
    elif command == "catalog-hash":
        print(
            json.dumps(
                {
                    "principal": arguments.principal,
                    "revision": REGISTRY.revision,
                    "sha256": REGISTRY.action_catalog_hash(arguments.principal),
                },
                indent=2,
            )
        )
    elif command == "approval-check":
        try:
            print(json.dumps(verify_approval(config, arguments.principal), indent=2))
        except ValueError as error:
            raise SystemExit(str(error)) from error
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
