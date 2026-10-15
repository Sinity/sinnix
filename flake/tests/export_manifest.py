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
    manifest_path = root / "MANIFEST.json"
    manifest_path.write_text('{"previous": true}\n')
    for _ in range(2):
        result = subprocess.run([command, str(root)], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        manifest = json.loads(manifest_path.read_text())
        assert manifest["generator"] == "sinnix-export-manifest"
        assert manifest["root"] == str(root.resolve())
        assert manifest["entry_count"] == 2
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
print("packaged export: hashes, replacement, self-exclusion and invalid roots passed")
