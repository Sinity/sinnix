"""Preserve private Claude state while reconciling the managed layout."""

import json
import os
import sys
import tempfile
from pathlib import Path


def read_object(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def reconcile(home, managed, seed, retired_hook):
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
    backup = None

    def backup_dir():
        nonlocal backup
        if backup is None:
            backup = Path(tempfile.mkdtemp(prefix=".sinnix-migration-", dir=config))
        return backup

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
        print(f"Preserved replaced Claude settings/retired links in {backup}")


if __name__ == "__main__":
    try:
        reconcile(*(Path(arg) for arg in sys.argv[1:]))
    except (OSError, ValueError) as error:
        sys.exit(f"Claude state migration: {error}")
