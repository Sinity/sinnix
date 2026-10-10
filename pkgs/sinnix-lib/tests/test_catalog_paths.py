"""Catalog prefix joins preserve normalized paths at the filesystem root."""

import pytest

from sinnix_lib.catalog_paths import normalized, relocate_path, resolve_historical_path


@pytest.mark.parametrize("source,destination,path,expected", [
    ("/", "/new", "/child", "/new/child"),
    ("/", "/new", "/", "/new"),
    ("/old", "/", "/old/child", "/child"),
    ("/old", "/", "/old", "/"),
    ("/", "/", "/child", "/child"),
    ("/", "/", "/", "/"),
])
def test_root_prefix_join(source, destination, path, expected):
    moves = [{"source": source, "destination": destination}]
    assert relocate_path(path, moves) == expected
    catalog = {"assets": [{"id": "fixture", "kind": "collection",
                           "current_path": destination, "previous_paths": [source]}]}
    assert resolve_historical_path(catalog, path, asset_id="fixture") == expected
    assert normalized(expected) == expected


def test_specific_component_prefix_overrides_root_mapping():
    moves = [{"source": "/", "destination": "/fallback"},
             {"source": "/old", "destination": "/"}]
    assert relocate_path("/old/child", moves) == "/child"
    assert relocate_path("/older/child", moves) == "/fallback/older/child"
