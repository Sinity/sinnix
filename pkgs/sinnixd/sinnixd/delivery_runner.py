from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from .delivery import DeliveryError, GitHubDelivery
from .jobs import GenericJobs, GenericJobStore, UserSystemdJobs
from .projects import ProjectCatalog
from .workspaces import GitWorkspaces, WorkspaceStore

DELIVERY_OPERATIONS = frozenset({"publish", "land"})
DELIVERY_INPUT_SCHEMA_VERSION = 1


def delivery_runner_executable() -> Path:
    module_path = Path(__file__).resolve()
    if len(module_path.parents) > 4 and module_path.parents[3].name == "lib":
        return module_path.parents[4] / "bin" / "sinnixd-delivery-runner"
    return Path(sys.executable).with_name("sinnixd-delivery-runner")


def _load_input(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"delivery input is unreadable: {error}") from error
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_version") != DELIVERY_INPUT_SCHEMA_VERSION
        or payload.get("operation") not in DELIVERY_OPERATIONS
        or not isinstance(payload.get("project_root"), str)
        or not isinstance(payload.get("state_dir"), str)
        or not isinstance(payload.get("arguments"), Mapping)
    ):
        raise ValueError("delivery input schema is invalid")
    return dict(payload)


def _delivery(payload: Mapping[str, Any]) -> GitHubDelivery:
    catalog = ProjectCatalog([Path(payload["project_root"])])
    store = GenericJobStore(Path(payload["state_dir"]))
    # The daemon owns recovery, admission cleanup, and retention; this runner
    # only reads finished verification jobs, so it must not touch that state.
    jobs = GenericJobs(UserSystemdJobs(), store, recover_on_init=False)
    workspaces = GitWorkspaces(catalog, WorkspaceStore(store.root))
    return GitHubDelivery(catalog, workspaces, jobs)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnixd-delivery-runner")
    parser.add_argument("--input", type=Path, required=True)
    parsed = parser.parse_args(arguments)
    try:
        payload = _load_input(parsed.input)
        delivery = _delivery(payload)
        call_arguments = dict(payload["arguments"])
        if payload["operation"] == "publish":
            receipt = delivery.publish(
                call_arguments["workspace_id"],
                call_arguments["job_id"],
                call_arguments["title"],
                call_arguments["body"],
                packet_job_id=call_arguments.get("packet_job_id"),
            )
        else:
            receipt = delivery.land(
                call_arguments["workspace_id"],
                call_arguments["job_id"],
                packet_job_id=call_arguments.get("packet_job_id"),
            )
    except (DeliveryError, KeyError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema_version": DELIVERY_INPUT_SCHEMA_VERSION,
                    "ok": False,
                    "error": str(error),
                },
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "schema_version": DELIVERY_INPUT_SCHEMA_VERSION,
                "ok": True,
                "receipt": receipt,
            },
            sort_keys=True,
        )
    )
    return 0


def cli() -> None:
    raise SystemExit(main())
