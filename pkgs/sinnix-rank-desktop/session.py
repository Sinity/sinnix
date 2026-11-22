"""Sources and resumable comparison sessions for the desktop ranker."""

from __future__ import annotations

import fcntl
import hashlib
import json
import mimetypes
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from rank_core import (
    Comparison,
    Store,
    append_log,
    build_selector,
    fit,
    read_log,
)
from rank_core import (
    Item as RankItem,
)
from rank_core.store import domain_path
from sinnix_lib.atomic import atomic_publish


def digest(value):
    return hashlib.sha256(os.fsencode(value)).hexdigest()


def rank_root():
    return Path(os.environ.get("SINNIX_RANK_ROOT", "/realm/activity/shared/ranking"))


def session_root():
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return Path(
        os.environ.get("SINNIX_RANK_DESKTOP_STATE", state / "sinnix-rank-desktop")
    )


def largest_first(item):
    # Stash IDs are decimal. Other sources use arbitrary stable IDs.
    return (
        (-item.size, 0, int(item.id))
        if item.id.isdecimal()
        else (-item.size, 1, item.id)
    )


def media_kind(path):
    if path:
        mime = mimetypes.guess_type(path)[0] or ""
        if mime.startswith(("image/", "video/")):
            return mime.split("/", 1)[0]
        if Path(path).suffix.lower() in {".mkv", ".mov", ".m4v", ".m2ts", ".ts"}:
            return "video"
    return "text"


@dataclass(frozen=True)
class Item:
    id: str
    label: str
    path: str | None = None
    size: int = 0
    kind: str = "text"
    description: str = ""
    image: str | None = None
    projection_kind: str = "unknown"
    projection: dict = field(default_factory=dict)
    scene_id: str | None = None
    scene_url: str | None = None
    play_count: int = 0
    duration: float | None = None
    versions: tuple[dict, ...] = ()
    identity: dict = field(default_factory=dict, repr=False)


class DomainSource:
    order = "informative"
    can_delete = False
    can_scope = False
    scope = "all"

    def __init__(self, domain):
        self.store = Store(domain_path(rank_root(), domain))
        self.key = str(self.store.domain_dir)
        self.title = domain

    def load(self, _scope):
        items = []
        for entry in self.store.load_items().values():
            meta = entry.meta
            image = meta.get("image")
            path = meta.get("path") or meta.get("video") or image
            size = meta.get("size")
            if size is None and path:
                try:
                    size = Path(path).stat().st_size
                except OSError:
                    pass
            items.append(
                Item(
                    entry.id,
                    entry.label,
                    path=path,
                    size=int(size or 0),
                    kind=media_kind(path),
                    description=str(meta.get("description") or ""),
                    image=image,
                    duration=meta.get("duration"),
                )
            )
        return items, None

    def comparisons(self):
        return self.store.load_comparisons()

    def record(self, pair, winner, operation_id):
        if operation_id not in read_log(self.store.comparisons_path).seen_ids:
            append_log(
                self.store.comparisons_path,
                {
                    "id": operation_id,
                    "kind": "pair",
                    "set": [item.id for item in pair],
                    "winner": winner,
                    "context": "desktop",
                },
            )
        return True

    def undo(self, operation_id):
        self.store.undo(operation_id)


class LocalSource(DomainSource):
    order = "largest"

    def __init__(self, paths):
        self.paths = tuple(sorted({Path(path).resolve() for path in paths}))
        if not self.paths:
            raise ValueError("Select at least one file or directory.")
        key = digest("\0".join(map(str, self.paths)))
        super().__init__(f"local/{key}")
        self.title = self.paths[0].name or str(self.paths[0])
        if len(self.paths) > 1:
            self.title = f"{self.title} and {len(self.paths) - 1} more"

    def load(self, _scope):
        items = {}
        for source in self.paths:
            if not source.exists():
                raise FileNotFoundError(source)
            for path in source.rglob("*") if source.is_dir() else [source]:
                if media_kind(str(path)) == "text" and source.is_dir():
                    continue
                if not path.is_file():
                    continue
                resolved = path.resolve()
                file = resolved.stat()
                identity = f"{resolved}\0{file.st_dev}:{file.st_ino}:{file.st_size}:{file.st_mtime_ns}"
                item = Item(
                    digest(identity),
                    resolved.name,
                    path=str(resolved),
                    size=file.st_size,
                    kind=media_kind(str(resolved)),
                    description=str(resolved.parent),
                )
                items[item.id] = item
        registered = self.store.load_items()
        self.store.add_items(
            [
                RankItem(
                    item.id,
                    item.label,
                    {
                        "path": item.path,
                        "size": item.size,
                        "description": item.description,
                    },
                )
                for item in items.values()
                if item.id not in registered
            ]
        )
        return list(items.values()), None


class StashSource:
    title = "Stashbox"
    order = "largest"
    can_delete = True
    can_scope = True

    def __init__(self, executable, scope=None):
        self.command = (
            [os.fspath(executable)]
            if isinstance(executable, (str, os.PathLike))
            else list(executable)
        )
        self.requested_scope = scope
        self.scope = scope or "vr"
        self.key = json.dumps(["stash", os.path.realpath(self.command[-1])])
        self.rows = []
        self.files = {}
        self.passes = None

    def call(self, op, **fields):
        result = subprocess.run(
            self.command,
            input=json.dumps({"op": op, **fields}) + "\n",
            text=True,
            capture_output=True,
            timeout=90,
        )
        try:
            response = json.loads(result.stdout)
        except ValueError:
            raise RuntimeError(
                "Stashbox adapter returned an invalid response."
            ) from None
        if result.returncode or response.get("error"):
            raise RuntimeError(
                response.get("error") or "Stashbox adapter returned an error."
            )
        return response

    def reconcile(self, scenes=None):
        data = self.call("roster", scenes=scenes)
        if scenes is None:
            self.files.clear()
            self.rows = data["comparisons"]
            self.passes = data["passes"]
        else:
            self.files = {key: item for key, item in self.files.items() if item.scene_id not in scenes}
        for group in data["groups"]:
            scene = str(group["id"])
            versions = tuple(group["files"])
            for row in versions:
                key = str(row["id"])
                self.files[key] = Item(
                    id=key, label=row["basename"], path=row["path"], kind="video",
                    size=int(row["size"]), projection_kind=row["kind"], scene_id=scene,
                    scene_url=f"{data['origin']}/scenes/{scene}", play_count=group["play_count"] or 0,
                    duration=row.get("duration"), versions=versions, identity=row,
                    projection={"projection": row["projection"]},
                )

    def load(self, scope):
        if self.passes is None:
            self.reconcile()
        return [item for item in self.files.values()
                if scope == "all" or item.projection_kind == scope
                or (scope == "unknown" and item.identity["projection"] == "unknown")], self.passes.get(scope)

    def comparisons(self):
        # Use one file per scene when projecting existing scene votes into file selection.
        ordered = sorted(self.files.values(), key=largest_first)
        by_scene = {}
        for item in ordered:
            by_scene.setdefault(item.scene_id, item.id)
        comparisons = []
        for row in self.rows:
            left, right = (by_scene.get(str(row.get(side))) for side in ("a", "b"))
            outcome = {1: "a", 0: "b", 0.5: "tie"}.get(
                row.get("outcome"), row.get("outcome")
            )
            if not left or not right or outcome not in ("a", "b", "tie"):
                continue
            winner = {"a": left, "b": right, "tie": None}[outcome]
            comparisons.append(
                Comparison(
                    str(row["id"]),
                    row.get("at", ""),
                    "pair",
                    [left, right],
                    winner,
                )
            )
        return comparisons

    def record(self, pair, winner, operation_id):
        left, right = pair
        if left.scene_id == right.scene_id:
            return False
        response = self.call(
            "record", left=left.id, right=right.id, winner=winner, id=operation_id
        )
        if not response.get("recorded"):
            return False
        if "comparisons" in response:
            self.rows = response["comparisons"]
        else:
            outcome = "tie" if winner is None else "a" if winner == left.id else "b"
            self.rows.append(
                {
                    "id": operation_id,
                    "a": left.scene_id,
                    "b": right.scene_id,
                    "outcome": outcome,
                }
            )
        return True

    def undo(self, operation_id):
        response = self.call("undo", id=operation_id)
        self.rows = response.get(
            "comparisons", [row for row in self.rows if row["id"] != operation_id]
        )

    def delete(self, files):
        fields = ("id", "scene_id", "path", "size", "mod_time")
        return self.call(
            "delete",
            files=[{key: file[key] for key in fields} for file in files],
            id=str(uuid.uuid4()),
        )["files"]


class Session:
    """One current pair per source, scope and ordering."""

    def __init__(self, source, *, state_root=None):
        self.source = source
        self.order = source.order
        self.scope = source.scope
        self.title = source.title
        self.can_delete = source.can_delete
        self.can_scope = source.can_scope
        self.path = (Path(state_root) if state_root else session_root()) / (
            digest(source.key) + ".json"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(
            self.path.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600
        )
        self.lock = os.fdopen(descriptor, "rb")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.close()
            raise RuntimeError("This comparison source is already open.") from None
        self.items = {}
        self.status = ""
        try:
            try:
                self.state = json.loads(self.path.read_text())
            except FileNotFoundError:
                self.state = {}
            if isinstance(source, StashSource) and source.requested_scope is None:
                self.scope = self.state.get("scope", self.scope)
            self.order = self.state.get("order", self.order)
            self.refresh(reconcile=False)
        except BaseException:
            self.close()
            raise

    def close(self):
        self.lock.close()

    @property
    def slot(self):
        passes = self.state.setdefault("passes", {})
        return passes.setdefault(
            f"{self.scope}/{self.order}",
            {
                "current": [None, None],
                "seen": [],
                "pairs": [],
                "undo": None,
                "failed": False,
            },
        )

    @property
    def pair(self):
        left, right = self.slot["current"]
        return self.items.get(left), self.items.get(right)

    @property
    def can_undo(self):
        return self.slot["undo"] is not None

    def save(self):
        self.state["scope"] = self.scope
        self.state["order"] = self.order
        atomic_publish(self.path, json.dumps(self.state).encode(), fsync=True)

    def load(self):
        items, imported = self.source.load(self.scope)
        self.items = {item.id: item for item in items}
        key = f"{self.scope}/largest"
        passes = self.state.setdefault("passes", {})
        if imported and key not in passes:
            pair = imported.get("pair") or {}
            passes[key] = {
                "current": [
                    str(pair[side]) if pair.get(side) else None
                    for side in ("left", "right")
                ],
                "seen": [str(item) for item in imported.get("seen", [])],
                "failed": bool(imported.get("failed")),
                "pairs": [],
                "undo": None,
            }

    def refresh(self, reconcile=True):
        if reconcile and isinstance(self.source, StashSource):
            self.source.reconcile()
        self.load()
        if not self.slot.get("failed"):
            self.advance()
        self.finish()

    def finish(self, status=None):
        current = sum(item is not None for item in self.pair)
        if status is None:
            if self.order == "largest":
                reviewed = len(set(self.slot["seen"]).intersection(self.items))
                remaining = len(self.items) - reviewed
                status = f"{reviewed} of {len(self.items)} shown"
                if remaining == 0 and current < 2:
                    status += " · Pass complete"
            else:
                status = f"{len(self.items)} items · {len(self.slot['pairs'])} comparisons shown"
        self.status = status
        self.save()

    def set_order(self, value):
        if value not in ("largest", "informative"):
            raise ValueError("Unknown comparison order.")
        if self.order != value:
            self.order = value
            if not self.slot.get("failed"):
                self.advance()
            self.finish()

    def set_scope(self, value):
        if value not in ("vr", "flat", "unknown", "all"):
            raise ValueError("Unknown library filter.")
        if self.can_scope and self.scope != value:
            previous = self.scope
            self.scope = value
            try:
                self.refresh(reconcile=False)
            except Exception:
                self.scope = previous
                raise

    def advance(self):
        current = [
            item_id if item_id in self.items else None
            for item_id in self.slot["current"]
        ]
        if self.order == "largest":
            seen = set(self.slot["seen"]) | {item_id for item_id in current if item_id}
            available = iter(
                sorted(
                    (item for item in self.items.values() if item.id not in seen),
                    key=largest_first,
                )
            )
            for index, item_id in enumerate(current):
                if item_id is None and (item := next(available, None)) is not None:
                    current[index] = item.id
                    self.slot["seen"].append(item.id)
        elif None in current:
            ids = list(self.items)
            if len(ids) > 1:
                comparisons = []
                for comparison in self.source.comparisons():
                    members = [
                        member for member in comparison.set if member in self.items
                    ]
                    if len(members) > 1 and (
                        comparison.winner is None or comparison.winner in members
                    ):
                        comparisons.append(
                            Comparison(
                                comparison.id,
                                comparison.at,
                                comparison.kind,
                                members,
                                comparison.winner,
                                comparison.weight,
                                comparison.context,
                            )
                        )
                selector = build_selector(ids, comparisons, fit(ids, comparisons))
                selector.seen_sets.update(
                    frozenset(pair) for pair in self.slot["pairs"]
                )
                current, _strategy = selector.pick_set()
                if (
                    current not in self.slot["pairs"]
                    and current[::-1] not in self.slot["pairs"]
                ):
                    self.slot["pairs"].append(current)
            else:
                current = [next(iter(ids), None), None]
        self.slot["current"] = current

    def decide(self, winner, *, skip=False):
        pair = self.pair
        if None in pair and not skip:
            raise ValueError("Show two items before comparing.")
        action = "skip" if skip else "tie" if winner is None else (
            "prefer left" if winner == pair[0].id else "prefer right")
        previous = {
            "action": action,
            "current": self.slot["current"],
            "seen": list(self.slot["seen"]),
            "pairs": list(self.slot["pairs"]),
            "comparison": None,
            "failed": self.slot.get("failed", False),
        }
        if not skip:
            operation_id = str(uuid.uuid4())
            if self.source.record(pair, winner, operation_id):
                previous["comparison"] = operation_id
        self.slot["undo"] = previous
        self.slot["failed"] = False
        self.slot["current"] = [
            item.id
            if item is not None and self.order == "largest" and item.id == winner
            else None
            for item in pair
        ]
        self.advance()
        if winner and self.order == "largest":
            kept = 0 if pair[0].id == winner else 1
            status = ["Left preferred", "Right preferred"][kept]
            if self.pair[1 - kept]:
                status += " · next file on " + ["right", "left"][kept]
            self.finish(status)
        else:
            self.finish()

    def prefer(self, side):
        if side not in (0, 1) or self.pair[side] is None:
            raise ValueError("Choose a displayed side.")
        self.decide(self.pair[side].id)

    def tie(self):
        self.decide(None)

    def skip(self):
        self.decide(None, skip=True)

    def undo(self):
        previous = self.slot["undo"]
        if previous is None:
            return
        if previous["comparison"]:
            self.source.undo(previous["comparison"])
        self.slot.update(
            {
                "current": previous["current"],
                "seen": previous["seen"],
                "pairs": previous["pairs"],
                "undo": None,
                "failed": previous["failed"],
            }
        )
        if not self.slot["failed"]:
            self.advance()
        self.finish()

    def delete(self, ids):
        if not self.can_delete:
            raise ValueError("This source does not provide permanent deletion.")
        pair = self.pair
        files = {}
        for item in pair:
            if item is None:
                continue
            files[item.id] = item.identity
            files.update((version["id"], version) for version in item.versions)
        ids = list(dict.fromkeys(map(str, ids)))
        if not 1 <= len(ids) <= 2 or any(item_id not in files for item_id in ids):
            raise ValueError("The selected files are outside the displayed pair.")
        results = self.source.delete([files[item_id] for item_id in ids])
        removed = [
            item_id for item_id in ids if results.get(item_id, {}).get("removed")
        ]
        failed = [
            results.get(item_id, {}).get("error") or "Removal was not verified."
            for item_id in ids
            if item_id not in removed
        ]
        self.slot["failed"] = bool(failed)
        if removed:
            # Save the verified outcome before refreshing the external library.
            self.slot["undo"] = None
            self.slot["current"] = [
                item.id if item is not None and item.id not in removed else None
                for item in pair
            ]
            for item_id in removed:
                self.items.pop(item_id, None)
            self.finish(f"Removed {len(removed)} of {len(ids)} files")
            if isinstance(self.source, StashSource):
                scenes = sorted({str(files[key]["scene_id"]) for key in ids})
                self.source.reconcile(scenes)
            self.load()
        if not failed:
            self.advance()
        self.finish(
            " · ".join(
                f"{Path(files[key]['path']).name}: " + (
                    results.get(key, {}).get("error") or ("deleted" if key in removed else "removal unverified")
                ) for key in ids
            )
        )
