"""Qt Quick front end for preference ranking."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from previews import PERCENTAGES, PreviewWorker
from session import DomainSource, Item, LocalSource, Session, StashSource


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
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02d}"


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


def probe_video(path, duration):
    projection = {}
    try:
        result = subprocess.run(
            ["video-projection", "inspect", path],
            capture_output=True, check=True, timeout=8, text=True,
        )
        projection = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    if not duration:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                capture_output=True, check=True, timeout=8, text=True,
            )
            duration = float(result.stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return projection, duration


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


class Controller(QObject):
    changed = Signal()
    media_changed = Signal()
    recents_changed = Signal()
    operation_completed = Signal(object, object, object)
    frames_completed = Signal(str, object)
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
        self._frame_requests = set()
        self._video_requests = {}
        self._version = None
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
        self._error = error
        if isinstance(result, str):
            path = result
            self._metadata_by_item.pop(path, None)
            ids = {str(item.id) for item in (*self._pair(), self._version) if item and item.path == path}
            self._frames.cancel_except(self._frame_requests - ids)
            for key in ids:
                self._frames_by_item.pop(key, None)
                self._frame_requests.discard(key)
        if source and result is not None:
            if self._session:
                self._session.close()
            self._session = result
            self._source = source
            self._version = None
            self._save_recent(source)
        self._request_media()
        self.changed.emit()
        self.media_changed.emit()

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
                    scope=values or "vr",
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
        self._open({"kind": "stash", "value": scope or "vr", "label": "Stash"})

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
            return path

        self._schedule(apply)

    @Slot("QVariantMap")
    def preview_version(self, info):
        self._version = Item(
            id=str(info["id"]), label=info["label"], path=info["path"], size=int(info.get("size") or 0),
            kind="video", duration=info.get("duration"),
        )
        self._request_media()
        self.media_changed.emit()

    @Slot()
    def close_preview(self):
        self._version = None
        self._request_media()
        self.media_changed.emit()

    def _pair(self):
        return self._session.pair if self._session else (None, None)

    def _request_media(self):
        items = tuple(item for item in (*self._pair(), self._version) if item and item.kind == "video" and item.path)
        keys = {str(item.id) for item in items}
        self._frames.cancel_except(keys)
        self._frame_requests.intersection_update(keys)
        for key in self._video_requests.keys() - keys:
            if self._video_requests[key].cancel():
                del self._video_requests[key]
        for item in items:
            key = str(item.id)
            if key not in self._frames_by_item and key not in self._frame_requests:
                self._frame_requests.add(key)
                self._frames.request(item, self.frames_completed.emit)
            video_key = str(item.path)
            if video_key in self._metadata_by_item or key in self._video_requests:
                continue
            task = self._metadata.submit(probe_video, video_key, item.duration)
            self._video_requests[key] = task

            def probed(future, id_=key, path=video_key):
                if not future.cancelled():
                    self.video_completed.emit(id_, (path, *future.result()))

            task.add_done_callback(probed)

    @Slot(str, object)
    def _receive_frames(self, key, frames):
        self._frame_requests.discard(key)
        self._frames_by_item[key] = dict(frames)
        self.media_changed.emit()

    @Slot(str, object)
    def _receive_video(self, key, payload):
        path, projection, duration = payload
        self._video_requests.pop(key, None)
        self._metadata_by_item[path] = (projection, duration)
        self.media_changed.emit()

    def _describe(self, item):
        if item is None:
            return {}
        item_id = str(item.id)
        path = str(item.path) if item.path else ""
        projection, duration = self._metadata_by_item.get(path, ({}, item.duration))
        kind = item.kind
        media = path
        if item.image and kind != "video":
            kind = "image"
            media = item.image
        overview = [file_size(item.size)] if item.size else []
        if duration:
            overview.append(timestamp(duration))
        if item.scene_id is not None:
            overview.append(f"{item.play_count} scene plays")
        known_frames = self._frames_by_item.get(item_id, {})
        frames = [
            {
                "fraction": pct / 100,
                "url": source_url(known_frames.get(pct)),
                "label": timestamp(duration * pct / 100) if duration else f"{pct}%",
            }
            for pct in PERCENTAGES
        ] if kind == "video" else []
        text = item.description or item.label
        if kind == "text" and path:
            try:
                with Path(path).open(errors="replace") as file:
                    text = file.read()
            except OSError:
                pass
        return {
            "id": item_id, "key": f"{item_id}\n{path}", "label": item.label, "path": path,
            "kind": kind, "media": source_url(media), "text": text, "duration": (duration or 0) * 1000,
            "projection": projection or item.projection or {}, "size_label": file_size(item.size),
            "details": " · ".join(overview), "frames": frames,
            "versions": [version_info(entry) for entry in item.versions],
        }

    @Property("QVariantMap", notify=media_changed)
    def left(self):
        return self._describe(self._pair()[0])

    @Property("QVariantMap", notify=media_changed)
    def right(self):
        return self._describe(self._pair()[1])

    @Property("QVariantMap", notify=media_changed)
    def preview(self):
        return self._describe(self._version)

    @Property("QVariantList", notify=recents_changed)
    def recents(self):
        return self._recents

    @Property(str, notify=changed)
    def title(self):
        return self._session.title if self._session else ""

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

    @Property(str, notify=media_changed)
    def both_size(self):
        return file_size(sum(int(item.size or 0) for item in self._pair() if item))

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def failed(self):
        return bool(self._error)

    @Property(str, notify=changed)
    def message(self):
        if self._busy:
            return "Working…"
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
