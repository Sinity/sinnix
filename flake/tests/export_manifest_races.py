"""A manifest must not combine pre-write metadata with post-write bytes."""
import hashlib
import os
from pathlib import Path
import runpy
import sys
import tempfile

source = os.environ["EXPORT_MANIFEST_SOURCE"]
for mode in ("rewrite", "replace", "fifo", "before-open-fifo"):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        payload = root / "payload"
        payload.write_bytes(b"old")
        manifest = root / "MANIFEST.json"
        previous = b'{"previous":"verified"}\n'
        manifest.write_bytes(previous)
        before = manifest.stat()
        original_open = os.open
        original = hashlib.sha256
        def change_at_hash_start(*args, **kwargs):
            if mode == "rewrite":
                payload.write_bytes(b"replacement contents")
            elif mode == "replace":
                replacement = root / "replacement"
                replacement.write_bytes(b"replacement contents")
                replacement.replace(payload)
            elif mode == "fifo":
                payload.unlink()
                os.mkfifo(payload)
            return original(*args, **kwargs)
        def opening(path, flags, *args, **kwargs):
            if mode == "before-open-fifo" and Path(path) == payload:
                payload.unlink()
                os.mkfifo(payload)
            return original_open(path, flags, *args, **kwargs)
        os.open = opening
        hashlib.sha256 = change_at_hash_start
        sys.argv = [source, str(root)]
        try:
            try:
                runpy.run_path(source, run_name="__main__")
            except RuntimeError as error:
                expected = "not a regular export file" if mode == "before-open-fifo" else "changed while hashing"
                assert expected in str(error), str(error)
            else:
                raise AssertionError(f"{mode}: changed payload published as a complete observation")
        finally:
            hashlib.sha256 = original
            os.open = original_open
        assert manifest.read_bytes() == previous
        after = manifest.stat()
        assert (before.st_ino, before.st_mode, before.st_mtime_ns) == (after.st_ino, after.st_mode, after.st_mtime_ns)
print("export manifest: rewrite, replacement and FIFO races at hash/open boundaries preserve previous inventory")
