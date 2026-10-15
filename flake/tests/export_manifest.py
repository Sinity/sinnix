"""Exercise the packaged entry point without caller Python dependencies."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

command = os.environ["EXPORT_MANIFEST"]
env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}}
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "nested").mkdir()
    payloads = {"one.txt": b"first\n", "nested/two.bin": bytes(range(256))}
    for relative, payload in payloads.items():
        (root / relative).write_bytes(payload)
    (root / "alias.txt").symlink_to(root / "one.txt")
    payloads["alias.txt"] = payloads["one.txt"]
    (root / "directory-link").symlink_to(root / "nested", target_is_directory=True)
    manifest_path = root / "MANIFEST.json"
    manifest_path.write_text('{"previous": true}\n')
    for _ in range(2):
        result = subprocess.run([command, str(root)], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        manifest = json.loads(manifest_path.read_text())
        assert manifest["generator"] == "sinnix-export-manifest"
        assert manifest["root"] == str(root.resolve())
        assert manifest["entry_count"] == 3
        assert manifest["total_bytes"] == sum(map(len, payloads.values()))
        assert [entry["path"] for entry in manifest["entries"]] == sorted(payloads)
        for entry in manifest["entries"]:
            assert entry["size"] == len(payloads[entry["path"]])
            assert entry["sha256"] == hashlib.sha256(payloads[entry["path"]]).hexdigest()
            assert entry["mtime"].endswith("+00:00")
    before = manifest_path.read_bytes()
    for args in [[], [str(root / "missing")], [str(root / "one.txt")]]:
        result = subprocess.run([command, *args], env=env, capture_output=True, text=True)
        assert result.returncode == 64, result.stderr
        assert "usage:" in result.stderr
        assert manifest_path.read_bytes() == before


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "visible.txt").write_text("visible payload")
    hidden = root / "unreadable"
    hidden.mkdir()
    (hidden / "retained.txt").write_text("payload that must not disappear from inventory")
    target = root / "MANIFEST.json"
    previous = b'{"previous":"verified inventory"}\n'
    target.write_bytes(previous)
    before = target.stat()
    hidden.chmod(0)
    try:
        result = subprocess.run([command, str(root)], env=env, capture_output=True, text=True)
        assert result.returncode != 0, "an unreadable subtree was silently omitted"
        assert "PermissionError" in result.stderr
        assert target.read_bytes() == previous
        assert target.stat().st_ino == before.st_ino
    finally:
        hidden.chmod(0o700)

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "empty-directory").mkdir()
    result = subprocess.run([command, str(root)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((root / "MANIFEST.json").read_text())
    assert manifest["entry_count"] == 0 and manifest["entries"] == []

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "broken.txt").symlink_to(root / "absent.txt")
    target = root / "MANIFEST.json"
    previous = b'{"previous":"verified inventory"}\n'
    target.write_bytes(previous)
    result = subprocess.run([command, str(root)], env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "FileNotFoundError" in result.stderr
    assert target.read_bytes() == previous

print("packaged export: content, links, empty trees and unavailable-source refusal passed")
