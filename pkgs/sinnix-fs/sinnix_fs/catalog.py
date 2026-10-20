#!/usr/bin/env python3

"""Maintain attributed file observations and their location history.

The catalog is deliberately metadata-only: importing an observation never
hashes a file or changes the file system.  Paths are checked and stat'ed so a
catalog cannot silently point at a different object after replacement.
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import fcntl
import hashlib
import html
import json
import os
import re
import shlex
import stat
import string
import subprocess
import sys
import uuid
from collections import Counter
from itertools import chain
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from sinnix_lib.atomic import atomic_publish
from sinnix_lib.catalog_paths import normalized, relocate_path, resolve_historical_path
from sinnix_lib.files import NotRegularFile, read_regular_bytes, read_regular_text
from sinnix_lib.mounts import has_mounted_ancestor, read_mountpoints
from sinnix_lib.note_links import prose_mask

SCHEMA_VERSION = 1
REQUIRED_INSPECTION = ("method", "scope", "basis")
COVERAGE_STATES = (
    "sampled",
    "metadata_only",
    "complete",
    "native_boundary",
    "unavailable",
)


class CatalogError(ValueError):
    pass


def entry_exists(path: Path) -> bool:
    """Only a confirmed missing entry proves absence, including broken links."""
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise CatalogError(
            f"cannot establish path presence: {path}: {error}"
        ) from error
    return True


def fail(message: str) -> int:
    display = json.dumps(message, ensure_ascii=True) if sys.stderr.isatty() else message
    print(f"sinnix fs catalog: {display}", file=sys.stderr)
    return 2


def now() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_json(path: Path) -> Any:
    try:
        return json.loads(read_regular_text(path))
    except FileNotFoundError as error:
        raise CatalogError(f"catalog does not exist: {path}") from error
    except (OSError, ValueError) as e:
        raise CatalogError(f"cannot read JSON {path}: {e}") from e


def identity(path: Path) -> dict[str, Any]:
    try:
        s = path.stat()
    except OSError as e:
        raise CatalogError(
            f"current_path does not exist or is inaccessible: {path}: {e}"
        ) from e
    observed = {
        "device": s.st_dev,
        "inode": s.st_ino,
        "size": s.st_size,
        "mtime_ns": s.st_mtime_ns,
        "mode": stat.S_IMODE(s.st_mode),
    }
    try:
        mount = subprocess.run(
            ["findmnt", "-T", str(path), "-n", "-o", "FSTYPE,UUID"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        fields = mount.stdout.split()
        if mount.returncode == 0 and len(fields) == 2:
            observed["filesystem_uuid"] = fields[1]
            if fields[0] == "btrfs":
                subvolume = subprocess.run(
                    ["btrfs", "inspect-internal", "rootid", str(path)],
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                if subvolume.returncode == 0 and subvolume.stdout.strip().isdigit():
                    observed["btrfs_subvolume_id"] = int(subvolume.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return observed


def identity_differences(
    a: dict, b: dict, kind: str = "file", *, include_device: bool = False
) -> dict:
    """Compare recorded observations; missing evidence never verifies identity."""
    stable = ("filesystem_uuid", "btrfs_subvolume_id")
    complete_stable = all(
        a.get(key) is not None and b.get(key) is not None for key in stable
    )
    keys = ["inode"] if kind == "collection" else ["inode", "size", "mtime_ns", "mode"]
    if include_device or not complete_stable:
        keys.insert(0, "device")
    # Newly available fields are observations, not retrospective requirements
    # on legacy records. Previously recorded fields must still be observed.
    keys.extend(key for key in stable if key in a)
    return {
        key: {"recorded": a.get(key), "observed": b.get(key)}
        for key in keys
        if a.get(key) is None or b.get(key) is None or a[key] != b[key]
    }


def same_identity(a: Any, b: Any, kind: str = "file") -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    return not identity_differences(a, b, kind)


def location_identity(asset: dict[str, Any]) -> dict[str, Any]:
    """Latest reviewed identity at this address, separate from older inspections."""
    for observation in chain(
        (asset.get("current_location"),),
        reversed(asset.get("location_observations", [])),
    ):
        if (
            isinstance(observation, dict)
            and observation.get("path") == asset["current_path"]
            and isinstance(observation.get("identity"), dict)
        ):
            return observation["identity"]
    return asset["identity"]


def record_location(asset: dict[str, Any], observation: dict[str, Any]) -> None:
    asset.setdefault("location_observations", []).append(observation)
    asset["current_location"] = observation
    asset["location_status"] = observation["status"]


def record_relocated_location(
    asset: dict[str, Any], source: str, actual: dict[str, Any]
) -> None:
    record_location(
        asset,
        {
            "observed_at": now(),
            "actor": "sinnix-file-catalog",
            "action": "relocation",
            "path": asset["current_path"],
            "source": source,
            "status": "available",
            "identity": actual,
            "basis": "Destination matches the reviewed filesystem identity after external rename.",
            "reason": "Verified relocation",
            "content_continuity": "unverified",
        },
    )


def check_path_kind(path: Path, kind: str) -> None:
    try:
        mode = path.stat().st_mode
        if kind == "collection" and not stat.S_ISDIR(mode):
            raise CatalogError(f"collection current_path is not a directory: {path}")
        if kind == "file" and not stat.S_ISREG(mode):
            raise CatalogError(f"file current_path is not a regular file: {path}")
    except OSError as e:
        raise CatalogError(f"cannot inspect current_path {path}: {e}") from e


def check_inspection(item: Any) -> None:
    if not isinstance(item, dict):
        raise CatalogError("inspection must be an object")
    for key in REQUIRED_INSPECTION:
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise CatalogError(f"inspection requires nonempty {key}")


def check_coverage(value: Any) -> None:
    if not isinstance(value, dict) or value.get("status") not in COVERAGE_STATES:
        raise CatalogError("coverage requires an explicit inspection status")
    if "discovered_count" not in value:
        raise CatalogError("coverage requires discovered_count; use null for unknown")
    for key in ("scope", "unit"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise CatalogError(f"coverage requires nonempty {key}")
    for key in ("discovered_count", "inspected_count"):
        count = value.get(key)
        if key == "discovered_count" and count is None:
            continue
        if type(count) is not int or count < 0:
            raise CatalogError(f"coverage requires nonnegative {key}")
    discovered, inspected = value.get("discovered_count"), value["inspected_count"]
    if discovered is not None and inspected > discovered:
        raise CatalogError("coverage inspected_count exceeds discovered_count")
    if value["status"] == "complete" and (
        discovered is None or inspected != discovered
    ):
        raise CatalogError(
            "complete coverage requires an explicit, fully inspected denominator"
        )
    if not isinstance(value.get("exclusions", []), list) or not all(
        isinstance(item, str) for item in value.get("exclusions", [])
    ):
        raise CatalogError("coverage exclusions must be strings")


def check_asset(
    asset: Any, *, require_path: bool = True, require_identity: bool = True
) -> None:
    if not isinstance(asset, dict):
        raise CatalogError("asset must be an object")
    for key in ("id", "kind", "current_path", "title", "description"):
        if not isinstance(asset.get(key), str) or not asset[key].strip():
            raise CatalogError(f"asset requires nonempty {key}")
    if asset["kind"] not in ("file", "collection"):
        raise CatalogError("asset kind must be file or collection")
    if require_identity and not isinstance(asset.get("identity"), dict):
        raise CatalogError("asset requires identity object")
    if isinstance(asset.get("identity"), dict):
        for key in ("device", "inode", "size", "mtime_ns", "mode"):
            if not isinstance(asset["identity"].get(key), int):
                raise CatalogError(f"identity requires integer {key}")
        if "sha256" in asset["identity"]:
            digest = asset["identity"]["sha256"]
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdefABCDEF" for c in digest)
            ):
                raise CatalogError(
                    "identity sha256 must contain exactly 64 hexadecimal characters"
                )
    try:
        parsed_id = uuid.UUID(asset["id"])
    except (ValueError, AttributeError):
        raise CatalogError(f"asset id is not a UUID: {asset.get('id')}") from None
    if str(parsed_id) != asset["id"]:
        raise CatalogError(f"asset id is not canonical UUID: {asset['id']}")
    for key in ("previous_paths", "tags", "inspections", "uncertainties", "relations"):
        if not isinstance(asset.get(key, []), list):
            raise CatalogError(f"asset {key} must be a list")
    try:
        normalized(asset["current_path"])
    except ValueError as exc:
        raise CatalogError(
            f"current_path must be a normalized absolute path: {exc}"
        ) from exc
    for previous in asset.get("previous_paths", []):
        try:
            normalized(previous)
        except ValueError as exc:
            raise CatalogError(
                f"previous_paths must contain normalized absolute paths: {exc}"
            ) from exc
    if not asset.get("inspections"):
        raise CatalogError("asset requires at least one inspection")
    if not all(isinstance(tag, str) for tag in asset.get("tags", [])):
        raise CatalogError("tags must contain strings")
    if not all(isinstance(note, str) for note in asset.get("uncertainties", [])):
        raise CatalogError("uncertainties must contain strings")
    for inspection in asset.get("inspections", []):
        check_inspection(inspection)
    if "coverage" in asset:
        check_coverage(asset["coverage"])
    if "facets" in asset and (
        not isinstance(asset["facets"], dict)
        or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in asset["facets"].items()
        )
    ):
        raise CatalogError("facets must map names to strings")
    if "organization" in asset:
        organization = asset["organization"]
        if (
            not isinstance(organization, dict)
            or organization.get("action")
            not in (
                "keep",
                "navigate",
                "consolidate",
                "split",
                "relocate",
                "investigate",
            )
            or not isinstance(organization.get("rationale"), str)
            or not organization["rationale"].strip()
        ):
            raise CatalogError("organization requires action and rationale")
        destination = organization.get("proposed_path")
        if destination is not None and (
            not isinstance(destination, str) or not Path(destination).is_absolute()
        ):
            raise CatalogError("organization proposed_path must be absolute or null")
        dependencies = organization.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) for item in dependencies
        ):
            raise CatalogError("organization dependencies must be strings")
    if "related_paths" in asset:
        if not isinstance(asset["related_paths"], list) or not all(
            isinstance(r, dict)
            and all(
                isinstance(r.get(k), str) and r[k].strip()
                for k in ("path", "type", "basis")
            )
            and Path(r["path"]).is_absolute()
            for r in asset["related_paths"]
        ):
            raise CatalogError("related_paths require absolute path, type and basis")
    for relation in asset.get("relations", []):
        if not isinstance(relation, dict) or not all(
            isinstance(relation.get(k), str) and relation[k].strip()
            for k in ("type", "target_id", "basis")
        ):
            raise CatalogError("relation requires nonempty type, target_id, and basis")
        try:
            if str(uuid.UUID(relation["target_id"])) != relation["target_id"]:
                raise ValueError
        except ValueError:
            raise CatalogError(
                f"relation target is not a UUID: {relation['target_id']}"
            ) from None
    if require_path:
        path = Path(asset["current_path"])
        location = asset.get("current_location")
        if isinstance(location, dict) and location.get("status") in (
            "missing",
            "offline_mount",
            "denied",
            "inaccessible",
            "wrong_type",
        ):
            if (
                location.get("path") != asset["current_path"]
                or asset.get("location_status") != location["status"]
                or not all(
                    isinstance(location.get(k), str) and location[k].strip()
                    for k in ("actor", "basis", "reason", "observed_at")
                )
            ):
                raise CatalogError(
                    "unavailable location requires consistent path, status and attributed evidence"
                )
            actual = location_diagnosis(path, asset["kind"])
            if actual["status"] != location["status"]:
                raise CatalogError(
                    f"availability observation is stale for {path}; record a fresh observation"
                )
            return
        check_path_kind(path, asset["kind"])
        actual = identity(path)
        if not same_identity(location_identity(asset), actual, asset["kind"]):
            raise CatalogError(f"identity mismatch for {asset['current_path']}")


def validate_catalog(catalog: Any, *, check_paths: bool = True) -> None:
    if (
        not isinstance(catalog, dict)
        or catalog.get("schema_version") != SCHEMA_VERSION
        or not isinstance(catalog.get("updated_at"), str)
        or not isinstance(catalog.get("assets"), list)
    ):
        raise CatalogError(
            "catalog must be an object with schema_version 1, updated_at, and assets list"
        )
    ids: set[str] = set()
    paths: set[str] = set()
    for asset in catalog["assets"]:
        check_asset(asset, require_path=check_paths)
        if asset["id"] in ids:
            raise CatalogError(f"duplicate asset id: {asset['id']}")
        if asset["current_path"] in paths:
            raise CatalogError(f"duplicate current_path: {asset['current_path']}")
        ids.add(asset["id"])
        paths.add(asset["current_path"])
    for asset in catalog["assets"]:
        for relation in asset.get("relations", []):
            if relation["target_id"] not in ids:
                raise CatalogError(f"dangling relation target: {relation['target_id']}")


def load_catalog(path: Path, *, paths: bool = True) -> dict[str, Any]:
    catalog = read_json(path)
    validate_catalog(catalog, check_paths=paths)
    return catalog


def observation_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict) and isinstance(value.get("observations"), list):
        rows = value["observations"]
    else:
        raise CatalogError("observations JSON must be a list")
    if not all(isinstance(row, dict) for row in rows):
        raise CatalogError("each observation must be an object")
    return rows


def observation_asset(row: dict[str, Any]) -> dict[str, Any]:
    item = copy.deepcopy(row)
    item.setdefault("id", str(uuid.uuid4()))
    item.setdefault("kind", "file")
    item.setdefault("previous_paths", [])
    item.setdefault("tags", [])
    item.setdefault("inspections", [])
    item.setdefault("uncertainties", [])
    item.setdefault("relations", [])
    check_asset(item, require_path=False, require_identity=False)
    p = Path(item["current_path"])
    check_path_kind(p, item["kind"])
    for inspection in item["inspections"]:
        # Keep the authored context alongside the observation.  This prevents
        # a later asset-level edit from rewriting the meaning of old evidence.
        inspection.setdefault("title", item["title"])
        inspection.setdefault("description", item["description"])
    observed = identity(p)
    old = item.get("identity")
    if old is not None and not same_identity(old, observed, item["kind"]):
        raise CatalogError(f"supplied identity mismatch for {p}")
    extras = (
        {k: v for k, v in old.items() if k not in observed}
        if isinstance(old, dict)
        else {}
    )
    item["identity"] = {**observed, **extras}
    return item


def merge_asset(
    old: dict[str, Any], incoming: dict[str, Any], *, on_conflict: str = "replace"
) -> dict[str, Any]:
    # Preserve annotation keys unknown to this version and merge known fields.
    merged = copy.deepcopy(old)
    old_identity = old.get("identity")
    if old_identity is not None and not same_identity(
        old_identity, incoming["identity"], old["kind"]
    ):
        raise CatalogError(
            f"refusing replacement at {incoming['current_path']}; identity differs from catalog"
        )
    identity_fields = (
        {**old_identity, **incoming["identity"]}
        if isinstance(old_identity, dict)
        else incoming["identity"]
    )
    conflicts = copy.deepcopy(old.get("annotation_conflicts", []))
    list_fields = (
        "previous_paths",
        "tags",
        "inspections",
        "uncertainties",
        "relations",
        "related_paths",
    )
    for key, value in incoming.items():
        if key == "facets" and key in old:
            facets = copy.deepcopy(old[key])
            for facet, proposed in value.items():
                if facet in facets and facets[facet] != proposed:
                    if on_conflict == "error":
                        raise CatalogError(
                            f"conflicting facets.{facet} for {incoming['current_path']}"
                        )
                    if on_conflict == "record":
                        conflict = {
                            "field": f"facets.{facet}",
                            "retained": facets[facet],
                            "proposed": proposed,
                            "inspections": incoming["inspections"],
                        }
                        if conflict not in conflicts:
                            conflicts.append(copy.deepcopy(conflict))
                        continue
                facets[facet] = copy.deepcopy(proposed)
            merged[key] = facets
            continue
        if (
            key in old
            and old[key] != value
            and key not in (*list_fields, "identity", "annotation_conflicts")
        ):
            if on_conflict == "error":
                raise CatalogError(f"conflicting {key} for {incoming['current_path']}")
            if on_conflict == "record":
                conflict = {
                    "field": key,
                    "retained": old[key],
                    "proposed": value,
                    "inspections": incoming["inspections"],
                }
                if conflict not in conflicts:
                    conflicts.append(copy.deepcopy(conflict))
                continue
        if key != "annotation_conflicts":
            merged[key] = copy.deepcopy(value)
    if conflicts:
        merged["annotation_conflicts"] = conflicts
    merged["identity"] = identity_fields
    for key in list_fields:
        values = []
        seen = set()
        for value in [*old.get(key, []), *incoming.get(key, [])]:
            marker = json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            if marker not in seen:
                values.append(copy.deepcopy(value))
                seen.add(marker)
        if values or key in old or key in incoming:
            merged[key] = values
    return merged


def write_catalog(path: Path, catalog: dict[str, Any]) -> None:
    catalog["updated_at"] = now()
    text = json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_publish(path, text.encode("utf-8"), fsync=True, mode=0o600)


def locked(path: Path):
    lock = path.with_name(path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    f = lock.open("a+")
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    return f


def cmd_import(args: argparse.Namespace) -> int:
    path = Path(args.catalog)
    rows = [
        row
        for source in args.observations
        for row in observation_list(read_json(Path(source)))
    ]
    with locked(path):
        if entry_exists(path):
            # Existing unrelated paths may be temporarily absent while a
            # batch of external renames is being repaired.
            catalog = load_catalog(path, paths=False)
        else:
            catalog = {
                "schema_version": SCHEMA_VERSION,
                "updated_at": now(),
                "assets": [],
            }
        additions = [observation_asset(row) for row in rows]
        assets = catalog["assets"]
        by_id = {x["id"]: i for i, x in enumerate(assets)}
        by_path = {x["current_path"]: i for i, x in enumerate(assets)}
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        for row, item in zip(rows, additions, strict=True):
            if item["id"] in seen_ids:
                raise CatalogError(f"duplicate asset id in observations: {item['id']}")
            if item["current_path"] in seen_paths:
                raise CatalogError(
                    f"duplicate current_path in observations: {item['current_path']}"
                )
            seen_ids.add(item["id"])
            seen_paths.add(item["current_path"])
            index = by_id.get(item["id"], by_path.get(item["current_path"]))
            old = assets[index] if index is not None else None
            if (
                old is not None
                and old["current_path"] == item["current_path"]
                and "id" not in row
            ):
                item["id"] = old["id"]
            if (
                old is not None
                and old["id"] == item["id"]
                and old["current_path"] != item["current_path"]
            ):
                raise CatalogError(f"asset path changed; use relocate for {item['id']}")
            if (
                old is not None
                and old["current_path"] == item["current_path"]
                and "id" in row
                and row["id"] != old["id"]
            ):
                raise CatalogError(f"current_path already belongs to asset {old['id']}")
            if old is None:
                index = len(assets)
                assets.append(item)
            else:
                assets[index] = merge_asset(old, item, on_conflict=args.on_conflict)
            by_id[item["id"]] = index
            by_path[item["current_path"]] = index
        validate_catalog(catalog, check_paths=False)
        write_catalog(path, catalog)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    if args.offset < 0 or (args.limit is not None and args.limit < 0):
        raise CatalogError("search offset and limit must be nonnegative")
    catalog = load_catalog(Path(args.catalog), paths=False)
    needle = args.text.casefold()
    matched = 0
    emitted = 0
    for asset in catalog["assets"]:
        if args.kind and asset["kind"] != args.kind:
            continue
        hay = json.dumps(asset, ensure_ascii=False).casefold()
        if needle in hay:
            matched += 1
            if matched <= args.offset:
                continue
            if args.limit is not None and emitted >= args.limit:
                break
            print(json.dumps(asset, ensure_ascii=sys.stdout.isatty(), sort_keys=True))
            emitted += 1
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog), paths=False)
    assets = catalog["assets"]
    selected = [a for a in assets if not args.kind or a["kind"] == args.kind]
    result = {
        "schema": "sinnix.file-catalog-coverage.v1",
        "catalog_updated_at": catalog["updated_at"],
        "asset_count": len(selected),
        "kinds": dict(Counter(a["kind"] for a in selected)),
        "inspection_status": dict(
            Counter(a.get("coverage", {}).get("status", "unrecorded") for a in selected)
        ),
        "organization_actions": dict(
            Counter(
                a.get("organization", {}).get("action", "unrecorded") for a in selected
            )
        ),
        "assets_with_conflicts": sum(
            bool(a.get("annotation_conflicts")) for a in selected
        ),
        "scope": "Catalog records only. Inherited taxonomy is not inspection; overlapping collection counts are not summed. No filesystem census denominator is implied.",
    }
    print(
        json.dumps(result, ensure_ascii=sys.stdout.isatty(), indent=2, sort_keys=True)
    )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog), paths=False)
    for asset in catalog["assets"]:
        if asset["id"] == args.id:
            print(
                json.dumps(
                    asset, ensure_ascii=sys.stdout.isatty(), indent=2, sort_keys=True
                )
            )
            return 0
    return fail(f"asset id not found: {args.id}")


def cmd_relocate(args: argparse.Namespace) -> int:
    path, new_path = Path(args.catalog), Path(normalized(args.new_path))
    with locked(path):
        # Relocation is the one operation that intentionally starts with the
        # old current_path absent; validate every other catalog invariant first.
        catalog = load_catalog(path, paths=False)
        target = next((a for a in catalog["assets"] if a["id"] == args.id), None)
        if target is None:
            raise CatalogError(f"asset id not found: {args.id}")
        old_path = Path(target["current_path"])
        if entry_exists(old_path):
            raise CatalogError(
                f"old path still exists; perform the external rename first: {old_path}"
            )
        if any(
            a is not target and a["current_path"] == str(new_path)
            for a in catalog["assets"]
        ):
            raise CatalogError(f"new path already belongs to another asset: {new_path}")
        actual = identity(new_path)
        check_path_kind(new_path, target["kind"])
        known = location_identity(target)
        if not same_identity(known, actual, target["kind"]):
            raise CatalogError("new path identity does not match catalog")
        prior = copy.deepcopy(target["identity"])
        continuity = same_identity(prior, actual, target["kind"])
        target.setdefault("relocations", []).append(
            {
                "at": now(),
                "source": str(old_path),
                "destination": str(new_path),
                "recorded_location_identity": copy.deepcopy(known),
                "after": actual,
                "prior_catalog_identity": prior,
                "prior_identity_matches": continuity,
                "basis": "Destination matches last reviewed location metadata; payload hashes are not reverified.",
            }
        )
        target.setdefault("previous_paths", []).append(target["current_path"])
        target["current_path"] = str(new_path)
        extras = {k: v for k, v in prior.items() if k not in actual}
        target["identity"] = {**actual, **(extras if continuity else {})}
        record_relocated_location(target, str(old_path), actual)
        validate_catalog(catalog, check_paths=False)
        write_catalog(path, catalog)
    return 0


def cmd_prepare_relocation(args: argparse.Namespace) -> int:
    """Bind a metadata transaction to a catalog digest and pre-rename identities."""
    path = Path(args.catalog)
    with locked(path):
        raw = path.read_bytes()
        catalog = load_catalog(path, paths=False)
        moves = read_json(Path(args.moves))
        if not isinstance(moves, list) or not moves:
            raise CatalogError(
                "moves must be a nonempty list of source/destination objects"
            )
        for move in moves:
            normalized(move["source"])
            normalized(move["destination"])
            if move["source"] == move["destination"]:
                raise CatalogError("source and destination must differ")
        rows, unavailable = [], []
        paths = set()
        for asset in catalog["assets"]:
            old = asset["current_path"]
            destination = relocate_path(old, moves)
            if destination in paths:
                raise CatalogError(f"relocation would collide at {destination}")
            paths.add(destination)
            if destination == old:
                continue
            source = Path(old)
            if not entry_exists(source) and args.retain_unavailable:
                unavailable.append(
                    {
                        "id": asset["id"],
                        "source": old,
                        "destination": destination,
                        "reason": "Already unavailable before cutover; no physical continuity or new current location asserted.",
                    }
                )
                continue
            check_path_kind(source, asset["kind"])
            observed = identity(source)
            continuity = same_identity(asset["identity"], observed, asset["kind"])
            if (
                not same_identity(location_identity(asset), observed, asset["kind"])
                and not args.record_existing_drift
            ):
                raise CatalogError(
                    f"existing identity drift: {old}; audit and explicitly record it first"
                )
            rows.append(
                {
                    "id": asset["id"],
                    "source": old,
                    "destination": destination,
                    "before": observed,
                    "catalog_identity": asset["identity"],
                    "prior_identity_matches": continuity,
                    "source_reused_as_container": destination.startswith(
                        old.rstrip("/") + "/"
                    ),
                }
            )
        receipt = {
            "schema": "sinnix.catalog-relocation.v1",
            "prepared_at": now(),
            "catalog_sha256": hashlib.sha256(raw).hexdigest(),
            "moves": moves,
            "assets": rows,
            "unavailable": unavailable,
        }
        output = Path(args.output)
        if entry_exists(output):
            raise CatalogError(f"refusing to overwrite relocation receipt: {output}")
        atomic_publish(
            output,
            (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(),
            fsync=True,
            mode=0o600,
        )
    return 0


def cmd_relocate_batch(args: argparse.Namespace) -> int:
    """Publish all metadata changes once; a failed check leaves the catalog intact."""
    path = Path(args.catalog)
    receipt = read_json(Path(args.receipt))
    if receipt.get("schema") != "sinnix.catalog-relocation.v1":
        raise CatalogError("unsupported relocation receipt")
    with locked(path):
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["catalog_sha256"]:
            raise CatalogError(
                "stale catalog digest; prepare a new receipt before renaming"
            )
        catalog = load_catalog(path, paths=False)
        by_id = {asset["id"]: asset for asset in catalog["assets"]}
        expected = {
            asset["id"]
            for asset in catalog["assets"]
            if relocate_path(asset["current_path"], receipt["moves"])
            != asset["current_path"]
        }
        rows = receipt["assets"]
        unavailable = receipt.get("unavailable", [])
        combined = [*rows, *unavailable]
        if (
            len(combined) != len({row["id"] for row in combined})
            or {row["id"] for row in combined} != expected
        ):
            raise CatalogError("receipt must include every affected asset exactly once")
        for row in unavailable:
            asset = by_id[row["id"]]
            if asset["current_path"] != row["source"]:
                raise CatalogError("stale unavailable-asset exception")
            if entry_exists(Path(row["source"])) or entry_exists(
                Path(row["destination"])
            ):
                raise CatalogError(
                    "unavailable-asset exception now has a live candidate; inspect its identity"
                )
            record_location(
                asset,
                {
                    "observed_at": now(),
                    **row,
                    "path": row["source"],
                    "status": "unavailable",
                    "actor": "sinnix-file-catalog",
                    "action": "unavailable",
                    "basis": "Prepared relocation exception; source and destination remain unavailable.",
                    "content_continuity": "unverified",
                },
            )
        for row in rows:
            asset = by_id[row["id"]]
            old, destination = normalized(row["source"]), normalized(row["destination"])
            if (
                asset["current_path"] != old
                or asset["identity"] != row["catalog_identity"]
            ):
                raise CatalogError(f"stale receipt for {row['id']}")
            if relocate_path(old, receipt["moves"]) != destination:
                raise CatalogError(
                    f"receipt destination disagrees with moves: {destination}"
                )
            if entry_exists(Path(old)):
                source = Path(old)
                reused = (
                    row.get("source_reused_as_container")
                    and destination.startswith(old.rstrip("/") + "/")
                    and source.is_dir()
                    and not source.is_symlink()
                    and not same_identity(row["before"], identity(source), "collection")
                )
                if not reused:
                    raise CatalogError(f"old address still exists: {old}")
            current = Path(destination)
            check_path_kind(current, asset["kind"])
            actual = identity(current)
            if not same_identity(row["before"], actual, asset["kind"]):
                raise CatalogError(f"pre/post rename identity mismatch: {destination}")
            asset.setdefault("previous_paths", []).append(old)
            asset.setdefault("relocations", []).append(
                {
                    "at": now(),
                    "source": old,
                    "destination": destination,
                    "before": row["before"],
                    "after": actual,
                    "prior_catalog_identity": row["catalog_identity"],
                    "prior_identity_matches": row["prior_identity_matches"],
                    "basis": "Same object verified immediately before and after external rename; older observation retained without a continuity claim when mismatched.",
                }
            )
            asset["current_path"] = destination
            # Hashes are attributed observations, never silently certified for a
            # changed object. Keep them in prior_catalog_identity in that case.
            extras = {
                key: value
                for key, value in asset["identity"].items()
                if key not in actual
            }
            asset["identity"] = {
                **actual,
                **(extras if row["prior_identity_matches"] else {}),
            }
            record_relocated_location(asset, old, actual)
        validate_catalog(catalog, check_paths=False)
        write_catalog(path, catalog)
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog), paths=False)
    path = str(resolve_historical_path(catalog, args.path, asset_id=args.id))
    print(json.dumps(path, ensure_ascii=True) if sys.stdout.isatty() else path)
    return 0


def location_diagnosis(path: Path, kind: str) -> dict:
    external = next(
        (
            root
            for root in (Path("/outer-realm"), Path("/neo-outer-realm"), Path("/mnt"))
            if path.is_relative_to(root)
        ),
        None,
    )
    if external is not None:
        try:
            mounted = read_mountpoints()
        except (OSError, ValueError) as exc:
            return {
                "status": "inaccessible",
                "reason": f"cannot observe external mounts: {exc}",
            }
        if not has_mounted_ancestor(path, external, mounted):
            return {"status": "offline_mount", "reason": str(external)}
    try:
        info = path.stat()
        if not (
            stat.S_ISDIR(info.st_mode)
            if kind == "collection"
            else stat.S_ISREG(info.st_mode)
        ):
            return {"status": "wrong_type", "reason": "configured object type differs"}
        return {"status": "available", "identity": identity(path)}
    except CatalogError as exc:
        cause = exc.__cause__
        if not isinstance(cause, OSError):
            raise
        status = (
            "denied"
            if isinstance(cause, PermissionError)
            else "missing"
            if isinstance(cause, FileNotFoundError)
            else "inaccessible"
        )
        return {"status": status, "reason": str(cause)}
    except PermissionError as exc:
        return {"status": "denied", "reason": str(exc)}
    except FileNotFoundError as exc:
        return {"status": "missing", "reason": str(exc)}
    except OSError as exc:
        return {"status": "inaccessible", "reason": str(exc)}


def recover_copy(asset: dict[str, Any], row: dict[str, Any], assets: dict) -> None:
    """Recover an unavailable inspected file, not a guessed replacement."""
    prior = copy.deepcopy(asset["identity"])
    digest = prior.get("sha256")
    limit = 8 * 1024 * 1024
    if (
        asset["kind"] != "file"
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
        or prior.get("fingerprint_kind", "sha256-full") != "sha256-full"
        or not isinstance(prior.get("size"), int)
        or not 0 <= prior["size"] <= limit
    ):
        raise CatalogError(
            "recovery requires a recorded full SHA-256 for a regular file up to 8 MiB"
        )
    old = Path(asset["current_path"])
    if old.is_symlink() or location_diagnosis(old, "file")["status"] != "missing":
        raise CatalogError("recovery requires the original location to be missing")
    destination = Path(normalized(row["new_path"]))
    if any(
        a is not asset and a["current_path"] == str(destination)
        for a in assets.values()
    ):
        raise CatalogError("recovery destination already belongs to another asset")
    diagnosis = location_diagnosis(destination, "file")
    if diagnosis["status"] != "available" or diagnosis["identity"] != row.get(
        "expected_identity"
    ):
        raise CatalogError("recovery source metadata differs from reviewed observation")
    with os.fdopen(
        os.open(destination, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb"
    ) as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise CatalogError("recovery requires a bounded regular file")
        for key, attr in [
            ("device", "st_dev"),
            ("inode", "st_ino"),
            ("size", "st_size"),
            ("mtime_ns", "st_mtime_ns"),
        ]:
            if getattr(before, attr) != diagnosis["identity"][key]:
                raise CatalogError("recovery source changed before hashing")
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")
    if (
        any(getattr(before, k) != getattr(after, k) for k in fields)
        or identity(destination) != diagnosis["identity"]
    ):
        raise CatalogError("recovery source changed while hashing")
    if len(raw) != prior["size"] or hashlib.sha256(raw).hexdigest() != digest:
        raise CatalogError("recovered bytes differ from recorded full SHA-256")
    if str(old) not in asset.setdefault("previous_paths", []):
        asset["previous_paths"].append(str(old))
    asset["current_path"] = str(destination)
    asset["identity"] = {**diagnosis["identity"], "sha256": digest}
    record_location(
        asset,
        {
            "observed_at": now(),
            "actor": row["actor"],
            "action": "recover_copy",
            "basis": row["basis"],
            "reason": row["reason"],
            "review_reason": row["reason"],
            "source": str(old),
            "path": str(destination),
            **diagnosis,
            "prior_catalog_identity": prior,
            "content_continuity": "verified_full_sha256",
            "sha256": digest,
        },
    )


def cmd_observe(args: argparse.Namespace) -> int:
    """Explicit reviewed metadata observations or revisions, never guessed continuity."""
    path = Path(args.catalog)
    rows = observation_list(read_json(Path(args.observations)))
    with locked(path):
        if hashlib.sha256(path.read_bytes()).hexdigest() != args.expected_sha256:
            raise CatalogError(
                "stale catalog digest; review current observations before mutation"
            )
        catalog = load_catalog(path, paths=False)
        assets = {a["id"]: a for a in catalog["assets"]}
        seen = set()
        for row in rows:
            if row.get("id") in seen:
                raise CatalogError("duplicate asset observation")
            seen.add(row.get("id"))
            asset = assets[row["id"]]
            action = row.get("action")
            if action not in (
                "metadata",
                "content_revision",
                "collection_replacement",
                "unavailable",
                "recover_copy",
            ):
                raise CatalogError("explicit observation action required")
            if not all(
                isinstance(row.get(k), str) and row[k].strip()
                for k in ("actor", "basis", "reason")
            ):
                raise CatalogError("actor, basis and reason required")
            if action == "recover_copy":
                recover_copy(asset, row, assets)
                continue
            diagnosis = location_diagnosis(Path(asset["current_path"]), asset["kind"])
            observation = {
                "observed_at": now(),
                "actor": row["actor"],
                "basis": row["basis"],
                "reason": row["reason"],
                "action": action,
                "path": asset["current_path"],
                **diagnosis,
                "review_reason": row["reason"],
                "content_continuity": "unverified",
            }
            if action == "unavailable":
                if diagnosis["status"] == "available":
                    raise CatalogError("unavailable observation has a live source")
                record_location(asset, observation)
                continue
            if diagnosis["status"] != "available":
                raise CatalogError("cannot observe an unavailable source as available")
            if row.get("expected_identity") != diagnosis["identity"]:
                raise CatalogError("source metadata differs from reviewed observation")
            if action != "metadata":
                if (action == "collection_replacement") != (
                    asset["kind"] == "collection"
                ):
                    raise CatalogError("revision action does not match asset type")
                previous_id = asset.get("revision_id", str(uuid.uuid4()))
                asset.setdefault("revisions", []).append(
                    {
                        "revision_id": previous_id,
                        "identity": copy.deepcopy(asset["identity"]),
                        "inspections": copy.deepcopy(asset["inspections"]),
                        "coverage": copy.deepcopy(asset.get("coverage")),
                        "retired_at": now(),
                        "description": asset["description"],
                        "content_evidence": {
                            key: copy.deepcopy(asset[key])
                            for key in (
                                "enrichment",
                                "visible_text",
                                "outline",
                                "claims",
                            )
                            if key in asset
                        },
                    }
                )
                for key in ("enrichment", "visible_text", "outline", "claims"):
                    asset.pop(key, None)
                asset["description"] = (
                    "Current revision has a location metadata observation. Earlier descriptions and content inspections remain in revision history."
                )
                asset["revision_id"] = str(uuid.uuid4())
                asset["identity"] = diagnosis["identity"]
                asset["inspections"] = [
                    {
                        "method": "metadata",
                        "scope": "current location metadata only",
                        "basis": row["basis"],
                    }
                ]
                asset["coverage"] = {
                    "status": "metadata_only",
                    "scope": "current revision; payload not inspected",
                    "unit": "object",
                    "discovered_count": None,
                    "inspected_count": 0,
                }
            record_location(asset, observation)
        validate_catalog(catalog, check_paths=False)
        write_catalog(path, catalog)
        committed_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({"observations": len(rows), "catalog_sha256": committed_sha256}))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Report every location mismatch without reading payloads or changing identity.

    Device-only drift is a diagnosis, never an identity-rebinding waiver.
    Collection membership is deliberately excluded from identity comparison.
    """
    catalog = load_catalog(Path(args.catalog), paths=False)
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for asset in catalog["assets"]:
        p = Path(asset["current_path"])
        row: dict[str, Any] = {"id": asset["id"], "path": str(p), "kind": asset["kind"]}
        diagnosis = location_diagnosis(p, asset["kind"])
        if diagnosis["status"] != "available":
            row.update(diagnosis)
        else:
            actual = diagnosis["identity"]
            recorded = location_identity(asset)
            # Device remains an observation in the audit even when a complete
            # stable identity permits it to drift during relocation verification.
            differences = identity_differences(
                recorded, actual, asset["kind"], include_device=True
            )
            row["status"] = (
                "match"
                if not differences
                else "device_only_mismatch"
                if list(differences) == ["device"]
                else "identity_mismatch"
            )
            row["content_continuity"] = asset.get("current_location", {}).get(
                "content_continuity", "not_reverified"
            )
            if differences:
                row["differences"] = differences
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        if row["status"] != "match" or args.all:
            rows.append(row)
    result = {
        "schema": "sinnix.file-catalog-audit.v1",
        "observed_at": now(),
        "catalog_updated_at": catalog.get("updated_at"),
        "asset_count": len(catalog["assets"]),
        "counts": counts,
        "scope": "Filesystem metadata only; no payload hash verification or identity rebinding.",
        "findings": rows,
    }
    print(
        json.dumps(result, ensure_ascii=sys.stdout.isatty(), indent=2, sort_keys=True)
    )
    return 0 if counts.get("match", 0) == len(catalog["assets"]) else 1


# ──────────────────────────────────────────────────────────────────────────
# report: render the catalog as a searchable offline page
# ──────────────────────────────────────────────────────────────────────────
STYLE = """
.catalog-controls{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}
.catalog-controls label{display:flex;flex-direction:column;gap:.25rem;max-width:100%}
.catalog-controls select{max-width:min(28rem,100%)}
.retrieval-aid{padding:.45rem .7rem;border-left:2px solid var(--line);margin:.6rem 0}
.catalog-controls input,.catalog-controls select{font:inherit;padding:.45rem;
 background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:.35rem}
.catalog-controls input{min-width:18rem;max-width:100%}
.asset{border-top:1px solid var(--line);padding:1.1rem 0;scroll-margin-top:5rem}
.asset:target{outline:2px solid var(--accent);outline-offset:.4rem}
.asset h3{margin:.1rem 0 .4rem}.asset p{margin:.45rem 0}
.asset .path,.asset code{overflow-wrap:anywhere;word-break:break-word}
.asset .tags{display:flex;gap:.3rem;flex-wrap:wrap;margin:.4rem 0}
.asset details{margin:.6rem 0}.asset .related{display:flex;gap:.45rem;flex-wrap:wrap}
.scope{color:var(--muted)}.catalog-controls[hidden],.asset[hidden]{display:none!important}
.catalog-count{font-variant-numeric:tabular-nums}.catalog-data{white-space:pre-wrap}
"""

SCRIPT = r"""
(()=>{
 if(location.protocol==='http:'||location.protocol==='https:'){
  document.querySelectorAll('a[href^="file:"]').forEach(link=>{
   const label=document.createElement('span');label.className=link.className;
   label.textContent=link.textContent+' (local path)';link.replaceWith(label);
  });
 }
 const rows=[...document.querySelectorAll('.asset')];
 const indexedRows=rows.map(row=>({row,text:row.textContent.toLocaleLowerCase(),methods:JSON.parse(row.dataset.methods)}));
 const q=document.getElementById('catalog-query');
 const method=document.getElementById('catalog-method');
 const kind=document.getElementById('catalog-kind');
 const docType=document.getElementById('catalog-document-type');
 const coverage=document.getElementById('catalog-coverage');
 const count=document.getElementById('catalog-count');
 let related=null;
 function filter(){
  const terms=q.value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  let visible=0;
  indexedRows.forEach(({row,text,methods})=>{
   const show=terms.every(term=>text.includes(term))&&(!method.value||methods.includes(method.value))
      &&(!kind.value||kind.value===row.dataset.kind)
      &&(!docType.value||docType.value===row.dataset.documentType)
      &&(!coverage.value||coverage.value===row.dataset.coverage)
      &&(!related||related.has(row.id));
   row.hidden=!show;if(show)visible++;
  });
  count.textContent=visible+' of '+rows.length+' records shown';
 }
 q.addEventListener('input',filter);method.addEventListener('change',filter);
 kind.addEventListener('change',filter);coverage.addEventListener('change',filter);docType.addEventListener('change',filter);
 document.getElementById('catalog-reset').addEventListener('click',()=>{
  q.value='';method.value='';kind.value='';coverage.value='';docType.value='';related=null;filter();
 });
 document.querySelectorAll('[data-related]').forEach(button=>button.addEventListener('click',()=>{
  related=new Set(JSON.parse(button.dataset.related));q.value='';method.value='';kind.value='';coverage.value='';docType.value='';filter();
  document.getElementById('catalog').scrollIntoView();
 }));
 function revealTarget(){
  if(location.hash.startsWith('#asset-')){
   q.value='';method.value='';kind.value='';coverage.value='';docType.value='';related=null;filter();
   const target=document.getElementById(location.hash.slice(1));
   if(target)target.scrollIntoView();
  }
 }
 addEventListener('hashchange',revealTarget);
 document.querySelector('.catalog-controls').hidden=false;
 filter();revealTarget();
})();
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def path_link(path: str) -> str:
    return f'<a class="path" href="{esc(Path(path).as_uri())}">{esc(path)}</a>'


def document_type(asset: dict) -> str:
    enrichment = asset.get("enrichment")
    value = enrichment.get("document_type") if isinstance(enrichment, dict) else None
    return value if isinstance(value, str) else ""


def render_enrichment(asset: dict, catalog: dict | None = None) -> str:
    """A readable projection of optional observations; raw fields stay intact.

    Annotation strings are text, never markup. A source locator is not treated
    as a URL or executed instruction. Rendering never stats or opens payloads.
    """
    enrichment = asset.get("enrichment")
    enrichment = enrichment if isinstance(enrichment, dict) else {}

    def strings(value):
        return (
            [x for x in value if isinstance(x, str) and x.strip()]
            if isinstance(value, list)
            else []
        )

    def text(value, missing):
        # A recorded value is shown as written; an absent or non-text one is
        # named as missing rather than invented.
        return value if isinstance(value, str) and value else missing

    parts = []
    labels = [
        ("Document type", document_type(asset)),
        ("Language", enrichment.get("language")),
    ]
    labels = [(k, v) for k, v in labels if isinstance(v, str) and v]
    if labels:
        parts.append(
            '<dl class="meta">'
            + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in labels)
            + "</dl>"
        )
    summary = enrichment.get("summary")
    if isinstance(summary, str) and summary and summary != asset.get("description"):
        parts.append(f"<p><strong>Catalog summary:</strong> {esc(summary)}</p>")
    topics = strings(enrichment.get("topics"))
    if topics:
        parts.append(
            "<p><strong>Topics:</strong> " + "; ".join(map(esc, topics)) + "</p>"
        )
    questions = list(
        dict.fromkeys(
            strings(asset.get("utility")) + strings(enrichment.get("questions"))
        )
    )
    if questions:
        parts.append(
            '<div class="retrieval-aid"><strong>Useful for finding</strong><ul>'
            + "".join(f"<li>{esc(question)}</li>" for question in questions)
            + "</ul></div>"
        )
    claims = enrichment.get("claims")
    claims = (
        [c for c in claims if isinstance(c, dict) and isinstance(c.get("claim"), str)]
        if isinstance(claims, list)
        else []
    )
    if claims:
        parts.append("<details><summary>Recorded claims and source locators</summary>")
        parts.append(
            '<p class="scope">Statuses and locators belong to the recorded inspection; this view does not independently verify the claims.</p><ul>'
        )
        for claim in claims:
            status = text(claim.get("status"), "status not recorded")
            locator = text(claim.get("source_locator"), "locator not recorded")
            parts.append(
                f'<li><span class="chip">{esc(status)}</span> {esc(claim["claim"])}'
                f"<br><code>{esc(locator)}</code></li>"
            )
        parts.append("</ul></details>")
    outline = enrichment.get("outline")
    outline = (
        [
            x
            for x in outline
            if isinstance(x, dict) and isinstance(x.get("heading"), str)
        ]
        if isinstance(outline, list)
        else []
    )
    if outline:
        parts.append("<details><summary>Inspected document outline</summary><ul>")
        parts.extend(
            f'<li>{esc(item["heading"])} <span class="scope">{esc(text(item.get("source_locator"), ""))}</span></li>'
            for item in outline
        )
        parts.append("</ul></details>")
    extraction = enrichment.get("extraction")
    if isinstance(extraction, dict):
        parts.append("<details><summary>Extraction evidence and limits</summary>")
        path = extraction.get("path")
        if (
            isinstance(path, str)
            and path.startswith("/")
            and not path.startswith("//")
            and not any(ord(c) < 32 for c in path)
        ):
            historical = catalog is not None and any(
                path == address
                or (
                    owner["kind"] == "collection"
                    and path.startswith(address.rstrip("/") + "/")
                )
                for owner in catalog["assets"]
                for address in owner.get("previous_paths", [])
            )
            if historical:
                parts.append(
                    f"<p>Recorded evidence locator: <code>{esc(path)}</code></p>"
                )
                try:
                    current = resolve_historical_path(catalog, path)
                except ValueError as error:
                    parts.append(f"<p>Evidence unavailable: {esc(error)}</p>")
                else:
                    parts.append("<p>Evidence: " + path_link(current) + "</p>")
            else:
                parts.append("<p>Evidence: " + path_link(path) + "</p>")
        elif path is not None:
            parts.append(f"<p>Evidence locator: <code>{esc(path)}</code></p>")
        for key, label in (
            ("source_sha256", "Inspected source SHA-256"),
            ("recipe", "Inspection recipe"),
        ):
            if isinstance(extraction.get(key), str):
                parts.append(f"<p><strong>{label}:</strong> {esc(extraction[key])}</p>")
        if "truncated" in extraction:
            value = extraction["truncated"]
            scope = (
                "yes"
                if value is True
                else "no (does not imply full review)"
                if value is False
                else "not established"
            )
            parts.append(f"<p>Selection/truncation recorded: {scope}.</p>")
        limitations = strings(enrichment.get("limitations"))
        if limitations:
            parts.append(
                "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in limitations) + "</ul>"
            )
        parts.append("</details>")
    elif strings(enrichment.get("limitations")):
        parts.append(
            "<details><summary>Enrichment limitations</summary><ul>"
            + "".join(f"<li>{esc(x)}</li>" for x in strings(enrichment["limitations"]))
            + "</ul></details>"
        )
    return "\n".join(parts)


def render_asset(
    asset: dict, by_id: dict, judgments: dict | None = None, catalog: dict | None = None
) -> str:
    asset_id = asset["id"]
    inspections = asset["inspections"]
    methods = sorted({item["method"] for item in inspections})
    tags = "".join(
        f'<span class="chip">{esc(tag)}</span>' for tag in asset.get("tags", [])
    )
    unavailable = asset.get("location_status") in {
        "unavailable",
        "missing",
        "offline_mount",
        "denied",
        "inaccessible",
        "wrong_type",
    }
    current_path = (
        f'<span class="path">{esc(asset["current_path"])}</span>'
        if unavailable
        else path_link(asset["current_path"])
    )
    parts = [
        f'<article class="asset" id="asset-{esc(asset_id)}" data-kind="{esc(asset["kind"])}" '
        f'data-coverage="{esc(asset.get("coverage", {}).get("status", "unrecorded"))}" '
        f'data-document-type="{esc(document_type(asset))}" data-methods="{esc(json.dumps(methods))}">',
        f"<h3>{esc(asset['title'])}</h3>",
        f"<p>{esc(asset['description'])}</p>",
        f'<p>{current_path}</p><div class="tags">{tags}</div>',
    ]
    if unavailable:
        parts.append(
            "<p><strong>Location unavailable.</strong> The retained address is historical; no new physical identity is asserted.</p>"
        )
    location = asset.get("current_location")
    if location:
        parts.append(
            f"<p>Latest location observation: {esc(location['observed_at'])}. Content continuity: {esc(location['content_continuity'])}.</p>"
        )
        review = location.get("review_reason") or location.get("reason", "")
        parts.append(
            f"<p>Review: {esc(review)}. Basis: {esc(location.get('basis', ''))}.</p>"
        )
        if location.get("reason") and location["reason"] != review:
            parts.append(f"<p>Location diagnosis: {esc(location['reason'])}</p>")
    for revision in asset.get("revisions", []):
        parts.append(
            f"<details><summary>Earlier revision {esc(revision['revision_id'])}</summary>"
        )
        parts.append(f"<p>{esc(revision.get('description', ''))}</p>")
        for inspection in revision["inspections"]:
            parts.append(
                f"<p>{esc(inspection['method'])}: {esc(inspection['scope'])}. {esc(inspection['basis'])}</p>"
            )
        parts.append("</details>")
    if judgments is not None:
        from sinnix_lib.judgments import resolve_judgments

        current = resolve_judgments(judgments, asset["current_path"])
        parts.append(
            "<p><strong>Current classification</strong> · ledger precedence and explicit uncertainty</p>"
        )
        parts.append(
            '<dl class="meta">'
            + "".join(
                f"<dt>{esc(key.replace('_', ' '))}</dt><dd>{esc(value.get('value') if value['status'] == 'known' else value['status'])}"
                f"{(' · ' + esc('; '.join(value['details']))) if value.get('details') else ''}</dd>"
                for key, value in current.items()
            )
            + "</dl>"
        )
    if asset.get("facets"):
        parts.append(
            '<p><strong>Recorded observations</strong> · original wording retained</p><dl class="meta">'
            + "".join(
                f"<dt>{esc(key.replace('_', ' '))}</dt><dd>{esc(value)}</dd>"
                for key, value in asset["facets"].items()
            )
            + "</dl>"
        )
    if asset.get("coverage"):
        coverage = asset["coverage"]
        denominator = coverage.get("discovered_count")
        count = f"{coverage['inspected_count']} / {denominator if denominator is not None else 'unknown'} {coverage['unit']}"
        parts.append(
            f"<p><strong>Inspection: {esc(coverage['status'])}</strong> · {esc(count)}. {esc(coverage['scope'])}</p>"
        )
    parts.append(render_enrichment(asset, catalog))
    if asset.get("organization"):
        organization = asset["organization"]
        parts.append(
            f"<p><strong>Organization proposal: {esc(organization['action'])}</strong>. {esc(organization['rationale'])}</p>"
        )
        if organization.get("proposed_path"):
            parts.append(
                f"<p>Proposed location: <code>{esc(organization['proposed_path'])}</code></p>"
            )
    if asset.get("annotation_conflicts"):
        parts.append(
            "<p><strong>Competing annotations retained.</strong> See the evidence details for proposed values.</p>"
        )
    for relation in asset.get("related_paths", []):
        parts.append(
            f"<p><strong>{esc(relation['type'])}</strong>: {path_link(relation['path'])}. {esc(relation['basis'])}</p>"
        )
    for inspection in inspections:
        parts.append(
            f'<p class="scope"><strong>{esc(inspection["method"])}</strong>: '
            f"{esc(inspection['scope'])}</p>"
        )
    if asset.get("uncertainties"):
        parts.append("<details><summary>Uncertainty and limits</summary><ul>")
        parts.extend(f"<li>{esc(note)}</li>" for note in asset["uncertainties"])
        parts.append("</ul></details>")
    if asset.get("visible_text"):
        parts.append("<details><summary>Selected visible text</summary><ul>")
        parts.extend(f"<li>{esc(text)}</li>" for text in asset["visible_text"])
        parts.append("</ul></details>")
    related_ids = {"asset-" + asset_id}
    for relation in asset.get("relations", []):
        target = by_id[relation["target_id"]]
        related_ids.add("asset-" + target["id"])
        parts.append(
            f"<p><strong>{esc(relation['type'].replace('_', ' '))}</strong>: "
            f'<a href="#asset-{esc(target["id"])}">{esc(target["title"])}</a>. '
            f'<span class="scope">{esc(relation["basis"])}</span></p>'
        )
    if len(related_ids) > 1:
        parts.append(
            f'<button class="fs" data-related="{esc(json.dumps(sorted(related_ids)))}">'
            "Show this record and related files</button>"
        )
    details = {
        "id": asset_id,
        "kind": asset["kind"],
        "previous_paths": asset.get("previous_paths", []),
        "identity": asset.get("identity", {}),
        "inspections": inspections,
    }
    for key, value in asset.items():
        if key not in {"title", "description", "tags", "relations", *details}:
            details[key] = value
    parts.append(
        "<details><summary>Identity, path history and inspection evidence</summary>"
    )
    parts.append(
        f'<pre class="catalog-data">{esc(json.dumps(details, ensure_ascii=False, indent=2))}</pre>'
    )
    parts.append("</details></article>")
    return "\n".join(parts)


def render(
    catalog: dict,
    source: Path,
    template: str,
    command: str,
    judgments: dict | None = None,
) -> str:
    if catalog.get("schema_version") != 1 or not isinstance(
        catalog.get("assets"), list
    ):
        raise ValueError("expected schema_version 1 catalog with assets")
    assets = catalog["assets"]
    collections = sum(asset.get("kind") == "collection" for asset in assets)
    coverage_states = sorted(
        {asset.get("coverage", {}).get("status", "unrecorded") for asset in assets}
    )
    coverage_options = "".join(
        f'<option value="{esc(value)}">{esc(value)}</option>'
        for value in coverage_states
    )
    by_id = {asset["id"]: asset for asset in assets}
    if len(by_id) != len(assets):
        raise ValueError("duplicate asset IDs")
    for asset in assets:
        for relation in asset.get("relations", []):
            if relation["target_id"] not in by_id:
                raise ValueError("dangling relation target")
    if "<body>" not in template or "<script>" not in template:
        raise ValueError("template needs body and inline script blocks")
    preamble = template.split("<body>", 1)[0]
    preamble = re.sub(
        r"<title>.*?</title>",
        "<title>File inspection catalog</title>",
        preamble,
        flags=re.S,
    )
    preamble = re.sub(
        r'data-accent="[^"]*"', 'data-accent="archive"', preamble, count=1
    )
    preamble = preamble.replace("</head>", f"<style>{STYLE}</style>\n</head>")
    common_script = template.split("<script>", 1)[1].rsplit("</script>", 1)[0]
    generated = _dt.datetime.now(_dt.timezone.utc).isoformat()
    methods = sorted(
        {item["method"] for asset in assets for item in asset["inspections"]}
    )
    type_options = '<option value="">All document types</option>' + "".join(
        f'<option value="{esc(value)}">{esc(value)}</option>'
        for value in sorted({document_type(asset) for asset in assets} - {""})
    )
    options = "".join(
        f'<option value="{esc(method)}">{esc(method)}</option>' for method in methods
    )
    relationship_rows = []
    for asset in assets:
        for relation in asset.get("relations", []):
            target = by_id[relation["target_id"]]
            relationship_rows.append(
                f'<tr><td><a href="#asset-{esc(asset["id"])}">{esc(asset["title"])}</a></td>'
                f"<td>{esc(relation['type'].replace('_', ' '))}</td>"
                f'<td><a href="#asset-{esc(target["id"])}">{esc(target["title"])}</a></td>'
                f"<td>{esc(relation['basis'])}</td></tr>"
            )
    cards = "\n".join(
        render_asset(asset, by_id, judgments, catalog)
        for asset in sorted(assets, key=lambda a: a["title"].casefold())
    )
    # The canonical data is embedded losslessly, but cannot terminate its script element.
    data = (
        json.dumps(catalog, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace("&", "\\u0026")
    )
    return f'''{preamble}
<body>
<header class="page"><h1>File inspection catalog</h1><span class="chip">private · portable</span>
<span class="spacer"></span><button class="fs" onclick="fs(-1)">A−</button>
<button class="fs" onclick="fs(1)">A+</button><button class="theme" onclick="tgl()">◐ theme</button></header>
<div class="layout"><nav id="toc" aria-label="contents"></nav><main>
<section id="about"><h2>Knowledge retained from inspections</h2>
<p>Descriptions, original paths and relationships stay attached to stable asset IDs. Descriptions are authored observations;
each record states the inspected surface and its limits. A title-page or filename inspection does not imply a full-content review.</p>
<dl class="meta"><dt>generated</dt><dd><time class="age" datetime="{esc(generated)}">{esc(generated)}</time></dd>
<dt>catalog updated</dt><dd>{esc(catalog["updated_at"])}</dd><dt>inspection dates</dt><dd>Recorded individually below</dd>
<dt>canonical source</dt><dd>{path_link(str(source))}</dd><dt>basis</dt><dd>Authored observations and attributed source metadata; counts derived from catalog records</dd></dl>
<div class="tiles"><div class="tile"><span class="n">{len(assets)}</span><span class="l">catalog records</span></div>
<div class="tile"><span class="n">{collections}</span><span class="l">collections described</span></div>
<div class="tile"><span class="n">{len(relationship_rows)}</span><span class="l">explicit relationships</span></div></div>
<p>Inspection counts describe each record's stated scope. Collections can overlap; their counts are not a filesystem-wide completion percentage. Organization proposals are not executed moves.</p>
</section>
<section id="catalog"><h2>Browse files and collections</h2>
<div class="catalog-controls" hidden><label>Search descriptions, tags and old names
<input id="catalog-query" type="search" placeholder="certificate, GPU, postcard…"></label>
<label>Inspection method<select id="catalog-method"><option value="">All methods</option>{options}</select></label>
<label>Record kind<select id="catalog-kind"><option value="">Files and collections</option><option value="collection">Collections</option><option value="file">Files</option></select></label>
<label>Document type<select id="catalog-document-type">{type_options}</select></label>
<label>Inspection coverage<select id="catalog-coverage"><option value="">All coverage</option>{coverage_options}</select></label>
<button class="fs" id="catalog-reset">Reset filters</button></div>
<p id="catalog-count" class="catalog-count" aria-live="polite">{len(assets)} records shown</p>
{cards}</section>
<section id="relationships"><h2>Relationships and their evidence</h2>
<p>These links are explicit assertions with a stated basis. They do not identify unknown people or imply causal relationships.</p>
<div class="tablewrap"><table><thead><tr><th>From</th><th>Relationship</th><th>To</th><th>Basis</th></tr></thead>
<tbody>{"".join(relationship_rows)}</tbody></table></div></section>
<section id="maintenance"><h2>Updating this view</h2>
<p>Edit observations through the catalog tool, retain prior inspections and path history, then regenerate this view.
The page does not edit source files or send annotations anywhere. Original-file links require local access.</p>
<pre class="catalog-data">{esc(command)}</pre></section>
</main></div>
<script type="application/json" id="catalog-source">{data}</script>
<script>{common_script}</script>
<script>{SCRIPT}</script>
</body></html>'''


def cmd_report(args: argparse.Namespace) -> int:
    """Render authored catalog observations without reading the described payloads."""
    source = Path(args.catalog).resolve()
    catalog = json.loads(read_regular_text(source))
    command_args = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--catalog",
        str(source),
        "report",
        "--template",
        str(args.template.resolve()),
        "--output",
        str(args.output.resolve()),
    ]
    judgments = None
    if args.judgments is not None:
        from sinnix_lib.judgments import read_judgments

        judgments = read_judgments(args.judgments)
        command_args.extend(["--judgments", str(args.judgments.resolve())])
    command = shlex.join(command_args)
    output = render(
        catalog, source, read_regular_text(args.template), command, judgments
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_publish(args.output, output.encode("utf-8"), fsync=True, mode=0o600)
    print(args.output)
    return 0


# ──────────────────────────────────────────────────────────────────────────
# links: read-only local link audit of explicitly selected index documents;
# native packages and historical reports are not scanned
# ──────────────────────────────────────────────────────────────────────────
# Escape and literal alternatives are disjoint; possessive repetitions prevent
# a missing closing parenthesis from repartitioning the destination exponentially.
INLINE = re.compile(
    r"!?\[(?:\\[^\n]|[^\[\]\\\n])*\]\(\s*(<[^<>\n]+>|(?:\\.|[^\s()\\])++(?:\([^()]*\)(?:\\.|[^\s()\\])*+)*+)[^\n)]*\)"
)
REFERENCE = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)", re.M)
# Preserve ordinary backslashes, but decode supported destination escapes
# before URI delimiters are interpreted. Keep the existing escaped-space form.
DESTINATION_ESCAPE = re.compile(r"\\([" + re.escape(string.punctuation + " ") + r"])")


def _unwrap_destination(target: str) -> str:
    return target[1:-1] if target.startswith("<") and target.endswith(">") else target


def link_targets(text: str):
    # Whitespace after the opener may span lines. Once consumed, inline links
    # stay on one line, so incomplete lines cannot repeatedly scan their suffix.
    inline_text = re.sub(r"(\]\()\s+", r"\1", text)
    for line in inline_text.split("\n"):
        if ")" in line:
            for match in INLINE.finditer(line):
                yield _unwrap_destination(match.group(1))
    for match in REFERENCE.finditer(text):
        yield _unwrap_destination(match.group(1))


FAILURES = {
    "invalid-link",
    "missing",
    "denied",
    "inaccessible",
    "invalid-document",
    "wrong-type-document",
    "missing-document",
    "denied-document",
    "inaccessible-document",
}


def access_error(exc: Exception) -> str:
    if isinstance(exc, PermissionError):
        return "denied"
    if isinstance(exc, FileNotFoundError):
        return "missing"
    return "inaccessible"


def audit(manifest: dict) -> dict:
    if manifest.get("schema_version") != 1 or not isinstance(
        manifest.get("documents"), list
    ):
        raise ValueError("expected navigation audit manifest version 1 with documents")
    external = [Path(root) for root in manifest.get("external_roots", [])]
    if any(not root.is_absolute() for root in external):
        raise ValueError("external roots must be absolute")
    mount_error = None
    try:
        mounted = read_mountpoints()
    except (OSError, ValueError) as exc:
        mounted = frozenset()
        mount_error = f"cannot observe external mounts: {exc}"
    rows = []
    for name in manifest["documents"]:
        if not isinstance(name, str) or "\0" in name:
            rows.append({"document": name, "status": "invalid-document"})
            continue
        document = Path(name)
        if not document.is_absolute():
            rows.append({"document": str(document), "status": "invalid-document"})
            continue
        # Mount policy uses a lexical path; stat/read keep filesystem traversal.
        mount_document = Path(os.path.abspath(document))
        if mount_error is not None and any(
            mount_document.is_relative_to(root) for root in external
        ):
            rows.append(
                {
                    "document": str(document),
                    "status": "inaccessible-document",
                    "reason": mount_error,
                }
            )
            continue
        if any(
            mount_document.is_relative_to(root)
            and not has_mounted_ancestor(mount_document, root, mounted)
            for root in external
        ):
            rows.append({"document": str(document), "status": "external-unprobed"})
            continue
        try:
            if not stat.S_ISREG(document.stat().st_mode):
                rows.append(
                    {"document": str(document), "status": "wrong-type-document"}
                )
                continue
            text = prose_mask(read_regular_text(document))
        except NotRegularFile as exc:
            rows.append(
                {
                    "document": str(document),
                    "status": "wrong-type-document",
                    "reason": str(exc),
                }
            )
            continue
        except (OSError, UnicodeError) as exc:
            rows.append(
                {
                    "document": str(document),
                    "status": access_error(exc) + "-document",
                    "reason": str(exc),
                }
            )
            continue
        except ValueError as exc:
            rows.append(
                {
                    "document": str(document),
                    "status": "wrong-type-document",
                    "reason": str(exc),
                }
            )
            continue
        for target in link_targets(text):
            try:
                parsed = urlsplit(DESTINATION_ESCAPE.sub(r"\1", target))
            except ValueError as exc:
                rows.append(
                    {
                        "document": str(document),
                        "target": target,
                        "status": "invalid-link",
                        "reason": str(exc),
                    }
                )
                continue
            if parsed.scheme and parsed.scheme != "file":
                continue
            if parsed.netloc and parsed.netloc != "localhost":
                continue
            if not parsed.path:
                continue
            try:
                decoded = unquote(parsed.path, errors="strict")
            except UnicodeError as exc:
                rows.append(
                    {
                        "document": str(document),
                        "target": target,
                        "status": "invalid-link",
                        "reason": str(exc),
                    }
                )
                continue
            if "\0" in decoded:
                rows.append(
                    {
                        "document": str(document),
                        "target": target,
                        "status": "invalid-link",
                        "reason": "local path contains a null character",
                    }
                )
                continue
            destination = Path(decoded)
            if not destination.is_absolute():
                destination = document.parent / destination
            mount_destination = Path(os.path.abspath(destination))
            offline = any(
                mount_destination.is_relative_to(root)
                and not has_mounted_ancestor(mount_destination, root, mounted)
                for root in external
            )
            row = {
                "document": str(document),
                "target": target,
                "destination": str(destination),
                "status": "external-unprobed",
            }
            if mount_error is not None and any(
                mount_destination.is_relative_to(root) for root in external
            ):
                row.update(status="inaccessible", reason=mount_error)
            elif not offline:
                try:
                    destination.stat()
                    row["status"] = "ok"
                except OSError as exc:
                    row.update(status=access_error(exc), reason=str(exc))
            rows.append(row)
    failed = sum(row["status"] in FAILURES for row in rows)
    return {
        "schema_version": 1,
        "documents": len(manifest["documents"]),
        "links": rows,
        "failures": failed,
    }


def cmd_links(args: argparse.Namespace) -> int:
    result = audit(json.loads(read_regular_text(args.manifest)))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for row in result["links"]:
            if row["status"] in FAILURES:
                print(f"{row['document']}: {row['status']}: {row.get('target', '')}")
        print(
            f"navigation-audit: {result['documents']} documents, {result['failures']} failures"
        )
    return 1 if result["failures"] else 0


# ──────────────────────────────────────────────────────────────────────────
# publish: stage a report site from a private allowlist, never directories.
# The output must not exist; the caller inspects and atomically publishes the
# staged directory. Nothing in the canonical source trees is changed.
# ──────────────────────────────────────────────────────────────────────────
def publication_path(url: str) -> PurePosixPath:
    """Map one relative URL to the filename served after URL decoding."""
    if (
        not isinstance(url, str)
        or not url
        or any(ord(c) < 32 for c in url)
        or re.search(r"%(?![0-9a-fA-F]{2})", url)
    ):
        raise ValueError(f"unsafe publication URL: {url!r}")
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or parsed.path != url:
        raise ValueError(f"unsafe publication URL: {url!r}")
    decoded = unquote(parsed.path, errors="strict")
    parts = PurePosixPath(decoded)
    if (
        parts.is_absolute()
        or str(parts) != decoded
        or any(part.startswith(".") for part in parts.parts)
        or "\\" in decoded
        or any(ord(c) < 32 for c in decoded)
    ):
        raise ValueError(f"unsafe publication URL: {url!r}")
    return parts


def build(manifest: dict, output: Path) -> None:
    if manifest.get("schema_version") != 1 or not isinstance(
        manifest.get("files"), list
    ):
        raise ValueError("publication manifest requires schema_version 1 and files")
    if output.exists() or output.is_symlink():
        raise ValueError(f"publication output already exists: {output}")
    private = [Path(root).resolve() for root in manifest.get("private_roots", [])]
    entries = []
    urls = set()
    for row in manifest["files"]:
        url, source = row["url"], Path(row["source"])
        parts = publication_path(url)
        serving_path = str(parts)
        if serving_path in urls:
            raise ValueError(f"duplicate publication URL: {url}")
        urls.add(serving_path)
        if not source.is_absolute() or not source.is_file():
            raise ValueError(
                f"publication source must be an existing absolute file: {source}"
            )
        resolved = source.resolve()
        if any(resolved.is_relative_to(root) for root in private):
            raise ValueError(
                f"publication source is inside a private source tree: {source}"
            )
        entries.append((parts, resolved))
    # Refuse file/directory URL collisions before creating anything.
    for url in urls:
        if any(
            str(parent) in urls
            for parent in PurePosixPath(url).parents
            if str(parent) != "."
        ):
            raise ValueError(f"file/directory publication collision: {url}")
    output.mkdir(parents=True, mode=0o755)
    for url, source in entries:
        link = output / str(url)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(source)


def cmd_publish(args: argparse.Namespace) -> int:
    raw = read_regular_bytes(args.publication, max_bytes=4 << 20)
    build(json.loads(raw), args.output)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnix fs catalog")
    parser.add_argument(
        "--catalog", help="catalog JSON path (every command but links and publish)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("import")
    p.add_argument("observations", nargs="+")
    p.add_argument(
        "--on-conflict",
        choices=("replace", "record", "error"),
        default="replace",
        help="How to handle competing annotations; record retains existing values and attributed proposals",
    )
    p.set_defaults(func=cmd_import)
    p = sub.add_parser("search")
    p.add_argument("text")
    p.add_argument("--kind", choices=("file", "collection"))
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_search)
    p = sub.add_parser(
        "coverage",
        help="Summarize explicit inspection coverage, without inherited completion claims",
    )
    p.add_argument("--kind", choices=("file", "collection"))
    p.set_defaults(func=cmd_coverage)
    p = sub.add_parser("show")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)
    p = sub.add_parser("relocate")
    p.add_argument("id")
    p.add_argument("new_path")
    p.set_defaults(func=cmd_relocate)
    p = sub.add_parser(
        "prepare-relocation",
        help="Capture bounded pre-rename identities and a catalog digest",
    )
    p.add_argument("moves")
    p.add_argument("--output", required=True)
    p.add_argument(
        "--record-existing-drift",
        action="store_true",
        help="Retain mismatched older identities as attributed history; certify only this rename",
    )
    p.add_argument(
        "--retain-unavailable",
        action="store_true",
        help="Keep already absent records as explicit unavailable history, without asserting a new identity",
    )
    p.set_defaults(func=cmd_prepare_relocation)
    p = sub.add_parser(
        "relocate-batch",
        help="Atomically publish a prepared metadata relocation after external renames",
    )
    p.add_argument("receipt")
    p.set_defaults(func=cmd_relocate_batch)
    p = sub.add_parser(
        "resolve",
        help="Resolve recorded historical addresses without filesystem aliases",
    )
    p.add_argument("path")
    p.add_argument("--id")
    p.set_defaults(func=cmd_resolve)
    p = sub.add_parser("validate")
    p.set_defaults(func=lambda a: (load_catalog(Path(a.catalog)) or 0) and 0)
    p = sub.add_parser(
        "observe",
        help="Append reviewed location observations or revisions, retaining prior inspections",
    )
    p.add_argument("observations")
    p.add_argument("--expected-sha256", required=True)
    p.set_defaults(func=cmd_observe)
    p = sub.add_parser(
        "audit",
        help="Read-only, all-asset metadata mismatch report; never repairs identity",
    )
    p.add_argument(
        "--all", action="store_true", help="Include matching assets as well as findings"
    )
    p.set_defaults(func=cmd_audit)
    p = sub.add_parser(
        "report", help="Render the catalog as a searchable offline HTML page"
    )
    p.add_argument("--template", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--judgments",
        type=Path,
        help="Explicit authored classification ledger; source catalog observations remain unchanged",
    )
    p.set_defaults(func=cmd_report)
    p = sub.add_parser(
        "links", help="Audit local links in the index documents a manifest selects"
    )
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_links, catalog_free=True)
    p = sub.add_parser(
        "publish",
        help="Stage an explicit file-only report site from a publication allowlist",
    )
    p.add_argument("--publication", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(func=cmd_publish, catalog_free=True)
    args = parser.parse_args(argv)
    if args.catalog is None and not getattr(args, "catalog_free", False):
        parser.error(f"{args.command} needs --catalog")
    try:
        return args.func(args)
    except (ValueError, OSError, KeyError, TypeError) as e:
        return fail(str(e))


if __name__ == "__main__":
    raise SystemExit(main())
