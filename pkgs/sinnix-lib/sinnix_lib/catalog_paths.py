"""Historical path lookup from catalog identity history, without filesystem aliases."""

from pathlib import PurePosixPath


def normalized(path: str) -> str:
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        raise ValueError("path must be absolute")
    if any(ord(c) < 32 for c in path) or ".." in PurePosixPath(path).parts:
        raise ValueError("path must be normalized without control characters")
    if str(PurePosixPath(path)) != path:
        raise ValueError("path must be normalized")
    return path


def relocate_path(path: str, moves: list[dict]) -> str:
    """Longest component-prefix wins; similarly named subjects never match."""
    path = normalized(path)
    matches = []
    for move in moves:
        source, destination = normalized(move["source"]), normalized(move["destination"])
        if path == source or path.startswith(source.rstrip("/") + "/"):
            matches.append((len(source), destination + path[len(source):]))
    if not matches:
        return path
    longest = max(length for length, _ in matches)
    destinations = {destination for length, destination in matches if length == longest}
    if len(destinations) != 1:
        raise ValueError(f"ambiguous relocation for {path}")
    return destinations.pop()


def resolve_historical_path(catalog: dict, path: str, *, asset_id: str | None = None) -> str:
    """Resolve old/current addresses; refuse reused addresses without an asset id.

    A collection permits descendant lookup. File records permit exact lookup
    only. History is owned by the catalog; no second prefix-rewrite ledger exists.
    """
    path = normalized(path)
    matches = []
    for asset in catalog["assets"]:
        if asset_id is not None and asset["id"] != asset_id:
            continue
        current = normalized(asset["current_path"])
        for address in [current, *asset.get("previous_paths", [])]:
            address = normalized(address)
            if path == address or (asset["kind"] == "collection" and path.startswith(address.rstrip("/") + "/")):
                matches.append((len(address), None if asset.get("location_status") in {
                    "unavailable", "missing", "denied", "offline_mount", "wrong_type", "inaccessible"
                }
                                else current + path[len(address):]))
    if not matches:
        raise ValueError(f"path has no catalog identity history: {path}")
    longest = max(length for length, _ in matches)
    targets = {target for length, target in matches if length == longest}
    if None in targets:
        raise ValueError(f"historical asset is explicitly unavailable: {path}")
    if len(targets) != 1:
        raise ValueError(f"reused or ambiguous historical address: {path}; specify asset id")
    return targets.pop()
