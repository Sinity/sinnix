"""Add only the missing acquisition hashes to Pi's published shrinkwrap."""

import base64
import gzip
import hashlib
import io
import json
import sys
import tarfile


def repair(source, declarations, destination):
    with open(declarations) as handle:
        specs = json.load(handle)
    with tarfile.open(source) as original:
        lock = json.load(original.extractfile("package/npm-shrinkwrap.json"))
        packages = lock["packages"]
        missing = {name for name, entry in packages.items() if name and not entry.get("integrity")}
        if missing != set(specs):
            raise ValueError("publisher shrinkwrap changed; review the missing-integrity set")
        for name, spec in specs.items():
            entry = packages[name]
            if entry["resolved"] != spec["url"]:
                raise ValueError("dependency URL differs from verified acquisition")
            with open(spec["archive"], "rb") as handle:
                digest = base64.b64encode(hashlib.file_digest(handle, "sha512").digest()).decode()
            if spec["hash"] != "sha512-" + digest:
                raise ValueError("dependency archive integrity differs")
            entry["integrity"] = spec["hash"]
        payload = (json.dumps(lock, indent=2) + "\n").encode()
        with open(destination, "wb") as output, gzip.GzipFile(fileobj=output, mode="wb", mtime=0, filename="") as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as repaired:
                for member in original.getmembers():
                    if member.name == "package/npm-shrinkwrap.json":
                        member.size = len(payload)
                        repaired.addfile(member, io.BytesIO(payload))
                    else:
                        repaired.addfile(member, original.extractfile(member) if member.isfile() else None)


if __name__ == "__main__":
    repair(*sys.argv[1:])
