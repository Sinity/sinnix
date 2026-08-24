from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import anyio

from .app import canonical_manifest, create_server
from .cli_support import (
    CliInputError,
    build_request,
    catalog_display,
    invoke,
)
from .runtime import manifest_measurement
from .capabilities import PRINCIPAL_CAPABILITIES
from .config import GatewayConfig
from .registry import REGISTRY

LOCAL_CONFIG_PATH = Path("/etc/sinnix/agent-gateway.json")


def _default_config_path() -> Path | None:
    """Use the deployed local estate contract unless the caller overrides it."""
    configured = os.environ.get("SINNIX_AGENT_GATEWAY_CONFIG")
    if configured:
        return Path(configured)
    return LOCAL_CONFIG_PATH if LOCAL_CONFIG_PATH.is_file() else None


async def build_manifest(config: GatewayConfig, principal_name: str) -> dict[str, Any]:
    manifest = canonical_manifest(await create_server(config, principal_name).list_tools())
    return {**manifest, "measurement": manifest_measurement(manifest)}


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
        default=_default_config_path(),
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

    def add_input_flags(command: argparse.ArgumentParser) -> None:
        source = command.add_mutually_exclusive_group()
        source.add_argument("--input", help="inline JSON object")
        source.add_argument("--input-file", type=Path, help="JSON object file")
        source.add_argument("--stdin", action="store_true", help="read one JSON object from stdin")
        command.add_argument("--action", "--action-name", dest="action_name")
        command.add_argument("--ref")
        command.add_argument("--operation")
        command.add_argument("--parameters", help="inline JSON object")
        command.add_argument("--query")
        command.add_argument("--request-id")
        command.add_argument("--actor")
        command.add_argument("--reason")
        command.add_argument("--idempotency-key")
        command.add_argument("--deadline-at", type=float)
        command.add_argument("--preconditions", help="inline JSON object")
        command.add_argument("--explain", action="store_true")
        command.add_argument(
            "--principal",
            dest="command_principal",
            choices=sorted(PRINCIPAL_CAPABILITIES),
        )

    for verb in ("status", "query", "get", "context", "events", "wait", "change", "operate", "run"):
        command = subcommands.add_parser(verb)
        add_input_flags(command)
        if verb == "change":
            mode = command.add_mutually_exclusive_group()
            mode.add_argument("--preview", action="store_true")
            mode.add_argument("--apply", action="store_true")

    catalog = subcommands.add_parser("catalog")
    add_input_flags(catalog)
    display = catalog.add_mutually_exclusive_group()
    display.add_argument("--schema", metavar="ACTION")
    display.add_argument("--example", metavar="ACTION")
    display.add_argument("--complete", nargs="?", const="", metavar="PREFIX")
    return result


def main() -> None:
    arguments = parser().parse_args()
    config = GatewayConfig.load(arguments.config)
    command = arguments.command or "serve"
    principal_name = getattr(arguments, "command_principal", None) or arguments.principal
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
    elif command == "catalog" and (
        arguments.schema
        or arguments.example
        or arguments.explain
        or arguments.complete is not None
    ):
        action_name = arguments.schema or arguments.example or arguments.action_name
        payload = catalog_display(
            principal=principal_name,
            action_name=action_name,
            schema=arguments.schema is not None,
            example=arguments.example is not None,
            explain=arguments.explain,
            complete=arguments.complete,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif command in {
        "status",
        "query",
        "get",
        "context",
        "events",
        "wait",
        "change",
        "operate",
        "run",
    } and arguments.explain:
        action_name = arguments.action_name or {
            "status": "gateway.status",
            "get": "resources.get",
            "context": "projects.context",
            "events": "audit.events",
            "wait": "jobs.wait",
        }.get(command)
        payload = catalog_display(
            principal=principal_name,
            action_name=action_name,
            explain=True,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif command in {
        "status",
        "catalog",
        "query",
        "get",
        "context",
        "events",
        "wait",
        "change",
        "operate",
        "run",
    }:
        try:
            payload = build_request(
                command,
                inline=arguments.input,
                input_file=arguments.input_file,
                use_stdin=arguments.stdin,
                action_name=arguments.action_name,
                ref=arguments.ref,
                operation=arguments.operation,
                parameters=arguments.parameters,
                query=arguments.query,
                request_id=arguments.request_id,
                actor=arguments.actor,
                reason=arguments.reason,
                idempotency_key=arguments.idempotency_key,
                deadline_at=arguments.deadline_at,
                preconditions=arguments.preconditions,
                preview=getattr(arguments, "preview", False),
                apply=getattr(arguments, "apply", False),
            )
            response = invoke(config, principal_name, command, payload)
        except (CliInputError, ValueError, RuntimeError) as error:
            raise SystemExit(str(error)) from error
        print(json.dumps(response, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
