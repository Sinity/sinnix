from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from typing import Any

import anyio

from . import actions as action_set
from .app import canonical_manifest, create_server
from .cli_support import (
    CliInputError,
    build_request,
    catalog_display,
    invoke,
    invoke_mcp,
)
from .config import GatewayConfig
from .runtime import manifest_measurement

LOCAL_CONFIG_PATH = Path("/etc/sinnix/agent-gateway.json")
VERSION = "0.3.0"


def _default_config_path() -> Path | None:
    """Use the deployed local estate contract unless the caller overrides it."""
    configured = os.environ.get("SINNIX_AGENT_GATEWAY_CONFIG")
    if configured:
        return Path(configured)
    return LOCAL_CONFIG_PATH if LOCAL_CONFIG_PATH.is_file() else None


async def build_manifest(config: GatewayConfig) -> dict[str, Any]:
    manifest = canonical_manifest(await create_server(config).list_tools())
    return {**manifest, "measurement": manifest_measurement(manifest)}


def verify_manifest(config: GatewayConfig) -> dict[str, object]:
    """Check deployed code against its package-generated tool manifest."""
    expected = None
    if config.package_manifest_path is not None:
        artifact = json.loads(config.package_manifest_path.read_text())
        expected = artifact.get("manifest", {}).get("sha256")
    if not isinstance(expected, str) or not expected:
        raise ValueError("a package tool manifest is required")
    live = anyio.run(build_manifest, config)["sha256"]
    if live != expected:
        raise ValueError(f"tool manifest drift: expected {expected}, got {live}")
    return {
        "tool_manifest_hash": live,
        "action_catalog_hash": action_set.catalog_hash(),
    }


async def self_test(config: GatewayConfig) -> dict[str, object]:
    """Exercise the typed envelopes a cold session starts from."""
    catalog = await invoke_mcp(config, "gateway.catalog", {"limit": 500})
    data = catalog.get("data") if isinstance(catalog, dict) else None
    if catalog.get("result", {}).get("outcome") != "ok" or not isinstance(data, dict):
        raise ValueError("self-test catalog did not return its typed envelope")
    names = {row.get("name") for row in data.get("actions", [])}
    required = {"gateway.status", "projects.list", "files.read", "beads.query"}
    missing = sorted(required - names)
    if missing:
        raise ValueError(f"self-test catalog omits actions: {', '.join(missing)}")
    projects = await invoke_mcp(config, "projects.list", {})
    rows = projects.get("data", {}).get("projects") if projects.get("data") else None
    if projects.get("result", {}).get("outcome") != "ok" or not isinstance(rows, list):
        raise ValueError("self-test projects.list did not return its typed envelope")
    if data.get("truncated"):
        raise ValueError("self-test catalog was truncated")
    return {
        "catalog_actions": len(names),
        "projects": len(rows),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="sinnix-agent-gateway",
        description="Invoke one typed gateway action or serve the MCP transport.",
    )
    result.add_argument("--config", type=Path, default=_default_config_path())
    subcommands = result.add_subparsers(dest="command")
    for name in (
        "serve",
        "manifest",
        "catalog-hash",
        "manifest-check",
        "self-test",
        "info",
    ):
        subcommands.add_parser(name)

    http_serve = subcommands.add_parser(
        "serve-http", help="serve MCP over a private Unix socket"
    )
    http_serve.add_argument("--socket", type=Path, required=True)

    call = subcommands.add_parser(
        "call",
        help='invoke an action by name, e.g. call files.read --set target=\'{"path":"/etc/os-release"}\'',
    )
    call.add_argument("action", help="action name, e.g. files.read")
    source = call.add_mutually_exclusive_group()
    source.add_argument("--input", help="inline JSON object")
    source.add_argument("--input-file", type=Path, help="JSON object file")
    source.add_argument("--stdin", action="store_true", help="read one JSON object")
    call.add_argument(
        "--set",
        dest="assignments",
        action="append",
        metavar="KEY=VALUE",
        help="set one input field; VALUE is parsed as JSON when it is JSON",
    )
    call.add_argument("--request-id")
    call.add_argument("--actor")
    call.add_argument("--reason")
    call.add_argument("--idempotency-key")
    call.add_argument("--deadline-at", type=float)

    catalog = subcommands.add_parser("catalog", help="describe actions")
    catalog.add_argument("action", nargs="?", help="action name to describe")
    catalog.add_argument(
        "--schema", action="store_true", help="print input/output schemas"
    )
    catalog.add_argument("--example", action="store_true", help="print examples")
    catalog.add_argument("--complete", nargs="?", const="", metavar="PREFIX")
    return result


def main() -> None:
    arguments = parser().parse_args()
    config = GatewayConfig.load(arguments.config)
    command = arguments.command or "serve"
    if command == "serve":
        create_server(config).run("stdio")
    elif command == "serve-http":
        from .serving import serve_unix

        if not arguments.socket.is_absolute():
            raise SystemExit("socket path must be absolute")
        parent = arguments.socket.parent.resolve(strict=True)
        parent_stat = parent.stat()
        if (
            parent_stat.st_uid != os.getuid()
            or stat.S_IMODE(parent_stat.st_mode) & 0o077
        ):
            raise SystemExit("socket directory must be owned by this user and private")
        app = create_server(
            config, transport="streamable_http_unix"
        ).streamable_http_app(json_response=True, host="localhost")
        original_umask = os.umask(0o077)
        try:
            serve_unix(app, arguments.socket)
        finally:
            os.umask(original_umask)
    elif command == "manifest":
        print(json.dumps(anyio.run(build_manifest, config), indent=2))
    elif command == "catalog-hash":
        print(
            json.dumps(
                {
                    "revision": action_set.REVISION,
                    "sha256": action_set.catalog_hash(),
                },
                indent=2,
            )
        )
    elif command == "manifest-check":
        try:
            print(json.dumps(verify_manifest(config), indent=2))
        except ValueError as error:
            raise SystemExit(str(error)) from error
    elif command == "self-test":
        try:
            print(json.dumps(anyio.run(self_test, config)))
        except ValueError as error:
            raise SystemExit(str(error)) from error
    elif command == "info":
        print(
            json.dumps(
                {
                    "version": VERSION,
                    "transport": "stdio",
                    "state": str(config.state_dir),
                    "actions": len(action_set.ALL_ACTIONS),
                },
                indent=2,
            )
        )
    elif command == "catalog":
        try:
            payload = catalog_display(
                action_name=arguments.action,
                schema=arguments.schema,
                example=arguments.example,
                complete=arguments.complete,
            )
        except CliInputError as error:
            raise SystemExit(str(error)) from error
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif command == "call":
        try:
            payload = build_request(
                inline=arguments.input,
                input_file=arguments.input_file,
                use_stdin=arguments.stdin,
                assignments=arguments.assignments,
                request_id=arguments.request_id,
                actor=arguments.actor,
                reason=arguments.reason,
                idempotency_key=arguments.idempotency_key,
                deadline_at=arguments.deadline_at,
            )
            response = invoke(config, arguments.action, payload)
        except (CliInputError, ValueError, RuntimeError) as error:
            raise SystemExit(str(error)) from error
        print(json.dumps(response, indent=2, sort_keys=True))
        if response.get("result", {}).get("outcome") == "error":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
