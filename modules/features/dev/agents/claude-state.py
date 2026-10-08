"""Preserve private Claude state while reconciling the managed layout."""

import json
import os
import stat
import sys
import tempfile
from pathlib import Path


def read_object(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def migrate_global_config(config, source, backup_dir):
    target = config / ".claude.json"
    if target.is_symlink():
        raise ValueError(f"preserving unexpected global Claude config link: {target}")
    if target.exists():
        if not stat.S_ISREG(target.lstat().st_mode):
            raise ValueError(
                f"preserving unexpected global Claude config type: {target}"
            )
        read_object(target)
        target.chmod(0o600)
        return
    if source.is_symlink():
        raise ValueError(f"preserving unexpected global Claude config source: {source}")
    if not source.exists():
        return
    if not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError(f"preserving unexpected global Claude config source: {source}")
    original = source.read_bytes()
    if not isinstance(json.loads(original), dict):
        raise ValueError(f"expected a JSON object: {source}")
    saved = backup_dir() / ".claude.json"
    with saved.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(saved.parent)
    fsync_directory(config)
    fd, name = tempfile.mkstemp(prefix=".global-config-", dir=config)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if source.read_bytes() != original:
            raise ValueError(f"global Claude config changed during migration: {source}")
        # Publish without replacing a concurrent native writer's file.
        os.link(temporary, target)
        fsync_directory(config)
    finally:
        temporary.unlink(missing_ok=True)


def reconcile(home, managed, seed, retired_hook, global_source=None):
    config = home / ".config/claude"
    legacy = home / ".claude"
    if legacy.is_symlink():
        if legacy.resolve() != config.resolve():
            raise ValueError(f"preserving unexpected Claude root link: {legacy}")
    elif legacy.exists():
        raise ValueError(
            f"preserving legacy Claude directory/file: {legacy}; "
            f"reconcile its private state with {config} before activation"
        )

    settings = config / "settings.json"
    payload = None
    original = None
    if settings.is_symlink():
        original = settings.read_bytes()
        value = json.loads(original)
        if not isinstance(value, dict):
            raise ValueError(f"expected a JSON object: {settings}")
        policy = read_object(managed)
        payload = {key: value for key, value in value.items() if key not in policy}
    elif not settings.exists():
        payload = read_object(seed)

    config.mkdir(parents=True, exist_ok=True)
    config.chmod(0o700)
    backup = None

    def backup_dir():
        nonlocal backup
        if backup is None:
            backup = Path(tempfile.mkdtemp(prefix=".sinnix-migration-", dir=config))
        return backup

    migrate_global_config(config, global_source or home / ".claude.json", backup_dir)

    if payload is not None:
        if original is not None:
            target = backup_dir() / "settings.json"
            with target.open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(original)
        fd, name = tempfile.mkstemp(prefix=".settings-", dir=config)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(payload, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, settings)
        finally:
            temporary.unlink(missing_ok=True)
    settings.chmod(0o600)
    if not legacy.is_symlink():
        legacy.symlink_to(".config/claude")

    retired = {
        f"commands/{name}.md": f"../skills/{name}/SKILL.md"
        for name in (
            "agent-orchestration",
            "history-cleanup",
            "persona",
            "sinnix-module-placement",
            "swarm",
            "workspace-recon-scan",
        )
    }
    retired["hooks/sessionstart-beads-prime.sh"] = str(retired_hook)
    for relative, expected in retired.items():
        link = config / relative
        if link.is_symlink() and not link.exists() and os.readlink(link) == expected:
            saved = backup_dir() / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            link.rename(saved)
    if backup is not None:
        fsync_directory(backup)
        fsync_directory(config)
        print(f"Preserved replaced Claude settings/retired links in {backup}")


if __name__ == "__main__":
    try:
        reconcile(*(Path(arg) for arg in sys.argv[1:]))
    except (OSError, ValueError) as error:
        sys.exit(f"Claude state migration: {error}")
