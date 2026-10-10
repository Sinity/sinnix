"""Add a reviewed platform dependency lock without changing publisher payloads."""

import base64
import gzip
import hashlib
import io
import json
import sys
import tarfile


def lock_archive(source, lock_path, native_archive, destination):
    with open(lock_path) as handle:
        lock = json.load(handle)
    with tarfile.open(source) as original:
        package = json.load(original.extractfile("package/package.json"))
        root = lock["packages"][""]
        if any(package.get(key) != root[key] for key in ("name", "version", "optionalDependencies")):
            raise ValueError("publisher package differs from reviewed platform lock")
        if package.get("dependencies") or "package/npm-shrinkwrap.json" in original.getnames():
            raise ValueError("review the changed publisher dependency contract")
        expected = {"node_modules/" + name for name in package["optionalDependencies"]}
        if set(lock["packages"]) - {""} != expected:
            raise ValueError("platform lock does not cover exactly the declared dependencies")
        for name in expected:
            entry = lock["packages"][name]
            algorithm, digest = entry["integrity"].split("-", 1)
            if algorithm != "sha512" or len(base64.b64decode(digest, validate=True)) != 64:
                raise ValueError("platform acquisition lacks full SHA-512 integrity")
            if not entry["resolved"].startswith("https://registry.npmjs.org/"):
                raise ValueError("unexpected platform acquisition origin")
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
