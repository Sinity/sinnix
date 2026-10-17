"""Check import origins inside the pytest process, before and after its tests."""

import importlib
import json
import os
import sys
from pathlib import Path


def _record(filename):
    name = os.environ["RUNTIME_MODULE"]
    expected = Path(os.environ["RUNTIME_PACKAGE"])
    importlib.import_module(name)
    origins = {}
    for key, module in tuple(sys.modules.items()):
        if key != name and not key.startswith(name + "."):
            continue
        location = getattr(module, "__file__", None)
        if location is None:
            continue
        actual = Path(location).resolve()
        assert actual.is_relative_to(expected), (
            f"{key} imported from {actual}, outside exact runtime {expected}"
        )
        origins[key] = str(actual)
    assert name in origins, f"runtime module {name} was not inspected"
    Path(filename).write_text(json.dumps(origins, indent=2))


def pytest_collection_finish(session):
    _record("runtime-import-before.json")


def pytest_sessionfinish(session, exitstatus):
    _record("runtime-import-after.json")
