"""Verify publisher preservation and npm's embedded-lock integrity boundary."""

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


def compare(original_path, repaired_path, count):
    with tarfile.open(original_path) as original, tarfile.open(repaired_path) as repaired:
        assert repaired.getnames() == original.getnames() + ["package/npm-shrinkwrap.json"]
        for entry in original.getmembers():
            other = repaired.getmember(entry.name)
            assert (entry.type, entry.mode, entry.uid, entry.gid, entry.mtime, entry.linkname) == (other.type, other.mode, other.uid, other.gid, other.mtime, other.linkname)
            if entry.isfile():
                assert original.extractfile(entry).read() == repaired.extractfile(other).read()
        lock = json.load(repaired.extractfile("package/npm-shrinkwrap.json"))
        assert len(lock["packages"]) == count + 1
        assert all(entry.get("integrity", "").startswith("sha512-") for name, entry in lock["packages"].items() if name)


def archive(path, files):
    with tarfile.open(path, "w:gz") as handle:
        for name, payload in files.items():
            data = payload.encode()
            entry = tarfile.TarInfo("package/" + name)
            entry.size = len(data)
            entry.mode = 0o755 if name == "bin.cjs" else 0o644
            handle.addfile(entry, io.BytesIO(data))


def npm_boundary():
    root = Path.cwd()
    child = root / "child.tgz"
    archive(child, {"package.json": json.dumps({"name": "@fixture/native", "version": "1.0.0", "main": "index.js"}), "index.js": "module.exports = 'GOOD';"})
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(child.read_bytes()).digest()).decode()
    package = {"name": "@fixture/root", "version": "1.0.0", "bin": {"fixture": "bin.cjs"}, "optionalDependencies": {"@fixture/native": "1.0.0"}}
    lock = {"name": package["name"], "version": "1.0.0", "lockfileVersion": 3, "requires": True, "packages": {"": package, "node_modules/@fixture/native": {"version": "1.0.0", "resolved": child.as_uri(), "integrity": integrity, "optional": True}}}
    source = root / "root.tgz"
    archive(source, {"package.json": json.dumps(package), "npm-shrinkwrap.json": json.dumps(lock), "bin.cjs": "#!/usr/bin/env node\nconsole.log(require('@fixture/native'));"})
    env = {**os.environ, "HOME": str(root / "home"), "npm_config_offline": "true", "npm_config_audit": "false", "npm_config_fund": "false", "npm_config_update_notifier": "false"}
    for case in ["good", "corrupt"]:
        prefix = Path(env["HOME"]) / ".local/state" / case / "npm"
        if case == "corrupt":
            archive(child, {"package.json": json.dumps({"name": "@fixture/native", "version": "1.0.0", "main": "index.js"}), "index.js": "module.exports = 'ALTERED';"})
        case_env = {**env, "npm_config_cache": str(root / (case + "-cache"))}
        result = subprocess.run(["bash", sys.argv[5], case, package["name"], "fixture", os.environ["PATH"], str(source)], env=case_env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout == "", result.stdout
        binary = prefix / "bin/fixture"
        assert binary.is_file()
        result = subprocess.run(["node", str(binary)], env=env, capture_output=True, text=True)
        if case == "good":
            if result.returncode != 0 or result.stdout.strip() != "GOOD":
                for log in sorted((root / (case + "-cache") / "_logs").glob("*.log")):
                    print(log.read_text()[-6000:])
                print("Installed files:", [str(path.relative_to(prefix)) for path in prefix.rglob("*")])
                raise AssertionError(result.stderr)
        else:
            assert result.returncode != 0 and "Cannot find module" in result.stderr
    print("Offline bootstrap consumed its lock and rejected corrupt optional bytes")


def alias_and_failure_boundary():
    root = Path.cwd()
    child = root / "alias-child.tgz"
    child_package = {"name": "@fixture/alias-root", "version": "1.0.0-native", "main": "index.js", "scripts": {"postinstall": "node -e \"require('fs').writeFileSync('child-hook', 'done')\""}}
    archive(child, {"package.json": json.dumps(child_package), "index.js": "module.exports = 'ALIAS';"})
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(child.read_bytes()).digest()).decode()
    package = {"name": "@fixture/alias-root", "version": "1.0.0", "bin": {"fixture": "bin.cjs"}, "dependencies": {"@fixture/root-native": "npm:@fixture/alias-root@1.0.0-native"}, "scripts": {"postinstall": "node -e \"require('fs').writeFileSync('root-hook', require('@fixture/root-native'))\"", "prepare": "node -e \"process.exit(93)\"", "prepublish": "node -e \"process.exit(94)\""}}
    lock = {"name": package["name"], "version": "1.0.0", "lockfileVersion": 3, "requires": True, "packages": {"": package, "node_modules/@fixture/root-native": {"name": child_package["name"], "version": child_package["version"], "resolved": child.as_uri(), "integrity": integrity, "hasInstallScript": True}}}
    source = root / "alias-root.tgz"
    archive(source, {"package.json": json.dumps(package), "npm-shrinkwrap.json": json.dumps(lock), "bin.cjs": "#!/usr/bin/env node\nconsole.log(require('@fixture/root-native'));"})
    env = {**os.environ, "HOME": str(root / "alias-home"), "npm_config_offline": "true", "npm_config_audit": "false", "npm_config_fund": "false", "npm_config_update_notifier": "false"}
    for case in ["alias-good", "alias-corrupt"]:
        state = Path(env["HOME"]) / ".local/state" / case
        target = state / "npm/lib/node_modules/@fixture/alias-root"
        target.mkdir(parents=True)
        old = target / "retained-evidence"
        old.write_bytes(b"prior package must survive")
        case_env = {**env, "npm_config_cache": str(root / (case + "-cache"))}
        if case == "alias-corrupt":
            archive(child, {"package.json": json.dumps(child_package), "index.js": "module.exports = 'ALTERED';"})
        command = ["bash", sys.argv[5], case, package["name"], "fixture", os.environ["PATH"], str(source)]
        result = subprocess.run(command, env=case_env, capture_output=True, text=True)
        assert result.stdout == ""
        if case == "alias-good":
            assert result.returncode == 0, result.stderr
            assert (target / "root-hook").read_text() == "ALIAS"
            assert (target / "node_modules/@fixture/root-native/child-hook").read_text() == "done"
            binary = state / "npm/bin/fixture"
            result = subprocess.run(["node", str(binary)], env=case_env, capture_output=True, text=True)
            assert result.returncode == 0 and result.stdout.strip() == "ALIAS", result.stderr
            evidence = list((state / "npm-recovery").glob("attempt.*/lib/node_modules/@fixture/alias-root/retained-evidence"))
            assert len(evidence) == 1 and evidence[0].read_bytes() == b"prior package must survive"
            before = [(path, path.read_bytes(), path.stat().st_mtime_ns) for path in [binary, target / "npm-shrinkwrap.json", state / "npm-bootstrap.lock"]]
            healthy = subprocess.run(command[:-1] + [str(root / "absent-source")], env=case_env, capture_output=True, text=True)
            assert healthy.returncode == 0 and not healthy.stdout and not healthy.stderr
            assert all(path.read_bytes() == data and path.stat().st_mtime_ns == mtime for path, data, mtime in before)
        else:
            assert result.returncode != 0 and "EINTEGRITY" in result.stderr, result.stderr
            assert old.read_bytes() == b"prior package must survive"
            assert not (state / "npm/bin/fixture").exists()
            attempts = list(target.parent.glob(".alias-root.recovery.*"))
            assert len(attempts) == 1 and (attempts[0] / "npm-shrinkwrap.json").is_file()
    print("Locked aliases and install hooks work; failed recovery preserves the old package and attempt; healthy launch bypasses recovery")


compare(sys.argv[1], sys.argv[2], 8)
compare(sys.argv[3], sys.argv[4], 6)
npm_boundary()
alias_and_failure_boundary()
print("All publisher payloads/metadata preserved; 14 platform acquisitions locked")
