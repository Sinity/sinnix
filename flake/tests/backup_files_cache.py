"""Real Borg files-cache aging regression; only small private synthetic inputs."""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


def scenario(root, isolated):
    root.mkdir()
    genome = root / "genome"
    realm = root / "realm"
    genome.mkdir()
    realm.mkdir()
    target = genome / "payload"
    target.write_bytes(b"neutral genome fixture\n" * 256)
    # Borg excludes the newest ctime from its saved cache. Keep the payload
    # older than a separate sentinel, using real metadata rather than mocks.
    time.sleep(0.02)
    (genome / "sentinel").write_text("newest ctime\n")
    (realm / "payload").write_text("neutral realm fixture\n")
    original_stat = (
        target.stat().st_ino,
        target.stat().st_size,
        target.stat().st_ctime_ns,
    )
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("BORG_"):
            del env[key]
    env.update(
        BORG_REPO=str(root / "repo"),
        BORG_CACHE_DIR=str(root / "cache"),
        BORG_SECURITY_DIR=str(root / "security"),
        BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK="yes",
    )

    def borg(*args, suffix=None):
        child_env = env.copy()
        if suffix is not None:
            child_env["BORG_FILES_CACHE_SUFFIX"] = suffix
        result = subprocess.run(
            ["borg", *args], env=child_env, text=True, capture_output=True, timeout=20
        )
        assert result.returncode == 0, result.stderr
        return result.stdout + result.stderr

    borg("init", "--encryption=none")
    suffix = "genome" if isolated else None

    def create(name, source, namespace=None):
        return borg(
            "create",
            "--list",
            "--files-cache=ctime,size,inode",
            "--files-changed=ctime",
            "::" + name,
            str(source),
            suffix=namespace,
        )

    create("genome-first", genome, suffix)
    # Real Borg U status is emitted only when cached chunk IDs are reused;
    # a cache miss emits A and enters file reading/chunking instead.
    warm = create("genome-warm", genome, suffix)
    assert "U " + str(target) in warm, warm
    for number in range(21):
        create("realm-" + str(number), realm)
    final = create("genome-final", genome, suffix)
    expected = "U" if isolated else "A"
    assert expected + " " + str(target) in final, final
    assert original_stat == (
        target.stat().st_ino,
        target.stat().st_size,
        target.stat().st_ctime_ns,
    )
    cache = next(p for p in (root / "cache").iterdir() if p.is_dir())
    assert (cache / "files").is_file()
    assert (cache / "files.genome").is_file() == isolated
    return {
        "isolated": isolated,
        "realm_creates": 21,
        "payload_status": expected,
        "unchanged_inode_size_ctime": True,
    }


with tempfile.TemporaryDirectory(
    prefix="borg-files-cache-", dir=os.environ.get("TMPDIR")
) as scratch:
    root = Path(scratch)
    print(
        json.dumps(
            [scenario(root / "shared", False), scenario(root / "isolated", True)]
        )
    )
