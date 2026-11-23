"""Qt Quick front end for preference ranking."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
import re
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from previews import PERCENTAGES, PreviewWorker
from session import comparison_title, largest_first, DomainSource, Item, LocalSource, Session, StashSource


def file_size(bytes_count):
    size = int(bytes_count or 0)
    if size >= 2**30:
        return f"{size / 2**30:.2f} GiB"
    if size >= 2**20:
        return f"{size / 2**20:.1f} MiB"
    if size >= 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size:,} B"


def timestamp(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def stash_adapter():
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    path = data_home / "sinnix-rank" / "sources" / "stash"
    if not path.is_file():
        raise RuntimeError("Stashbox has not registered a desktop ranking source.")
    return [sys.executable, str(path)]


def source_url(value):
    if not value:
        return ""
    name = str(value)
    if name.startswith(("file:", "https://", "http://")):
        return name
    return QUrl.fromLocalFile(str(Path(name).expanduser().absolute())).toString()


def probe_video(path, duration, vr=False):
    """Read projection and the video facts shown in the pane header."""
    projection = {}
    try:
        result = subprocess.run(
            ["video-projection", "inspect", path, *(["--vr"] if vr else [])],
            capture_output=True, check=True, timeout=8, text=True,
        )
        projection = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    video = {}
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,codec_name:format=duration", "-of", "json", path],
            capture_output=True, check=True, timeout=8, text=True,
        )
        probe = json.loads(result.stdout)
        stream = (probe.get("streams") or [{}])[0]
        video = {"width": stream.get("width"), "height": stream.get("height"),
                 "video_codec": stream.get("codec_name")}
        duration = duration or float(probe.get("format", {}).get("duration") or 0) or None
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return projection, duration, video


def version_info(entry):
    path = str(entry.get("path") or "")
    details = [file_size(entry.get("size"))]
    if entry.get("width") and entry.get("height"):
        details.append(f"{entry['width']} × {entry['height']}")
    if entry.get("duration"):
        details.append(timestamp(float(entry["duration"])))
    if entry.get("video_codec"):
        details.append(str(entry["video_codec"]))
    if entry.get("primary"):
        details.append("Primary")
    return {
        **entry,
        "id": str(entry["id"]),
        "path": path,
        "label": entry.get("basename") or Path(path).name,
        "size_label": file_size(entry.get("size")),
        "details": " · ".join(details),
    }


def readable(label):
    """A filename as words: no extension, separators as spaces."""
    name = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", str(label or ""))
    return re.sub(r"\s+", " ", name.replace("_", " ")).strip()


def projection_label(projection):
    kind = (projection or {}).get("projection")
    layout = {"sbs": "side by side", "tb": "top and bottom"}.get((projection or {}).get("layout"), "")
    if kind == "equirect":
        return " ".join(filter(None, [f"{int(projection.get('hfov') or 180)}°", layout]))
    if kind == "fisheye":
        return " ".join(filter(None, [f"Fisheye {int(projection.get('hfov') or 180)}°", layout]))
    return {"flat": "Flat", "unknown": "Not set"}.get(kind, "")


def compare_rows(left, right):
    """The facts of a pair, side by side, with the stronger value marked.

    Bigger wins for size, resolution, length and bitrate; plays only mark
    which file has been watched more. Rows missing on both sides are left
    out.
    """
    a, b = left.get("stats") or {}, right.get("stats") or {}
    rows = []

    def row(label, key, show, better=True):
        va, vb = a.get(key), b.get(key)
        if not va and not vb:
            return
        winner = ""
        if better and va and vb and va != vb:
            winner = "left" if va > vb else "right"
        rows.append({"label": label, "left": show(va, a) if va else "—",
                     "right": show(vb, b) if vb else "—", "winner": winner})

    row("Size", "size", lambda v, _: file_size(v))
    row("Resolution", "pixels", lambda _, s: f"{s['width']} × {s['height']}")
    row("Length", "duration", lambda v, _: timestamp(v))
    row("Bitrate", "bitrate", lambda v, _: f"{v / 1e6:.0f} Mb/s")
    row("Codec", "codec", lambda v, _: v, better=False)
    row("Projection", "projection", lambda v, _: v, better=False)
    row("Plays", "plays", lambda v, _: str(v), better=False)
    return rows


class Controller(QObject):
    changed = Signal()
    left_changed = Signal()
    right_changed = Signal()
    preview_changed = Signal()
    frame_changed = Signal(str, int)
    comment_saved = Signal(str)
    recents_changed = Signal()
    pair_changed = Signal()
    upcoming_changed = Signal()
    operation_completed = Signal(object, object, object)
    frames_completed = Signal(str, object, object)
    video_completed = Signal(str, object)

    def __init__(self):
        super().__init__()
        self._session = None
        self._source = None
        self._busy = False
        self._error = ""
        self._recents_file = (
            Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            / "sinnix-rank" / "desktop-recents.json"
        )
        try:
            self._recents = json.loads(self._recents_file.read_text())
        except (OSError, ValueError):
            self._recents = []
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rank-session")
        self._metadata = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rank-metadata")
        self._frames = PreviewWorker()
        self._frames_by_item = {}
        self._metadata_by_item = {}
        self._frame_requests = {}
        self._video_requests = {}
        self._version = None
        self._epoch = 0
        self._file_identities = {}
        self._visible_items = [None, None, None]
        self._descriptions = [{}, {}, {}]
        self._prefetch = None
        self._saving_comment = None
        self._first_frame_requests = set()
        # This sitting's work, for the rail: what was decided and freed.
        self._tally = {"compared": 0, "deleted": 0, "freed": 0}
        self._recent = []
        self._pending = None
        self.operation_completed.connect(self._complete)
        self.frames_completed.connect(self._receive_frames)
        self.video_completed.connect(self._receive_video)

    def close(self):
        self._frames.close()
        self._metadata.shutdown(wait=False, cancel_futures=True)
        self._pool.shutdown(wait=True, cancel_futures=True)
        if self._session:
            self._session.close()

    def _schedule(self, fn, source=None):
        if self._busy:
            return
        self._busy = True
        self._error = ""
        self.changed.emit()
        task = self._pool.submit(fn)

        def finished(done):
            try:
                result = done.result()
            except Exception as error:
                self.operation_completed.emit(None, source, str(error))
            else:
                self.operation_completed.emit(result, source, "")

        task.add_done_callback(finished)

    @Slot(object, object, object)
    def _complete(self, result, source, error):
        self._busy = False
        self._epoch += 1
        self._error = error
        if isinstance(result, str):
            path = result
            self._metadata_by_item.pop(path, None)
            stale_probe = self._video_requests.pop(path, None)
            if stale_probe:
                stale_probe.cancel()
            self._frames.cancel_except(self._frame_requests.keys() - {path})
            self._frames_by_item.pop(path, None)
            self._frame_requests.pop(path, None)
            self._first_frame_requests.discard(path)
        pending, self._pending = self._pending, None
        if pending and not error and self._session:
            self._record(pending)
        if source and result is not None:
            if self._session:
                self._session.close()
            self._session = result
            self._source = source
            self._version = None
            self._save_recent(source)
        self._request_media()
        self._publish_items()
        self.changed.emit()
        if self._saving_comment is not None:
            key, self._saving_comment = self._saving_comment, None
            if not error:
                self.comment_saved.emit(key)

    def _save_recent(self, source):
        self._recents = [source] + [old for old in self._recents if old != source][:9]
        self.recents_changed.emit()
        try:
            self._recents_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            tmp = self._recents_file.with_suffix(f".{os.getpid()}.tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as file:
                json.dump(self._recents, file, ensure_ascii=False)
            tmp.replace(self._recents_file)
        except OSError:
            pass

    def _open(self, source):
        if self._source == source:
            self.refresh()
            return

        def start():
            action = source["kind"]
            values = source.get("value")
            provider = {
                "domain": lambda: DomainSource(values),
                "files": lambda: LocalSource(values),
                "stash": lambda: StashSource(
                    stash_adapter(),
                    scope=values,
                ),
            }[action]()
            return Session(provider)

        self._schedule(start, source)

    def _apply(self, method, *args):
        if self._session:
            session = self._session
            self._schedule(lambda: getattr(session, method)(*args))

    @Slot(str)
    def open_domain(self, domain):
        if domain:
            self._open({"kind": "domain", "value": domain, "label": domain})

    @Slot("QVariantList")
    def open_files(self, values):
        files = []
        for value in values:
            local = QUrl(str(value)).toLocalFile()
            path = Path(local or str(value)).expanduser().resolve()
            files.append(str(path))
        if files:
            label = Path(files[0]).name if len(files) == 1 else f"{len(files)} selected files"
            self._open({"kind": "files", "value": files, "label": label})

    @Slot()
    def open_stash(self, scope=None):
        if self._source and self._source["kind"] == "stash":
            if scope:
                self.set_scope(scope)
            else:
                self.refresh()
            return
        self._open({"kind": "stash", "value": scope, "label": "Stash"})

    @Slot(int)
    def open_recent(self, index):
        if 0 <= index < len(self._recents):
            self._open(self._recents[index])

    @Slot()
    def refresh(self):
        self._apply("refresh")

    @Slot(str)
    def set_order(self, order):
        self._apply("set_order", order)

    @Slot(str)
    def set_scope(self, scope):
        self._apply("set_scope", scope)

    @Property(int, notify=changed)
    def epoch(self):
        return self._epoch

    @Slot(int, str, str, str, "QVariantList")
    def decide(self, epoch, left, right, action, ids):
        if self._busy or epoch != self._epoch or [left, right] != [value.get("key", "") for value in self._descriptions[:2]]:
            return
        pair = self._visible_items[:2]
        self._pending = {"action": action, "pair": pair, "ids": [str(i) for i in ids],
                         "sizes": self._sizes(pair, ids)}
        if action in ("left", "right"):
            self.prefer(int(action == "right"))
        elif action in ("tie", "skip", "undo"):
            getattr(self, action)()
        elif action == "delete":
            self.delete_files(ids)

    @Slot(int)
    def prefer(self, side):
        self._apply("prefer", side)

    @Slot()
    def tie(self):
        self._apply("tie")

    @Slot()
    def skip(self):
        self._apply("skip")

    @Slot()
    def undo(self):
        self._apply("undo")

    @Slot("QVariantList")
    def delete_files(self, ids):
        if self.can_delete and ids:
            self._apply("delete", tuple(map(str, ids)))

    @staticmethod
    def _sizes(pair, ids):
        sizes = {}
        for item in pair:
            if item is None:
                continue
            sizes[str(item.id)] = (item.label, int(item.size or 0))
            for version in item.versions:
                sizes[str(version["id"])] = (version.get("basename") or item.label, int(version.get("size") or 0))
        return {key: sizes[key] for key in map(str, ids) if key in sizes}

    def _record(self, pending):
        action, pair = pending["action"], pending["pair"]
        if action in ("left", "right") and all(pair):
            kept = pair[action == "right"]
            self._tally["compared"] += 1
            self._recent.insert(0, {"text": f"Kept {action} · {readable(kept.label)}", "kind": "choice"})
        elif action == "tie":
            self._tally["compared"] += 1
            self._recent.insert(0, {"text": "Tie", "kind": "choice"})
        elif action == "skip":
            self._recent.insert(0, {"text": "Skipped the pair", "kind": "skip"})
        elif action == "undo" and self._recent:
            undone = self._recent.pop(0)
            if undone["kind"] == "choice":
                self._tally["compared"] -= 1
        elif action == "delete":
            present = set()
            for item in self._session.items.values():
                present.add(str(item.id))
                present.update(str(version["id"]) for version in item.versions)
            for key, (label, size) in pending["sizes"].items():
                if key not in present:
                    self._tally["deleted"] += 1
                    self._tally["freed"] += size
                    self._recent.insert(0, {"text": f"Deleted {readable(label)} · {file_size(size)}", "kind": "delete"})
        del self._recent[8:]

    @Property("QVariantMap", notify=changed)
    def tally(self):
        return {**self._tally, "freed_label": file_size(self._tally["freed"]) if self._tally["freed"] else ""}

    @Property("QVariantList", notify=changed)
    def recent(self):
        return self._recent

    @Property("QVariantList", notify=pair_changed)
    def comparison(self):
        return compare_rows(self._descriptions[0], self._descriptions[1])

    @Property("QVariantMap", notify=upcoming_changed)
    def upcoming(self):
        """The file the next pair will bring in, already being prefetched."""
        if not (self._session and self._prefetch):
            return {}
        item = next((i for i in self._session.items.values() if str(i.path) == self._prefetch), None)
        if item is None:
            return {}
        frame = (self._frames_by_item.get(self._prefetch) or {}).get(PERCENTAGES[0])
        return {"label": readable(item.label), "size_label": file_size(item.size), "frame": source_url(frame)}

    @Slot(str, result=str)
    def file_comment(self, key):
        for item, description in zip(self._visible_items, self._descriptions):
            if item and item.kind == "video" and description.get("key") == key:
                return self._session.comment(item.id)
        return ""

    @Slot(str, str)
    def save_file_comment(self, key, text):
        if self._busy:
            return
        for item, description in zip(self._visible_items, self._descriptions):
            if item and item.kind == "video" and description.get("key") == key:
                self._saving_comment = key
                self._apply("save_comment", item.id, text)
                return

    @Slot(str, str, str, int, bool)
    def correct_projection(self, path, projection, layout, field_of_view, swap):
        def apply():
            command = ["video-projection", "clear" if projection == "automatic" else "set", path]
            if projection != "automatic":
                command.extend(["--projection", projection, "--layout", layout, "--hfov", str(field_of_view)])
                if swap:
                    command.append("--swap")
            result = subprocess.run(command, capture_output=True, timeout=10, text=True)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "The projection could not be saved.")
            if self._session and isinstance(self._session.source, StashSource):
                provider = self._session.source
                scenes = {item.scene_id for item in provider.files.values() if item.path == path}
                if scenes:
                    provider.reconcile(sorted(scenes))
                    self._session.refresh(reconcile=False)
            return path

        self._schedule(apply)

    @Slot("QVariantMap")
    def preview_version(self, info):
        self._version = Item(
            id=str(info["id"]), label=info["label"], path=info["path"], size=int(info.get("size") or 0),
            kind="video", duration=info.get("duration"),
        )
        self._request_media()
        self._publish_items()

    @Slot()
    def close_preview(self):
        self._version = None
        self._request_media()
        self._publish_items()

    def _pair(self):
        return self._session.pair if self._session else (None, None)

    def _request_media(self):
        items = tuple(item for item in (*self._pair(), self._version) if item and item.kind == "video" and item.path)
        self._prefetch = None
        if (self._session and self._session.order == "largest" and items):
            seen = set(self._session.slot["seen"]) | set(self._session.slot["current"])
            following = min((item for item in self._session.items.values() if item.id not in seen),
                            key=largest_first, default=None)
            if following and following.kind == "video" and following.path:
                self._prefetch = following.path
                items += (following,)
        keys = {str(item.path) for item in items}
        replaced = set()
        for item in items:
            path = str(item.path)
            identity = (item.id, item.size, item.identity.get("mod_time"))
            previous = self._file_identities.get(path)
            if previous is not None and previous != identity:
                replaced.add(path)
                self._frames_by_item.pop(path, None)
                self._frame_requests.pop(path, None)
                self._first_frame_requests.discard(path)
                self._metadata_by_item.pop(path, None)
                if stale := self._video_requests.pop(path, None):
                    stale.cancel()
            self._file_identities[path] = identity
        if replaced:
            self._frames.cancel_except(keys - replaced)
        self._frames.cancel_except(keys)
        for key in self._frame_requests.keys() - keys:
            del self._frame_requests[key]
            self._first_frame_requests.discard(key)
        for key in self._video_requests.keys() - keys:
            if self._video_requests[key].cancel():
                del self._video_requests[key]
        for item in items:
            key = str(item.path)
            background = key == self._prefetch
            known = self._frames_by_item.get(key, {})
            moments = PERCENTAGES[:1] if background else PERCENTAGES
            pending = tuple(pct for pct in moments if pct not in known)
            if pending and key not in self._frame_requests:
                generation = object()
                self._frame_requests[key] = generation
                if background:
                    self._first_frame_requests.add(key)

                def publish_frames(path, frames, token=generation):
                    self.frames_completed.emit(path, token, frames)

                self._frames.request(replace(item, id=key), publish_frames,
                                     background=background, percentages=pending)
            if key == self._prefetch or key in self._metadata_by_item or key in self._video_requests:
                continue
            task = self._metadata.submit(probe_video, key, item.duration, item.projection_kind == "vr")
            self._video_requests[key] = task

            def probed(future, path=key):
                if not future.cancelled():
                    self.video_completed.emit(path, (future, *future.result()))

            task.add_done_callback(probed)

    @Slot(str, object, object)
    def _receive_frames(self, path, generation, frames):
        if self._frame_requests.get(path) is generation:
            known = self._frames_by_item.setdefault(path, {})
            known.update(frames)
            for pct, _ in frames:
                self.frame_changed.emit(path, pct)
            if path == self._prefetch:
                self.upcoming_changed.emit()
            if path in self._first_frame_requests:
                self._first_frame_requests.remove(path)
                self._frame_requests.pop(path)
                self._frames.cancel_except(self._frame_requests)
                if not self._busy:
                    self._request_media()

    @Slot(str, int, result="QVariantMap")
    def frame(self, path, pct):
        frames = self._frames_by_item.get(path, {})
        return {"url": source_url(frames.get(pct)), "failed": pct in frames and not frames[pct]}

    @Slot(str)
    def retry_frames(self, path):
        if path not in self._frame_requests:
            return
        self._frames.cancel_except(self._frame_requests.keys() - {path})
        self._frame_requests.pop(path)
        self._first_frame_requests.discard(path)
        self._frames_by_item.pop(path, None)
        self._request_media()

    @Slot(str, object)
    def _receive_video(self, path, payload):
        job, projection, duration, video = payload
        if self._video_requests.get(path) is job:
            del self._video_requests[path]
            self._metadata_by_item[path] = (projection, duration, video)
            self._publish_items(path)

    def _describe(self, item):
        if item is None:
            return {}
        item_id = str(item.id)
        path = str(item.path) if item.path else ""
        projection, duration, video = self._metadata_by_item.get(path, ({}, item.duration, {}))
        video = {key: item.identity.get(key) or video.get(key) for key in ("width", "height", "video_codec")}
        kind = item.kind
        media = path
        if item.image and kind != "video":
            kind = "image"
            media = item.image
        facts = []
        if video["width"] and video["height"]:
            facts.append(f"{video['width']} × {video['height']}")
        if video["video_codec"]:
            facts.append(str(video["video_codec"]).upper())
        if duration:
            facts.append(timestamp(duration))
        if item.scene_id is not None:
            facts.append(f"{item.play_count} plays")
        stats = {
            "size": int(item.size or 0), "duration": duration or 0,
            "pixels": (video["width"] or 0) * (video["height"] or 0),
            "width": video["width"], "height": video["height"],
            "bitrate": int(item.size or 0) * 8 / duration if duration and item.size else 0,
            "codec": str(video["video_codec"]).upper() if video["video_codec"] else "",
            "projection": projection_label(projection or item.projection) if kind == "video" else "",
            "plays": item.play_count if item.scene_id is not None else 0,
        }
        frames = [{"pct": pct, "fraction": pct / 100,
                   "label": timestamp(duration * pct / 100) if duration else f"{pct}%"}
                  for pct in PERCENTAGES] if kind == "video" else []
        text = item.description or item.label
        if kind == "text" and path:
            try:
                with Path(path).open("rb") as file:
                    data = file.read(64 * 1024 + 1)
                text = data[:64 * 1024].decode("utf-8", errors="replace")
                if len(data) > 64 * 1024:
                    text += "\n\n[Preview limited to 64 KiB]"
            except OSError:
                pass
        return {
            "id": item_id, "key": f"{item_id}\n{path}", "label": item.label, "path": path,
            "poster": (
                f"{item.scene_url.replace('/scenes/', '/scene/')}/screenshot"
                if item.scene_url and item.identity.get("primary") else ""
            ),
            "kind": kind, "media": source_url(media), "text": text, "duration": (duration or 0) * 1000,
            "projection": projection or item.projection or {}, "size_label": file_size(item.size),
            "details": " · ".join(facts), "frames": frames, "stats": stats,
            "aspect": (video["width"] / video["height"]) if video["width"] and video["height"] else 16 / 9,
            "versions": [version_info(entry) for entry in item.versions],
        }

    def _publish_items(self, changed_path=None):
        for index, (item, signal) in enumerate(zip((*self._pair(), self._version),
                (self.left_changed, self.right_changed, self.preview_changed))):
            if item != self._visible_items[index] or (item and item.path == changed_path):
                self._visible_items[index] = item
                self._descriptions[index] = self._describe(item)
                signal.emit()
                if index < 2:
                    self.pair_changed.emit()
        self.upcoming_changed.emit()

    @Property("QVariantMap", notify=left_changed)
    def left(self):
        return self._descriptions[0]

    @Property("QVariantMap", notify=right_changed)
    def right(self):
        return self._descriptions[1]

    @Property("QVariantMap", notify=preview_changed)
    def preview(self):
        return self._descriptions[2]

    @Property(str, notify=changed)
    def undo_label(self):
        previous = self._session.slot["undo"] if self._session else None
        return (previous or {}).get("action", "ranking")

    @Property("QVariantList", notify=recents_changed)
    def recents(self):
        return self._recents

    @Property(str, notify=changed)
    def title(self):
        return self._session.title if self._session else ""

    @Property(str, notify=changed)
    def window_title(self):
        return comparison_title(self.title, self._visible_items[:2])

    @Property(str, notify=changed)
    def source_label(self):
        if not self._source:
            return ""
        return {"stash": "Stash video library", "domain": "Ranking domain", "files": "Local files"}[self._source["kind"]]

    @Property(str, notify=changed)
    def scope(self):
        return self._session.scope if self._session else "vr"

    @Property(str, notify=changed)
    def order(self):
        return self._session.order if self._session else "informative"

    @Property(bool, notify=changed)
    def can_scope(self):
        return bool(self._session and self._session.can_scope)

    @Property(bool, notify=changed)
    def can_compare(self):
        return bool(all(self._pair()))

    @Property(bool, notify=changed)
    def can_delete(self):
        return bool(self._session and self._session.can_delete)

    @Property(bool, notify=changed)
    def can_undo(self):
        return bool(self._session and self._session.can_undo)

    @Property(str, notify=changed)
    def both_size(self):
        return file_size(sum(int(item.size or 0) for item in self._pair() if item))

    @Property(str, notify=changed)
    def progress_label(self):
        return self._session.progress_label if self._session else ""

    @Property(float, notify=changed)
    def progress_fraction(self):
        done, total = self._session.progress if self._session else (0, 0)
        return done / total if total else -1.0

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def failed(self):
        return bool(self._error)

    @Property(str, notify=changed)
    def message(self):
        return self._error or (self._session.status if self._session else "")


def parse_args(arguments):
    parser = argparse.ArgumentParser(description="Compare two items on the desktop.")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("domain", nargs="?")
    sources.add_argument("--files", nargs="+", metavar="PATH")
    sources.add_argument("--stash", action="store_true")
    parser.add_argument("--scope", choices=("vr", "flat", "unknown", "all"))
    args = parser.parse_args(arguments)
    if args.scope and not args.stash:
        parser.error("--scope requires --stash")
    return args


def main(arguments=None):
    args = parse_args(arguments)
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("Preference ranking")
    QQuickStyle.setStyle("Fusion")
    controller = Controller()
    if args.domain:
        controller.open_domain(args.domain)
    elif args.files:
        controller.open_files(args.files)
    elif args.stash:
        controller.open_stash(args.scope)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().with_name("Main.qml"))))
    if not engine.rootObjects():
        controller.close()
        return 1
    try:
        return app.exec()
    finally:
        engine.rootContext().setContextProperty("controller", None)
        controller.close()


if __name__ == "__main__":
    raise SystemExit(main())
