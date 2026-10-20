"""The one reader of /etc/sinnix/runtime-inventory.json.

The snapshot collectors, the health sweep, the status report, the action
service and the failure recorder all read the inventory Nix generates. Each
caller decides what an unavailable inventory means for it; this module only
says whether there is one and, if not, why.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_path() -> Path:
    """``SINNIX_RUNTIME_INVENTORY_FILE`` lets hermetic tests and fixture hosts
    point every reader at another file at once."""
    return Path(
        os.environ.get(
            "SINNIX_RUNTIME_INVENTORY_FILE", "/etc/sinnix/runtime-inventory.json"
        )
    )


def load(path: Path | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """The inventory and None, or None and the reason it is unavailable."""
    path = default_path() if path is None else path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "runtime inventory missing"
    except OSError:
        return None, "runtime inventory unreadable"
    except (json.JSONDecodeError, UnicodeError):
        return None, "runtime inventory malformed"
    if not isinstance(value, dict):
        return None, "runtime inventory malformed"
    return value, None
