from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sinnix_lib.layout import ACTIVITY_LANES, capture_lane_path

from .config import GatewayConfig
from .owner_execution import ExecutionProfile, OwnerExecution, OwnerRoute
from .permissions import Permission, PolicyError, Principal


class CaptureInventoryUnavailableError(RuntimeError):
    """The capture authority could not be read or interpreted."""


class CaptureScopeError(PolicyError):
    """Configured selectors cannot be resolved through the runtime authority."""


@dataclass(frozen=True)
class CaptureLane:
    """One runtime-declared capture lane and its exact native contract."""

    name: str
    path: Path
    native_contract: str
    root: Path | None = None
    native_lane: str | None = None

    @property
    def progress_path(self) -> Path | None:
        if self.native_contract == "sinnix-capture-v1-sidecar":
            if self.root is None or self.native_lane is None:
                return None
            return self.path / f"{self.native_lane}-index.jsonl"
        if self.path.is_file():
            return self.path
        return None


def queryable_capture_lanes(
    runtime_inventory: Path,
    selectors: frozenset[str] = frozenset(),
    allowed_lanes: frozenset[str] | None = None,
) -> dict[str, CaptureLane]:
    """Derive capture query contracts from every declared runtime lane.

    The inventory is the capture authority.  Every valid declared path is
    visible, including direct-file lanes that have no ``sinnix-capture``
    reader.  Sidecar capability is discovered only to choose the established
    reader, never to decide whether a runtime declaration exists.  Its native
    identity and collection root follow the shared layout registry. Custom
    lanes retain their basename identity, independently of globally unique
    inventory display names such as ``peripherals-logitech``.
    """
    try:
        inventory = json.loads(runtime_inventory.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CaptureInventoryUnavailableError(
            f"capture runtime inventory unavailable: {error}"
        ) from error
    if not isinstance(inventory, dict) or not isinstance(
        inventory.get("captures"), list
    ):
        raise CaptureInventoryUnavailableError(
            "capture runtime inventory must contain a captures list"
        )
    captures = inventory["captures"]
    declarations: dict[str, Path] = {}
    for row in captures:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        path = row.get("path")
        if not isinstance(name, str) or not name or not isinstance(path, str):
            continue
        lane_path = Path(path)
        if not lane_path.is_absolute():
            continue
        declarations[name] = lane_path
    selected = _selected_capture_names(inventory, set(declarations), selectors)
    if allowed_lanes is not None:
        selected.intersection_update(allowed_lanes)
    lanes: dict[str, CaptureLane] = {}
    for name, lane_path in declarations.items():
        if name not in selected:
            continue
        native_lane = lane_path.name
        root = lane_path.parent
        for identity, relative in ACTIVITY_LANES.items():
            parts = Path(relative).parts
            if lane_path.parts[-len(parts) :] == parts:
                native_lane = identity
                root = lane_path.parents[len(parts) - 1]
                break
        # A retired flat managed path cannot be read by the registry-aware
        # owner. Never admit it only to query a different, empty directory.
        matches_owner = capture_lane_path(root, native_lane) == lane_path
        index_path = lane_path / f"{native_lane}-index.jsonl"
        if matches_owner and index_path.is_file():
            lanes[name] = CaptureLane(
                name=name,
                path=lane_path,
                native_contract="sinnix-capture-v1-sidecar",
                root=root,
                native_lane=native_lane,
            )
        else:
            lanes[name] = CaptureLane(
                name=name,
                path=lane_path,
                native_contract="runtime-declared-path",
            )
    return lanes


def _selected_capture_names(
    inventory: dict, names: set[str], selectors: frozenset[str]
) -> set[str]:
    if not selectors:
        return names
    scope = inventory.get("capture_scopes")
    subjects = None
    if any(selector.startswith("subject:") for selector in selectors):
        if (
            not isinstance(scope, dict)
            or scope.get("schema") != "sinnix-capture-scope-v1"
            or not isinstance(scope.get("subjects"), dict)
        ):
            raise CaptureScopeError(
                "subject selectors require the versioned runtime capture subject registry"
            )
        subjects = scope["subjects"]
    selected = set()
    for selector in sorted(selectors):
        kind, separator, name = selector.partition(":")
        if not separator or not name:
            raise CaptureScopeError(f"invalid capture-scope-v1 selector: {selector}")
        if kind == "lane":
            if name not in names:
                raise CaptureScopeError(
                    f"unknown runtime capture lane selector: {selector}"
                )
            selected.add(name)
        elif kind == "subject":
            if name not in subjects:
                raise CaptureScopeError(
                    f"unknown runtime capture subject selector: {selector}"
                )
            members = subjects[name]
            if not isinstance(members, list) or any(
                not isinstance(member, str) or member not in names for member in members
            ):
                raise CaptureScopeError(
                    f"invalid runtime capture subject membership: {name}"
                )
            selected.update(members)
        else:
            raise CaptureScopeError(f"unknown capture selector kind: {kind}")
    return selected


class CaptureService:
    """Query declared native capture lanes without owning a lane registry."""

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        self.execution = OwnerExecution()

    def _available_lanes(self) -> dict[str, CaptureLane]:
        return queryable_capture_lanes(
            self.config.runtime_inventory,
            self.config.capture_scope,
            self.principal.allowed_lanes,
        )

    def lanes_visible(self) -> dict[str, Any]:
        """List runtime-declared native lane contracts visible to this principal."""
        self.principal.require(Permission.CAPTURE_READ)
        lanes = self._available_lanes()
        available = sorted(lanes)
        visible = self.principal.filter_lanes(None, available)
        return {
            "lanes": [
                {
                    "name": name,
                    "ref": f"sinnix://captures/{name}",
                    "path": str(lanes[name].path),
                    "native_contract": lanes[name].native_contract,
                    **(
                        {
                            "capture_root": str(lanes[name].root),
                            "native_lane": lanes[name].native_lane,
                        }
                        if lanes[name].root is not None
                        else {}
                    ),
                }
                for name in visible
            ],
            "total_declared_lanes": len(available),
        }

    def lane(self, name: str) -> dict[str, Any]:
        """Return one canonical lane's inventory-derived native contract."""
        self.principal.require_lane(name)
        try:
            lane = self._available_lanes()[name]
        except KeyError as exc:
            if self.config.capture_scope:
                raise PolicyError("capture lane is outside endpoint scope") from exc
            raise ValueError(
                "capture lane is not declared by runtime inventory"
            ) from exc
        return {
            "ref": f"sinnix://captures/{name}",
            "name": lane.name,
            "path": str(lane.path),
            "native_contract": lane.native_contract,
            **(
                {"capture_root": str(lane.root), "native_lane": lane.native_lane}
                if lane.root is not None
                else {}
            ),
        }

    def freshness(self, name: str) -> dict[str, Any]:
        """Return freshness from the lane's actual capture progress record."""
        self.principal.require_lane(name)
        try:
            lane = self._available_lanes()[name]
        except KeyError as exc:
            if self.config.capture_scope:
                raise PolicyError("capture lane is outside endpoint scope") from exc
            raise ValueError(
                "capture lane is not declared by runtime inventory"
            ) from exc
        progress_path = lane.progress_path
        if progress_path is None:
            return {
                "available": False,
                "reason": "capture lane has no admitted progress record",
                "lane": name,
            }
        try:
            stat = progress_path.stat()
        except FileNotFoundError:
            return {
                "available": False,
                "reason": "capture progress record is missing",
                "lane": name,
                "progress_path": str(progress_path),
            }
        mtime = stat.st_mtime
        return {
            "available": True,
            "lane": name,
            "progress_path": str(progress_path),
            "mtime": mtime,
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }

    def query(
        self, lanes: list[str] | None = None, since: float = 0.0, limit: int = 100
    ) -> dict[str, Any]:
        available = self._available_lanes()
        effective_lanes = self.principal.filter_lanes(lanes, sorted(available))
        if not effective_lanes:
            return {"records": [], "lanes_queried": [], "truncated": False}

        non_sidecar = [
            name
            for name in effective_lanes
            if available[name].native_contract != "sinnix-capture-v1-sidecar"
        ]
        if non_sidecar:
            return {
                "available": False,
                "failure_class": "native_contract_unavailable",
                "reason": "selected runtime capture paths have no admitted query reader",
                "lanes": non_sidecar,
            }

        lanes_by_root: dict[Path, list[CaptureLane]] = defaultdict(list)
        for lane in effective_lanes:
            contract = available[lane]
            assert contract.root is not None and contract.native_lane is not None
            lanes_by_root[contract.root].append(contract)

        bounded_limit = max(0, min(limit, 1_000))
        records: list[dict[str, Any]] = []
        truncated = False
        sorted_roots = sorted(lanes_by_root.items(), key=lambda item: str(item[0]))
        for root, root_lanes in sorted_roots:
            command = [
                self.config.capture_command,
                "query",
                "--capture-root",
                str(root),
                "--since",
                str(since),
            ]
            for lane in root_lanes:
                assert lane.native_lane is not None
                command += ["--lane", lane.native_lane]

            result = self.execution.run(
                command,
                ExecutionProfile(
                    route=OwnerRoute("capture-query"),
                    timeout_seconds=20,
                    max_stdout_bytes=self.config.max_result_bytes,
                ),
            )
            if result.failure_class is not None:
                failure_class = {
                    "command_timeout": "collector_timeout",
                    "command_unavailable:FileNotFoundError": "collector_unavailable",
                }.get(result.failure_class, "collector_failed")
                return {
                    "available": False,
                    "failure_class": failure_class,
                    "reason": result.stderr_excerpt()
                    or (
                        "sinnix-capture query is unavailable"
                        if failure_class == "collector_unavailable"
                        else "sinnix-capture query failed"
                    ),
                    "command": list(result.command),
                }

            try:
                payload = result.decode_json()
            except json.JSONDecodeError:
                return {
                    "available": False,
                    "failure_class": "unparseable_output",
                    "reason": "sinnix-capture query did not return valid JSON",
                }

            root_records = (
                payload.get("records", payload)
                if isinstance(payload, dict)
                else payload
            )
            if not isinstance(root_records, list):
                return {
                    "available": False,
                    "failure_class": "unparseable_output",
                    "reason": "sinnix-capture query did not return a record list",
                }
            for record in root_records:
                if len(records) >= bounded_limit:
                    truncated = True
                    break
                if isinstance(record, dict):
                    records.append(record)
            if truncated:
                break

        return {
            "records": records,
            "lanes_queried": effective_lanes,
            "truncated": truncated,
        }
