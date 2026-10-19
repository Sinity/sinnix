"""Check the declared operation's kernel limits without generating pressure."""

import json
from pathlib import Path


def main():
    entry = next(
        line
        for line in Path("/proc/self/cgroup").read_text().splitlines()
        if line.startswith("0::")
    )
    group = entry.removeprefix("0::")
    root = Path("/sys/fs/cgroup") / group.lstrip("/")
    limits = {
        name: (root / name).read_text().strip()
        for name in (
            "memory.high",
            "memory.max",
            "memory.swap.max",
            "io.weight",
            "io.max",
        )
    }
    assert limits["memory.high"] == str(1024**3), limits
    assert limits["memory.max"] == str(1536 * 1024**2), limits
    assert limits["memory.swap.max"] == "0", limits
    assert limits["io.weight"] == "default 10", limits
    devices = [
        dict(field.split("=", 1) for field in line.split()[1:])
        for line in limits["io.max"].splitlines()
    ]
    assert any(
        row.get("rbps") == "20000000" and row.get("wbps") == "20000000"
        for row in devices
    ), limits
    print(json.dumps({"status": "passed", "cgroup": group, "limits": limits}))


if __name__ == "__main__":
    main()
