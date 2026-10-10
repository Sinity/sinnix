"""Add a reviewed dependency lock without changing publisher payloads."""

import base64
import gzip
import hashlib
import io
import json
import re
import sys
import tarfile


def lock_archive(source, lock_path, native_archive, destination):
    with open(lock_path) as handle:
        lock = json.load(handle)
    with tarfile.open(source) as original:
        package = json.load(original.extractfile("package/package.json"))
        root = lock["packages"][""]
        if any(package.get(key) != root.get(key) for key in ("name", "version")):
            raise ValueError("publisher identity differs from reviewed lock")
        for key in ("dependencies", "optionalDependencies", "devDependencies", "peerDependencies"):
            if package.get(key, {}) != root.get(key, {}):
                raise ValueError("publisher dependency contract differs from reviewed lock")
        if "package/npm-shrinkwrap.json" in original.getnames():
            raise ValueError("review the changed publisher dependency contract")
        expected = {"node_modules/" + name for key in ("dependencies", "optionalDependencies", "devDependencies") for name in package.get(key, {})}
        if not expected.issubset(lock["packages"]):
            raise ValueError("lock does not cover every declared dependency")
        for name in set(lock["packages"]) - {""}:
            entry = lock["packages"][name]
            algorithm, digest = entry["integrity"].split("-", 1)
            if algorithm != "sha512" or len(base64.b64decode(digest, validate=True)) != 64:
                raise ValueError("dependency acquisition lacks full SHA-512 integrity")
            if not entry["resolved"].startswith("https://registry.npmjs.org/"):
                raise ValueError("unexpected dependency acquisition origin")
            if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][\w.+-]+)?", entry["version"]):
                raise ValueError("dependency version is not exact")
        if native_archive != "-":
            if set(lock["packages"]) - {""} != expected:
                raise ValueError("platform lock has unexpected transitive dependencies")
            native = lock["packages"]["node_modules/" + package["name"] + "-linux-x64"]
            with open(native_archive, "rb") as handle:
                digest = base64.b64encode(hashlib.file_digest(handle, "sha512").digest()).decode()
            if native["integrity"] != "sha512-" + digest:
                raise ValueError("native platform archive differs from reviewed acquisition")
            with tarfile.open(native_archive) as archive:
                metadata = json.load(archive.extractfile("package/package.json"))
            if metadata["name"] != native["name"] or metadata["version"] != native["version"]:
                raise ValueError("native publisher identity differs from the lock")
            if metadata.get("dependencies") or metadata.get("optionalDependencies"):
                raise ValueError("native platform package now has further dependencies")
            if any(key in metadata.get("scripts", {}) for key in ("preinstall", "install", "postinstall")):
                raise ValueError("native platform package now has install hooks")
        payload = (json.dumps(lock, indent=2) + "\n").encode()
        with open(destination, "wb") as output, gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as repaired:
                for member in original.getmembers():
                    repaired.addfile(member, original.extractfile(member) if member.isfile() else None)
                member = tarfile.TarInfo("package/npm-shrinkwrap.json")
                member.size = len(payload)
                member.mode = 0o644
                repaired.addfile(member, io.BytesIO(payload))


if __name__ == "__main__":
    lock_archive(*sys.argv[1:])
